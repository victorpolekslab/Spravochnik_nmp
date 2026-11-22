"""Isolated HTTP fixture. Synthetic auth and volatile repository, real gateway."""
from importlib import import_module
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from wsgiref.simple_server import WSGIRequestHandler, make_server

gateway = import_module("07_pilot_gateway")
ROOT = Path(__file__).parent


class Fixture:
    def __init__(self):
        self.records = {}
        self.revoked = set()
        self.users = {}
        self.repo = self

    def login(self, email, _password, app, **_kwargs):
        self.users.setdefault(email, str(uuid4()))
        return self.issue(self.users[email], str(uuid4()), app)

    def issue(self, uid, sid, app):
        access, refresh = str(uuid4()), str(uuid4())
        self.records[access] = self.records[refresh] = [uid, sid, app]
        return dict(user_id=uid, session_id=sid, access_token=access,
                    refresh_token=refresh, access_expires_at=100, refresh_expires_at=1000)

    def claims(self, token, app, _kind=None):
        value = self.records.get(token)
        if not value or value[2] != app:
            raise gateway.AuthError()
        return value

    def validate(self, token, app):
        value = self.claims(token, app)
        if value[1] in self.revoked:
            raise gateway.AuthError()

    def refresh(self, token, app):
        self.validate(token, app)
        return self.issue(*self.claims(token, app))

    def revoke(self, _claims, sid, **_kwargs):
        self.revoked.add(sid)


class Quiet(WSGIRequestHandler):
    def log_message(self, *_args):
        pass


def main():
    fixture = Fixture()
    handler = None
    def app(env, respond):
        path = env["PATH_INFO"]
        if path == "/fixture":
            body, mime = b"<!doctype html><title>Isolated regression</title>", "text/html"
        elif path == "/07_client.mjs":
            body, mime = (ROOT / "07_client.mjs").read_bytes(), "text/javascript"
        else:
            return handler(env, respond)
        respond("200 OK", [("Content-Type", mime), ("Content-Length", str(len(body)))])
        return [body]

    with make_server("127.0.0.1", 0, app, handler_class=Quiet) as server:
        origin = f"http://localhost:{server.server_port}"
        services = SimpleNamespace(login=fixture, sessions=fixture)
        handler = gateway.PilotGateway(services, None, origin, fixture_memory=True, clock=lambda: 90)
        print(origin, flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
