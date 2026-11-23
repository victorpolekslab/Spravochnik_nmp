"""Chromium acceptance test for the client origin gate with a temporary TLS fixture."""
import base64
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
import unittest

HTML = b"""<!doctype html><body data-result="pending">
<script type="module">
import {attachMedicalPilot} from '/072_ui_adapter.mjs';
const enabled = !location.search.includes('off');
const pilot = await attachMedicalPilot({enabled, app:'nmp'});
document.body.dataset.result = pilot ? 'allowed' : 'denied';
pilot?.close();
</script></body>"""


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path.startswith('/?') or self.path == '/':
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML)
        elif self.path == '/pilot/config.json':
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(('{"origins":["https://allowed.test:%d"]}' % self.server.server_port).encode())
        else:
            super().do_GET()


class OriginTest(unittest.TestCase):
    def test_chromium_exact_origin_and_opt_in(self):
        source = Path(os.getenv("PILOT_ADAPTER_SOURCE", Path(__file__).parent))
        with tempfile.TemporaryDirectory() as tmp:
            cert, key = (str(Path(tmp)/name) for name in ("cert.pem", "key.pem"))
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                            "-subj", "/CN=allowed.test", "-addext", "subjectAltName=DNS:allowed.test,DNS:denied.test",
                            "-keyout", key, "-out", cert], check=True, capture_output=True)
            pub = subprocess.check_output(["openssl", "x509", "-pubkey", "-noout", "-in", cert])
            der = subprocess.check_output(["openssl", "pkey", "-pubin", "-outform", "DER"], input=pub)
            pin = base64.b64encode(hashlib.sha256(der).digest()).decode()
            handler = lambda *args: Handler(*args, directory=str(source))
            with ThreadingHTTPServer(("127.0.0.1",0), handler) as https, ThreadingHTTPServer(("127.0.0.1",0), handler) as http:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(cert, key)
                https.socket = ctx.wrap_socket(https.socket, server_side=True)
                for server in (https,http):
                    threading.Thread(target=server.serve_forever, daemon=True).start()
                for i, (url, expected) in enumerate([
                    (f"https://allowed.test:{https.server_port}/", "allowed"),
                    (f"https://denied.test:{https.server_port}/", "denied"),
                    (f"http://allowed.test:{http.server_port}/", "denied"),
                    (f"https://allowed.test:{https.server_port}/?off", "denied"),
                    (f"https://allowed.test:{https.server_port}/", "allowed"),
                ]):
                    with self.subTest(index=i, expected=expected):
                        subprocess.run(["node",str(Path(__file__).with_name("078_https_probe.cjs")),
                                        url, expected, str(Path(tmp)/"profile"), pin],
                                       check=True, timeout=30)
                        print(f"Chromium case {i+1}: {expected}")
                for server in (https,http):
                    server.shutdown()


if __name__ == "__main__":
    unittest.main()
