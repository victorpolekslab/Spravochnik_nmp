"""Stage-6 data operations use the stage-5 SerializableReadWrite repository."""
from importlib import import_module
from datetime import UTC, datetime, timedelta

LearningError = import_module("06_learning_grader").LearningError

ATTEMPT = "attempt_id, test_id, course_id, test_version, score, max_score, passed, completed_at"
PROGRESS = "course_id, item_id, status, updated_at, completed_at"


def scope(claims):
    return {"uid": (claims[0], "Utf8"), "app": (claims[2], "Utf8")}


def public_row(row, fields):
    result = {key: getattr(row, key) for key in fields.split(", ")}
    for key in ("completed_at", "updated_at"):
        if key not in result or result[key] is None:
            continue
        value = result[key]
        if isinstance(value, int):
            value = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=value)
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        result[key] = value.isoformat()
    return result


def persist(repo, claims, assess):
    def operation(tx):
        repo.authorize(tx, claims, "learning:submit")
        grade = assess()
        test = grade.test
        if test.app != claims[2]:
            raise LearningError(400, "INVALID_ATTEMPT")
        key = {**scope(claims), "test": (test.test_id, "Utf8"), "attempt": (grade.attempt_id, "Utf8")}
        prior = repo.one(tx, f"""SELECT {ATTEMPT}, answers_digest FROM test_attempts
            WHERE user_id=$uid AND app_id=$app AND test_id=$test AND attempt_id=$attempt;""", **key)
        if prior:
            if not grade.matches_digest(prior.answers_digest):
                raise LearningError(409, "ATTEMPT_CONFLICT")
            return public_row(prior, ATTEMPT)
        repo.query(tx, """INSERT INTO test_attempts
            (user_id, app_id, test_id, attempt_id, course_id, test_version, score, max_score, passed,
             completed_at, answers_digest)
            VALUES ($uid,$app,$test,$attempt,$course,$version,$score,$max,$passed,
                    CurrentUtcTimestamp(),$digest);""", **key,
                   course=(test.course_id,"Utf8"),version=(test.version,"Utf8"),
                   score=(grade.score,"Uint32"),max=(len(test.questions),"Uint32"),
                   passed=(grade.passed,"Bool"),digest=(grade.digest,"String"))
        pk = {**scope(claims), "course": (test.course_id,"Utf8"), "item": ("test:" + test.test_id,"Utf8")}
        current = repo.one(tx, """SELECT status FROM learning_progress WHERE
            user_id=$uid AND app_id=$app AND course_id=$course AND item_id=$item;""", **pk)
        if not current or current.status != "completed":
            repo.query(tx, """UPSERT INTO learning_progress
                (user_id, app_id, course_id, item_id, status, updated_at, completed_at)
                VALUES ($uid,$app,$course,$item,IF($passed,'completed'u,'attempted'u),
                 CurrentUtcTimestamp(),IF($passed,Just(CurrentUtcTimestamp()),Nothing(Timestamp?)));""",
                       **pk, passed=(grade.passed,"Bool"))
        row = repo.one(tx, f"""SELECT {ATTEMPT} FROM test_attempts WHERE
            user_id=$uid AND app_id=$app AND test_id=$test AND attempt_id=$attempt;""", **key)
        return public_row(row, ATTEMPT)
    return repo.transaction(operation, write=True)
