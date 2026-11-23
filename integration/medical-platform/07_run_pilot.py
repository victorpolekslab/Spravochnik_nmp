"""Run the review-only pilot on a dedicated local YDB and loopback HTTP."""
import base64
from importlib import import_module
import json
import os
import stat
from tempfile import NamedTemporaryFile
from mimetypes import guess_type
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server
import ydb


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def capture_mail(directory, kind):
    def capture(email, token):
        if not email.endswith("@example.invalid"):
            raise ValueError("Capture accepts synthetic addresses only")
        with NamedTemporaryFile(mode="w", dir=directory, prefix=kind + "-", delete=False) as out:
            json.dump({"email": email, "token": token}, out)
    return capture


def main():
    port = int(os.getenv("MEDICAL_PILOT_PORT", "8766"))
    database = import_module("076_ydb").Database.from_env(os.environ)
    key_names = ("ACCESS", "REFRESH", "REGISTRATION", "RECOVERY", "DIGEST")
    keys = [base64.b64decode(os.environ["MEDICAL_PILOT_"+name+"_KEY"],validate=True) for name in key_names]
    if len(set(keys)) != 5 or any(len(key)!=32 for key in keys):
        raise ValueError("Five distinct base64-encoded 32-byte keys required")
    auth = import_module("05_auth_services")
    gateway = import_module("07_pilot_gateway").PilotGateway
    catalog_class = import_module("06_learning_grader").Catalog
    root = Path(__file__).resolve().parent
    web_root = Path(os.environ["MEDICAL_PILOT_WEB_ROOT"]).resolve() if os.getenv("MEDICAL_PILOT_WEB_ROOT") else None
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
    origin = os.environ["MEDICAL_PILOT_HTTPS_ORIGIN"] if database.managed else f"http://localhost:{port}"
    def metadata():
        from ydb.iam import MetadataUrlCredentials
        return MetadataUrlCredentials()
    capture_dir = os.getenv("MEDICAL_PILOT_SYNTHETIC_MAIL_DIR")
    if capture_dir:
        directory = Path(capture_dir).resolve(strict=True)
        info = directory.stat()
        if (database.managed or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o700
                or directory.is_relative_to(root) or (web_root and directory.is_relative_to(web_root))):
            raise ValueError("Synthetic capture requires a private local directory outside served assets")
        verification = capture_mail(directory, "verify")
        recovery = capture_mail(directory, "reset")
    else:
        def verification(*_):
            raise RuntimeError("Synthetic capture disabled")
        recovery = verification
    with database.pool(ydb, metadata) as pool:
        service=auth.build(pool,access_key=keys[0],refresh_key=keys[1],
                           registration_key=keys[2],recovery_key=keys[3],
                           verification_queue=verification,recovery_queue=recovery)
        service.sessions.configure_retired_keys(access=old_access, refresh=old_refresh)
        shared = import_module("072_browser_sessions").BrowserSessions(service.sessions, service.sessions.clock)
        handler=gateway(service,catalog,origin,browser_sessions=shared, allow_private_ingress=database.managed,
                        enable_account_capture=bool(capture_dir), enable_learning=os.getenv("MEDICAL_PILOT_LEARNING")=="1")

        bounded_api = import_module("075_deadline").Deadline(handler)

        def dispatch(env, respond):
            path=env.get("PATH_INFO","")
            if path == "/pilot/config.json":
                if (env.get("REQUEST_METHOD") != "GET" or env.get("HTTP_HOST") != handler.host
                        or not database.managed or os.getenv("MEDICAL_PILOT_CONFIG_ENABLED") != "1"):
                    respond("404 Not Found", [("Cache-Control", "no-store")])
                    return [b""]
                data = json.dumps({"origins": [handler.origin]}).encode()
                respond("200 OK", [("Content-Type", "application/json"),
                                   ("Cache-Control", "no-store"),
                                   ("X-Content-Type-Options", "nosniff")])
                return [data]
            allowed={ "/pilot/nmp": ("07_pilot.html", "text/html"),
                      "/pilot/074_panel.mjs": ("074_panel.mjs", "text/javascript"),
                      "/pilot/07_pilot_ui.mjs": ("07_pilot_ui.mjs", "text/javascript"),
                      "/pilot/072_ui_adapter.mjs": ("072_ui_adapter.mjs", "text/javascript"),
                      "/pilot/07_client.mjs": ("07_client.mjs", "text/javascript") }
            if therapist:
                allowed["/pilot/terapevt"]=("07_pilot.html","text/html")
            if env.get("REQUEST_METHOD")=="GET" and path in allowed and env.get("HTTP_HOST")==handler.host:
                name, content_type=allowed[path]
                folder=therapist if path=="/pilot/terapevt" else root
                data=(folder/name).read_bytes()
                respond("200 OK",[("Content-Type",content_type+"; charset=utf-8"),
                                  ("Cache-Control","no-store"),("X-Content-Type-Options","nosniff"),
                                  ("Content-Security-Policy","default-src 'none'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")])
                return [data]
            if (web_root and env.get("REQUEST_METHOD") == "GET"
                    and env.get("HTTP_HOST") == handler.host and not path.startswith(("/v1/", "/pilot/"))):
                asset = (web_root / (path.lstrip("/") or "index.html")).resolve()
                if (asset.is_relative_to(web_root) and asset.is_file() and
                        asset.suffix in {".html", ".js", ".css", ".svg", ".png", ".jpg", ".webp", ".woff2"}):
                    data = asset.read_bytes()
                    respond("200 OK", [("Content-Type", guess_type(asset)[0] or "application/octet-stream"),
                        ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                        ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")])
                    return [data]
            return bounded_api(env,respond)

        with make_server("127.0.0.1",port,dispatch,handler_class=Quiet) as web:
            print(origin+"/pilot/nmp",flush=True)
            web.serve_forever()


if __name__=="__main__":
    main()
