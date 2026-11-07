"""memory.storage: built-in memory kept in a bucket (GCS, or S3-compatible such as MinIO) — FORK.md.

The bucket holds the truth and the profile's memories/ folder is a cache. Each backend runs against
an in-process fake that enforces that API's documented preconditions: GCS ``ifGenerationMatch``
(0 = must not exist) and S3 ``If-Match`` / ``If-None-Match: *``, both answering 412 when they fail.
The fake S3 also re-derives every request's SigV4 signature from what arrived on the wire.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import itertools
import json
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from tools.memory_storage import MemoryMirror, mirror_for, reset_memory_files, storage_settings
from tools.memory_storage_gcs import GCSStore
from tools.memory_storage_s3 import S3Store, sigv4_headers
from tools.memory_tool_store import ENTRY_DELIMITER, MemoryStore

ACCESS_KEY, SECRET_KEY, BUCKET = "minioadmin", "minio-secret-key", "tuos-memory"


class _Bucket:
    """Objects (key -> (data, version)) plus the knobs the tests turn."""

    def __init__(self):
        self.objects: dict[str, tuple[bytes, str]] = {}
        self._versions = itertools.count(1000)
        self.before_write = None  # called once before the next write is applied (a racing writer)
        self.bearer = None  # GCS: the token every request must carry (None: anonymous)

    def next_version(self) -> str:
        return str(next(self._versions))


def _gcs_handler(bucket: _Bucket, keys: dict):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body=b"", content_type="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self):
            if bucket.bearer is None or self.headers.get("Authorization") == f"Bearer {bucket.bearer}":
                return True
            self._send(401)
            return False

        def _object_key(self, path):
            prefix = f"/storage/v1/b/{BUCKET}/o/"
            return urllib.parse.unquote(path[len(prefix):]) if path.startswith(prefix) else None

        def do_GET(self):
            if not self._authorized():
                return
            parts = urllib.parse.urlsplit(self.path)
            query = dict(urllib.parse.parse_qsl(parts.query))
            key = self._object_key(parts.path)
            if key not in bucket.objects:
                return self._send(404)
            data, generation = bucket.objects[key]
            if query.get("alt") == "media":
                if query.get("generation", generation) != generation:
                    return self._send(404)
                return self._send(200, data, "text/plain")
            self._send(200, json.dumps({"name": key, "generation": generation}).encode())

        def do_POST(self):
            parts = urllib.parse.urlsplit(self.path)
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if parts.path == "/token":  # the OAuth token endpoint a key file names
                return self._token(body)
            if not self._authorized():
                return
            query = dict(urllib.parse.parse_qsl(parts.query))
            if bucket.before_write:
                hook, bucket.before_write = bucket.before_write, None
                hook()
            key, expected = query["name"], query["ifGenerationMatch"]
            current = bucket.objects.get(key, (b"", "0"))[1]
            if expected != current:
                return self._send(412)
            generation = bucket.next_version()
            bucket.objects[key] = (body, generation)
            self._send(200, json.dumps({"name": key, "generation": generation}).encode())

        def do_DELETE(self):
            if not self._authorized():
                return
            key = self._object_key(urllib.parse.urlsplit(self.path).path)
            if bucket.objects.pop(key, None) is None:
                return self._send(404)
            self._send(204)

        def _token(self, body):
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding

            form = dict(urllib.parse.parse_qsl(body.decode()))
            header, claims, signature = form["assertion"].split(".")
            pad = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
            keys["public"].verify(pad(signature), f"{header}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256())
            keys["claims"] = json.loads(pad(claims))
            self._send(200, json.dumps({"access_token": "gcs-token", "expires_in": 3600}).encode())

    return Handler


def _s3_handler(bucket: _Bucket):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body=b"", etag=None):
            self.send_response(code)
            if etag:
                self.send_header("ETag", etag)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _verified(self, body: bytes) -> bool:
            """Re-derive the SigV4 signature from the request as received."""
            auth = self.headers.get("Authorization", "")
            match = re.fullmatch(r"AWS4-HMAC-SHA256 Credential=([^/]+)/(\d{8})/([^/]+)/s3/aws4_request, "
                                 r"SignedHeaders=([^,]+), Signature=([0-9a-f]{64})", auth)
            payload_hash = hashlib.sha256(body).hexdigest()
            if not match or match[1] != ACCESS_KEY or self.headers.get("x-amz-content-sha256") != payload_hash:
                self._send(403)
                return False
            signed = {name: self.headers.get(name, "") for name in match[4].split(";")}
            now = datetime.datetime.strptime(self.headers["x-amz-date"], "%Y%m%dT%H%M%SZ").replace(tzinfo=datetime.UTC)
            expected = sigv4_headers(self.command, f"http://{self.headers['Host']}{self.path}", signed, payload_hash,
                                     access_key=ACCESS_KEY, secret_key=SECRET_KEY, region=match[3], now=now)
            if expected["Authorization"] != auth:
                self._send(403)
                return False
            return True

        def _key(self):
            path = urllib.parse.urlsplit(self.path).path
            assert path.startswith(f"/{BUCKET}/")
            return urllib.parse.unquote(path[len(BUCKET) + 2:])

        def do_GET(self):
            if not self._verified(b""):
                return
            if self._key() not in bucket.objects:
                return self._send(404)
            data, version = bucket.objects[self._key()]
            self._send(200, data, etag=f'"{version}"')

        def do_PUT(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if not self._verified(body):
                return
            if bucket.before_write:
                hook, bucket.before_write = bucket.before_write, None
                hook()
            key = self._key()
            current = bucket.objects.get(key)
            if_match, if_none = self.headers.get("If-Match"), self.headers.get("If-None-Match")
            if (if_none == "*" and current is not None) or (
                    if_match is not None and (current is None or if_match != f'"{current[1]}"')):
                return self._send(412)
            version = bucket.next_version()
            bucket.objects[key] = (body, version)
            self._send(200, etag=f'"{version}"')

        def do_DELETE(self):
            if not self._verified(b""):
                return
            bucket.objects.pop(self._key(), None)
            self._send(204)

    return Handler


@pytest.fixture(params=["gcs", "s3"])
def backend(request, monkeypatch, tmp_path):
    """(kind, bucket, server, remote store, memory config) for each backend."""
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", ACCESS_KEY)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", SECRET_KEY)
    bucket = _Bucket()
    handler = _gcs_handler(bucket, {}) if request.param == "gcs" else _s3_handler(bucket)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    endpoint = f"http://127.0.0.1:{server.server_address[1]}"
    remote = GCSStore(BUCKET, endpoint_url=endpoint) if request.param == "gcs" else S3Store(BUCKET, endpoint_url=endpoint)
    config = {"storage": {"backend": request.param, "bucket": BUCKET, "endpoint_url": endpoint, "prefix": "team"}}
    yield request.param, bucket, server, remote, config
    server.shutdown()
    server.server_close()


def _store(home: Path, remote, monkeypatch) -> MemoryStore:
    monkeypatch.setenv("HERMES_HOME", str(home))
    store = MemoryStore(mirror=MemoryMirror(remote, prefix="team", namespace="agent"))
    store.load_from_disk()
    return store


KEY = "team/agent/memories/MEMORY.md"


def test_a_write_lands_in_the_bucket_and_another_home_reads_it(backend, tmp_path, monkeypatch):
    _, bucket, _, remote, _ = backend
    pod_a = _store(tmp_path / "a", remote, monkeypatch)
    assert pod_a.add("memory", "Deploys go through staging first.")["success"]
    assert bucket.objects[KEY][0] == b"Deploys go through staging first."

    pod_b = _store(tmp_path / "b", remote, monkeypatch)
    assert pod_b.memory_entries == ["Deploys go through staging first."]


def test_a_lost_race_is_reapplied_to_the_newer_copy(backend, tmp_path, monkeypatch):
    _, bucket, _, remote, _ = backend
    pod_a = _store(tmp_path / "a", remote, monkeypatch)
    assert pod_a.add("memory", "first")["success"]

    def other_pod_writes():  # lands between pod A's pull and its conditional write
        bucket.objects[KEY] = (ENTRY_DELIMITER.join(["first", "from pod b"]).encode(), bucket.next_version())

    bucket.before_write = other_pod_writes
    assert pod_a.add("memory", "from pod a")["success"]
    assert bucket.objects[KEY][0].decode().split(ENTRY_DELIMITER) == ["first", "from pod b", "from pod a"]
    assert (tmp_path / "a" / "memories" / "MEMORY.md").read_bytes() == bucket.objects[KEY][0]


def test_existing_local_memory_moves_to_an_empty_bucket(backend, tmp_path, monkeypatch):
    _, bucket, _, remote, _ = backend
    (tmp_path / "a" / "memories").mkdir(parents=True)
    (tmp_path / "a" / "memories" / "MEMORY.md").write_text("kept from before", encoding="utf-8")

    pod_a = _store(tmp_path / "a", remote, monkeypatch)
    assert pod_a.memory_entries == ["kept from before"]
    assert bucket.objects[KEY][0] == b"kept from before"


def test_memory_deleted_in_the_bucket_is_deleted_locally(backend, tmp_path, monkeypatch):
    _, bucket, _, remote, _ = backend
    assert _store(tmp_path / "a", remote, monkeypatch).add("memory", "forget me")["success"]
    del bucket.objects[KEY]

    assert _store(tmp_path / "a", remote, monkeypatch).memory_entries == []
    assert not (tmp_path / "a" / "memories" / "MEMORY.md").exists()


def test_unreachable_bucket_keeps_the_cache_readable_and_refuses_writes(backend, tmp_path, monkeypatch):
    _, _, server, remote, _ = backend
    assert _store(tmp_path / "a", remote, monkeypatch).add("memory", "cached")["success"]
    server.shutdown()
    server.server_close()

    pod_a = _store(tmp_path / "a", remote, monkeypatch)
    assert pod_a.memory_entries == ["cached"]
    result = pod_a.add("memory", "not saved")
    assert result["success"] is False and "nothing was saved" in result["error"]
    assert (tmp_path / "a" / "memories" / "MEMORY.md").read_text(encoding="utf-8") == "cached"


def test_reset_deletes_the_bucket_copy_too(backend, tmp_path, monkeypatch):
    _, bucket, _, _, config = backend
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "a"))
    store = MemoryStore(mirror=mirror_for(config))
    store.load_from_disk()
    assert store.add("memory", "erase me")["success"]
    assert bucket.objects  # under <prefix>/<profile>/memories/

    path = tmp_path / "a" / "memories" / "MEMORY.md"
    assert reset_memory_files([path], config) == ["MEMORY.md"]
    assert not bucket.objects and not path.exists()


def test_gcs_key_file_signs_a_jwt_for_its_token(monkeypatch, tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    keys = {"public": private.public_key()}
    bucket = _Bucket()
    bucket.bearer = "gcs-token"
    server = ThreadingHTTPServer(("127.0.0.1", 0), _gcs_handler(bucket, keys))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    endpoint = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        key_file = tmp_path / "sa.json"
        key_file.write_text(json.dumps({
            "client_email": "tuos@example.iam.gserviceaccount.com", "private_key_id": "k1",
            "token_uri": f"{endpoint}/token",
            "private_key": private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                 serialization.NoEncryption()).decode()}), encoding="utf-8")
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(key_file))

        store = GCSStore(BUCKET, endpoint_url=endpoint)
        version = store.put("k", b"v", if_version=None)
        assert store.get("k").version == version
        assert keys["claims"]["iss"] == "tuos@example.iam.gserviceaccount.com"
        assert keys["claims"]["scope"].endswith("devstorage.read_write")
    finally:
        server.shutdown()
        server.server_close()


def test_sigv4_matches_the_aws_documented_example():
    """AWS's published GET Object example (Signature Version 4, single-chunk payload)."""
    signed = {"host": "examplebucket.s3.amazonaws.com", "range": "bytes=0-9",
              "x-amz-content-sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
              "x-amz-date": "20130524T000000Z"}
    auth = sigv4_headers("GET", "https://examplebucket.s3.amazonaws.com/test.txt", signed,
                         signed["x-amz-content-sha256"], access_key="AKIAIOSFODNN7EXAMPLE",
                         secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", region="us-east-1",
                         now=datetime.datetime(2013, 5, 24, tzinfo=datetime.UTC))["Authorization"]
    assert auth.endswith("Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41")


@pytest.mark.parametrize(("section", "message"), [
    ({"backend": "dropbox"}, "must be one of"),
    ({"backend": "gcs"}, "bucket is empty"),
    ({"backend": "s3", "bucket": ""}, "bucket is empty"),
])
def test_unusable_settings_are_refused(section, message):
    with pytest.raises(ValueError, match=message):
        storage_settings({"storage": section})


def test_local_is_the_default_and_has_no_mirror():
    assert storage_settings({}).backend == "local"
    assert mirror_for({}) is None


def test_misconfigured_storage_turns_memory_off_instead_of_writing_locally(tmp_path, monkeypatch):
    """A bucket backend that cannot start must not leave a local-only store the bucket would undo."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    (tmp_path / "config.yaml").write_text(
        "memory:\n  storage:\n    backend: s3\n    bucket: tuos-memory\n    endpoint_url: http://127.0.0.1:9\n",
        encoding="utf-8")

    from tools.memory_tool import load_on_disk_store

    store = load_on_disk_store()
    assert not store.target_enabled("memory") and not store.target_enabled("user")
