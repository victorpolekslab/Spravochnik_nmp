"""Transactional submission of a result already graded on the server."""
from importlib import import_module

AuthError = import_module("05_auth_sessions").AuthError


def submit_verified(sessions, access, app, *, test_id, attempt_id, course_id,
                    test_version, score, max_score, passed):
    """Caller must supply values from a trusted, versioned server-side grader."""
    values = (test_id, attempt_id, course_id, test_version)
    if (not all(isinstance(v, str) and v.isascii() and 1 <= len(v) <= 128 for v in values)
            or type(score) is not int or type(max_score) is not int
            or not 0 <= score <= max_score < 2**32 or max_score == 0 or type(passed) is not bool):
        raise AuthError(400, "INVALID_ATTEMPT")
    claims = sessions.claims(access, app)
    repo = sessions.repo

    def operation(tx):
        repo.authorize(tx, claims, "learning:submit")
        key = {"uid": (claims[0], "Utf8"), "app": (claims[2], "Utf8"),
               "test": (test_id, "Utf8"), "attempt": (attempt_id, "Utf8")}
        prior = repo.one(tx, """SELECT course_id, test_version, score, max_score, passed
             FROM test_attempts WHERE user_id=$uid AND app_id=$app AND test_id=$test AND attempt_id=$attempt;""",
                         **key)
        if prior:
            if (prior.course_id, prior.test_version, prior.score, prior.max_score, prior.passed) != (
                    course_id, test_version, score, max_score, passed):
                raise AuthError(409, "ATTEMPT_CONFLICT")
            return "accepted"
        repo.query(tx, """INSERT INTO test_attempts
            (user_id, app_id, test_id, attempt_id, course_id, test_version, score, max_score, passed, completed_at)
            VALUES ($uid, $app, $test, $attempt, $course, $version, $score, $max_score, $passed,
                    CurrentUtcTimestamp());""",
                   **key, course=(course_id, "Utf8"), version=(test_version, "Utf8"),
                   score=(score, "Uint32"), max_score=(max_score, "Uint32"), passed=(passed, "Bool"))
        progress = {"uid": (claims[0], "Utf8"), "app": (claims[2], "Utf8"),
                    "course": (course_id, "Utf8"), "item": ("test:" + test_id, "Utf8")}
        current = repo.one(tx, """SELECT status FROM learning_progress WHERE
            user_id=$uid AND app_id=$app AND course_id=$course AND item_id=$item;""", **progress)
        if not current or current.status != "completed":
            repo.query(tx, """UPSERT INTO learning_progress
                (user_id, app_id, course_id, item_id, status, updated_at, completed_at)
                VALUES ($uid, $app, $course, $item, IF($passed, 'completed'u, 'attempted'u),
                        CurrentUtcTimestamp(),
                        IF($passed, Just(CurrentUtcTimestamp()), Nothing(Timestamp?)));""",
                       **progress, passed=(passed, "Bool"))
        return "accepted"

    return repo.transaction(operation, write=True)
