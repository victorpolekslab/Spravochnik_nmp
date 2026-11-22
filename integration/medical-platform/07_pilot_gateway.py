"""Loopback-only stage-7 WSGI integration, with process-local cookie sessions."""
import hmac
from importlib import import_module
from http import HTTPStatus
from http.cookies import SimpleCookie, CookieError
import json
import secrets
from threading import RLock
from time import time
from urllib.parse import urlsplit

AuthError = import_module("05_auth_sessions").AuthError
learning = import_module("06_learning_api")


class PilotGateway:
    def __init__(self, services, catalog, origin, *, enable_learning=False, clock=time):
        url = urlsplit(origin)
        if (url.scheme not in ("http", "https") or url.hostname not in ("localhost", "127.0.0.1")
                or url.username or url.password or url.path or url.query or url.fragment):
            raise ValueError("Use an exact loopback origin")
        self.services = services
        self.learning = learning.LearningAPI(services.sessions, catalog)
        self.origin, self.host = origin, url.netloc
        self.enable_learning, self.clock = enable_learning, clock
        self.sessions, self.guard = {}, RLock()

    def __call__(self, env, respond):
        cookie = None
        try:
            status, result, cookie = self.dispatch(env)
        except (learning.Error, AuthError) as error:
            status, result = error.status, {"error": error.code}
        except Exception:
            status, result = 503, {"error": "PILOT_UNAVAILABLE"}
        if status is None:
            return self.learning(env, respond)
        body = json.dumps(result, separators=(",", ":")).encode()
        headers = [("Content-Type", "application/json"), ("Cache-Control", "no-store"),
                   ("X-Content-Type-Options", "nosniff"), ("Content-Length", str(len(body)))]
        if cookie:
            headers.append(("Set-Cookie", cookie))
        respond(f"{status} {HTTPStatus(status).phrase}", headers)
        return [body]

    def dispatch(self, env):
        if env.get("HTTP_HOST") != self.host or env.get("REMOTE_ADDR") not in ("127.0.0.1", "::1"):
            raise AuthError(403, "PILOT_LOOPBACK_ONLY")
        for field, limit in (("HTTP_AUTHORIZATION", 1040), ("HTTP_COOKIE", 4096),
                             ("PATH_INFO", 500), ("QUERY_STRING", 1200)):
            if len(env.get(field, "")) > limit:
                raise AuthError(400, "REQUEST_LIMIT")
        if env.get("HTTP_TRANSFER_ENCODING") or env.get("HTTP_CONTENT_ENCODING"):
            raise AuthError(400, "REQUEST_LIMIT")
        parts = env.get("PATH_INFO", "").split("/")
        if len(parts) < 5 or parts[:2] != ["", "v1"] or parts[2] not in ("nmp", "terapevt"):
            raise AuthError(404, "NOT_FOUND")
        app = parts[2]
        method = env.get("REQUEST_METHOD")
        if method == "POST" and env.get("HTTP_ORIGIN") != self.origin:
            raise AuthError(403, "ORIGIN_DENIED")
        if parts[3] == "learning":
            if not self.enable_learning or app != "nmp":
                raise AuthError(503, "LEARNING_PILOT_DISABLED")
            active = self.cookie_handle(env, "__Host-medical_" + app)
            with self.guard:
                state = self.sessions.get(active)
                auth = env.get("HTTP_AUTHORIZATION", "")
                if not state or state[0] != app or not auth.startswith("Bearer "):
                    raise AuthError(401, "SESSION_CHANGED")
                claims = self.services.sessions.claims(auth[7:], app)
                if tuple(claims[:2]) != (state[1]["user_id"], state[1]["session_id"]):
                    raise AuthError(401, "SESSION_CHANGED")
                captured = {}
                def capture(status, headers):
                    captured["status"] = status
                output = self.learning(env, capture)
                return int(captured["status"].split()[0]), json.loads(b"".join(output)), None
        if parts[3] != "auth" or len(parts) != 5 or method != "POST":
            raise AuthError(404, "NOT_FOUND")
        body = learning.get_body(env)
        if not isinstance(body, dict):
            raise AuthError(400, "INVALID_REQUEST")
        action = parts[4]
        name = "__Host-medical_" + app
        handle = self.cookie_handle(env, name)
        with self.guard:
            now = int(self.clock())
            for entry, (_, pair) in tuple(self.sessions.items()):
                if pair["refresh_expires_at"] <= now:
                    self.sessions.pop(entry, None)
            old = self.sessions.get(handle)
            if action == "login" and set(body) == {"email", "password"}:
                if len(self.sessions) >= 128 and old is None:
                    raise AuthError(503, "PILOT_SESSION_LIMIT")
                pair = self.services.login.login(body["email"], body["password"], app,
                                                source_ip=env["REMOTE_ADDR"])
                if old and old[0] == app:
                    self.sessions.pop(handle, None)
                handle = secrets.token_urlsafe(32)
                self.sessions[handle] = app, pair
                return 200, self.public(pair), self.cookie(name, handle)
            if action == "resume" and not body:
                expected = set()
            elif action in ("refresh", "logout"):
                expected = {"user_id", "session_id"}
            else:
                raise AuthError(400, "INVALID_REQUEST")
            if set(body) != expected:
                raise AuthError(400, "INVALID_REQUEST")
            if not old or old[0] != app:
                raise AuthError()
            pair = old[1]
            if not all(isinstance(body[k], str) and body[k].isascii() and
                       hmac.compare_digest(body[k], pair[k]) for k in expected):
                raise AuthError(401, "SESSION_CHANGED")
            if action == "logout":
                try:
                    sessions = self.services.sessions
                    claims = sessions.claims(pair["refresh_token"], app, "r5")
                    sessions.repo.revoke(claims, claims[1], allow_already_revoked=True)
                except AuthError as error:
                    if error.status not in (401, 403):
                        raise
                self.sessions.pop(handle, None)
                return 200, {}, self.cookie(name, "", clear=True)
            if pair["access_expires_at"] <= now + 15:
                try:
                    pair = self.services.sessions.refresh(pair["refresh_token"], app)
                except AuthError as error:
                    if error.status in (401, 403):
                        self.sessions.pop(handle, None)
                    raise
                self.sessions[handle] = app, pair
            else:
                self.services.sessions.validate(pair["access_token"], app)
            return 200, self.public(pair), None

    @staticmethod
    def cookie_handle(env, name):
        jar = SimpleCookie()
        try:
            jar.load(env.get("HTTP_COOKIE", ""))
        except CookieError:
            raise AuthError() from None
        return jar[name].value if name in jar else ""

    @staticmethod
    def public(pair):
        return {key: pair[key] for key in ("user_id", "session_id", "access_token", "access_expires_at")}

    @staticmethod
    def cookie(name, value, *, clear=False):
        return f"{name}={value}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age={0 if clear else 2592000}"
