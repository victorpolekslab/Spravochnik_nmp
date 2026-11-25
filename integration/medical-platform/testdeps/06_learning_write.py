"""Only the server grader supplies assessed data to persistence."""
from importlib import import_module

persist = import_module("06_learning_repository").persist


def submit(sessions, catalog, claims, body):
    return persist(sessions.repo, claims, lambda: catalog.grade(claims[0], claims[2], body))
