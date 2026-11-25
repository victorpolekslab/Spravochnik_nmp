"""Stage-5 parameterized YQL for the seven existing medical platform tables."""
from importlib import import_module
import hmac
from uuid import UUID

import ydb

AuthError = import_module("05_auth_sessions").AuthError
PERMISSIONS = frozenset(("app:use", "learning:view", "learning:submit", "learning:manage", "users:manage"))
STAFF_GRANTABLE = PERMISSIONS - {"users:manage", "learning:manage"}
MAX_VERSION = 2**64 - 1

ACCOUNT = """SELECT u.user_id AS user_id, u.status AS status, u.auth_version AS auth_version,
                    u.password_hash AS password_hash, e.verified_at AS verified_at
             FROM user_emails e INNER JOIN users u ON e.user_id = u.user_id
             WHERE e.email_normalized = $email;"""
USER = """SELECT status, auth_version FROM users WHERE user_id = $uid;"""
ACCESS = """SELECT permission, revoked_at FROM user_access
            WHERE user_id = $uid AND app_id = $app AND permission = $permission;"""
SESSION = """SELECT app_id, auth_version, revoked_at, refresh_token_hash,
                   expires_at > CurrentUtcTimestamp() AS live,
                   $exp > CurrentUtcTimestamp() AS credential_live
             FROM auth_sessions WHERE user_id = $uid AND session_id = $sid;"""


class Repository:
    def __init__(self, pool):
        self.pool = pool
        self.settings = ydb.BaseRequestSettings().with_timeout(3)
        self.retry = ydb.RetrySettings(max_retries=2, idempotent=True)

    def query(self, tx, sql, **params):
        declarations = "".join(
            f"DECLARE ${key} AS {kind};\n" for key, (_, kind) in params.items())
        typed = {"$" + key: ydb.TypedValue(value, getattr(ydb.PrimitiveType, kind))
                 for key, (value, kind) in params.items()}
        with tx.execute(declarations + sql, parameters=typed, settings=self.settings) as results:
            return [row for result in results for row in result.rows]

    def transaction(self, operation, *, write=False, replay_commit=True):
        def invoke(session):
            with session.transaction(ydb.QuerySerializableReadWrite()) as tx:
                try:
                    result = operation(tx)
                except AuthError:
                    try:
                        tx.rollback()
                    except (ydb.issues.Error, TimeoutError):
                        pass
                    raise
                if write:
                    try:
                        tx.commit(settings=self.settings)
                    except (ydb.issues.ConnectionError, ydb.issues.Undetermined):
                        if not replay_commit:
                            raise AuthError(503, "AUTH_TEMPORARILY_UNAVAILABLE") from None
                        raise
                    except (ydb.issues.Timeout, ydb.issues.DeadlineExceed, TimeoutError):
                        if not replay_commit:
                            raise AuthError(503, "AUTH_TEMPORARILY_UNAVAILABLE") from None
                        raise ydb.issues.Undetermined("Commit acknowledgement unavailable") from None
                else:
                    tx.rollback()
                return result
        try:
            return self.pool.retry_operation_sync(invoke, retry_settings=self.retry)
        except (ydb.issues.Error, TimeoutError):
            raise AuthError(503, "AUTH_TEMPORARILY_UNAVAILABLE") from None

    def one(self, tx, sql, **params):
        rows = self.query(tx, sql, **params)
        return rows[0] if rows else None

    def account(self, email):
        return self.transaction(lambda tx: self.one(tx, ACCOUNT, email=(email, "Utf8")))

    def user(self, tx, uid):
        return self.one(tx, USER, uid=(uid, "Utf8"))

    def allowed(self, tx, uid, app, permission):
        row = self.one(tx, ACCESS, uid=(uid, "Utf8"), app=(app, "Utf8"),
                       permission=(permission, "Utf8"))
        return row is not None and row.revoked_at is None

    def session(self, tx, uid, sid, expiry):
        return self.one(tx, SESSION, uid=(uid, "Utf8"), sid=(sid, "Utf8"),
                        exp=(expiry * 1_000_000, "Timestamp"))

    def authorize(self, tx, claims, permission="app:use", *, allow_revoked=False):
        uid, sid, app, version, expiry = claims[:5]
        row = self.session(tx, uid, sid, expiry)
        user = self.user(tx, uid)
        if (not row or not user or row.app_id != app or row.auth_version != version
                or user.auth_version != version or user.status != "active" or not row.live
                or not row.credential_live or (row.revoked_at is not None and not allow_revoked)):
            raise AuthError()
        # user_emails.verified_at transitions only from NULL to non-NULL under the
        # approved account lifecycle; clearing/migrating an address must advance auth_version.
        if permission not in PERMISSIONS or not self.allowed(tx, uid, app, "app:use"):
            raise AuthError(403, "PERMISSION_DENIED")
        if permission != "app:use" and not self.allowed(tx, uid, app, permission):
            raise AuthError(403, "PERMISSION_DENIED")
        return row

    def create(self, row, email, expected_hash, state):
        def operation(tx):
            user = self.one(tx, ACCOUNT, email=(email, "Utf8"))
            if (not user or user.user_id != row.uid or user.verified_at is None or user.status != "active" or user.auth_version != row.version
                    or not hmac.compare_digest(user.password_hash, expected_hash)):
                raise AuthError()
            if not self.allowed(tx, row.uid, row.app, "app:use"):
                raise AuthError(403, "PERMISSION_DENIED")
            existing = self.session(tx, row.uid, row.sid, row.expires)
            if existing:
                if (existing.live and existing.revoked_at is None
                        and hmac.compare_digest(existing.refresh_token_hash, state)):
                    return
                raise AuthError(503, "AUTH_TEMPORARILY_UNAVAILABLE")
            self.query(tx, """INSERT INTO auth_sessions
                (user_id, session_id, app_id, refresh_token_hash, auth_version, created_at, expires_at)
                VALUES ($uid, $sid, $app, $state, $version, CurrentUtcTimestamp(), $expiry);""",
                uid=(row.uid, "Utf8"), sid=(row.sid, "Utf8"), app=(row.app, "Utf8"),
                state=(state, "String"), version=(row.version, "Uint64"),
                expiry=(row.expires * 1_000_000, "Timestamp"))
        return self.transaction(operation, write=True)

    def check(self, claims, permission):
        self.transaction(lambda tx: self.authorize(tx, claims, permission))

    def rotate(self, claims, old, new):
        def operation(tx):
            row = self.authorize(tx, claims)
            current = row.refresh_token_hash
            if len(current) != 40:
                return False
            if hmac.compare_digest(current, new):
                return True
            uid, sid = claims[:2]
            key = {"uid": (uid, "Utf8"), "sid": (sid, "Utf8")}
            if hmac.compare_digest(current, old):
                self.query(tx, """UPDATE auth_sessions SET refresh_token_hash = $state
                              WHERE user_id = $uid AND session_id = $sid;""",
                           **key, state=(new, "String"))
                return True
            if old[:8] < current[:8]:
                self.mark_revoked(tx, uid, sid)
            return False
        return self.transaction(operation, write=True)

    def mark_revoked(self, tx, uid, sid):
        self.query(tx, """UPDATE auth_sessions SET revoked_at = CurrentUtcTimestamp()
                          WHERE user_id = $uid AND session_id = $sid AND revoked_at IS NULL;""",
                   uid=(uid, "Utf8"), sid=(sid, "Utf8"))

    def revoke(self, claims, target, *, allow_already_revoked=False):
        uid, _, app, _, expiry = claims[:5]
        def operation(tx):
            self.authorize(tx, claims, allow_revoked=allow_already_revoked)
            row = self.session(tx, uid, target, expiry)
            if not row or row.app_id != app:
                raise AuthError(404, "SESSION_NOT_FOUND")
            self.mark_revoked(tx, uid, target)
        self.transaction(operation, write=True)

    def advance(self, tx, uid, version):
        if version >= MAX_VERSION:
            raise AuthError(503, "AUTH_TEMPORARILY_UNAVAILABLE")
        self.query(tx, """UPDATE users SET auth_version = $version, updated_at = CurrentUtcTimestamp()
                          WHERE user_id = $uid;""", uid=(uid, "Utf8"), version=(version + 1, "Uint64"))

    def revoke_all(self, claims):
        # No blind replay of global revoke after an uncertain commit. A retry
        # observes the bumped version and denies authorization; the client logs out.
        def operation(tx):
            self.authorize(tx, claims)
            self.advance(tx, claims[0], claims[3])
        self.transaction(operation, write=True)

    def permissions(self, claims):
        def operation(tx):
            self.authorize(tx, claims)
            rows = self.query(tx, """SELECT permission FROM user_access
                                     WHERE user_id = $uid AND app_id = $app
                                       AND revoked_at IS NULL LIMIT 32;""",
                              uid=(claims[0], "Utf8"), app=(claims[2], "Utf8"))
            return sorted({row.permission for row in rows} & PERMISSIONS)
        return self.transaction(operation)

    def manage(self, claims, target, permission, grant):
        try:
            valid = isinstance(target, str) and len(target) == 36 and str(UUID(target)) == target
        except ValueError:
            valid = False
        if not valid or not isinstance(permission, str) or type(grant) is not bool:
            raise AuthError(400, "INVALID_PERMISSION_CHANGE")
        if target == claims[0] or permission not in STAFF_GRANTABLE:
            raise AuthError(403, "PERMISSION_DENIED")

        def operation(tx):
            self.authorize(tx, claims, "users:manage")
            target_user = self.user(tx, target)
            if not target_user:
                raise AuthError(404, "USER_NOT_FOUND")
            if self.allowed(tx, target, claims[2], "users:manage"):
                raise AuthError(403, "PERMISSION_DENIED")
            if grant and target_user.status != "active":
                raise AuthError(403, "PERMISSION_DENIED")
            key = {"uid": (target, "Utf8"), "app": (claims[2], "Utf8"),
                   "permission": (permission, "Utf8")}
            active = self.allowed(tx, target, claims[2], permission)
            if grant and not active:
                self.query(tx, """UPSERT INTO user_access (user_id, app_id, permission, granted_at, revoked_at)
                    VALUES ($uid, $app, $permission, CurrentUtcTimestamp(), NULL);""", **key)
            elif not grant and active:
                self.query(tx, """UPDATE user_access SET revoked_at = CurrentUtcTimestamp()
                    WHERE user_id = $uid AND app_id = $app AND permission = $permission;""", **key)
        self.transaction(operation, write=True, replay_commit=False)

    def challenge(self, tx, digest):
        return self.one(tx, """SELECT user_id, email_normalized, purpose, consumed_at,
                                      expires_at > CurrentUtcTimestamp() AS live
                               FROM auth_challenges WHERE token_hash = $digest;""",
                        digest=(digest, "String"))

    def put_challenge(self, tx, digest, uid, email, purpose, interval, *, insert=False):
        command = "INSERT" if insert else "UPSERT"
        # Only a locally selected SQL keyword varies; all data is bound.
        self.query(tx, f"""{command} INTO auth_challenges
             (token_hash, user_id, email_normalized, purpose, created_at, expires_at, consumed_at)
             VALUES ($digest, $uid, $email, $purpose, CurrentUtcTimestamp(),
                     Unwrap(CurrentUtcTimestamp() + $duration), NULL);""",
                   digest=(digest, "String"), uid=(uid, "Utf8"), email=(email, "Utf8"),
                   purpose=(purpose, "Utf8"), duration=(interval * 1_000_000, "Interval"))

    def issue_reset(self, email, digest, cooldown_key):
        def operation(tx):
            user = self.one(tx, ACCOUNT, email=(email, "Utf8"))
            if not user or user.verified_at is None or user.status != "active":
                return False
            purpose = f"reset5:{user.auth_version}"
            existing = self.challenge(tx, digest)
            if existing:
                return bool(existing.live and existing.consumed_at is None
                            and existing.purpose == purpose and existing.user_id == user.user_id)
            marker = self.challenge(tx, cooldown_key)
            if marker and marker.live:
                return False
            self.put_challenge(tx, cooldown_key, user.user_id, email, "reset5:cooldown", 300)
            self.put_challenge(tx, digest, user.user_id, email, purpose, 1800, insert=True)
            return True
        return self.transaction(operation, write=True)

    def reset_state(self, tx, digest, receipt):
        done = self.challenge(tx, receipt)
        if done and done.live and done.purpose == "reset5:receipt":
            return "done", None, None
        row = self.challenge(tx, digest)
        if not row or not row.live or row.consumed_at is not None:
            return "invalid", None, None
        account = self.one(tx, ACCOUNT, email=(row.email_normalized, "Utf8"))
        if (not account or account.user_id != row.user_id or account.verified_at is None
                or account.status != "active" or row.purpose != f"reset5:{account.auth_version}"):
            return "invalid", None, None
        return "pending", account, row

    def inspect_reset(self, digest, receipt):
        return self.transaction(lambda tx: self.reset_state(tx, digest, receipt)[0])

    def complete_reset(self, digest, receipt, new_hash):
        def operation(tx):
            state, account, row = self.reset_state(tx, digest, receipt)
            if state != "pending":
                return state == "done"
            self.advance(tx, account.user_id, account.auth_version)
            self.query(tx, "UPDATE users SET password_hash = $hash WHERE user_id = $uid;",
                       hash=(new_hash, "Utf8"), uid=(account.user_id, "Utf8"))
            self.query(tx, """UPDATE auth_challenges SET consumed_at = CurrentUtcTimestamp()
                             WHERE token_hash = $digest;""", digest=(digest, "String"))
            self.put_challenge(tx, receipt, account.user_id, row.email_normalized,
                               "reset5:receipt", 86400, insert=True)
            return True
        return self.transaction(operation, write=True)
