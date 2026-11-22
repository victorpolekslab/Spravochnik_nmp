"""Integration only. Uses a dedicated loopback-only /local test database."""
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
import os
from pathlib import Path
import re
from threading import Barrier, Event
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import ydb

build = import_module("05_auth_services").build
AuthError = import_module("05_auth_sessions").AuthError
submit = import_module("05_learning_write").submit_verified
IP = "192.0.2.5"
PW = "valid owner password"
NEW = "new owner password"


@unittest.skipUnless(os.getenv("MEDICAL_YDB_LOCAL_PORT"), "requires a dedicated local /local")
class YdbTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        port = int(os.environ["MEDICAL_YDB_LOCAL_PORT"])
        driver = ydb.Driver(endpoint=f"grpc://127.0.0.1:{port}", database="/local",
                            credentials=ydb.AnonymousCredentials(), disable_discovery=True)
        cls.addClassCleanup(driver.stop)
        driver.wait(timeout=20)
        cls.pool = ydb.QuerySessionPool(driver)
        cls.addClassCleanup(cls.pool.stop)
        ddl = Path(__file__).with_name("05_medical_platform_schema.sql").read_text()
        for query in re.sub(r"(?m)^--.*$", "", ddl).split(";"):
            if query.strip():
                cls.pool.execute_with_retries(query.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1))

    def setUp(self):
        self.now = int(time.time()) + 3
        self.mail = []
        self.s = self.worker()
        self.email, self.uid = self.make_account()
        for app in ("nmp", "terapevt"):
            self.grant_fixture(self.uid, app, "app:use")

    def worker(self):
        return build(self.pool, access_key=b"A"*32, refresh_key=b"B"*32,
                       registration_key=b"C"*32, recovery_key=b"D"*32,
                       verification_queue=lambda *mail: self.mail.append(mail),
                       recovery_queue=lambda *mail: self.mail.append(mail), clock=lambda: self.now)

    def make_account(self):
        email = f"{uuid4().hex}@example.org"
        self.assertEqual(self.s.register.register(email, source_ip=IP)[0], 202)
        self.assertEqual(self.s.register.verify_email(self.mail[-1][1], PW, str(uuid4()),
                                                     source_ip=IP)[0], 200)
        return email, self.s.repo.account(email).user_id

    def grant_fixture(self, uid, app, permission):
        self.s.repo.transaction(lambda tx: self.s.repo.query(tx, """UPSERT INTO user_access
            (user_id,app_id,permission,granted_at) VALUES($uid,$app,$permission,CurrentUtcTimestamp());""",
            uid=(uid,"Utf8"), app=(app,"Utf8"),permission=(permission,"Utf8")), write=True)

    def enter(self, app="nmp", email=None, password=PW):
        return self.s.login.login(email or self.email, password, app, source_ip=IP)

    def deny(self, status, call):
        with self.assertRaises(AuthError) as result:
            call()
        self.assertEqual(result.exception.status, status)

    def concurrent(self, fn):
        barrier = Barrier(2)
        def run(i):
            barrier.wait(timeout=10)
            try:
                return fn(i)
            except AuthError as exc:
                return exc.status
        with ThreadPoolExecutor(2) as pool:
            return list(pool.map(run, range(2)))

    def test_login_sessions_and_cross_app(self):
        a, b, c = self.enter(), self.enter(), self.enter("terapevt")
        self.assertEqual({x["user_id"] for x in (a,b,c)}, {self.uid})
        self.assertEqual(len({x["session_id"] for x in (a,b,c)}), 3)
        self.deny(401, lambda: self.enter(password="wrong password"))
        self.deny(401, lambda: self.enter(email="missing@example.org"))
        self.deny(401, lambda: self.s.sessions.validate(a["access_token"], "terapevt"))
        self.s.sessions.validate(a["access_token"], "nmp")
        self.now += 300
        self.deny(401, lambda: self.s.sessions.validate(a["access_token"], "nmp"))
        self.now += 30*86400
        self.deny(401, lambda: self.s.sessions.refresh(a["refresh_token"], "nmp"))

    def test_refresh_replay_and_concurrency(self):
        initial = self.enter()
        self.deny(401, lambda: self.s.sessions.refresh(initial["refresh_token"]+"x", "nmp"))
        updated = self.s.sessions.refresh(initial["refresh_token"], "nmp")
        self.deny(401, lambda: self.s.sessions.refresh(initial["refresh_token"], "nmp"))
        self.deny(401, lambda: self.s.sessions.validate(updated["access_token"], "nmp"))
        initial = self.enter()
        result = self.concurrent(lambda _: self.s.sessions.refresh(initial["refresh_token"], "nmp"))
        self.assertIn(401, result)
        winner, = [value for value in result if isinstance(value, dict)]
        self.deny(401, lambda: self.s.sessions.validate(winner["access_token"], "nmp"))

    def test_logout_revoke_all_and_ownership(self):
        a,b,c = self.enter(),self.enter(),self.enter("terapevt")
        other_email, uid = self.make_account()
        self.grant_fixture(uid, "nmp", "app:use")
        d = self.enter(email=other_email)
        self.deny(404, lambda: self.s.sessions.revoke(a["access_token"], "nmp", d["session_id"]))
        self.s.sessions.logout(a["access_token"], "nmp")
        self.s.sessions.logout(a["access_token"], "nmp")
        self.deny(401, lambda: self.s.sessions.validate(a["access_token"], "nmp"))
        e = self.s.login.login(self.email, PW, "nmp", source_ip="192.0.2.6")
        self.s.sessions.revoke(b["access_token"], "nmp", e["session_id"])
        self.deny(401, lambda: self.s.sessions.validate(e["access_token"], "nmp"))
        self.s.sessions.revoke_all(b["access_token"], "nmp")
        self.deny(401, lambda: self.s.sessions.validate(c["access_token"], "terapevt"))
        self.s.sessions.validate(d["access_token"], "nmp")

    def learning(self, token, *, attempt="attempt1", score=4):
        return submit(self.s.sessions, token, "nmp", test_id="test1", attempt_id=attempt,
                      course_id="course1", test_version="1", score=score, max_score=5, passed=True)

    def test_permission_and_idempotent_submission(self):
        token = self.enter()["access_token"]
        _, other_uid = self.make_account()
        self.deny(403, lambda: self.s.sessions.manage(token, "nmp", other_uid, "app:use", True))
        self.grant_fixture(self.uid, "nmp", "users:manage")
        self.deny(403, lambda: self.s.sessions.manage(token, "nmp", self.uid,"learning:submit",True))
        self.deny(403, lambda: self.s.sessions.manage(token, "nmp", other_uid,"users:manage",True))
        for permission in ("app:use","learning:submit"):
            self.s.sessions.manage(token,"nmp",other_uid,permission,True)
        email = self.mail[-1][0]
        other = self.enter(email=email)["access_token"]
        self.assertEqual(self.s.sessions.permissions(other,"nmp"), ["app:use","learning:submit"])
        self.deny(403, lambda: self.enter(app="terapevt", email=email))
        self.assertEqual(self.learning(other), "accepted")
        self.assertEqual(self.learning(other), "accepted")
        self.deny(409, lambda: self.learning(other, score=3))
        self.s.sessions.manage(token,"nmp",other_uid,"learning:submit",False)
        self.deny(403, lambda: self.learning(other,attempt="offline2"))
        self.s.sessions.manage(token,"nmp",other_uid,"app:use",False)
        self.deny(403, lambda: self.s.sessions.validate(other,"nmp"))

    def test_reset_and_competing_operations(self):
        a,b = self.enter(),self.enter("terapevt")
        self.assertEqual(self.s.reset.request(self.email, source_ip=IP),
                         self.s.reset.request("missing@example.org", source_ip=IP))
        token = self.mail[-1][1]
        ids = [str(uuid4()),str(uuid4())]
        workers = [self.worker(), self.worker()]
        values = self.concurrent(lambda i: workers[i].reset.complete(token,NEW,ids[i],source_ip=IP)[0])
        self.assertEqual(sorted(values), [200,400])
        self.assertEqual(self.s.reset.complete(token,NEW,ids[values.index(200)],source_ip=IP)[0],200)
        self.deny(401, lambda: self.s.sessions.validate(a["access_token"],"nmp"))
        self.deny(401, lambda: self.s.sessions.refresh(b["refresh_token"],"terapevt"))
        self.deny(401, self.enter)
        self.s.login.login(self.email, NEW, "nmp", source_ip="192.0.2.6")

    def test_lost_commit_ack_and_overload(self):
        cls = ydb.query.transaction.QueryTxContext
        original = cls.commit
        lost = [True]
        def commit(tx, *args, **kwargs):
            result = original(tx,*args,**kwargs)
            if lost:
                lost.pop()
                raise ydb.issues.Undetermined("simulated")
            return result
        with patch.object(cls,"commit",commit):
            active = self.enter()
        lost.append(True)
        with patch.object(cls,"commit",commit):
            self.s.sessions.refresh(active["refresh_token"],"nmp")
        old_query = self.s.repo.query
        def overloaded(*args, **kwargs):
            raise ydb.issues.Overloaded("simulated")
        with patch.object(self.s.repo,"query",overloaded):
            self.deny(503,self.enter)
        self.assertIs(self.s.repo.query.__func__,old_query.__func__)
        self.enter()

    def test_revoke_between_authorize_and_write(self):
        self.grant_fixture(self.uid, "nmp", "users:manage")
        admin = self.enter()["access_token"]
        email, uid = self.make_account()
        self.s.sessions.manage(admin, "nmp", uid, "app:use", True)
        self.s.sessions.manage(admin, "nmp", uid, "learning:submit", True)
        learner = self.enter(email=email)["access_token"]
        other = self.worker()
        checked, released = Event(), Event()
        authorize = self.s.repo.authorize

        def pause(tx, claims, permission="app:use", **options):
            row = authorize(tx, claims, permission, **options)
            if permission == "learning:submit":
                checked.set()
                if not released.wait(timeout=12):
                    raise AssertionError("revoke did not complete")
            return row

        def attempt():
            self.deny(403, lambda: self.learning(learner, attempt="during_revoke"))

        with patch.object(self.s.repo, "authorize", pause), ThreadPoolExecutor(1) as workers:
            future = workers.submit(attempt)
            try:
                self.assertTrue(checked.wait(timeout=10))
                other.sessions.manage(admin, "nmp", uid, "learning:submit", False)
            finally:
                released.set()
            future.result(timeout=15)
        repo = self.s.repo
        row = repo.transaction(lambda tx: repo.one(tx, """SELECT attempt_id FROM test_attempts
           WHERE user_id=$uid AND app_id='nmp'u AND test_id='test1'u AND attempt_id='during_revoke'u;""",
           uid=(uid,"Utf8")))
        self.assertIsNone(row)

    def test_server_session_deadline_and_stale_password_snapshot(self):
        account = self.s.repo.account(self.email)
        a = self.enter()
        repo = self.s.repo
        repo.transaction(lambda tx: repo.query(tx, """UPDATE auth_sessions SET
            expires_at=Unwrap(CurrentUtcTimestamp()-Interval("PT1S"))
            WHERE user_id=$uid AND session_id=$sid;""",
            uid=(self.uid,"Utf8"),sid=(a["session_id"],"Utf8")), write=True)
        self.deny(401, lambda: self.s.sessions.validate(a["access_token"], "nmp"))
        self.deny(401, lambda: self.s.sessions.refresh(a["refresh_token"], "nmp"))
        self.s.reset.request(self.email, source_ip=IP)
        token = self.mail[-1][1]
        cls = ydb.query.transaction.QueryTxContext
        original = cls.commit
        pending = [True]

        def commit(tx, *args, **kwargs):
            result = original(tx, *args, **kwargs)
            if pending:
                pending.pop()
                raise ydb.issues.DeadlineExceed("simulated")
            return result

        with patch.object(cls, "commit", commit):
            self.assertEqual(self.s.reset.complete(token, NEW, str(uuid4()), source_ip=IP)[0], 200)
        self.deny(401, lambda: self.s.sessions.create(
            self.uid, "nmp", account.auth_version, account.password_hash, self.email))

    def test_reset_cooldown_and_server_expiry(self):
        self.s.reset.request(self.email, source_ip=IP)
        self.s.reset.request(self.email, source_ip=IP)
        self.assertEqual(len(self.mail), 2)  # initial verification + one reset
        token = self.mail[-1][1]
        from hashlib import sha256
        repo = self.s.repo
        repo.transaction(lambda tx: repo.query(tx, """UPDATE auth_challenges SET
            expires_at=Unwrap(CurrentUtcTimestamp()-Interval("PT1S")) WHERE token_hash=$digest;""",
            digest=(sha256(token.encode("ascii")).digest(),"String")), write=True)
        self.deny(400, lambda: self.s.reset.complete(token, NEW, str(uuid4()), source_ip=IP))
