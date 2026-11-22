from importlib import import_module
from io import BytesIO
import json
from types import SimpleNamespace
from unittest import TestCase

pilot = import_module("07_pilot_gateway")
fixture_module = import_module("071_browser_fixture")
ORIGIN = "http://localhost:8766"


class GatewayModel(TestCase):
    def setUp(self):
        self.model = fixture_module.Fixture()
        self.clock = 1
        self.services = SimpleNamespace(sessions=self.model, login=self.model)
        self.gateway = pilot.PilotGateway(self.services, None, ORIGIN, fixture_memory=True, clock=lambda: self.clock,
                                          enable_learning=True)
        self.cookie = ""

    def request(self, path, body=None, *, origin=ORIGIN, bearer="", cookie=None):
        raw = json.dumps(body).encode()
        env = dict(REQUEST_METHOD="POST" if body is not None else "GET",
                   PATH_INFO="/v1/nmp/"+path, HTTP_HOST="localhost:8766", HTTP_ORIGIN=origin,
                   REMOTE_ADDR="127.0.0.1", CONTENT_TYPE="application/json",
                   CONTENT_LENGTH=str(len(raw)), HTTP_AUTHORIZATION="Bearer "+bearer,
                   HTTP_COOKIE=self.cookie if cookie is None else cookie)
        env["wsgi.input"] = BytesIO(raw)
        result = []
        raw = b"".join(self.gateway(env, lambda status, headers: result.extend(
            (int(status.split()[0]), dict(headers)))))
        return (*result, json.loads(raw))

    def login(self, name="synthetic"):
        status, headers, result = self.request("auth/login", {"email":name,"password":"fixture"})
        self.assertEqual(status, 200)
        self.cookie = headers["Set-Cookie"].split(";")[0]
        self.assertIn("Max-Age=2592000", headers["Set-Cookie"])
        return {key:result[key] for key in ("user_id", "session_id")}, result

    def test_refresh_when_backend_temporarily_unavailable_keeps_cookie_handle(self):
        identity, _ = self.login()
        self.clock = 99
        original = self.model.refresh
        def temporary(*_):
            raise pilot.AuthError(503, "AUTH_TEMPORARILY_UNAVAILABLE")
        self.model.refresh = temporary
        self.assertEqual(self.request("auth/refresh", identity)[0], 503)
        self.model.refresh = original
        self.assertEqual(self.request("auth/refresh", identity)[0], 200)

    def test_logout_waits_for_revocation_and_does_not_rotate(self):
        identity, _ = self.login()
        self.clock = 101
        original = self.model.revoke
        def temporary(*_, **__):
            raise pilot.AuthError(503, "AUTH_TEMPORARILY_UNAVAILABLE")
        self.model.revoke = temporary
        self.model.refresh = lambda *_: self.fail("logout must not rotate")
        self.assertEqual(self.request("auth/logout", identity)[0], 503)
        self.model.revoke = original
        status, headers, _ = self.request("auth/logout", identity)
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        self.assertIn(identity["session_id"], self.model.revoked)
        self.assertEqual(self.request("auth/refresh", identity)[0], 401)

    def test_get_rejects_old_bearer_after_account_change(self):
        _, old = self.login()
        self.login("other")
        self.assertEqual(self.request("learning/tests/quiz", bearer=old["access_token"])[0], 401)

    def test_foreign_origin_and_unsupported_worker(self):
        self.login()
        self.assertEqual(self.request("auth/resume", {}, origin="https://other.invalid")[0], 403)
        self.gateway = pilot.PilotGateway(self.services, None, ORIGIN, fixture_memory=True)
        self.assertEqual(self.request("auth/resume", {})[0], 401)

    def test_revoked_session_cannot_resume_from_fresh_cached_access(self):
        identity, _ = self.login()
        self.model.revoked.add(identity["session_id"])
        self.assertEqual(self.request("auth/resume", {})[0], 401)
