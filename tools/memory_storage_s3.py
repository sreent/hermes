"""S3-compatible backend for built-in memory (``memory.storage.backend: s3``): MinIO, AWS S3, R2.

Standard library HTTP with AWS Signature Version 4, path-style URLs (``<endpoint>/<bucket>/<key>``,
what MinIO serves). Writes are conditional: ``If-Match: <etag>``, or ``If-None-Match: *`` for an
object that must not exist yet; a 412 (or AWS's 409 for a concurrent conditional write) is a lost race.
The server must support conditional PUTs.

Credentials come from ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` and, for temporary
credentials, ``AWS_SESSION_TOKEN`` — the profile's ``.env`` or the process environment. ``memory.storage.endpoint_url`` is required for MinIO
(e.g. ``http://minio.minio.svc:9000``); without it the AWS endpoint for ``region`` is used.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from tools.memory_storage import MemoryStorageConflict, MemoryStorageError, RemoteObject

_TIMEOUT = 15
_UNRESERVED = "-_.~"


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def sigv4_headers(method: str, url: str, signed: dict[str, str], payload_hash: str, *, access_key: str,
                  secret_key: str, region: str, now: datetime.datetime, service: str = "s3") -> dict[str, str]:
    """The ``Authorization`` header for one request. ``signed`` holds every header to sign (lowercase
    names, ``host`` and ``x-amz-*`` included); ``url``'s path must already be percent-encoded."""
    parts = urllib.parse.urlsplit(url)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    scope = f"{amz_date[:8]}/{region}/{service}/aws4_request"
    query = "&".join(f"{urllib.parse.quote(k, safe=_UNRESERVED)}={urllib.parse.quote(v, safe=_UNRESERVED)}"
                     for k, v in sorted(urllib.parse.parse_qsl(parts.query, keep_blank_values=True)))
    names = sorted(signed)
    canonical = "\n".join([
        method, parts.path or "/", query,
        "".join(f"{name}:{' '.join(signed[name].split())}\n" for name in names),
        ";".join(names), payload_hash])
    string_to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope,
                                hashlib.sha256(canonical.encode("utf-8")).hexdigest()])
    key = _hmac(_hmac(_hmac(_hmac(f"AWS4{secret_key}".encode(), amz_date[:8]), region), service),
                "aws4_request")
    signature = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"Authorization": f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
                             f"SignedHeaders={';'.join(names)}, Signature={signature}"}


class S3Store:
    def __init__(self, bucket: str, *, endpoint_url: str = "", region: str = "us-east-1"):
        self._bucket, self._region = bucket, region or "us-east-1"
        self._endpoint = endpoint_url or f"https://s3.{self._region}.amazonaws.com"
        from agent.secret_scope import get_secret_str  # the served profile's .env, not the launch profile's
        self._access_key = get_secret_str("AWS_ACCESS_KEY_ID").strip()
        self._secret_key = get_secret_str("AWS_SECRET_ACCESS_KEY").strip()
        self._session_token = get_secret_str("AWS_SESSION_TOKEN").strip()
        if not (self._access_key and self._secret_key):
            raise MemoryStorageError("memory.storage.backend is s3 but AWS_ACCESS_KEY_ID / "
                                     "AWS_SECRET_ACCESS_KEY are not set")

    def _url(self, key: str) -> str:
        return f"{self._endpoint}/{urllib.parse.quote(self._bucket, safe='')}/{urllib.parse.quote(key, safe='/' + _UNRESERVED)}"

    def _request(self, method: str, key: str, data: bytes = b"", extra: Optional[dict[str, str]] = None):
        url = self._url(key)
        payload_hash = hashlib.sha256(data).hexdigest()
        now = datetime.datetime.now(datetime.UTC)
        signed = {"host": urllib.parse.urlsplit(url).netloc, "x-amz-content-sha256": payload_hash,
                  "x-amz-date": now.strftime("%Y%m%dT%H%M%SZ")}
        if self._session_token:
            signed["x-amz-security-token"] = self._session_token
        headers = {**signed, **sigv4_headers(method, url, signed, payload_hash, access_key=self._access_key,
                                             secret_key=self._secret_key, region=self._region, now=now)}
        headers.pop("host")  # urllib sets Host from the URL; the value signed above is the same
        req = urllib.request.Request(url, data=data if method == "PUT" else None, method=method,
                                     headers={**headers, **(extra or {})})
        return urllib.request.urlopen(req, timeout=_TIMEOUT)

    def get(self, key: str) -> Optional[RemoteObject]:
        try:
            with self._request("GET", key) as resp:
                data = resp.read()
                etag = resp.headers.get("ETag")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise MemoryStorageError(f"S3 read of {key} failed: HTTP {exc.code}") from exc
        if not etag:
            raise MemoryStorageError(f"S3 read of {key} returned no ETag")
        return RemoteObject(data, etag)

    def put(self, key: str, data: bytes, *, if_version: Optional[str]) -> str:
        condition = {"If-Match": if_version} if if_version else {"If-None-Match": "*"}
        try:
            with self._request("PUT", key, data, {**condition, "Content-Type": "text/markdown; charset=utf-8"}) as resp:
                etag = resp.headers.get("ETag")
        except urllib.error.HTTPError as exc:
            if exc.code in (409, 412):
                raise MemoryStorageConflict(f"{key} changed in the bucket since it was read") from exc
            raise MemoryStorageError(f"S3 write of {key} failed: HTTP {exc.code}") from exc
        if not etag:
            raise MemoryStorageError(f"S3 write of {key} returned no ETag")
        return etag

    def delete(self, key: str) -> None:
        try:
            with self._request("DELETE", key):
                pass
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise MemoryStorageError(f"S3 delete of {key} failed: HTTP {exc.code}") from exc
