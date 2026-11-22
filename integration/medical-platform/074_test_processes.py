"""Two HTTP worker subprocesses with an isolated /local backend."""
import base64
from importlib import import_module
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

base = import_module("05_test_ydb")
catalog = import_module("06_test_learning")


@unittest.skipUnless(os.getenv("MEDICAL_YDB_LOCAL_PORT"), "requires disposable loopback YDB")
class MultiProcess(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.YdbTest.setUpClass()
        cls.addClassCleanup(base.YdbTest.doClassCleanups)
        ddl = Path(__file__).with_name("072_browser_sessions.sql").read_text()
        base.YdbTest.pool.execute_with_retries(ddl.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1))

    def setUp(self):
        self.fixture = base.YdbTest("test_login_sessions_and_cross_app")
        self.fixture.setUp()
        path = Path(self.enterContext(tempfile.TemporaryDirectory())) / "catalog.json"
        path.write_text(json.dumps(catalog.fixture()))
        self.env = dict(os.environ, MEDICAL_PILOT_CATALOG=str(path))
        for label, value in zip(("ACCESS","REFRESH","REGISTRATION","RECOVERY","DIGEST"), b"ABCDE"):
            self.env["MEDICAL_PILOT_"+label+"_KEY"] = base64.b64encode(bytes([value])*32).decode()

    def worker(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        command = [sys.executable, "-u", str(Path(__file__).with_name("07_run_pilot.py"))]
        child = subprocess.Popen(command, env=dict(self.env, MEDICAL_PILOT_PORT=str(port)),
                                 stdout=subprocess.DEVNULL)
        self.addCleanup(self.stop, child)
        print(f"worker pid={child.pid} loopback={port} command={command[-1]}", flush=True)
        deadline = time.monotonic()+15
        while time.monotonic()<deadline:
            if child.poll() is not None:
                self.fail(f"worker exited with {child.returncode}")
            try:
                with socket.create_connection(("127.0.0.1",port), timeout=0.2):
                    return child,port
            except OSError:
                time.sleep(0.05)
        self.fail("worker startup timeout")

    @staticmethod
    def stop(child):
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=10)

    @staticmethod
    def post(port, action, body, cookie=""):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        origin = f"http://localhost:{port}"
        try:
            conn.request("POST", "/v1/nmp/auth/"+action, json.dumps(body),
                {"Host":f"localhost:{port}", "Origin":origin,"Content-Type":"application/json","Cookie":cookie})
            response = conn.getresponse()
            return response.status, json.loads(response.read()), (response.getheader("Set-Cookie") or "").split(";")[0]
        finally:
            conn.close()

    def test_workers_share_refresh_restart_and_revoke(self):
        child,a = self.worker()
        _,b = self.worker()
        code,data,cookie = self.post(a,"login",dict(email=self.fixture.email,password=base.PW))
        self.assertEqual(code,200)
        self.assertTrue(self.post(b,"resume",{},cookie)[:2] == (200,data), "other worker must see the same session")
        time.sleep(1.1)
        self.fixture.s.repo.transaction(lambda tx:self.fixture.s.repo.query(tx,
            "UPDATE browser_sessions SET issued_at_seconds=1 WHERE app_id='nmp' AND session_id=$sid;",
            sid=(data["session_id"],"Utf8")),write=True)
        identity = {key:data[key] for key in ("session_id","user_id")}
        left,right = self.fixture.concurrent(lambda i:self.post([a,b][i],"refresh",identity,cookie))
        self.assertTrue(left[:2] == right[:2], "concurrent refresh must converge")
        self.assertEqual(left[0],200)
        self.assertTrue(left[1]["access_token"] != data["access_token"], "expired access must be replaced")
        self.stop(child)
        _,restarted = self.worker()
        self.assertTrue(self.post(restarted,"resume",{},cookie)[:2] == left[:2], "restarted worker must resume session")
        self.assertEqual(self.post(b,"logout",identity,cookie)[0],200)
        self.assertEqual(self.post(restarted,"resume",{},cookie)[0],401)
        code,data,cookie = self.post(b,"login",dict(email=self.fixture.email,password=base.PW))
        self.assertEqual(code,200)
        self.fixture.s.repo.transaction(lambda tx:self.fixture.s.repo.query(tx,
            "UPDATE user_access SET revoked_at=CurrentUtcTimestamp() WHERE user_id=$uid AND app_id='nmp' AND permission='app:use';",
            uid=(self.fixture.uid,"Utf8")),write=True)
        self.assertEqual(self.post(restarted,"resume",{},cookie)[0],403)
        self.fixture.grant_fixture(self.fixture.uid,"nmp","app:use")
        self.fixture.s.repo.transaction(lambda tx:self.fixture.s.repo.query(tx,
            "UPDATE user_access SET revoked_at=NULL WHERE user_id=$uid AND app_id='nmp' AND permission='app:use';",
            uid=(self.fixture.uid,"Utf8")),write=True)
        self.fixture.s.sessions.revoke_all(data["access_token"],"nmp")
        self.assertEqual(self.post(restarted,"resume",{},cookie)[0],401)
