from importlib import import_module
from io import BytesIO
import json
import os
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
import unittest
from uuid import uuid4

Gateway = import_module("07_pilot_gateway").PilotGateway
integration = import_module("06_test_ydb")
origin = "http://localhost:8766"


def request(app, path, body, *, cookie="", bearer="", site=origin, host="localhost:8766"):
    encoded = json.dumps(body).encode()
    request_env = {"REQUEST_METHOD":"POST","PATH_INFO":path,"HTTP_HOST":host,
                   "HTTP_ORIGIN":site,"REMOTE_ADDR":"127.0.0.1","HTTP_COOKIE":cookie,
                   "HTTP_AUTHORIZATION":"Bearer "+bearer if bearer else "",
                   "CONTENT_TYPE":"application/json","CONTENT_LENGTH":str(len(encoded)),
                   "wsgi.input":BytesIO(encoded)}
    found={}
    def respond(status, headers):
        found["status"]=int(status.split()[0])
        found["headers"]=dict(headers)
    result=json.loads(b"".join(app(request_env,respond)))
    return found["status"],found["headers"],result


@unittest.skipUnless(os.getenv("MEDICAL_YDB_LOCAL_PORT"), "requires dedicated loopback YDB")
class GatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        integration.Integration.setUpClass()
        cls.addClassCleanup(integration.Integration.doClassCleanups)

    def setUp(self):
        self.fixture=integration.Integration("test_concurrent_progress_monotonic")
        self.fixture.setUp()
        self.service=self.fixture.s
        self.gateway=Gateway(self.service,self.fixture.catalog,origin,enable_learning=True, fixture_memory=True,
                             clock=lambda: self.fixture.old.now)
        self.path="/v1/nmp/"
        self.password=integration.stage5.PW

    def login(self, email):
        status,headers,result=request(self.gateway,self.path+"auth/login",{"email":email,"password":self.password})
        self.assertEqual(status,200)
        self.assertNotIn("refresh_token",result)
        self.assertIn("HttpOnly",headers["Set-Cookie"])
        return headers["Set-Cookie"].split(";",1)[0],result

    def test_submit_switch_user_and_replay(self):
        client,session=self.login(self.fixture.old.email)
        body=integration.helpers.payload()
        path=self.path+"learning/attempts"
        def post(cookie,token):
            return request(self.gateway,path,body,cookie=cookie,bearer=token)
        token=session["access_token"]
        self.assertEqual(post(client,token)[0],200)
        self.assertEqual(post(client,token)[2],post(client,token)[2])
        second,uid=self.fixture.old.make_account()
        self.fixture.old.grant_fixture(uid,"nmp","app:use")
        cookie,_=self.login(second)
        self.assertEqual(post(cookie,token)[0],401)
        self.assertEqual(request(self.gateway,path,body,cookie=client,bearer=token,site="https://other.invalid")[0],403)

    def test_two_refreshes_use_same_rotated_pair(self):
        cookie,session=self.login(self.fixture.old.email)
        self.assertEqual(request(self.gateway,self.path+"auth/resume",{},cookie=cookie)[2],session)
        self.fixture.old.now+=301
        identity={key:session[key] for key in ("user_id","session_id")}
        barrier=Barrier(2)
        def refresh(_):
            barrier.wait(6)
            return request(self.gateway,self.path+"auth/refresh",identity,cookie=cookie)
        with ThreadPoolExecutor(2) as pool:
            a,b=list(pool.map(refresh,range(2)))
        self.assertEqual(a[0],200)
        self.assertEqual(a,b)
        self.assertNotEqual(a[2]["access_token"],session["access_token"])
        self.assertEqual(request(self.gateway,self.path+"auth/logout",identity,cookie=cookie)[0],200)
        self.assertEqual(refresh_after_logout(self.gateway,self.path,identity,cookie),401)

    def test_write_disabled_and_loopback_only(self):
        disabled=Gateway(self.service,self.fixture.catalog,origin,fixture_memory=True)
        self.assertEqual(request(disabled,self.path+"learning/attempts",{})[0],503)
        self.assertEqual(request(disabled,self.path+"auth/login",{},host="external.invalid")[0],403)


def refresh_after_logout(gateway,path,identity,cookie):
    return request(gateway,path+"auth/refresh",identity,cookie=cookie)[0]
