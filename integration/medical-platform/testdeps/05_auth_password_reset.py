"""Recovery with neutral responses and transactional reset receipts."""
from hashlib import sha256
import hmac
from importlib import import_module
import secrets

registration = import_module("05_auth_registration")
AuthError = import_module("05_auth_sessions").AuthError


class PasswordReset:
    def __init__(self, repo, key, enqueue, limiter, hash_slot, hasher, observe=None):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("A separate recovery key of at least 32 bytes is required")
        self.repo, self.key, self.enqueue = repo, key, enqueue
        self.limiter, self.hash_slot, self.hasher = limiter, hash_slot, hasher
        self.observe = observe

    def request(self, email, *, source_ip):
        if not self.limiter.allow(source_ip):
            raise AuthError(429, "TRY_LATER")
        email = registration.normalize_email(email)
        if email is None:
            raise AuthError(400, "INVALID_EMAIL")
        token = secrets.token_urlsafe(32)
        digest = sha256(token.encode("ascii")).digest()
        cooldown = hmac.digest(self.key, b"cooldown\x00" + email.encode("ascii"), "sha256")
        if self.repo.issue_reset(email, digest, cooldown):
            try:
                self.enqueue(email, token)
            except Exception:
                if self.observe is not None:
                    try:
                        self.observe("reset_delivery_error")
                    except Exception:
                        pass
        return 202, {"message": "If eligible, check your email."}

    def complete(self, token, password, request_id, *, source_ip):
        from argon2.exceptions import HashingError
        if not self.limiter.allow(source_ip):
            raise AuthError(429, "TRY_LATER")
        value = registration.password_bytes(password)
        attempt = registration.request_uuid(request_id)
        if (value is None or attempt is None or not isinstance(token, str)
                or not registration.TOKEN_PATTERN.fullmatch(token)):
            raise AuthError(400, "INVALID_RESET")
        digest = sha256(token.encode("ascii")).digest()
        receipt = hmac.digest(self.key, b"receipt\x00" + digest + attempt.bytes + value, "sha256")
        state = self.repo.inspect_reset(digest, receipt)
        if state == "done":
            return 200, {"message": "Password updated."}
        if state != "pending":
            raise AuthError(400, "INVALID_RESET")
        if not self.hash_slot.acquire(blocking=False):
            raise AuthError(503, "TRY_LATER")
        try:
            new_hash = self.hasher.hash(value)
        except HashingError:
            raise AuthError(503, "TRY_LATER") from None
        finally:
            self.hash_slot.release()
        if not self.repo.complete_reset(digest, receipt, new_hash):
            raise AuthError(400, "INVALID_RESET")
        return 200, {"message": "Password updated."}
