from importlib import import_module
from io import BytesIO
from threading import Event
from unittest import TestCase

Deadline = import_module("075_deadline").Deadline


class DeadlineTest(TestCase):
    def test_timeout_does_not_release_capacity_before_completion(self):
        entered, release = Event(), Event()
        def work(env, respond):
            entered.set()
            release.wait(2)
            respond("200 OK", [])
            return [b"done"]
        app = Deadline(work, seconds=0.03, workers=1)
        self.addCleanup(app.pool.shutdown)
        self.addCleanup(release.set)
        def call():
            headers=[]
            return b"".join(app({"wsgi.input":BytesIO()}, lambda status,h:headers.append(status)))
        self.assertIn(b"PILOT_DEADLINE",call())
        self.assertTrue(entered.is_set())
        self.assertIn(b"PILOT_BUSY",call())
        release.set()
