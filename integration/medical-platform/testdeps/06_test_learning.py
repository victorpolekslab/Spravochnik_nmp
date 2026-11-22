import copy
from importlib import import_module
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from uuid import uuid4

grader = import_module("06_learning_grader")
API = import_module("06_learning_api").LearningAPI

def fixture():
    return {"tests": [
        {"app":"nmp", "test_id":"quiz", "version":version, "course_id":"course",
         "title":"Practice", "min_correct":2, "questions":[
             {"id":"q1","prompt":"one","options":["a","b"],"correct":first},
             {"id":"q2","prompt":"two","options":["a","b"],"correct":0}]}
        for version,first in [("v1",0),("v2",1)]
    ]}

def payload(version="v1", answers=(0,0)):
    return {"test_id":"quiz","test_version":version,"attempt_id":str(uuid4()),
            "answers":[{"question_id":f"q{i}","choice":v} for i,v in enumerate(answers,1)]}

def request(api, method, path, token, data=None, query="", raw=None):
    body = raw if raw is not None else (json.dumps(data).encode() if data is not None else b"")
    env = {"REQUEST_METHOD":method,"PATH_INFO":path,"QUERY_STRING":query,
           "HTTP_AUTHORIZATION":"Bearer "+token,"wsgi.input":BytesIO(body),
           "CONTENT_LENGTH":str(len(body)),"CONTENT_TYPE":"application/json"}
    status = []
    body = b"".join(api(env, lambda s, h: status.append(int(s.split()[0]))))
    return status[0],json.loads(body)

class Tests(unittest.TestCase):
    def setUp(self):
        self.catalog = grader.Catalog(fixture(), b"F"*32)

    def test_catalog_export(self):
        parsed = json.loads(Path(__file__).with_name("06_catalog_nmp.json").read_text())
        real = grader.Catalog(parsed,b"F"*32)
        self.assertEqual(len(real.current),32)
        self.assertEqual(len(real.get("nmp","course:gbn").questions),6)
        self.assertNotIn("correct",real.get("nmp","course:gbn").public()["questions"][0])

    def test_correct_wrong_and_version_archive(self):
        self.assertTrue(self.catalog.grade("u","nmp",payload()).passed)
        self.assertEqual(self.catalog.grade("u","nmp",payload(answers=(1,1))).score,0)
        self.assertEqual(self.catalog.grade("u","nmp",payload("v2")).score,1)
        self.assertEqual(self.catalog.get("nmp","quiz").version,"v2")

    def test_duplicate_partial_unknown(self):
        for mode in ("duplicate","partial","unknown","boolean"):
            with self.subTest(mode=mode), self.assertRaises(grader.LearningError):
                body=payload()
                if mode=="duplicate": body["answers"][1]["question_id"]="q1"
                if mode=="partial": body["answers"].pop()
                if mode=="unknown": body["answers"][1]["question_id"]="missing"
                if mode=="boolean": body["answers"][1]["choice"]=True
                self.catalog.grade("u","nmp",body)

    def test_unknown_test_and_version(self):
        for field,value,status in [("test_id","missing",404),("test_version","v9",409)]:
            body=payload(); body[field]=value
            with self.assertRaises(grader.LearningError) as exc:
                self.catalog.grade("u","nmp",body)
            self.assertEqual(exc.exception.status,status)

    def test_fingerprint_order_and_same_score(self):
        body=payload(answers=(0,1))
        original=self.catalog.grade("u","nmp",body)
        revised=copy.deepcopy(body)
        revised["answers"].reverse()
        self.assertEqual(self.catalog.grade("u","nmp",revised).digest,original.digest)
        for answer in revised["answers"]:
            answer["choice"]=1-answer["choice"]
        changed=self.catalog.grade("u","nmp",revised)
        self.assertEqual(changed.score,original.score)
        self.assertNotEqual(changed.digest,original.digest)

    def test_untrusted_fields_and_http_bounds(self):
        sessions=SimpleNamespace(claims=lambda token,app: ("u","s",app),
                                 repo=SimpleNamespace(check=lambda *args: None,
                                     authorize=lambda *args: None,
                                     transaction=lambda fn, **kw: fn(None)))
        api=API(sessions,self.catalog)
        url="/v1/nmp/learning/attempts"
        for field in ("score","passed","user_id","app_id"):
            body=payload(); body[field]=0
            self.assertEqual(request(api,"POST",url,"t",body)[0],400)
        self.assertEqual(request(api,"POST",url,"t",raw=b" "*32769)[0],413)
        self.assertEqual(request(api,"POST",url,"t",raw=b'{"answers":[],"answers":[]}')[0],400)
        public=request(api,"GET","/v1/nmp/learning/tests/quiz","t")[1]
        self.assertNotIn("correct",str(public))

    def test_offline_retry_policy(self):
        decide=import_module("06_offline_sync").next_action
        self.assertEqual(decide(200,matches_ack=True),"delete_confirmed")
        for code in (None,200,408,429,503):
            self.assertEqual(decide(code),"retry_same_payload")
            self.assertEqual(decide(code,retries=5),"pause_retry_budget")
        self.assertEqual(decide(401),"pause_for_auth")
        self.assertEqual(decide(403),"pause_for_permission")
        self.assertEqual(decide(409,"TEST_VERSION_UNAVAILABLE"),"retake")
        self.assertEqual(decide(409,"ATTEMPT_CONFLICT"),"needs_review")
