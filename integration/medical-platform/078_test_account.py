"""HTTP acceptance using the real local YDB and a private synthetic capture."""
from importlib import import_module
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

process = import_module("074_test_processes")


@unittest.skipUnless(os.getenv("MEDICAL_YDB_LOCAL_PORT"), "requires disposable loopback YDB")
class Lifecycle(process.MultiProcess):
    test_workers_share_refresh_restart_and_revoke = None
    test_ydb_transport_failure_and_recovery_across_workers = None

    def test_register_confirm_reset_revokes_browser(self):
        sink = Path(self.enterContext(TemporaryDirectory()))
        self.env["MEDICAL_PILOT_SYNTHETIC_MAIL_DIR"] = str(sink)
        _, port = self.worker()
        email = uuid4().hex + "@example.invalid"
        def post(action, body, cookie=""):
            return self.post(port, action, body, cookie)
        def captured(kind):
            return json.loads(next(sink.glob(kind+"-*")).read_text())["token"]
        def completion(token, password):
            return dict(token=token,password=password,request_id=str(uuid4()))
        self.assertEqual(post("register",{"email":email})[0],202)
        data = completion(captured("verify"), process.base.PW)
        self.assertEqual(post("confirm",data)[0],200)
        self.assertEqual(post("confirm",data)[0],200)
        self.assertEqual(post("confirm",{**data,"request_id":str(uuid4())})[0],400)
        account = self.fixture.s.repo.account(email)
        self.fixture.grant_fixture(account.user_id,"nmp","app:use")
        status, _, cookie = post("login",{"email":email,"password":process.base.PW})
        self.assertEqual(status,200)
        self.assertEqual(post("forgot",{"email":"missing-"+email})[:2],post("forgot",{"email":email})[:2])
        password = "Synthetic-reset-password-78!"
        data = completion(captured("reset"),password)
        self.assertEqual(post("reset",data)[0],200)
        self.assertEqual(post("resume",{},cookie)[0],401)
        _, second_port = self.worker()
        self.assertEqual(self.post(second_port,"login",{"email":email,"password":password})[0],200)
