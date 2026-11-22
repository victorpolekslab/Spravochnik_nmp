"""Boot real loopback WSGI workers and verify browser writes against YDB."""
from importlib import import_module
import os
from pathlib import Path
import subprocess
import unittest

mp = import_module("074_test_processes")
ROOT = Path(__file__).resolve().parent

class FullE2E(mp.MultiProcess):
    test_workers_share_refresh_restart_and_revoke = None
    test_ydb_transport_failure_and_recovery_across_workers = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mp.base.YdbTest.pool.execute_with_retries(
            "ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS answers_digest String;")

    def test_browser_learning_and_isolation(self):
        fixture = self.fixture
        second, second_uid = fixture.make_account()
        for uid in (fixture.uid, second_uid):
            for permission in ("app:use","learning:view","learning:submit"):
                fixture.grant_fixture(uid,"nmp",permission)
        self.env.update(MEDICAL_PILOT_LEARNING="1", MEDICAL_PILOT_WEB_ROOT=str(
            ROOT.parents[1]/"android/app/src/main/assets/www"))
        _,a = self.worker()
        _,b = self.worker()
        subprocess.run(["node", str(ROOT/"075_e2e.cjs")], check=True, timeout=60,
            env=dict(os.environ, MP_A=str(a), MP_B=str(b), MP_EMAIL=fixture.email,
                     MP_SECOND=second, MP_PASSWORD=mp.base.PW))
        def verify(tx):
            key=dict(uid=(fixture.uid,"Utf8"))
            attempts=fixture.s.repo.query(tx, """SELECT score, max_score, passed FROM test_attempts
                 WHERE user_id=$uid AND app_id='nmp' AND test_id='quiz';""",**key)
            progress=fixture.s.repo.query(tx, """SELECT status FROM learning_progress
                 WHERE user_id=$uid AND app_id='nmp' AND course_id='course' AND item_id='test:quiz';""",**key)
            self.assertEqual([(x.score,x.max_score,x.passed) for x in attempts],[(2,2,True)])
            self.assertEqual([x.status for x in progress],["completed"])
            print("YDB readback: test_attempts count=1 score=2 max_score=2 passed=true; learning_progress status=completed")
        fixture.s.repo.transaction(verify)
