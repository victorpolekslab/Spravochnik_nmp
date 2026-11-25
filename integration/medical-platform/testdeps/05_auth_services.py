"""Compose one set of services per worker. No network clients are created here."""
from importlib import import_module
from threading import BoundedSemaphore
from time import time
from types import SimpleNamespace

registration = import_module("05_auth_registration")
sessions = import_module("05_auth_sessions")
login = import_module("05_auth_login")
reset = import_module("05_auth_password_reset")
repository = import_module("05_ydb_auth_repository")


def build(pool, *, access_key, refresh_key, registration_key, recovery_key,
          verification_queue, recovery_queue, clock=time, observe=lambda event: None):
    keys = (access_key, refresh_key, registration_key, recovery_key)
    if not all(isinstance(key, bytes) and len(key) >= 32 for key in keys) or len(set(keys)) != 4:
        raise ValueError("Four distinct secret keys of at least 32 bytes are required")
    slot = BoundedSemaphore(1)
    limiter = registration.SourceLimiter()
    repo = repository.Repository(pool)
    service = sessions.Sessions(repo, access_key, refresh_key, clock)
    return SimpleNamespace(
        repo=repo,
        sessions=service,
        login=login.Login(service, registration.HASHER, limiter, slot,
                          registration.normalize_email, sessions.AuthError),
        register=registration.RegistrationService(
            registration.YdbRegistrationStore(pool), verification_queue, receipt_secret=registration_key,
            observe=observe, limiter=limiter, hash_slot=slot),
        reset=reset.PasswordReset(repo, recovery_key, recovery_queue, limiter, slot,
                                  registration.HASHER, observe=observe),
    )
