from importlib import import_module
import os
from pathlib import Path
import secrets
import unittest
from unittest.mock import patch

import ydb

base = import_module("05_test_ydb")
BrowserSessions = import_module("072_browser_sessions").BrowserSessions


@unittest.skipUnless(os.getenv("MEDICAL_YDB_LOCAL_PORT"), "requires dedicated loopback YDB")
class SharedSessions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.YdbTest.setUpClass()
        cls.addClassCleanup(base.YdbTest.doClassCleanups)
        cls.pool = base.YdbTest.pool
        ddl = Path(__file__).with_name("072_browser_sessions.sql").read_text()
        cls.pool.execute_with_retries(ddl.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1))

    def setUp(self):
        self.fixture = base.YdbTest("test_login_sessions_and_cross_app")
        self.fixture.setUp()
        self.workers = [BrowserSessions(self.fixture.worker().sessions, lambda: self.fixture.now)
                        for _ in range(2)]
        self.handle = secrets.token_urlsafe(32)
        self.pair = self.workers[0].bind("nmp", self.handle, "", self.fixture.enter())

    def test_parallel_refresh_shared_logout_and_account_switch(self):
        self.fixture.now += 301
        a, b = self.fixture.concurrent(lambda i: self.workers[i].use("nmp", self.handle, "refresh"))
        self.assertEqual(a, b)
        self.assertNotEqual(self.pair["access_token"], a["access_token"])
        second = secrets.token_urlsafe(32)
        email, uid = self.fixture.make_account()
        self.fixture.grant_fixture(uid, "nmp", "app:use")
        current = self.workers[1].bind("nmp", second, self.handle, self.fixture.enter(email=email))
        self.fixture.deny(401, lambda: self.workers[0].use("nmp", self.handle, "resume"))
        self.fixture.deny(401, lambda: self.workers[0].use("terapevt", second, "resume"))
        self.workers[0].use("nmp", second, "logout", (current["user_id"], current["session_id"]))
        self.fixture.deny(401, lambda: self.workers[1].use("nmp", second, "refresh"))

    def test_authorization_version_revokes_browser_cookie(self):
        self.fixture.s.sessions.revoke_all(self.pair["access_token"], "nmp")
        self.fixture.deny(401, lambda: self.workers[1].use("nmp", self.handle, "resume"))

    def test_refresh_retries_after_lost_commit_ack(self):
        self.fixture.now += 301
        commits = []
        original = ydb.query.transaction.QueryTxContext.commit
        def lost_ack(tx, *args, **kwargs):
            result = original(tx, *args, **kwargs)
            if not commits:
                commits.append(True)
                raise ydb.issues.Undetermined("synthetic post-commit failure")
            return result
        with patch.object(ydb.query.transaction.QueryTxContext, "commit", lost_ack):
            result = self.workers[0].use("nmp", self.handle, "refresh")
        self.assertTrue(commits)
        self.assertEqual(result, self.workers[1].use("nmp", self.handle, "resume"))

    def test_parallel_login_replacements_have_one_winner(self):
        replacements = [secrets.token_urlsafe(32) for _ in range(2)]
        entered = [self.fixture.enter(), self.fixture.enter()]
        results = self.fixture.concurrent(lambda i: self.workers[i].bind(
            "nmp", replacements[i], self.handle, entered[i]))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertIn(409, results)
        self.fixture.deny(401, lambda: self.workers[0].use("nmp", self.handle, "resume"))
