import importlib
import unittest
from types import SimpleNamespace

Database = importlib.import_module("076_ydb").Database

class DatabaseTest(unittest.TestCase):
    def test_local(self):
        self.assertEqual(Database.from_env({"MEDICAL_YDB_LOCAL_PORT":"2136"}),
                         Database("grpc://localhost:2136","/local",False))

    def test_managed_rejects_plaintext_and_wrong_database(self):
        env = dict(MEDICAL_YDB_MODE="managed-test",MEDICAL_ENVIRONMENT="isolated-test",
                   MEDICAL_YDB_ENDPOINT="grpcs://ydb.example.test:2135",
                   MEDICAL_YDB_DATABASE="/test/folder/medical-platform-pilot")
        self.assertTrue(Database.from_env(env).managed)
        for key,value in [("MEDICAL_YDB_ENDPOINT","grpc://ydb.example.test:2135"),
                          ("MEDICAL_YDB_DATABASE","/test/folder/medical-platform-db"),
                          ("MEDICAL_ENVIRONMENT","production")]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                Database.from_env(dict(env, **{key:value}))

    def test_driver_closes_on_wait_failure_and_error_is_neutral(self):
        events=[]
        class Driver:
            def __init__(self, **opts): self.opts=opts
            def __enter__(self): return self
            def __exit__(self,*_): events.append("closed")
            def wait(self, **_): raise OSError("sensitive SDK diagnostics")
        sdk=SimpleNamespace(Driver=Driver)
        with self.assertRaisesRegex(RuntimeError,"^Pilot YDB unavailable$"):
            with Database("grpcs://example.test:2135","/test/medical-platform-pilot",True).pool(sdk,object):
                self.fail("must fail closed")
        self.assertEqual(events,["closed"])
