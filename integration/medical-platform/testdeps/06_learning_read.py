"""Own-history reads and stable keyset pagination."""
from importlib import import_module

grader = import_module("06_learning_grader")
repository = import_module("06_learning_repository")


def one_attempt(sessions, claims, test, attempt):
    repo = sessions.repo
    def operation(tx):
        repo.authorize(tx, claims, "learning:view")
        row = repo.one(tx, f"""SELECT {repository.ATTEMPT} FROM test_attempts WHERE
            user_id=$uid AND app_id=$app AND test_id=$test AND attempt_id=$attempt;""",
                       **repository.scope(claims),test=(test,"Utf8"),attempt=(attempt,"Utf8"))
        if row is None:
            raise grader.LearningError(404, "ATTEMPT_NOT_FOUND")
        return repository.public_row(row, repository.ATTEMPT)
    return repo.transaction(operation)


def page(sessions, claims, *, kind, limit, first=None, after=None):
    repo = sessions.repo
    if kind == "attempts":
        table, cols = "test_attempts", repository.ATTEMPT
        major, minor = "test_id", "attempt_id"
    elif kind == "progress":
        table, cols = "learning_progress", repository.PROGRESS
        major, minor = "course_id", "item_id"
    else:
        raise ValueError("Unknown read kind")
    params = {**repository.scope(claims), "limit": (limit+1,"Uint64")}
    clause = ""
    if first is not None:
        clause = f" AND {major} = $first"
        params["first"] = first, "Utf8"
    if after is not None:
        clause += (f" AND {minor} > $minor" if first is not None else
                   f" AND ({major}, {minor}) > ($major, $minor)")
        if first is None:
            params["major"] = after[0], "Utf8"
        params["minor"] = after[1], "Utf8"

    def operation(tx):
        repo.authorize(tx, claims, "learning:view")
        rows = repo.query(tx, f"""SELECT {cols} FROM {table} WHERE user_id=$uid AND app_id=$app
            {clause} ORDER BY {major}, {minor} LIMIT $limit;""", **params)
        cursor = [getattr(rows[limit-1], major), getattr(rows[limit-1], minor)] if len(rows)>limit else None
        return {"items": [repository.public_row(row, cols) for row in rows[:limit]], "next": cursor}
    return repo.transaction(operation)
