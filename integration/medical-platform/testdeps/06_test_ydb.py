"""Real loopback YDB. Creates disposable tables from a candidate DDL snapshot."""
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
import os
from pathlib import Path
import re
from threading import Barrier, Event
import unittest
from unittest.mock import patch
from uuid import uuid4

import ydb

helpers = import_module("06_test_learning")
stage5 = import_module("05_test_ydb")
grader = import_module("06_learning_grader")
repository = import_module("05_ydb_auth_repository")
AuthError = stage5.AuthError


class FixtureRepository(repository.Repository):
    def __init__(self, pool, names):
        super().__init__(pool)
        self.names = names

    def query(self, tx, sql, **params):
        for old, new in self.names.items():
            sql = re.sub(r"\b"+old+r"\b", new, sql)
        return super().query(tx, sql, **params)


@unittest.skipUnless(os.getenv("MEDICAL_YDB_LOCAL_PORT"), "requires a dedicated /local YDB")
class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src = stage5.YdbTest
        src.setUpClass()
        cls.addClassCleanup(src.doClassCleanups)
        cls.pool = src.pool
        suffix = uuid4().hex[:12]
        cls.names = {name: name+"_"+suffix for name in ("test_attempts","learning_progress")}
        ddl = Path(stage5.__file__).with_name("05_medical_platform_schema.sql").read_text()
        for old,new in cls.names.items():
            query = next(s for s in ddl.split(";") if f"CREATE TABLE `{old}`" in s)
            query = query.replace(f"`{old}`",f"`{new}`")
            if old == "test_attempts":
                query = query.replace("    PRIMARY KEY", "    `answers_digest` String,\n    PRIMARY KEY")
            cls.pool.execute_with_retries(query)

    def setUp(self):
        self.old = stage5.YdbTest("test_login_sessions_and_cross_app")
        self.old.setUp()
        self.s = self.old.s
        self.uid = self.old.uid
        self.s.sessions.repo = FixtureRepository(self.pool,self.names)
        self.repo = self.s.sessions.repo
        self.old.grant_fixture(self.uid,"nmp","learning:view")
        self.old.grant_fixture(self.uid,"nmp","learning:submit")
        self.token = self.old.enter()["access_token"]
        self.catalog = grader.Catalog(helpers.fixture(), b"L"*32)
        self.api = helpers.API(self.s.sessions,self.catalog)
        self.base = "/v1/nmp/learning"

    def post(self, body, token=None):
        return helpers.request(self.api,"POST",self.base+"/attempts",token or self.token,body)

    def get(self, path, query="", token=None):
        return helpers.request(self.api,"GET",self.base+path,token or self.token,query=query)

    def pair(self, action):
        barrier=Barrier(2)
        def go(index):
            barrier.wait(timeout=8)
            return action(index)
        with ThreadPoolExecutor(2) as pool:
            return list(pool.map(go,range(2)))

    def test_concurrent_duplicate_same_score_conflict_and_other_device(self):
        body=helpers.payload(answers=(0,1))
        pair=self.pair(lambda i: self.post(body))
        self.assertEqual(pair[0],pair[1])
        self.assertEqual(pair[0][0],200)
        another=self.old.enter()["access_token"]
        self.assertEqual(self.post(body,another),pair[0])
        body["answers"][0]["choice"]=1
        body["answers"][1]["choice"]=0
        self.assertEqual(self.post(body)[0],409)
        self.assertEqual(len(self.get("/attempts")[1]["items"]),1)

    def test_offline_queue_revision_pages_and_expired_session(self):
        queue=[helpers.payload("v1",(1,0)),helpers.payload("v2",(1,0)),helpers.payload()]
        unavailable=helpers.payload("missing")
        self.assertEqual(self.post(unavailable)[0],409)
        for body in queue:
            self.assertEqual(self.post(body)[0],200)
        self.assertEqual(self.post(queue[0])[1]["score"],1)
        self.assertEqual(self.post(queue[1])[1]["score"],2)
        page=self.get("/attempts","limit=1")[1]
        major,minor=page["next"]
        page2=self.get("/attempts",f"limit=2&after_major={major}&after_minor={minor}")
        self.assertEqual(page2[0],200)
        self.assertEqual(len(page2[1]["items"]),2)
        self.assertEqual(self.get("/progress","course_id=course")[1]["items"][0]["status"],"completed")
        self.old.now+=301
        self.assertEqual(self.post(queue[0])[0],401)

    def test_history_ownership_app_and_no_submit_right(self):
        body=helpers.payload()
        self.assertEqual(self.post(body)[0],200)
        path="/attempts/quiz/"+body["attempt_id"]
        self.assertEqual(self.get(path)[0],200)
        email,other=self.old.make_account()
        for p in ("app:use","learning:view"):
            self.old.grant_fixture(other,"nmp",p)
        stranger=self.old.enter(email=email)["access_token"]
        self.assertEqual(self.get(path,token=stranger)[0],404)
        self.assertEqual(self.get("/attempts",token=stranger)[1]["items"],[])
        self.assertEqual(self.post(body,stranger)[0],403)
        self.assertEqual(self.get("/attempts","user_id=other")[0],400)
        self.assertEqual(helpers.request(self.api,"GET","/v1/terapevt/learning/attempts",self.token)[0],401)
        self.old.grant_fixture(self.uid,"terapevt","learning:view")
        therapy=self.old.enter("terapevt")["access_token"]
        self.assertEqual(helpers.request(self.api,"GET","/v1/terapevt/learning/attempts",therapy)[1]["items"],[])
        with self.assertRaises(AuthError):
            self.s.sessions.manage(self.token,"nmp",self.uid,"learning:submit",True)

    def test_timeout_after_real_commit_and_response_recovery(self):
        cls=ydb.query.transaction.QueryTxContext
        original=cls.commit
        missed=[True]
        def commit(tx,*args,**kwargs):
            result=original(tx,*args,**kwargs)
            if missed:
                missed.pop()
                raise ydb.issues.DeadlineExceed("injected after commit")
            return result
        body=helpers.payload()
        with patch.object(cls,"commit",commit):
            first=self.post(body)
        self.assertEqual(first[0],200)
        self.assertFalse(missed)
        self.assertEqual(self.post(body),first)
        self.assertEqual(len(self.get("/attempts")[1]["items"]),1)

    def test_concurrent_progress_monotonic(self):
        bodies=[helpers.payload(answers=(1,1)),helpers.payload()]
        self.assertEqual([code for code,_ in self.pair(lambda i:self.post(bodies[i]))],[200,200])
        self.assertEqual(self.get("/progress")[1]["items"][0]["status"],"completed")

    def test_revoke_while_authorized_write_is_paused(self):
        self.old.grant_fixture(self.uid,"nmp","users:manage")
        email,other=self.old.make_account()
        for p in ("app:use","learning:submit","learning:view"):
            self.old.grant_fixture(other,"nmp",p)
        other_token=self.old.enter(email=email)["access_token"]
        admin=self.old.worker()
        checked,released=Event(),Event()
        original=self.repo.authorize
        def pause(tx,claims,permission="app:use",**options):
            row=original(tx,claims,permission,**options)
            if permission=="learning:submit":
                checked.set()
                if not released.wait(10):
                    raise AssertionError("release timeout")
            return row
        body=helpers.payload()
        with patch.object(self.repo,"authorize",pause),ThreadPoolExecutor(1) as pool:
            result=pool.submit(self.post,body,other_token)
            try:
                self.assertTrue(checked.wait(8))
                admin.sessions.manage(self.token,"nmp",other,"learning:submit",False)
            finally:
                released.set()
            self.assertEqual(result.result(timeout=12)[0],403)
        self.assertEqual(self.get("/attempts",token=other_token)[1]["items"],[])
        self.assertEqual(self.post(body,other_token)[0],403)
