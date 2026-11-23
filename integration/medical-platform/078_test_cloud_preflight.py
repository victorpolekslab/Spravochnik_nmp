from copy import deepcopy
from importlib import import_module
import unittest

check = import_module("078_cloud_preflight").checked_info


class CloudGuard(unittest.TestCase):
    def setUp(self):
        self.plan = dict(cloud_id="cloud", folder_id="qa", database_id="db",
                         database_path="/zone/cloud/qa/medical-platform-pilot",
                         endpoint="grpcs://pilot.example.invalid:2135",
                         service_account_sid="qa@as", production_folder_id="prod",
                         environment="isolated-test")
        self.cloud = {"id":"cloud"}
        self.folder = {"id":"qa", "cloud_id":"cloud"}
        self.db = {"id":"db", "folder_id":"qa", "name":"medical-platform-pilot",
                   "endpoint":self.plan["endpoint"]+"?database="+self.plan["database_path"]}

    def test_exact_tuple(self):
        check(self.plan, self.cloud, self.folder, self.db, "qa@as")

    def test_refuse_discrepancies(self):
        for target, key, value in (
            (0,"folder_id","prod"), (0,"environment","production"),
            (0,"database_path","/production"), (0,"service_account_sid","other@as"),
            (0,"endpoint","grpcs://other.example.invalid:2135"), (0,"database_id","wrong"),
            (0,"cloud_id","wrong"), (0,"folder_id","wrong"), (0,"endpoint",""),
            (2,"cloud_id","wrong"), (3,"name","production"),
        ):
            with self.subTest(key=key, value=value):
                args = deepcopy([self.plan,self.cloud,self.folder,self.db,"qa@as"])
                args[target][key] = value
                with self.assertRaises(ValueError):
                    check(*args)

    def test_refuse_missing_parameters(self):
        del self.plan["service_account_sid"]
        with self.assertRaises(ValueError):
            check(self.plan, self.cloud, self.folder, self.db, "qa@as")
