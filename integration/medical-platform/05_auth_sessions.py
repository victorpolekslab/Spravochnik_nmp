"""Signed stage-5 session credentials and authoritative YDB checks."""
import base64
import hashlib
import hmac
import json
import re
import secrets
from types import SimpleNamespace
from uuid import UUID, uuid4

APPS = frozenset(("nmp", "terapevt"))
ACCESS_TTL = 300
REFRESH_TTL = 30 * 86400

class AuthError(Exception):
    def __init__(self, status=401, code="INVALID_CREDENTIALS"):
        super().__init__(code)
        self.status, self.code = status, code

def _encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode(text):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", text):
        raise ValueError("invalid encoding")
    result = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    if _encode(result) != text:
        raise ValueError("noncanonical encoding")
    return result


def _refresh_state(generation, token):
    return generation.to_bytes(8, "big") + hashlib.sha256(token.encode("ascii")).digest()


class Sessions:
    def __init__(self, repo, access_key, refresh_key, clock):
        if not all(isinstance(k, bytes) and len(k) >= 32 for k in (access_key, refresh_key)):
            raise ValueError("Two independent 256-bit keys are required")
        if hmac.compare_digest(access_key, refresh_key):
            raise ValueError("Access and refresh keys must be distinct")
        self.repo, self.clock = repo, clock
        self.keys = {"a5": access_key, "r5": refresh_key}
        self._verification = {"a5": (access_key,), "r5": (refresh_key,)}

    def configure_retired_keys(self, *, access=(), refresh=()):
        """Configure bounded verification-only keys before accepting requests."""
        access, refresh = tuple(access), tuple(refresh)
        all_keys = (*self.keys.values(), *access, *refresh)
        if (len(access) > 3 or len(refresh) > 3 or
                any(not isinstance(key, bytes) or len(key) < 32 for key in all_keys)
                or len(set(all_keys)) != len(all_keys)):
            raise ValueError("Verification keys must be distinct and bounded")
        self._verification = {"a5": (self.keys["a5"], *access),
                              "r5": (self.keys["r5"], *refresh)}

    def _seal(self, kind, values):
        body = _encode(json.dumps(values, separators=(",", ":"), ensure_ascii=True).encode("ascii"))
        tag = hmac.digest(self.keys[kind], f"{kind}.{body}".encode("ascii"), "sha256")
        return f"{kind}.{body}.{_encode(tag)}"

    def _open(self, kind, token):
        if not isinstance(token, str) or len(token) > 1024:
            raise AuthError()
        try:
            prefix, body, signature = token.split(".")
            if prefix != kind or not re.fullmatch(r"[A-Za-z0-9_-]+", body):
                raise ValueError("incorrect token kind")
            received = _decode(signature)
            message = f"{kind}.{body}".encode("ascii")
            matches = [hmac.compare_digest(hmac.digest(key, message, "sha256"), received)
                       for key in self._verification[kind]]
            if not any(matches):
                raise ValueError("invalid signature")
            claims = json.loads(_decode(body))
            if not isinstance(claims, list) or len(claims) != 8:
                raise ValueError("invalid claims")
            uid, sid, app, ver, expiry, issued, generation, nonce = claims
            if (not all(isinstance(x, str) for x in (uid, sid, app, nonce))
                    or app not in APPS or not all(type(x) is int for x in (ver, expiry, issued, generation))
                    or not 0 <= generation < 2**64 or not 0 <= issued < expiry):
                raise ValueError("invalid claims")
            now = int(self.clock())
            if not issued <= now < expiry:
                raise ValueError("expired token")
            return claims
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise AuthError() from None

    def _issue(self, row, generation):
        now = int(self.clock())
        claims = [row.uid, row.sid, row.app, row.version, row.expires, now, generation]
        refresh = self._seal("r5", [*claims, secrets.token_urlsafe(24)])
        claims[4] = min(row.expires, now + ACCESS_TTL)
        access = self._seal("a5", [*claims, secrets.token_urlsafe(16)])
        return {"user_id": row.uid, "session_id": row.sid, "access_token": access,
                "refresh_token": refresh, "access_expires_at": claims[4],
                "refresh_expires_at": row.expires}


    def create(self, uid, app, expected_version, expected_hash, email):
        if app not in APPS:
            raise AuthError(400, "INVALID_APP")
        row = SimpleNamespace(uid=uid, sid=str(uuid4()), app=app, version=expected_version,
                              expires=int(self.clock()) + REFRESH_TTL)
        pair = self._issue(row, 0)
        self.repo.create(row, email, expected_hash, _refresh_state(0, pair["refresh_token"]))
        return pair

    def claims(self, token, app, kind="a5"):
        claims = self._open(kind, token)
        if claims[2] != app:
            raise AuthError()
        return claims

    def refresh(self, token, app):
        uid, sid, _, ver, exp, _, gen, _ = claims = self.claims(token, app, "r5")
        if gen == 2**64 - 1:
            raise AuthError()
        pair = self._issue(SimpleNamespace(uid=uid, sid=sid, app=app, version=ver, expires=exp),
                           gen + 1)
        old = _refresh_state(gen, token)
        new = _refresh_state(gen + 1, pair["refresh_token"])
        if not self.repo.rotate(claims, old, new):
            raise AuthError()
        return pair

    def validate(self, token, app, permission="app:use"):
        claims = self.claims(token, app)
        self.repo.check(claims, permission)
        return {"user_id": claims[0], "session_id": claims[1], "app_id": app}

    def logout(self, token, app):
        claims = self.claims(token, app)
        self.repo.revoke(claims, claims[1], allow_already_revoked=True)

    def revoke(self, token, app, target_sid):
        try:
            if not isinstance(target_sid, str) or len(target_sid) != 36 or str(UUID(target_sid)) != target_sid:
                raise ValueError
        except (TypeError, ValueError):
            raise AuthError(400, "INVALID_SESSION_ID") from None
        self.repo.revoke(self.claims(token, app), target_sid)

    def revoke_all(self, token, app):
        self.repo.revoke_all(self.claims(token, app))

    def permissions(self, token, app):
        return self.repo.permissions(self.claims(token, app))

    def manage(self, token, app, target_uid, permission, grant):
        return self.repo.manage(self.claims(token, app), target_uid, permission, grant)
