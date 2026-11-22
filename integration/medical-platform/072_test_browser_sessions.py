"""Serialized repository model. These tests do not execute YQL."""
import copy
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Lock
from types import SimpleNamespace
import unittest

module = import_module("072_browser_sessions")
AuthError = module.auth.AuthError
A, B, C = ("A"*43, "B"*43, "C"*43)


class RepositoryModel:
    def __init__(self):
        self.rows, self.revoked = {}, set()
        self.available, self.replay, self.version = True, False, 0
        self.lock = Lock()
        self.updates = 0

    def transaction(self, fn, **_):
        if not self.available:
            raise AuthError(503)
        with self.lock:
            before = copy.deepcopy((self.rows, self.revoked))
            try:
                result = fn(None)
                return fn(None) if self.replay else result
            except Exception:
                self.rows, self.revoked = before
                raise

    def authorize(self, tx, claims):
        if claims[1] in self.revoked or claims[3] != self.version:
            raise AuthError()

    def mark_revoked(self, tx, uid, sid):
        self.revoked.add(sid)

    def one(self, tx, sql, **p):
        return self.rows.get((p["app"][0], p["digest"][0]))

    def query(self, tx, sql, **p):
        key = (p["app"][0], p["digest"][0])
        if sql.startswith("INSERT"):
            self.rows[key] = SimpleNamespace(user_id=p["uid"][0], session_id=p["sid"][0],
               expiry=p["exp"][0]//1_000_000, issued_at_seconds=p["issued"][0], auth_version=p["ver"][0], disabled=False)
        elif "SET disabled=true" in sql:
            self.rows[key].disabled = True
        elif sql.startswith("UPDATE"):
            self.updates += 1
            self.rows[key].issued_at_seconds = p["issued"][0]
        elif sql.startswith("DELETE"):
            self.rows.pop(key, None)
        else:
            raise AssertionError(sql)


class SessionsTest(unittest.TestCase):
    def setUp(self):
        self.repo = RepositoryModel()
        self.now = 10
        self.auth = module.auth.Sessions(self.repo, b"a"*32, b"b"*32, lambda: self.now)
        self.a = self.worker()
        self.bind(self.a, A)

    def worker(self):
        return module.BrowserSessions(self.auth, lambda: self.now)

    def bind(self, worker, handle, previous="", uid="user", sid="sid"):
        pair = self.auth._issue(SimpleNamespace(uid=uid, sid=sid, app="nmp", version=0,
                                                 expires=4000), 0)
        return worker.bind("nmp", handle, previous, pair)

    def test_workers_and_commit_replay_converge(self):
        self.now = 310
        self.repo.replay = True
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda w: w.use("nmp", A, "refresh"),
                                    [self.worker(), self.worker()]))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.repo.updates, 1)
        self.assertEqual(self.worker().use("nmp", A, "resume"), results[0])

    def test_logout_and_account_switch_invalidate_globally(self):
        self.bind(self.worker(), B, A, uid="other", sid="sid2")
        self.assertIn("sid", self.repo.revoked)
        with self.assertRaises(AuthError):
            self.a.use("nmp", A, "resume")
        with self.assertRaises(AuthError):
            self.a.use("nmp", B, "refresh", ("user", "sid"))
        self.repo.replay = True
        self.worker().use("nmp", B, "logout", ("other", "sid2"))
        with self.assertRaises(AuthError):
            self.a.use("nmp", B, "resume")

    def test_revocation_database_failure_and_app_isolation(self):
        with self.assertRaises(AuthError):
            self.worker().use("terapevt", A, "resume")
        self.repo.version = 1
        with self.assertRaises(AuthError):
            self.worker().use("nmp", A, "refresh")
        self.repo.available = False
        with self.assertRaises(AuthError) as error:
            self.worker().use("nmp", A, "refresh")
        self.assertEqual(error.exception.status, 503)

    def test_stale_cookie_cannot_create_second_replacement(self):
        self.bind(self.worker(), B, A, uid="other", sid="sid2")
        with self.assertRaises(AuthError) as raised:
            self.bind(self.worker(), C, A, uid="third", sid="sid3")
        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(self.worker().use("nmp", B, "resume")["user_id"], "other")
