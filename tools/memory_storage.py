"""Where built-in memory (MEMORY.md / USER.md) is kept: ``memory.storage`` in config.yaml (FORK.md).

* ``local`` (the default): the profile's ``memories/`` folder only, as upstream Hermes keeps it.
* ``gcs``: a Google Cloud Storage bucket (``tools/memory_storage_gcs.py``).
* ``s3``: an S3-compatible bucket — MinIO, AWS S3, Cloudflare R2 (``tools/memory_storage_s3.py``).

With a bucket, the bucket holds the truth and the local files are a cache the rest of Hermes keeps
reading. ``MemoryStore`` pulls the bucket copy before it reads, and writes the bucket with a
conditional write (generation / ETag match) before it writes the local file; a write that lost a race
to another writer raises :class:`MemoryStorageConflict` and is re-applied to the newer copy. Each
profile's objects live under ``<prefix><profile>/memories/``, keeping the folders
``memory.sharing`` gives each user (``users/<platform>/<id>/``).

Secrets never come from config.yaml: S3 reads ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` (and
``AWS_SESSION_TOKEN``); GCS uses the metadata server (GKE workload identity, GCE) or the service-account
key file named by ``GOOGLE_APPLICATION_CREDENTIALS``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)

BACKENDS = ("local", "gcs", "s3")
_VERSION_SUFFIX = ".storage-version"


class MemoryStorageError(Exception):
    """The bucket could not be read or written (unreachable, refused, misconfigured)."""


class MemoryStorageConflict(MemoryStorageError):
    """A conditional write lost: another writer changed the object since it was read."""


@dataclass(frozen=True)
class RemoteObject:
    data: bytes
    version: str  # GCS generation / S3 ETag: what the next conditional write must match


class RemoteStore(Protocol):
    def get(self, key: str) -> Optional[RemoteObject]:
        """The object, or None when it does not exist."""

    def put(self, key: str, data: bytes, *, if_version: Optional[str]) -> str:
        """Write only if the object is still at ``if_version`` (``None``: only if it does not exist);
        return the new version. Raises :class:`MemoryStorageConflict` when the precondition fails."""

    def delete(self, key: str) -> None:
        """Delete the object; deleting a missing object is not an error."""


@dataclass(frozen=True)
class StorageSettings:
    backend: str = "local"
    bucket: str = ""
    prefix: str = ""
    endpoint_url: str = ""
    region: str = "us-east-1"


def storage_settings(mem_config: Optional[dict[str, Any]]) -> StorageSettings:
    """The ``memory.storage`` section, validated. Raises ``ValueError`` on an unusable setting so a
    misconfigured bucket is never mistaken for local storage."""
    raw = (mem_config or {}).get("storage") or {}
    if not isinstance(raw, dict):
        raise ValueError("memory.storage must be a mapping")
    backend = str(raw.get("backend") or "local").strip().lower()
    if backend not in BACKENDS:
        raise ValueError(f"memory.storage.backend must be one of {', '.join(BACKENDS)}, not {backend!r}")
    settings = StorageSettings(
        backend=backend, bucket=str(raw.get("bucket") or "").strip(), prefix=str(raw.get("prefix") or "").strip(),
        endpoint_url=str(raw.get("endpoint_url") or "").strip().rstrip("/"),
        region=str(raw.get("region") or "us-east-1").strip())
    if backend != "local" and not settings.bucket:
        raise ValueError(f"memory.storage.backend is {backend!r} but memory.storage.bucket is empty")
    return settings


def build_remote(settings: StorageSettings) -> Optional[RemoteStore]:
    if settings.backend == "gcs":
        from tools.memory_storage_gcs import GCSStore
        return GCSStore(settings.bucket, endpoint_url=settings.endpoint_url)
    if settings.backend == "s3":
        from tools.memory_storage_s3 import S3Store
        return S3Store(settings.bucket, endpoint_url=settings.endpoint_url, region=settings.region)
    return None


def _profile_namespace() -> str:
    from hermes_constants import get_hermes_home, profile_name_for_home
    return profile_name_for_home(get_hermes_home()) or "default"


def _memory_relpath(path: Path) -> str:
    """``path`` relative to the profile's memories/ folder: ``MEMORY.md``, or ``users/<platform>/<id>/USER.md``
    under ``memory.sharing`` (tools/memory_sharing.py). Raises for a path outside it rather than let two
    owners' files share one object."""
    from tools import memory_tool
    root = memory_tool.get_memory_dir()
    for candidate, base in ((path, root), (path.resolve(), root.resolve())):
        try:
            return candidate.relative_to(base).as_posix()
        except ValueError:
            continue
    raise ValueError(f"{path} is not under {root}")


class MemoryMirror:
    """Keeps one profile's memory files in step with a bucket (see the module docstring).

    Each local file has a ``.<name>.storage-version`` sidecar holding the bucket version it mirrors.
    A missing object with a sidecar was deleted in the bucket (the local copy goes too); a missing
    object without one has never been synced, so an existing local file is uploaded (migration)."""

    def __init__(self, remote: RemoteStore, prefix: str = "", namespace: Optional[str] = None):
        self._remote = remote
        self._prefix = prefix if not prefix or prefix.endswith("/") else prefix + "/"
        self._namespace = namespace

    def key_for(self, path: Path) -> str:
        return f"{self._prefix}{self._namespace or _profile_namespace()}/memories/{_memory_relpath(path)}"

    @staticmethod
    def _version_file(path: Path) -> Path:
        return path.with_name(f".{path.name}{_VERSION_SUFFIX}")

    def _known_version(self, path: Path) -> Optional[str]:
        try:
            return self._version_file(path).read_text(encoding="utf-8-sig").strip() or None
        except OSError:
            return None

    def _remember(self, path: Path, version: Optional[str]) -> None:
        from utils import atomic_write_text
        marker = self._version_file(path)
        if version is None:
            marker.unlink(missing_ok=True)
        else:
            atomic_write_text(marker, version, tmp_prefix=".mem_")

    def pull(self, path: Path) -> Optional[str]:
        """Refresh ``path`` from the bucket; return the version a write must match (None: no object).
        Callers hold the file's lock."""
        from utils import atomic_write_text
        obj = self._get(path)
        if obj is None:
            if self._known_version(path) is not None:  # deleted in the bucket since the last sync
                path.unlink(missing_ok=True)
                self._remember(path, None)
                return None
            if path.exists():  # never synced: this local memory moves to the bucket
                try:
                    version = self.push(path, path.read_bytes(), None)
                except MemoryStorageConflict:  # created meanwhile by another writer: take theirs
                    return self.pull(path)
                return version
            return None
        if not path.exists() or path.read_bytes() != obj.data:
            from hermes_constants import mkdir_under_hermes_home
            mkdir_under_hermes_home(path.parent)
            atomic_write_text(path, obj.data.decode("utf-8"), tmp_prefix=".mem_")
        self._remember(path, obj.version)
        return obj.version

    def push(self, path: Path, data: bytes, if_version: Optional[str]) -> str:
        """Conditionally write ``data`` as ``path``'s object; record and return the new version."""
        version = self._call(self._remote.put, self.key_for(path), data, if_version=if_version)
        self._remember(path, version)
        return version

    def delete(self, path: Path) -> None:
        self._call(self._remote.delete, self.key_for(path))
        self._remember(path, None)

    def _get(self, path: Path) -> Optional[RemoteObject]:
        return self._call(self._remote.get, self.key_for(path))

    @staticmethod
    def _call(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except MemoryStorageError:
            raise
        except Exception as exc:  # network, TLS, malformed response: one error type for callers
            raise MemoryStorageError(str(exc)) from exc


def mirror_for(mem_config: Optional[dict[str, Any]]) -> Optional[MemoryMirror]:
    """The mirror ``memory.storage`` asks for, or None for local storage."""
    settings = storage_settings(mem_config)
    remote = build_remote(settings)
    return MemoryMirror(remote, prefix=settings.prefix) if remote is not None else None


def reset_memory_files(paths: list[Path], mem_config: Optional[dict[str, Any]] = None) -> list[str]:
    """Delete memory files everywhere they are kept (bucket first, then the local cache); return the
    names deleted. A reset that only cleared the cache would come back on the next pull."""
    if mem_config is None:
        from tools.memory_tool import get_builtin_memory_config
        mem_config = get_builtin_memory_config()
    mirror = mirror_for(mem_config)
    deleted = []
    for path in paths:
        existed = path.exists()
        if mirror is not None:
            existed = existed or mirror._get(path) is not None
            mirror.delete(path)
        path.unlink(missing_ok=True)
        if existed:
            deleted.append(path.name)
    return deleted
