"""Backend-only immutable single-choice catalog and verifier."""
from dataclasses import dataclass
from hashlib import sha256
import hmac
from importlib import import_module
import json
import re
from types import MappingProxyType
from uuid import UUID


class LearningError(import_module("05_auth_sessions").AuthError):
    pass


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9:_-]{1,128}", value) is not None


def uuid4_id(value):
    if not isinstance(value, str) or len(value) != 36:
        return False
    try:
        parsed = UUID(value)
        return parsed.version == 4 and str(parsed) == value
    except ValueError:
        return False


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    options: tuple[str, ...]
    correct: int


@dataclass(frozen=True)
class Test:
    app: str
    test_id: str
    version: str
    course_id: str
    title: str
    min_correct: int
    questions: tuple[Question, ...]

    def public(self):
        return {"test_id": self.test_id, "test_version": self.version,
                "course_id": self.course_id, "title": self.title,
                "questions": [{"question_id": q.id, "prompt": q.prompt, "options": list(q.options)}
                              for q in self.questions]}


@dataclass(frozen=True)
class Grade:
    test: Test
    attempt_id: str
    score: int
    passed: bool
    digest: bytes
    historical_digests: tuple[bytes, ...] = ()

    def matches_digest(self, stored):
        if stored is None:
            return False
        # Evaluate all configured candidates regardless of which key matches.
        matches = [hmac.compare_digest(stored, candidate)
                   for candidate in (self.digest, *self.historical_digests)]
        return any(matches)


class Catalog:
    def __init__(self, document, key, *, historical_keys=()):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("An independent catalog fingerprint key is required")
        retired = tuple(historical_keys)
        if (len(retired) > 3 or any(not isinstance(k, bytes) or len(k) != 32 for k in retired)
                or len(set((key, *retired))) != len(retired) + 1):
            raise ValueError("At most three distinct retired digest keys are allowed")
        self._keys = (key, *retired)
        tests = {}
        current = {}
        for spec in document["tests"]:
            questions = tuple(Question(q["id"], q["prompt"], tuple(q["options"]), q["correct"])
                              for q in spec["questions"])
            app, tid, version, course = (spec[k] for k in ("app", "test_id", "version", "course_id"))
            test = Test(app, tid, version, course, spec["title"], spec["min_correct"], questions)
            k = app, tid, version
            if (app not in ("nmp", "terapevt") or not all(map(valid_id, (tid, version, course)))
                    or k in tests or not isinstance(test.title, str) or not 1 <= len(test.title) <= 300
                    or type(test.min_correct) is not int
                    or not 1 <= test.min_correct <= len(questions) <= 150
                    or len({q.id for q in questions}) != len(questions)
                    or not all(valid_id(q.id) and isinstance(q.prompt, str) and 1 <= len(q.prompt) <= 2000
                               and 2 <= len(q.options) <= 12 and all(
                                   isinstance(o, str) and 1 <= len(o) <= 1000 for o in q.options)
                               and type(q.correct) is int and 0 <= q.correct < len(q.options)
                               for q in questions)):
                raise ValueError("Invalid or duplicate catalog definition")
            existing = current.get((app, tid))
            if existing and existing.course_id != course:
                raise ValueError("Test course must stay stable across versions")
            tests[k] = test
            current[app, tid] = test  # Document order is oldest to newest.
        self.tests = MappingProxyType(tests)
        self.current = MappingProxyType(current)

    def get(self, app, tid, version=None):
        if (app, tid) not in self.current:
            raise LearningError(404, "TEST_NOT_FOUND")
        if version is None:
            return self.current[app, tid]
        test = self.tests.get((app, tid, version))
        if test is None:
            raise LearningError(409, "TEST_VERSION_UNAVAILABLE")
        return test

    def grade(self, uid, app, payload):
        if not isinstance(payload, dict) or set(payload) != {"test_id", "test_version", "attempt_id", "answers"}:
            raise LearningError(400, "INVALID_ATTEMPT")
        tid, version, aid, answers = (payload[k] for k in ("test_id", "test_version", "attempt_id", "answers"))
        if not valid_id(tid) or not valid_id(version) or not uuid4_id(aid) or not isinstance(answers, list):
            raise LearningError(400, "INVALID_ATTEMPT")
        test = self.get(app, tid, version)
        questions = {q.id: q for q in test.questions}
        if len(answers) != len(questions):
            raise LearningError(400, "INVALID_ANSWERS")
        choices = {}
        for answer in answers:
            if not isinstance(answer, dict) or set(answer) != {"question_id", "choice"}:
                raise LearningError(400, "INVALID_ANSWERS")
            qid, choice = answer["question_id"], answer["choice"]
            if (not valid_id(qid) or qid not in questions or qid in choices
                    or type(choice) is not int or not 0 <= choice < len(questions[qid].options)):
                raise LearningError(400, "INVALID_ANSWERS")
            choices[qid] = choice
        score = sum(choices[q.id] == q.correct for q in test.questions)
        canonical = json.dumps([uid, app, tid, version, aid, sorted(choices.items())],
                               separators=(",", ":"), ensure_ascii=True).encode("ascii")
        current, *historical = [hmac.digest(key, b"learning-attempt-v1\0" + canonical, sha256)
                                for key in self._keys]
        return Grade(test, aid, score, score >= test.min_correct, current, tuple(historical))
