"""Registration and email confirmation on the existing seven-table schema.

Keep one RegistrationService per worker. The HTTP adapter supplies a trusted
source IP, a stable secret and a bounded, trusted mail callback.
"""
from functools import wraps
from hashlib import sha256
import hmac
import ipaddress
import re
import secrets
from threading import BoundedSemaphore, Lock
from time import monotonic
from typing import Protocol
from uuid import UUID, uuid4

from argon2 import PasswordHasher, Type, exceptions as argon2_errors
import ydb

PENDING = "pending_email"
PLACEHOLDER = "!disabled:pending-email"
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")
EMAIL_LOCAL = re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+", re.ASCII)
DOMAIN_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", re.ASCII)
HASHER = PasswordHasher(type=Type.ID, time_cost=2, memory_cost=19456, parallelism=1)

EMAIL_STATE = """
DECLARE $email AS Utf8;
SELECT e.user_id AS user_id, e.verified_at AS verified_at,
       u.status AS status,
       u.updated_at + Interval("PT5M") <= CurrentUtcTimestamp() AS can_issue
FROM user_emails AS e LEFT JOIN users AS u ON e.user_id = u.user_id
WHERE e.email_normalized = $email;
"""

ISSUED_TOKEN = """
DECLARE $token AS String;
DECLARE $email AS Utf8;
DECLARE $id AS Utf8;
SELECT token_hash FROM auth_challenges WHERE token_hash = $token
AND email_normalized = $email AND user_id = $id AND purpose = 'verify_email_v3'u
AND consumed_at IS NULL AND expires_at > CurrentUtcTimestamp();
"""

CREATE_PENDING = """
DECLARE $id AS Utf8;
DECLARE $email AS Utf8;
DECLARE $placeholder AS Utf8;
$now = CurrentUtcTimestamp();
INSERT INTO users (user_id, password_hash, status, auth_version, created_at, updated_at)
VALUES ($id, $placeholder, 'pending_email'u, 0ul, $now, $now);
INSERT INTO user_emails (email_normalized, user_id, created_at)
VALUES ($email, $id, $now);
"""

EXTEND_PENDING = """
DECLARE $id AS Utf8;
UPDATE users SET updated_at = CurrentUtcTimestamp() WHERE user_id = $id;
"""

ISSUE_TOKEN = """
DECLARE $token AS String;
DECLARE $email AS Utf8;
DECLARE $id AS Utf8;
$now = CurrentUtcTimestamp();
INSERT INTO auth_challenges (token_hash, user_id, email_normalized, purpose, created_at, expires_at)
VALUES ($token, $id, $email, 'verify_email_v3'u, $now, Unwrap($now + Interval("PT30M")));
"""

CHECK_TOKEN = """
DECLARE $token AS String;
SELECT c.user_id AS user_id, c.email_normalized AS email_normalized
FROM auth_challenges AS c
INNER JOIN user_emails AS e ON c.email_normalized = e.email_normalized
INNER JOIN users AS u ON c.user_id = u.user_id
WHERE c.token_hash = $token AND c.purpose = 'verify_email_v3'u
AND c.consumed_at IS NULL AND c.expires_at > CurrentUtcTimestamp()
AND e.user_id = c.user_id AND e.verified_at IS NULL AND u.status = 'pending_email'u;
"""

CHECK_RECEIPT = """
DECLARE $receipt AS String;
SELECT token_hash FROM auth_challenges WHERE token_hash = $receipt
AND purpose = 'verify_email_v3_receipt'u AND expires_at > CurrentUtcTimestamp();
"""

COMPLETE = """
DECLARE $token AS String;
DECLARE $receipt AS String;
DECLARE $id AS Utf8;
DECLARE $email AS Utf8;
DECLARE $hash AS Utf8;
$now = CurrentUtcTimestamp();
UPDATE users SET status = 'active'u, password_hash = $hash, auth_version = 1ul,
                 updated_at = $now WHERE user_id = $id;
UPDATE user_emails SET verified_at = $now WHERE email_normalized = $email;
UPDATE auth_challenges SET consumed_at = $now WHERE token_hash = $token;
INSERT INTO auth_challenges
(token_hash, user_id, email_normalized, purpose, created_at, expires_at, consumed_at)
VALUES ($receipt, $id, $email, 'verify_email_v3_receipt'u, $now, Unwrap($now + Interval("P1D")), $now);
"""

# Only a YDB error category is observed at the API boundary; original details are excluded.
YDB_ERRORS = (ydb.issues.Error, TimeoutError)
DEADLINE_ERRORS = (ydb.issues.DeadlineExceed, ydb.issues.Timeout, TimeoutError)
CONSTRAINT_ERRORS = (ydb.issues.PreconditionFailed, ydb.issues.AlreadyExists)


def normalize_email(value):
    if not isinstance(value, str) or len(value) > 320:
        return None
    address = value.strip()
    local, separator, domain = address.rpartition("@")
    labels = domain.split(".")
    if (not separator or len(address) > 254 or not 1 <= len(local) <= 64
            or not EMAIL_LOCAL.fullmatch(local) or local.startswith(".")
            or local.endswith(".") or ".." in local or len(labels) < 2
            or not all(DOMAIN_LABEL.fullmatch(label) for label in labels)):
        return None
    return address.lower()


def password_bytes(value):
    if not isinstance(value, str) or not 12 <= len(value) <= 128:
        return None
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return encoded if len(encoded) <= 512 else None


def request_uuid(value):
    if not isinstance(value, str) or len(value) != 36:
        return None
    try:
        parsed = UUID(value)
    except ValueError:
        return None
    return parsed if parsed.version == 4 and str(parsed) == value else None


class SourceLimiter:
    """Worker-wide limits with bounded memory, plus per-IP/prefix limits."""

    def __init__(self, *, total=60, per_source=8, window=60, clock=monotonic):
        if not (1 <= per_source <= total and window > 0):
            raise ValueError("Invalid registration rate limits")
        self.total = total
        self.per_source = per_source
        self.window = window
        self.clock = clock
        self.lock = Lock()
        self.end = 0
        self.used = 0
        self.sources = {}

    def allow(self, source_ip):
        if not isinstance(source_ip, str) or len(source_ip) > 45 or "%" in source_ip:
            return False
        try:
            ip = ipaddress.ip_address(source_ip)
        except ValueError:
            return False
        if ip.version == 6 and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        source = (ip.version, int(ip) >> (64 if ip.version == 6 else 0))
        with self.lock:
            now = self.clock()
            if now >= self.end:
                self.end = now + self.window
                self.used = 0
                self.sources.clear()
            count = self.sources.get(source, 0)
            if count >= self.per_source or self.used >= self.total:
                return False
            self.used += 1
            self.sources[source] = count + 1
            return True


class RegistrationStore(Protocol):
    def issue(self, email: str, token_hash: bytes) -> bool: ...
    def state(self, token_hash: bytes, receipt: bytes) -> str: ...
    def complete(self, token_hash: bytes, receipt: bytes, password_hash: str) -> bool: ...


def registration_boundary(method):
    @wraps(method)
    def invoke(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except YDB_ERRORS:
            self.metric("registration_ydb_error")
            return 503, {"error": "REGISTRATION_TEMPORARILY_UNAVAILABLE"}
        except argon2_errors.HashingError:
            self.metric("registration_hash_error")
            return 503, {"error": "REGISTRATION_TEMPORARILY_UNAVAILABLE"}
    return invoke


class RegistrationService:
    def __init__(self, store: RegistrationStore, send_verification, *, receipt_secret: bytes,
                 observe=lambda event: None, limiter=None, hasher=HASHER, hash_slot=None):
        if not isinstance(receipt_secret, bytes) or len(receipt_secret) < 32:
            raise ValueError("A stable random receipt key of at least 32 bytes is required")
        self.store = store
        self.send_verification = send_verification
        self.receipt_secret = receipt_secret
        self.observe = observe
        self.limiter = limiter if limiter is not None else SourceLimiter()
        self.hasher = hasher
        self.hash_slot = hash_slot if hash_slot is not None else BoundedSemaphore(1)
        self.mail_slot = BoundedSemaphore(2)

    def metric(self, code):
        try:
            self.observe(code)
        except Exception:
            pass

    @registration_boundary
    def register(self, email, *, source_ip):
        # Every request, including malformed inputs, incurs the local quota.
        if not self.limiter.allow(source_ip):
            return 429, {"error": "TRY_LATER"}
        normalized = normalize_email(email)
        if normalized is None:
            return 400, {"error": "INVALID_EMAIL"}
        if not self.mail_slot.acquire(blocking=False):
            return 503, {"error": "REGISTRATION_TEMPORARILY_UNAVAILABLE"}
        try:
            token = secrets.token_urlsafe(32)
            if self.store.issue(normalized, sha256(token.encode("ascii")).digest()):
                try:
                    self.send_verification(normalized, token)
                except Exception:
                    self.metric("registration_mail_error")
            return 202, {"message": "If eligible, check your email for verification instructions."}
        finally:
            self.mail_slot.release()

    # Start and resend have one security policy, including the durable per-email cooldown.
    resend = register

    @registration_boundary
    def verify_email(self, token, password, request_id, *, source_ip):
        if not self.limiter.allow(source_ip):
            return 429, {"error": "TRY_LATER"}
        attempt = request_uuid(request_id)
        encoded = password_bytes(password)
        if (not isinstance(token, str) or not TOKEN_PATTERN.fullmatch(token)
                or attempt is None or encoded is None):
            return 400, {"error": "INVALID_CONFIRMATION"}
        token_hash = sha256(token.encode("ascii")).digest()
        receipt = hmac.digest(self.receipt_secret,
                             b"registration-v3\0" + token_hash + attempt.bytes + encoded, "sha256")
        state = self.store.state(token_hash, receipt)
        if state == "done":
            return 200, {"message": "Email verified."}
        if state != "pending":
            return 400, {"error": "INVALID_CONFIRMATION"}
        if not self.hash_slot.acquire(blocking=False):
            return 503, {"error": "REGISTRATION_TEMPORARILY_UNAVAILABLE"}
        try:
            password_hash = self.hasher.hash(encoded)
        finally:
            self.hash_slot.release()
        if self.store.complete(token_hash, receipt, password_hash):
            return 200, {"message": "Email verified."}
        return 400, {"error": "INVALID_CONFIRMATION"}


class YdbRegistrationStore:
    def __init__(self, pool: ydb.QuerySessionPool):
        self.pool = pool
        self.settings = ydb.BaseRequestSettings().with_timeout(3)
        self.retries = ydb.RetrySettings(max_retries=2, idempotent=True)

    def _execute(self, tx, query, parameters, *, commit=False):
        try:
            with tx.execute(query, parameters=parameters, commit_tx=commit,
                            settings=self.settings) as results:
                return [row for result in results for row in result.rows]
        except DEADLINE_ERRORS:
            if commit:
                # The response can time out after the server commits. The SDK
                # retries with the same issuance digest or confirmation receipt.
                raise ydb.issues.Undetermined("Commit acknowledgement unavailable") from None
            raise

    def _retry(self, operation):
        return self.pool.retry_operation_sync(operation, retry_settings=self.retries)

    def issue(self, email, token_hash):
        candidate_id = str(uuid4())
        email_param = {"$email": email}

        def operation(session):
            with session.transaction(ydb.QuerySerializableReadWrite()) as tx:
                rows = self._execute(tx, EMAIL_STATE, email_param)
                if rows:
                    current = rows[0]
                    if current.verified_at is not None or current.status != PENDING:
                        tx.rollback()
                        return False
                    params = {**email_param, "$id": current.user_id, "$token": token_hash}
                    if not current.can_issue:
                        # Only retries of this invocation have the original random candidate.
                        return bool(self._execute(tx, ISSUED_TOKEN, params, commit=True))
                    if self._execute(tx, ISSUED_TOKEN, params):
                        tx.rollback()
                        return True
                    self._execute(tx, EXTEND_PENDING, {"$id": current.user_id})
                else:
                    params = {**email_param, "$id": candidate_id, "$token": token_hash}
                    self._execute(tx, CREATE_PENDING, {
                        **email_param, "$id": candidate_id, "$placeholder": PLACEHOLDER,
                    })
                self._execute(tx, ISSUE_TOKEN, params, commit=True)
                return True

        try:
            return self._retry(operation)
        except CONSTRAINT_ERRORS:
            # Duplicate normalized email can be reported as a constraint conflict.
            # Read fresh and apply the same guards with the same candidate.
            return self._retry(operation)

    def state(self, token_hash, receipt):
        def operation(session):
            with session.transaction(ydb.QuerySerializableReadWrite()) as tx:
                if self._execute(tx, CHECK_RECEIPT, {"$receipt": receipt}):
                    tx.rollback()
                    return "done"
                rows = self._execute(tx, CHECK_TOKEN, {"$token": token_hash}, commit=True)
                return "pending" if rows else "invalid"

        return self._retry(operation)

    def complete(self, token_hash, receipt, password_hash):
        def operation(session):
            with session.transaction(ydb.QuerySerializableReadWrite()) as tx:
                if self._execute(tx, CHECK_RECEIPT, {"$receipt": receipt}):
                    tx.rollback()
                    return True
                rows = self._execute(tx, CHECK_TOKEN, {"$token": token_hash})
                if not rows:
                    tx.rollback()
                    return False
                row = rows[0]
                self._execute(tx, COMPLETE, {
                    "$token": token_hash, "$receipt": receipt, "$id": row.user_id,
                    "$email": row.email_normalized, "$hash": password_hash,
                }, commit=True)
                return True

        return self._retry(operation)
