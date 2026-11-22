"""YDB-backed opaque browser credentials. No refresh token is persisted here."""
import hashlib
import hmac
from importlib import import_module
import re

auth = import_module("05_auth_sessions")
HANDLE = re.compile(r"[A-Za-z0-9_-]{43}")


class BrowserSessions:
    def __init__(self, sessions, clock):
        self.sessions, self.repo, self.clock = sessions, sessions.repo, clock

    @staticmethod
    def key(app, handle):
        if not HANDLE.fullmatch(handle):
            raise auth.AuthError()
        return dict(app=(app, "Utf8"), digest=(hashlib.sha256(handle.encode("ascii")).digest(), "String"))

    def lookup(self, tx, key):
        return self.repo.one(tx, """SELECT user_id, session_id, auth_version, issued_at_seconds,
             CAST(CAST(expires_at AS Uint64) / 1000000 AS Uint64) AS expiry
             FROM browser_sessions WHERE app_id=$app AND handle_digest=$digest
             AND expires_at > CurrentUtcTimestamp();""", **key)

    def claims(self, row, app, now):
        if not row or row.expiry <= now:
            raise auth.AuthError()
        return [row.user_id, row.session_id, app, row.auth_version, row.expiry, now, 0, ""]

    def access(self, claims, issued):
        uid, sid, app, ver, expiry = claims[:5]
        expires = min(expiry, issued + auth.ACCESS_TTL)
        return {"user_id": uid, "session_id": sid, "access_expires_at": expires,
                "access_token": self.sessions._seal("a5", [uid, sid, app, ver, expires, issued, 0, "browser"])}

    def bind(self, app, handle, previous, pair):
        claims = self.sessions.claims(pair["refresh_token"], app, "r5")
        key = self.key(app, handle)
        now = int(self.clock())
        old_key = self.key(app, previous) if HANDLE.fullmatch(previous) else None

        def operation(tx):
            self.repo.authorize(tx, claims)
            existing = self.lookup(tx, key)
            if existing:
                if (existing.user_id, existing.session_id) != tuple(claims[:2]):
                    raise auth.AuthError(503, "PILOT_UNAVAILABLE")
                return self.access(claims, existing.issued_at_seconds)
            if old_key:
                old = self.lookup(tx, old_key)
                if old:
                    self.repo.mark_revoked(tx, old.user_id, old.session_id)
                    self.repo.query(tx, "DELETE FROM browser_sessions WHERE app_id=$app AND handle_digest=$digest;",
                                    **old_key)
            self.repo.query(tx, """INSERT INTO browser_sessions
                 (app_id,handle_digest,user_id,session_id,auth_version,expires_at,issued_at_seconds)
                 VALUES ($app,$digest,$uid,$sid,$ver,$exp,$issued);""", **key,
                            uid=(claims[0], "Utf8"), sid=(claims[1], "Utf8"), ver=(claims[3], "Uint64"),
                            exp=(claims[4]*1_000_000, "Timestamp"), issued=(now, "Uint64"))
            return self.access(claims, now)
        return self.repo.transaction(operation, write=True)

    def use(self, app, handle, action, identity=()):
        key = self.key(app, handle)
        now = int(self.clock())

        def operation(tx):
            row = self.lookup(tx, key)
            if row is None and action == "logout":
                return {}
            claims = self.claims(row, app, now)
            if identity and not all(isinstance(value, str) and value.isascii() and
                                    hmac.compare_digest(value, expected)
                                    for value, expected in zip(identity, claims[:2])):
                raise auth.AuthError(401, "SESSION_CHANGED")
            if action == "logout":
                self.repo.mark_revoked(tx, row.user_id, row.session_id)
                self.repo.query(tx, "DELETE FROM browser_sessions WHERE app_id=$app AND handle_digest=$digest;",
                                **key)
                return {}
            self.repo.authorize(tx, claims)
            issued = row.issued_at_seconds
            if action != "check" and (issued + auth.ACCESS_TTL <= now + 15 and
                                      row.expiry > issued + auth.ACCESS_TTL):
                issued = now
                self.repo.query(tx, """UPDATE browser_sessions SET issued_at_seconds=$issued
                    WHERE app_id=$app AND handle_digest=$digest;""", **key, issued=(issued, "Uint64"))
            return self.access(claims, issued)
        return self.repo.transaction(operation, write=action != "check")
