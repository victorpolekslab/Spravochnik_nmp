"""Bound API response wait and the number of in-flight backend operations."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from io import BytesIO
import json
from threading import BoundedSemaphore


class Deadline:
    def __init__(self, app, *, seconds=3.0, workers=4):
        self.app, self.seconds = app, seconds
        self.available = BoundedSemaphore(workers)
        self.pool = ThreadPoolExecutor(max_workers=workers)

    @staticmethod
    def error(respond, status, error):
        payload = json.dumps({"error":error}).encode()
        respond(status,[("Content-Type","application/json"),("Cache-Control","no-store"),
                        ("Content-Length",str(len(payload)))])
        return [payload]

    def __call__(self, env, respond):
        if not self.available.acquire(blocking=False):
            return self.error(respond,"503 Service Unavailable","PILOT_BUSY")
        transferred = False
        try:
            length = env.get("CONTENT_LENGTH","") or "0"
            if len(length)>8 or not length.isascii() or not length.isdecimal() or int(length)>32768:
                return self.error(respond,"400 Bad Request","REQUEST_LIMIT")
            snapshot=dict(env, **{"wsgi.input":BytesIO(env["wsgi.input"].read(int(length)))})
            def execute():
                status_headers=[]
                result=self.app(snapshot,lambda status,headers:status_headers.extend((status,headers)))
                return status_headers,list(result)
            future=self.pool.submit(execute)
            future.add_done_callback(lambda _:self.available.release())
            transferred=True
            try:
                status_headers,result=future.result(timeout=self.seconds)
            except TimeoutError:
                return self.error(respond,"503 Service Unavailable","PILOT_DEADLINE")
            respond(*status_headers)
            return result
        finally:
            if not transferred:
                self.available.release()
