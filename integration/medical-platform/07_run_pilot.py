"""Run the review-only pilot on a dedicated local YDB and loopback HTTP."""
import base64
from importlib import import_module
import json
import os
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server
import ydb


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def main():
    port = int(os.getenv("MEDICAL_PILOT_PORT", "8766"))
    db_port = int(os.environ["MEDICAL_YDB_LOCAL_PORT"])
    key_names = ("ACCESS", "REFRESH", "REGISTRATION", "RECOVERY", "DIGEST")
    keys = [base64.b64decode(os.environ["MEDICAL_PILOT_"+name+"_KEY"],validate=True) for name in key_names]
    if len(set(keys)) != 5 or any(len(key)!=32 for key in keys):
        raise ValueError("Five distinct base64-encoded 32-byte keys required")
    auth = import_module("05_auth_services")
    gateway = import_module("07_pilot_gateway").PilotGateway
    catalog_class = import_module("06_learning_grader").Catalog
    root = Path(__file__).resolve().parent
    therapist = Path(os.environ["MEDICAL_PILOT_THERAPIST_DIR"]).resolve() if os.getenv("MEDICAL_PILOT_THERAPIST_DIR") else None
    def retired(kind):
        raw = os.getenv("MEDICAL_PILOT_RETIRED_" + kind + "_KEYS", "")
        return [base64.b64decode(value, validate=True) for value in raw.split(",")] if raw else []

    old_access, old_refresh, old_digest = map(retired, ("ACCESS", "REFRESH", "DIGEST"))
    all_keys = [*keys, *old_access, *old_refresh, *old_digest]
    if len(set(all_keys)) != len(all_keys) or any(len(key) != 32 for key in all_keys):
        raise ValueError("All active and retired keys must be independent 32-byte keys")
    catalog = catalog_class(json.loads(Path(os.environ["MEDICAL_PILOT_CATALOG"]).read_text()),
                            keys[4], historical_keys=old_digest)
    origin = f"http://localhost:{port}"
    with ydb.Driver(endpoint=f"grpc://127.0.0.1:{db_port}",database="/local",
                    credentials=ydb.AnonymousCredentials(),disable_discovery=True) as driver:
        driver.wait(timeout=10,fail_fast=True)
        with ydb.QuerySessionPool(driver) as pool:
            service=auth.build(pool,access_key=keys[0],refresh_key=keys[1],
                               registration_key=keys[2],recovery_key=keys[3],
                               verification_queue=lambda *_: None,recovery_queue=lambda *_: None)
            service.sessions.configure_retired_keys(access=old_access, refresh=old_refresh)
            shared = import_module("072_browser_sessions").BrowserSessions(service.sessions, service.sessions.clock)
            handler=gateway(service,catalog,origin,browser_sessions=shared,
                            enable_learning=os.getenv("MEDICAL_PILOT_LEARNING")=="1")

            def dispatch(env, respond):
                path=env.get("PATH_INFO","")
                allowed={ "/pilot/nmp": ("07_pilot.html", "text/html"),
                          "/pilot/07_pilot_ui.mjs": ("07_pilot_ui.mjs", "text/javascript"),
                          "/pilot/072_ui_adapter.mjs": ("072_ui_adapter.mjs", "text/javascript"),
                          "/pilot/07_client.mjs": ("07_client.mjs", "text/javascript") }
                if therapist:
                    allowed["/pilot/terapevt"]=("07_pilot.html","text/html")
                if env.get("REQUEST_METHOD")=="GET" and path in allowed and env.get("HTTP_HOST")==f"localhost:{port}":
                    name, content_type=allowed[path]
                    folder=therapist if path=="/pilot/terapevt" else root
                    data=(folder/name).read_bytes()
                    respond("200 OK",[("Content-Type",content_type+"; charset=utf-8"),
                                      ("Cache-Control","no-store"),("X-Content-Type-Options","nosniff"),
                                      ("Content-Security-Policy","default-src 'none'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")])
                    return [data]
                return handler(env,respond)

            with make_server("127.0.0.1",port,dispatch,handler_class=Quiet) as web:
                print(origin+"/pilot/nmp",flush=True)
                web.serve_forever()


if __name__=="__main__":
    main()
