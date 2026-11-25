"""Configuration and lifetime of the dedicated pilot YDB session pool."""
from contextlib import contextmanager
from dataclasses import dataclass
import re
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Database:
    endpoint: str
    path: str
    managed: bool

    @classmethod
    def from_env(cls, env):
        mode = env.get("MEDICAL_YDB_MODE", "local")
        if mode == "local":
            port = int(env["MEDICAL_YDB_LOCAL_PORT"])
            if not 1 <= port <= 65535:
                raise ValueError("Invalid local YDB port")
            return cls(f"grpc://localhost:{port}", "/local", False)
        if mode != "managed-test" or env.get("MEDICAL_ENVIRONMENT") != "isolated-test":
            raise ValueError("Only local or isolated managed test YDB is supported")
        endpoint, path = env["MEDICAL_YDB_ENDPOINT"], env["MEDICAL_YDB_DATABASE"]
        url = urlsplit(endpoint)
        if (url.scheme != "grpcs" or not url.hostname or url.username or url.password
                or not re.fullmatch(r"[a-zA-Z0-9.-]+", url.hostname)
                or url.path or url.query or url.fragment or not url.port):
            raise ValueError("Managed YDB requires a TLS endpoint")
        if not re.fullmatch(r"(?:/[a-zA-Z0-9_-]+)+/medical-platform-pilot", path):
            raise ValueError("Unexpected dedicated pilot database path")
        return cls(endpoint, path, True)

    @contextmanager
    def pool(self, sdk, metadata_factory):
        try:
            credentials = metadata_factory() if self.managed else sdk.AnonymousCredentials()
            with sdk.Driver(endpoint=self.endpoint, database=self.path, credentials=credentials) as driver:
                driver.wait(timeout=10, fail_fast=True)
                with sdk.QuerySessionPool(driver) as pool:
                    yield pool
        except Exception:
            raise RuntimeError("Pilot YDB unavailable") from None
