"""Loopback WSGI integration with an explicit browser-session backend."""
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
    def __init__(self, services, catalog, origin, *, enable_learning=False, clock=time, browser_sessions=None, fixture_memory=False, allow_private_ingress=False, enable_account_capture=False):
        url = urlsplit(origin)
        allowed = (url.scheme == "https" and url.hostname) if allow_private_ingress else (
            url.scheme in ("http", "https") and url.hostname in ("localhost", "127.0.0.1"))
        if (not allowed
                or url.username or url.password or url.path or url.query or url.fragment):
            raise ValueError("Use an exact pilot origin")
        self.services = services
        self.learning = learning.LearningAPI(services.sessions, catalog)
        self.origin, self.host = origin, url.netloc
        self.enable_learning, self.clock = enable_learning, clock
        if browser_sessions is None and not fixture_memory:
            raise ValueError("A browser-session backend is required")
        self.browser_sessions = browser_sessions
        if enable_account_capture and (allow_private_ingress or not browser_sessions):
            raise ValueError("Synthetic account capture requires local shared sessions")
        self.enable_account_capture = enable_account_capture
        if fixture_memory:
            self.sessions, self.guard = {}, RLock()

    def __call__(self, env, respond):
        cookie = None
        try:
            status, result, cookie = self.dispatch(env)
        except (learning.Error, AuthError) as error:
            status, result = error.status, {"error": error.code}
        except Exception:
            status, result = 503, {"error": "PILOT_UNAVAILABLE"}
        if status == 429:
            retry_after = "60"
        else:
            retry_after = None
        if status is None:
            return self.learning(env, respond)
        body = json.dumps(result, separators=(",", ":")).encode()
        headers = [("Content-Type", "application/json"), ("Cache-Control", "no-store"),
                   ("X-Content-Type-Options", "nosniff"), ("Content-Length", str(len(body)))]
        if retry_after:
            headers.append(("Retry-After", retry_after))
        if cookie:
            headers.append(("Set-Cookie", cookie))
        respond(f"{status} {HTTPStatus(status).phrase}", headers)
        return [body]

    def dispatch(self, env):
        if env.get("HTTP_HOST") != self.host or env.get("REMOTE_ADDR") not in ("127.0.0.1", "::1"):
            raise AuthError(403, "PILOT_LOOPBACK_ONLY")
        for field, limit in (("HTTP_ORIGIN", 256), ("HTTP_AUTHORIZATION", 1040), ("HTTP_COOKIE", 4096),
                             ("PATH_INFO", 500), ("QUERY_STRING", 1200)):
            if len(env.get(field, "")) > limit:
                raise AuthError(400, "REQUEST_LIMIT")
        if any(env.get(name) for name in ("HTTP_FORWARDED", "HTTP_X_FORWARDED_FOR",
                                             "HTTP_X_FORWARDED_HOST", "HTTP_X_FORWARDED_PROTO")):
            raise AuthError(400, "UNSUPPORTED_PROXY_HEADERS")
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
            if self.browser_sessions is not None:
                value = env.get("HTTP_AUTHORIZATION", "")
                if not value.startswith("Bearer "):
                    raise AuthError()
                claims = self.services.sessions.claims(value[7:], app)
                shared = self.browser_sessions.use(app, active, "check", claims[:2])
                if shared["session_id"] != claims[1]:
                    raise AuthError()
                return None, None, None
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
        if action in ("register", "confirm", "forgot", "reset"):
            if not self.enable_account_capture:
                raise AuthError(404, "NOT_FOUND")
            status, result = self.synthetic_account(action, body, env["REMOTE_ADDR"])
            return status, result, None
        if self.browser_sessions is not None:
            return self.shared_auth(env, body, app, action, name, handle)
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

    def synthetic_account(self, action, body, source_ip):
        # Capture is local-only and expressly limited to synthetic addresses.
        if action in ("register", "forgot") and set(body) == {"email"}:
            email = body["email"]
            if not isinstance(email, str) or not email.casefold().endswith("@example.invalid"):
                raise AuthError(400, "INVALID_EMAIL")
            service = self.services.register.register if action == "register" else self.services.reset.request
            return service(email, source_ip=source_ip)
        if action in ("confirm", "reset") and set(body) == {"token", "password", "request_id"}:
            service = self.services.register.verify_email if action == "confirm" else self.services.reset.complete
            return service(body["token"], body["password"], body["request_id"], source_ip=source_ip)
        raise AuthError(400, "INVALID_REQUEST")

    def shared_auth(self, env, body, app, action, name, handle):
        if action == "login" and set(body) == {"email", "password"}:
            pair = self.services.login.login(body["email"], body["password"], app,
                                            source_ip=env["REMOTE_ADDR"])
            replacement = secrets.token_urlsafe(32)
            public = self.browser_sessions.bind(app, replacement, handle, pair)
            return 200, public, self.cookie(name, replacement)
        if action == "resume" and not body:
            return 200, self.browser_sessions.use(app, handle, action), None
        if action in ("refresh", "logout") and set(body) == {"user_id", "session_id"}:
            result = self.browser_sessions.use(app, handle, action, (body["user_id"], body["session_id"]))
            return 200, result, self.cookie(name, "", clear=True) if action == "logout" else None
        raise AuthError(400, "INVALID_REQUEST")

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
