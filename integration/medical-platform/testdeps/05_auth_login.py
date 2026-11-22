"""Login service for the isolated stage-4 repository."""
from dataclasses import dataclass
import secrets

from argon2 import Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError


def allowed_hash(value):
    if not isinstance(value, str) or len(value) > 256:
        return False
    try:
        settings = extract_parameters(value)
    except (InvalidHashError, ValueError, TypeError):
        return False
    return (settings.type == Type.ID and settings.version == 19
            and 1 <= settings.time_cost <= 3 and 1 <= settings.parallelism <= 2
            and 8 * settings.parallelism <= settings.memory_cost <= 65536
            and 16 <= settings.hash_len <= 64 and 8 <= settings.salt_len <= 32)


@dataclass
class Login:
    sessions: object
    hasher: object
    limiter: object
    hash_slot: object
    normalize_email: object
    auth_error: type

    def __post_init__(self):
        with self.hash_slot:
            self.dummy_hash = self.hasher.hash(secrets.token_urlsafe(32))

    def login(self, email, password, app, *, source_ip):
        if not self.limiter.allow(source_ip):
            raise self.auth_error(429, "TRY_LATER")
        email = self.normalize_email(email)
        if (email is None or not isinstance(app, str) or app not in ("nmp", "terapevt")
                or not isinstance(password, str) or not 1 <= len(password) <= 128):
            raise self.auth_error(400, "INVALID_LOGIN")
        try:
            if len(password.encode("utf-8")) > 512:
                raise self.auth_error(400, "INVALID_LOGIN")
        except UnicodeEncodeError:
            raise self.auth_error(400, "INVALID_LOGIN") from None
        row = self.sessions.repo.account(email)
        snapshot = ((row.user_id, row.auth_version, row.password_hash)
                    if row and row.status == "active" and row.verified_at is not None else None)

        if snapshot and not allowed_hash(snapshot[2]):
            snapshot = None
        if not self.hash_slot.acquire(blocking=False):
            raise self.auth_error(503, "TRY_LATER")
        try:
            try:
                valid = self.hasher.verify(snapshot[2] if snapshot else self.dummy_hash, password)
            except InvalidHashError:
                try:
                    self.hasher.verify(self.dummy_hash, password)
                except VerificationError:
                    pass
                valid = False
            except VerificationError:
                valid = False
        finally:
            self.hash_slot.release()
        if not valid or snapshot is None:
            raise self.auth_error()
        uid, version, password_hash = snapshot
        return self.sessions.create(uid, app, version, password_hash, email)
