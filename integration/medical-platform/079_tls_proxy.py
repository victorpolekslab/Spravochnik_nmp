"""Test-only TLS front end for two real WSGI workers on one exact origin."""
from contextlib import contextmanager
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ssl
from pathlib import Path
from threading import Thread


@contextmanager
def ingress(tls_dir):
    upstream = []

    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def forward(self):
            if self.headers.get("Host") != f"localhost:{self.server.server_port}":
                self.send_error(421)
                return
            if not upstream:
                self.send_error(503)
                return
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 <= size <= 32768:
                self.send_error(413)
                return
            names = ('Host','Origin','Cookie','Content-Type','Authorization')
            headers = {k:self.headers[k] for k in names if k in self.headers}
            index = int(self.path.endswith(("/resume", "/refresh")))
            connection = http.client.HTTPConnection("127.0.0.1", upstream[index], timeout=10)
            try:
                connection.request(self.command, self.path, self.rfile.read(size) if size else None, headers)
                response = connection.getresponse()
                body = response.read()
                self.send_response(response.status)
                for key, value in response.getheaders():
                    if key.lower() not in ('connection','date','server','content-length'):
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            finally:
                connection.close()

        do_GET = do_POST = forward

    with ThreadingHTTPServer(("127.0.0.1",0), Proxy) as server:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        directory = Path(tls_dir)
        ctx.load_cert_chain(directory/"server.pem", directory/"server.key")
        server.socket = ctx.wrap_socket(server.socket,server_side=True)
        thread=Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            yield f"https://localhost:{server.server_port}", upstream
        finally:
            server.shutdown()
            thread.join()
