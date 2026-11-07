"""Google Cloud Storage backend for built-in memory (``memory.storage.backend: gcs``).

Standard library HTTP against the GCS JSON API; generations make every write conditional
(``ifGenerationMatch``, 0 = only if the object does not exist yet).

Credentials, first match wins:
1. ``GOOGLE_APPLICATION_CREDENTIALS`` (the profile's ``.env`` or the process environment): a service-account key file, exchanged for an access token
   with a JWT signed by ``cryptography``;
2. ``memory.storage.endpoint_url`` set (an emulator such as fake-gcs-server): no credentials;
3. the metadata server: GKE workload identity or a GCE service account.
"""

from __future__ import annotations

import base64
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from tools.memory_storage import MemoryStorageConflict, MemoryStorageError, RemoteObject

_API = "https://storage.googleapis.com"
_SCOPE = "https://www.googleapis.com/auth/devstorage.read_write"
_METADATA_TOKEN = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
_TIMEOUT = 15


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class _TokenSource:
    """Cached OAuth access token for the configured credential."""

    def __init__(self, key_file: str, anonymous: bool):
        self._key_file, self._anonymous = key_file, anonymous
        self._token: Optional[str] = None
        self._expires = 0.0
        self._lock = threading.Lock()

    def header(self) -> dict[str, str]:
        if self._anonymous:
            return {}
        with self._lock:
            if self._token is None or time.time() > self._expires - 60:
                self._token, lifetime = self._fetch()
                self._expires = time.time() + lifetime
            return {"Authorization": f"Bearer {self._token}"}

    def _fetch(self) -> tuple[str, float]:
        if self._key_file:
            return self._from_key_file()
        # The metadata server is link-local: never route it through an HTTP(S) proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(_METADATA_TOKEN, headers={"Metadata-Flavor": "Google"})
        with opener.open(req, timeout=_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["access_token"], float(body.get("expires_in", 300))

    def _from_key_file(self) -> tuple[str, float]:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        with open(self._key_file, encoding="utf-8-sig") as fh:
            key = json.load(fh)
        token_uri = key.get("token_uri") or "https://oauth2.googleapis.com/token"
        now = int(time.time())
        header = {"alg": "RS256", "typ": "JWT", **({"kid": key["private_key_id"]} if key.get("private_key_id") else {})}
        claims = {"iss": key["client_email"], "scope": _SCOPE, "aud": token_uri, "iat": now, "exp": now + 3600}
        signing_input = f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(claims).encode())}"
        private_key = serialization.load_pem_private_key(key["private_key"].encode("utf-8"), password=None)
        signature = private_key.sign(signing_input.encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
        form = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                       "assertion": f"{signing_input}.{_b64url(signature)}"}).encode("ascii")
        req = urllib.request.Request(token_uri, data=form, method="POST",
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["access_token"], float(body.get("expires_in", 3600))


class GCSStore:
    def __init__(self, bucket: str, *, endpoint_url: str = ""):
        self._bucket = bucket
        self._endpoint = endpoint_url or _API
        from agent.secret_scope import get_secret_str  # the served profile's .env, not the launch profile's
        key_file = get_secret_str("GOOGLE_APPLICATION_CREDENTIALS").strip()
        self._auth = _TokenSource(key_file, anonymous=bool(endpoint_url) and not key_file)

    def _object_url(self, key: str) -> str:
        return (f"{self._endpoint}/storage/v1/b/{urllib.parse.quote(self._bucket, safe='')}"
                f"/o/{urllib.parse.quote(key, safe='')}")

    def _request(self, method: str, url: str, data: Optional[bytes] = None, headers: Optional[dict] = None):
        req = urllib.request.Request(url, data=data, method=method, headers={**self._auth.header(), **(headers or {})})
        return urllib.request.urlopen(req, timeout=_TIMEOUT)

    def get(self, key: str) -> Optional[RemoteObject]:
        # Metadata first, then the bytes of exactly that generation: the version handed to the next
        # conditional write always matches the data read, even if the object changes in between.
        try:
            with self._request("GET", self._object_url(key)) as resp:
                generation = str(json.loads(resp.read().decode("utf-8"))["generation"])
            with self._request("GET", f"{self._object_url(key)}?alt=media&generation={generation}") as resp:
                data = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:  # missing, or deleted between the two requests
                return None
            raise MemoryStorageError(f"GCS read of {key} failed: HTTP {exc.code}") from exc
        return RemoteObject(data, generation)

    def put(self, key: str, data: bytes, *, if_version: Optional[str]) -> str:
        query = urllib.parse.urlencode({"uploadType": "media", "name": key, "ifGenerationMatch": if_version or "0"})
        url = f"{self._endpoint}/upload/storage/v1/b/{urllib.parse.quote(self._bucket, safe='')}/o?{query}"
        try:
            with self._request("POST", url, data, {"Content-Type": "text/markdown; charset=utf-8"}) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 412:
                raise MemoryStorageConflict(f"{key} changed in the bucket since it was read") from exc
            raise MemoryStorageError(f"GCS write of {key} failed: HTTP {exc.code}") from exc
        return str(body["generation"])

    def delete(self, key: str) -> None:
        try:
            with self._request("DELETE", self._object_url(key)):
                pass
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise MemoryStorageError(f"GCS delete of {key} failed: HTTP {exc.code}") from exc
