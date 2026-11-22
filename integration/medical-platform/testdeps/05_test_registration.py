"""Service and YDB-adapter tests on a transactional model and real SDK retries."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
from threading import Barrier, Lock
from types import SimpleNamespace
import unittest
from uuid import uuid4

from argon2 import PasswordHasher, Type
import ydb
from ydb.convert import query_parameters_to_pb
from ydb.retries import retry_operation_sync

from importlib import import_module
auth = import_module("05_auth_registration")

EMAIL = "user@example.org"
IP = "192.0.2.41"
PASSWORD = "owner only password"
OTHER = "different valid password"


class FakePool:
    """Serializable transaction model with explicit rollback and lost commit ACK."""
    def __init__(self):
        self.lock = Lock()
        self.data = ({}, {}, {})
        self.now = 1
        self.lost_ack = {}
        self.before_commit = {}
        self.fail_read = None

    def retry_operation_sync(self, operation, retry_settings):
        return retry_operation_sync(lambda: operation(self), retry_settings)

    @contextmanager
    def transaction(self, mode):
        assert isinstance(mode, ydb.QuerySerializableReadWrite)
        with self.lock:
            yield FakeTransaction(self)


class FakeTransaction:
    def __init__(self, pool):
        self.pool = pool
        self.data = deepcopy(pool.data)
        self.users, self.emails, self.challenges = self.data

    def rollback(self):
        pass

    @contextmanager
    def execute(self, query, parameters, commit_tx, settings):
        p = parameters
        rows = []
        now = self.pool.now
        if self.pool.fail_read:
            raise self.pool.fail_read
        if query == auth.EMAIL_STATE:
            entry = self.emails.get(p["$email"])
            if entry:
                user = self.users[entry[0]]
                rows = [SimpleNamespace(user_id=entry[0], verified_at=entry[1],
                                        status=user[0], can_issue=now >= user[2] + 300)]
        elif query == auth.ISSUED_TOKEN:
            row = self.challenges.get(p["$token"])
            if (row and row[:3] == (p["$id"], p["$email"], "token")
                    and row[3] > now and not row[4]):
                rows = [row]
        elif query == auth.CREATE_PENDING:
            assert p["$email"] not in self.emails and not commit_tx
            self.users[p["$id"]] = (auth.PENDING, p["$placeholder"], now)
            self.emails[p["$email"]] = (p["$id"], None)
        elif query == auth.EXTEND_PENDING:
            status, password, _ = self.users[p["$id"]]
            self.users[p["$id"]] = status, password, now
        elif query == auth.ISSUE_TOKEN:
            assert p["$token"] not in self.challenges and commit_tx
            self.challenges[p["$token"]] = (p["$id"], p["$email"], "token", now + 1800, False)
        elif query == auth.CHECK_TOKEN:
            row = self.challenges.get(p["$token"])
            if row:
                uid, email, purpose, expiry, consumed = row
                if (purpose == "token" and expiry > now and not consumed
                        and self.emails.get(email) == (uid, None)
                        and self.users[uid][0] == auth.PENDING):
                    rows = [SimpleNamespace(user_id=uid, email_normalized=email)]
        elif query == auth.CHECK_RECEIPT:
            row = self.challenges.get(p["$receipt"])
            if row and row[2] == "receipt" and row[3] > now:
                rows = [row]
        elif query == auth.COMPLETE:
            assert commit_tx
            uid, email = p["$id"], p["$email"]
            self.users[uid] = "active", p["$hash"], now
            self.emails[email] = uid, now
            self.challenges[p["$token"]] = (*self.challenges[p["$token"]][:4], True)
            self.challenges[p["$receipt"]] = uid, email, "receipt", now + 86400, True
        else:
            raise AssertionError("Unexpected query")
        if commit_tx:
            error = self.pool.before_commit.pop(query, None)
            if error:
                raise error
            self.pool.data = self.data
            error = self.pool.lost_ack.pop(query, None)
            if error:
                raise error
        yield [SimpleNamespace(rows=rows)]


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.pool = FakePool()
        self.store = auth.YdbRegistrationStore(self.pool)
        self.mail, self.events = [], []
        self.hasher = PasswordHasher(type=Type.ID, time_cost=1, memory_cost=1024, parallelism=1)
        self.service = self.make_service()

    def make_service(self, **kwargs):
        return auth.RegistrationService(
            self.store, lambda *args: self.mail.append(args), receipt_secret=b"K" * 32,
            observe=self.events.append,
            limiter=kwargs.pop("limiter", auth.SourceLimiter(total=100, per_source=100)),
            hasher=self.hasher, **kwargs,
        )

    def start(self, email=EMAIL):
        return self.service.register(email, source_ip=IP)

    def verify(self, token, password=PASSWORD, attempt=None):
        return self.service.verify_email(token, password, attempt or str(uuid4()), source_ip=IP)[0]

    def token(self):
        return self.mail[-1][1]

    def run_concurrent(self, callback):
        barrier = Barrier(2)
        def run(i):
            barrier.wait(timeout=5)
            return callback(i)
        with ThreadPoolExecutor(2) as executor:
            return list(executor.map(run, range(2)))

    def test_owner_sets_password_and_duplicate_registration(self):
        first = self.start(" User@Example.ORG ")
        self.assertEqual(first, self.start())
        self.assertEqual(len(self.mail), 1)
        users, emails, _ = self.pool.data
        self.assertEqual(list(users.values())[0][:2], (auth.PENDING, auth.PLACEHOLDER))
        self.assertIsNone(emails[EMAIL][1])
        self.assertEqual(self.verify(self.token()), 200)
        password_hash = list(self.pool.data[0].values())[0][1]
        self.assertTrue(self.hasher.verify(password_hash, PASSWORD))
        self.assertEqual(first, self.start())
        self.assertEqual(len(self.mail), 1)

    def test_two_concurrent_registrations(self):
        self.assertEqual([x[0] for x in self.run_concurrent(lambda i: self.start())], [202, 202])
        self.assertEqual(len(self.mail), 1)
        self.assertEqual(len(self.pool.data[0]), 1)

    def test_smtp_error_and_resend_after_cooldown(self):
        def fail(email, token):
            raise OSError("private diagnostic")
        self.service.send_verification = fail
        first = self.start()
        self.assertEqual(first[0], 202)
        self.assertEqual(self.events, ["registration_mail_error"])
        self.service = self.make_service()
        self.pool.now = 300
        self.assertEqual(first, self.service.resend(EMAIL, source_ip=IP))
        self.assertFalse(self.mail)
        self.pool.now = 301
        self.assertEqual(first, self.service.resend(EMAIL, source_ip=IP))
        self.assertEqual(len(self.pool.data[0]), 1)
        self.assertEqual(len(self.mail), 1)
        self.assertEqual(self.verify(self.token()), 200)

    def test_resend_keeps_previous_live_link(self):
        self.start()
        old = self.token()
        self.pool.now = 301
        self.service.resend(EMAIL, source_ip=IP)
        self.assertNotEqual(old, self.token())
        self.assertEqual(self.verify(old), 200)
        self.assertEqual(self.verify(self.token()), 400)

    def test_two_concurrent_confirmations(self):
        self.start()
        token = self.token()
        barrier = Barrier(2)
        original_complete = self.store.complete
        def complete(*args):
            barrier.wait(timeout=5)
            return original_complete(*args)
        self.store.complete = complete
        # Separate workers share DB, each has its own argon2 budget.
        services = [self.make_service(), self.make_service()]
        attempts = [str(uuid4()), str(uuid4())]
        passwords = [PASSWORD, OTHER]
        results = self.run_concurrent(lambda i: services[i].verify_email(
            token, passwords[i], attempts[i], source_ip=IP)[0])
        self.assertEqual(sorted(results), [200, 400])
        winner = passwords[results.index(200)]
        self.assertTrue(self.hasher.verify(list(self.pool.data[0].values())[0][1], winner))

    def test_expired_and_wrong_purpose(self):
        self.start()
        token = self.token()
        digest = sha256(token.encode()).digest()
        row = self.pool.data[2][digest]
        self.pool.data[2][digest] = (*row[:2], "reset", *row[3:])
        self.assertEqual(self.verify(token), 400)
        self.pool.data[2][digest] = row
        self.pool.now = 1801
        self.assertEqual(self.verify(token), 400)

    def test_issuance_lost_ack_and_definite_abort(self):
        self.pool.before_commit[auth.ISSUE_TOKEN] = ydb.issues.Aborted("internal")
        self.pool.lost_ack[auth.ISSUE_TOKEN] = ydb.issues.Undetermined("internal")
        self.assertEqual(self.start()[0], 202)
        self.assertEqual(len(self.mail), 1)
        self.assertEqual(len(self.pool.data[0]), 1)
        self.assertEqual(len(self.pool.data[2]), 1)

    def test_confirmation_lost_ack_and_exact_replay(self):
        self.start()
        token, attempt = self.token(), str(uuid4())
        self.pool.lost_ack[auth.COMPLETE] = ydb.issues.DeadlineExceed("internal")
        self.assertEqual(self.verify(token, PASSWORD, attempt), 200)
        self.service = self.make_service()
        self.assertEqual(self.verify(token, PASSWORD, attempt), 200)
        self.assertEqual(self.verify(token, OTHER, attempt), 400)
        self.assertEqual(self.verify(token, PASSWORD), 400)
        self.assertEqual(len([r for r in self.pool.data[2].values() if r[2] == "receipt"]), 1)
        self.pool.now += 86400
        self.assertEqual(self.verify(token, PASSWORD, attempt), 400)

    def test_ydb_exception_redacted(self):
        self.pool.fail_read = ydb.issues.SchemeError("internal endpoint and credential")
        self.assertEqual(self.start(), (503, {"error": "REGISTRATION_TEMPORARILY_UNAVAILABLE"}))
        self.assertEqual(self.events, ["registration_ydb_error"])
        self.assertFalse(self.mail)

    def test_request_limits_and_ipv6_prefix(self):
        limiter = auth.SourceLimiter(total=2, per_source=1)
        self.service = self.make_service(limiter=limiter)
        self.assertEqual(self.service.register(EMAIL, source_ip="2001:db8::1")[0], 202)
        self.assertEqual(self.service.register(EMAIL, source_ip="2001:db8::2")[0], 429)
        self.assertEqual(self.start()[0], 202)
        self.assertEqual(self.service.register(EMAIL, source_ip="198.51.100.1")[0], 429)

    def test_argon_slot_saturation_and_invalid_token(self):
        self.start()
        self.service.hash_slot.acquire()
        try:
            self.assertEqual(self.verify("A" * 43), 400)
            self.assertEqual(self.verify(self.token()), 503)
        finally:
            self.service.hash_slot.release()
        self.assertEqual(self.verify(self.token()), 200)

    def test_sdk_serializes_digest_and_email(self):
        params = query_parameters_to_pb({"$email": EMAIL, "$receipt": b"r" * 32})
        self.assertEqual(params["$email"].type.type_id, ydb.PrimitiveType.Utf8.proto.type_id)
        self.assertEqual(params["$receipt"].type.type_id, ydb.PrimitiveType.String.proto.type_id)


if __name__ == "__main__":
    unittest.main()
