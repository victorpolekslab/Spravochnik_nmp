"""Private WSGI adapter. Inject stage-5 sessions and server-only catalog."""
from http import HTTPStatus
from importlib import import_module
import json
from urllib.parse import parse_qs

grader = import_module("06_learning_grader")
reader = import_module("06_learning_read")
writer = import_module("06_learning_write")
auth = import_module("05_auth_sessions")
Error = grader.LearningError
MAX_BODY = 32768
MAX_RESPONSE = 262144


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate JSON field")
    return result


def invalid_constant(value):
    raise ValueError("invalid JSON constant")


def get_body(env):
    dtype = env.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower()
    if dtype != "application/json":
        raise Error(415, "JSON_REQUIRED")
    raw_size = env.get("CONTENT_LENGTH", "")
    if not raw_size:
        raise Error(411, "LENGTH_REQUIRED")
    if len(raw_size) > 8 or not raw_size.isascii() or not raw_size.isdecimal():
        raise Error(400, "INVALID_LENGTH")
    size = int(raw_size)
    if size > MAX_BODY:
        raise Error(413, "BODY_TOO_LARGE")
    try:
        data = env["wsgi.input"].read(size)
        if len(data) != size:
            raise ValueError("incomplete body")
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique_object,
                          parse_constant=invalid_constant)
    except (UnicodeError, ValueError, RecursionError, OSError):
        raise Error(400, "INVALID_JSON") from None


def get_query(env):
    raw = env.get("QUERY_STRING", "")
    if len(raw) > 1200:
        raise Error(400, "INVALID_QUERY")
    try:
        values = parse_qs(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=5)
        if any(len(v) != 1 for v in values.values()):
            raise ValueError
    except ValueError:
        raise Error(400, "INVALID_QUERY") from None
    return {k: v[0] for k, v in values.items()}


def page_options(query, field):
    if set(query) - {"limit", field, "after_major", "after_minor"}:
        raise Error(400, "INVALID_QUERY")
    raw = query.get("limit", "20")
    if not raw.isascii() or not raw.isdecimal() or len(raw) > 2 or not 1 <= int(raw) <= 50:
        raise Error(400, "INVALID_QUERY")
    first = query.get(field)
    major, minor = query.get("after_major"), query.get("after_minor")
    if ((first is not None and not grader.valid_id(first)) or
            ((major is None) != (minor is None)) or
            (major is not None and (
                not grader.valid_id(major) or not isinstance(minor, str) or
                not (grader.valid_id(minor) or (field == "course_id" and
                     minor.startswith("test:") and grader.valid_id(minor[5:]))) or
                (first is not None and major != first)))):
        raise Error(400, "INVALID_CURSOR")
    return {"limit": int(raw), "first": first, "after": (major, minor) if major is not None else None}


class LearningAPI:
    def __init__(self, sessions, catalog):
        self.sessions, self.catalog = sessions, catalog

    def __call__(self, env, start_response):
        try:
            status, data = self.dispatch(env)
        except (Error, auth.AuthError) as exc:
            status, data = exc.status, {"error": exc.code}
        except Exception:
            status, data = 503, {"error": "LEARNING_TEMPORARILY_UNAVAILABLE"}
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(body) > MAX_RESPONSE:
            status, body = 503, b'{"error":"RESPONSE_LIMIT"}'
        headers = [("Content-Type", "application/json; charset=utf-8"),
                   ("Content-Length", str(len(body))), ("Cache-Control", "no-store"),
                   ("X-Content-Type-Options", "nosniff")]
        if status == 401:
            headers.append(("WWW-Authenticate", "Bearer"))
        start_response(f"{status} {HTTPStatus(status).phrase}", headers)
        return [body]

    def dispatch(self, env):
        path = env.get("PATH_INFO", "")
        if len(path) > 500:
            raise Error(404, "NOT_FOUND")
        parts = path.split("/")
        if len(parts) < 5 or parts[:2] != ["", "v1"] or parts[2] not in auth.APPS or parts[3] != "learning":
            raise Error(404, "NOT_FOUND")
        app, route = parts[2], parts[4:]
        method = env.get("REQUEST_METHOD", "GET")
        value = env.get("HTTP_AUTHORIZATION", "")
        prefix, sep, token = value.partition(" ")
        if prefix.lower() != "bearer" or not sep:
            raise Error(401, "AUTH_REQUIRED")
        claims = self.sessions.claims(token, app)
        query = get_query(env)

        if method == "POST" and route == ["attempts"]:
            if query:
                raise Error(400, "INVALID_QUERY")
            return 200, writer.submit(self.sessions, self.catalog, claims, get_body(env))
        if method != "GET":
            raise Error(405, "METHOD_NOT_ALLOWED")
        if route == ["attempts"]:
            return 200, reader.page(self.sessions, claims, kind="attempts", **page_options(query, "test_id"))
        if route == ["progress"]:
            return 200, reader.page(self.sessions, claims, kind="progress", **page_options(query, "course_id"))
        if len(route) == 3 and route[0] == "attempts" and grader.valid_id(route[1]) and grader.valid_id(route[2]):
            if query:
                raise Error(400, "INVALID_QUERY")
            return 200, reader.one_attempt(self.sessions, claims, route[1], route[2])
        self.sessions.repo.check(claims, "learning:view")
        if len(route) == 2 and route[0] == "tests" and grader.valid_id(route[1]):
            if set(query) - {"version"} or ("version" in query and not grader.valid_id(query["version"])):
                raise Error(400, "INVALID_QUERY")
            return 200, self.catalog.get(app, route[1], query.get("version")).public()
        if route == ["courses"] or (len(route) == 2 and route[0] == "courses" and grader.valid_id(route[1])):
            if query:
                raise Error(400, "INVALID_QUERY")
            courses = {}
            for (test_app, _), test in self.catalog.current.items():
                if test_app == app:
                    courses.setdefault(test.course_id, []).append(
                        {"test_id": test.test_id, "test_version": test.version, "title": test.title})
            if len(route) == 2:
                if route[1] not in courses:
                    raise Error(404, "COURSE_NOT_FOUND")
                return 200, {"course_id": route[1], "tests": courses[route[1]]}
            return 200, {"items": [{"course_id": key, "tests": entries}
                                   for key, entries in sorted(courses.items())]}
        raise Error(404, "NOT_FOUND")
