from importlib import import_module
from types import SimpleNamespace
import unittest
from uuid import uuid4

auth = import_module("05_auth_sessions")
helpers = import_module("06_test_learning")


class Keyring(unittest.TestCase):
    def test_active_token_signing_and_retired_verification(self):
        old = auth.Sessions(None, b"a"*32, b"r"*32, lambda: 10)
        new = auth.Sessions(None, b"b"*32, b"s"*32, lambda: 10)
        new.configure_retired_keys(access=(b"a"*32,), refresh=(b"r"*32,))
        row = SimpleNamespace(uid=str(uuid4()), sid=str(uuid4()), app="nmp", version=0, expires=1000)
        for kind, name in (("a5", "access_token"), ("r5", "refresh_token")):
            token = old._issue(row, 0)[name]
            self.assertEqual(new.claims(token, "nmp", kind)[1], row.sid)
            with self.assertRaises(auth.AuthError):
                old.claims(new._issue(row, 0)[name], "nmp", kind)

    def test_key_purposes_cannot_share_verification_secret(self):
        ring = auth.Sessions(None, b"b"*32, b"s"*32, lambda: 10)
        with self.assertRaises(ValueError):
            ring.configure_retired_keys(access=(b"s"*32,))

    def test_old_digest_accepts_exact_retry_and_rejects_changed_answers(self):
        grader = import_module("06_learning_grader")
        repo = import_module("06_learning_repository")
        uid, body = str(uuid4()), helpers.payload()
        original = grader.Catalog(helpers.fixture(), b"a"*32)
        current = grader.Catalog(helpers.fixture(), b"b"*32, historical_keys=(b"a"*32,))
        old = original.grade(uid, "nmp", body)
        row = SimpleNamespace(**{field: None for field in repo.ATTEMPT.split(", ")},
                              answers_digest=old.digest)
        model = SimpleNamespace(authorize=lambda *_: None, one=lambda *_, **__: row,
                                transaction=lambda operation, **_: operation(None))
        claims = (uid, str(uuid4()), "nmp")
        grade = current.grade(uid, "nmp", body)
        self.assertNotEqual(old.digest, grade.digest)
        self.assertIsInstance(repo.persist(model, claims, lambda: grade), dict)
        body["answers"][0]["choice"] ^= 1
        with self.assertRaisesRegex(grader.LearningError, "ATTEMPT_CONFLICT"):
            repo.persist(model, claims, lambda: current.grade(uid, "nmp", body))
