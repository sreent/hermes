"""Whose built-in memory a conversation reads and writes: ``memory.sharing`` in a profile's
config.yaml (FORK.md, "Per-agent memory sharing").

* ``shared`` (the default): one MEMORY.md and USER.md for the agent, whoever is talking to it.
* ``per_user``: every user has their own MEMORY.md and USER.md.
* ``hybrid``: MEMORY.md (the agent's notes on its work and environment) is shared; USER.md (who the
  user is) is each user's own.

A conversation's owner decides which files it gets:

* nobody — the agent's operator on the CLI, TUI or desktop, a cron job the operator made, anything
  that carries no messaging identity: the profile's ``memories/`` files, as with ``shared``;
* a messaging user — in a DM, or in a group session isolated per participant (the gateway default):
  ``memories/users/<platform>/<user id>/``;
* a group or thread session its members share: ``memories/chats/<platform>/<chat id>[/<thread id>]/``.
  Everyone in it reads the same transcript, so no single member's memory may load into it.

With ``per_user`` or ``hybrid``, ``session_search`` also only finds the owner's own sessions; the
operator's search is not restricted.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator, Optional
from urllib.parse import quote, unquote

logger = logging.getLogger(__name__)

MODES = ("shared", "per_user", "hybrid")
_KINDS = {"users": "user", "chats": "chat"}

# Who is looking at pending memory writes (``/memory`` in a chat): ``None`` sees every pending write.
_viewer: ContextVar[Optional[str]] = ContextVar("memory_sharing_viewer", default=None)


def sharing_mode(mem_config: Optional[dict[str, Any]]) -> str:
    """The ``memory.sharing`` setting, validated (``per-user`` is accepted for ``per_user``). Raises
    ``ValueError`` on anything else: guessing could put one user's memory in front of another."""
    raw = (mem_config or {}).get("sharing")
    if raw is None or raw == "":
        return "shared"
    mode = str(raw).strip().lower().replace("-", "_")
    if mode not in MODES:
        raise ValueError(f"memory.sharing must be one of {', '.join(MODES)}, not {raw!r}")
    return mode


def _segment(value: str) -> str:
    """One path segment for an id: percent-encoded, so any platform's ids fit a file name."""
    encoded = quote(value, safe="")
    return encoded.replace(".", "%2E") if encoded in (".", "..") else encoded


@dataclass(frozen=True)
class MemoryOwner:
    """The user or shared chat a conversation's memory belongs to."""

    kind: str  # "user" or "chat"
    platform: str
    ids: tuple[str, ...]  # (user id,) or (chat id[, thread id])

    @property
    def key(self) -> str:
        """``users/<platform>/<id>`` or ``chats/<platform>/<chat>[/<thread>]``: the owner's folder under
        ``memories/`` (and in a bucket), and how staged writes and cron jobs record the owner."""
        return "/".join((f"{self.kind}s", _segment(self.platform), *map(_segment, self.ids)))

    @classmethod
    def from_key(cls, key: Optional[str]) -> Optional[MemoryOwner]:
        if not key:
            return None
        parts = str(key).split("/")
        kind = _KINDS.get(parts[0])
        if kind is None or len(parts) < 3 or len(parts) > (3 if kind == "user" else 4) or not all(parts[1:]):
            raise ValueError(f"not a memory owner: {key!r}")
        if any(part in (".", "..") for part in parts):
            raise ValueError(f"not a memory owner: {key!r}")
        return cls(kind, unquote(parts[1]), tuple(unquote(p) for p in parts[2:]))


def _participant(platform: str, user_id: Any, user_id_alt: Any) -> Optional[str]:
    """The sender id the gateway keys per-participant sessions on (``gateway.session._canonical_participant``)."""
    participant = user_id_alt or user_id
    if participant and platform == "whatsapp":
        from gateway.whatsapp_identity import canonical_whatsapp_identifier
        participant = canonical_whatsapp_identifier(str(participant)) or participant
    return str(participant) if participant else None


def owner_from_identity(*, platform: Any, user_id: Any = None, user_id_alt: Any = None, chat_type: Any = None,
                        chat_id: Any = None, thread_id: Any = None, session_key: Any = None) -> Optional[MemoryOwner]:
    """The owner of a conversation with this messaging identity; ``None`` without one (the operator)."""
    if not platform or not (user_id or user_id_alt or chat_id):
        return None
    platform = str(platform)
    participant = _participant(platform, user_id, user_id_alt)
    if chat_type == "dm":
        sender = participant or chat_id
        return MemoryOwner("user", platform, (str(sender),)) if sender else None
    # A group session isolated per participant ends its key with the participant id
    # (gateway.session.build_session_key); one without it is shared by everyone in the chat.
    if participant and (not session_key or str(session_key).endswith(f":{participant}")):
        return MemoryOwner("user", platform, (participant,))
    if chat_id:
        return MemoryOwner("chat", platform, tuple(str(i) for i in (chat_id, thread_id) if i))
    return None


def owner_from_session_row(row: Optional[dict[str, Any]]) -> Optional[MemoryOwner]:
    """The owner of a stored session (``sessions`` row: ``source``, ``user_id``, ``chat_id``, ``session_key``)."""
    if not row:
        return None
    key, platform = str(row.get("session_key") or ""), row.get("source")
    parts = key.split(":")  # agent:<profile>:<platform>:<chat_type>:... (gateway.session.build_session_key)
    chat_type = row.get("chat_type") or (
        parts[3] if len(parts) > 3 and parts[0] == "agent" and parts[2] == platform else None)
    return owner_from_identity(platform=platform, user_id=row.get("user_id"), chat_type=chat_type,
                               chat_id=row.get("chat_id"), thread_id=row.get("thread_id"), session_key=key or None)


def owner_for_agent(agent: Any) -> Optional[MemoryOwner]:
    """The owner of an agent's conversation: one a cron job gave it, its memory store's (a review fork
    shares its parent's store), its messaging identity, else its delegating parent's."""
    for _ in range(16):  # a delegation chain is shallow; a cycle must not hang
        if agent is None:
            return None
        if (owner := getattr(agent, "_memory_owner", None)) is not None:
            return owner
        if (store := getattr(agent, "_memory_store", None)) is not None and getattr(store, "owner", None):
            return store.owner
        owner = owner_from_identity(
            platform=getattr(agent, "platform", None), user_id=getattr(agent, "_user_id", None),
            user_id_alt=getattr(agent, "_user_id_alt", None), chat_type=getattr(agent, "_chat_type", None),
            chat_id=getattr(agent, "_chat_id", None), thread_id=getattr(agent, "_thread_id", None),
            session_key=getattr(agent, "_gateway_session_key", None))
        if owner is not None:
            return owner
        parent_ref = getattr(agent, "_delegate_parent_ref", None)
        agent = parent_ref() if parent_ref is not None else None
    return None


def owner_from_session_env() -> Optional[MemoryOwner]:
    """The owner of the conversation a tool call is running in (gateway session context)."""
    from gateway.session_context import get_session_env
    return owner_from_identity(
        platform=get_session_env("HERMES_SESSION_PLATFORM"), user_id=get_session_env("HERMES_SESSION_USER_ID"),
        user_id_alt=get_session_env("HERMES_SESSION_USER_ID_ALT"), chat_type=get_session_env("HERMES_SESSION_CHAT_TYPE"),
        chat_id=get_session_env("HERMES_SESSION_CHAT_ID"), thread_id=get_session_env("HERMES_SESSION_THREAD_ID"),
        session_key=get_session_env("HERMES_SESSION_KEY"))


def scope_dirs(mode: str, owner: Optional[MemoryOwner]) -> dict[str, str]:
    """Folder (relative to ``memories/``) of each built-in memory file for this mode and owner."""
    private = owner.key if owner is not None else ""
    return {"memory": private if mode == "per_user" else "",
            "user": private if mode in ("per_user", "hybrid") else ""}


def build_store(mem_config: Optional[dict[str, Any]], owner: Optional[MemoryOwner], *, memory_enabled: bool = True,
                user_profile_enabled: bool = True):
    """A MemoryStore for ``owner`` under the profile's memory settings (not yet loaded). Raises
    ``ValueError`` / ``MemoryStorageError`` on unusable settings, logged here."""
    from tools.memory_tool import MemoryStore, memory_mirror
    mem_config = mem_config or {}
    try:
        mode = sharing_mode(mem_config)
    except ValueError as exc:
        logger.error("Built-in memory is off: %s", exc)
        raise
    return MemoryStore(int(mem_config.get("memory_char_limit", 2200)), int(mem_config.get("user_char_limit", 1375)),
                       memory_enabled=memory_enabled, user_profile_enabled=user_profile_enabled,
                       mirror=memory_mirror(mem_config), owner=owner, sharing=mode)


def store_for_agent(agent: Any, mem_config: Optional[dict[str, Any]]):
    """The loaded MemoryStore for an agent's conversation."""
    store = build_store(mem_config, owner_for_agent(agent), memory_enabled=agent._memory_enabled,
                        user_profile_enabled=agent._user_profile_enabled)
    store.load_from_disk()
    return store


def session_viewer(agent: Any) -> Optional[str]:
    """Whose sessions ``session_search`` may show this agent: the owner's key under ``per_user`` and
    ``hybrid``, ``None`` (no restriction) under ``shared`` or for the operator."""
    from tools.memory_tool import get_builtin_memory_config
    try:
        mode = sharing_mode(get_builtin_memory_config())
    except ValueError:
        mode = "per_user"  # an unreadable setting must not widen what a user can search
    owner = owner_for_agent(agent) if mode != "shared" else None
    return owner.key if owner is not None else None


def apply_job_owner(agent: Any, job: dict[str, Any]) -> None:
    """Give a cron job's agent the memory of the conversation that created the job (``origin.memory_owner``)."""
    key = ((job or {}).get("origin") or {}).get("memory_owner")
    if not key:
        return
    agent._memory_owner = MemoryOwner.from_key(key)
    if getattr(agent, "_memory_store", None) is not None:
        agent._memory_store = agent._memory_store.for_owner(agent._memory_owner)


def origin_memory_owner() -> dict[str, str]:
    """``{"memory_owner": key}`` for a cron job created in a messaging conversation while ``memory.sharing``
    keeps users apart, else ``{}``."""
    from tools.memory_tool import get_builtin_memory_config
    try:
        if sharing_mode(get_builtin_memory_config()) == "shared":
            return {}
    except ValueError:
        pass
    owner = owner_from_session_env()
    return {"memory_owner": owner.key} if owner is not None else {}


@contextmanager
def viewing_as(owner: Optional[MemoryOwner]) -> Iterator[None]:
    """Show pending memory writes as ``owner`` sees them (only theirs) for the duration."""
    token = _viewer.set(owner.key if owner is not None else None)
    try:
        yield
    finally:
        _viewer.reset(token)


def visible_to_viewer(record: dict[str, Any]) -> bool:
    """Whether the current viewer may see a pending memory write (everyone's, without a viewer)."""
    viewer = _viewer.get()
    return viewer is None or (record.get("payload") or {}).get("owner") == viewer


def with_owner(payload: dict[str, Any], store: Any) -> dict[str, Any]:
    """A pending memory write's payload carrying its store's owner, so approval applies it there."""
    owner = getattr(store, "owner", None)
    return {**payload, "owner": owner.key} if owner is not None else payload


def viewing_owner() -> Optional[str]:
    """The owner key ``viewing_as`` set, or ``None`` (the operator, who sees every pending write)."""
    return _viewer.get()


def owner_for_source(source: Any, session_key: Optional[str]) -> Optional[MemoryOwner]:
    """The owner of a gateway conversation (a ``SessionSource``) when ``memory.sharing`` keeps users apart;
    ``None`` under ``shared``. An unreadable setting is treated as ``per_user``: never wider."""
    from tools.memory_tool import get_builtin_memory_config
    try:
        if sharing_mode(get_builtin_memory_config()) == "shared":
            return None
    except ValueError:
        pass
    platform = getattr(source, "platform", None)
    return owner_from_identity(
        platform=getattr(platform, "value", platform), user_id=getattr(source, "user_id", None),
        user_id_alt=getattr(source, "user_id_alt", None), chat_type=getattr(source, "chat_type", None),
        chat_id=getattr(source, "chat_id", None), thread_id=getattr(source, "thread_id", None),
        session_key=session_key)


class OwnerScopedSessions:
    """A read view of a SessionDB that shows only the sessions one memory owner had, for
    ``session_search`` under ``per_user`` / ``hybrid``: another owner's session reads as missing.
    Methods not overridden here pass through."""

    _SCAN_FACTOR = 5  # read further before filtering, so other owners' rows don't crowd a result out

    def __init__(self, db: Any, viewer: str):
        self._db, self._viewer = db, viewer
        self._owners: dict[str, Optional[str]] = {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self._db, name)

    def _owner_key(self, session_id: Optional[str]) -> Optional[str]:
        """The owner of a session; a continuation without identity columns takes its parent's."""
        chain: list[str] = []
        owner: Optional[str] = None
        while session_id and session_id not in chain:
            if session_id in self._owners:
                owner = self._owners[session_id]
                break
            chain.append(session_id)
            row = self._db.get_session(session_id)
            if not row:
                break
            if row.get("user_id") or row.get("chat_id") or row.get("session_key"):
                found = owner_from_session_row(row)
                owner = found.key if found is not None else None
                break
            session_id = row.get("parent_session_id")
        for sid in chain:
            self._owners[sid] = owner
        return owner

    def visible(self, session_id: Optional[str]) -> bool:
        return bool(session_id) and self._owner_key(session_id) == self._viewer

    def get_session(self, session_id: str, *args: Any, **kwargs: Any) -> Any:
        return self._db.get_session(session_id, *args, **kwargs) if self.visible(session_id) else None

    def get_messages(self, session_id: str, *args: Any, **kwargs: Any) -> Any:
        return self._db.get_messages(session_id, *args, **kwargs) if self.visible(session_id) else []

    def get_anchored_view(self, session_id: str, *args: Any, **kwargs: Any) -> Any:
        return self._db.get_anchored_view(session_id, *args, **kwargs) if self.visible(session_id) else {}

    def get_messages_around(self, session_id: str, *args: Any, **kwargs: Any) -> Any:
        return self._db.get_messages_around(session_id, *args, **kwargs) if self.visible(session_id) else {}

    def resolve_session_by_title(self, *args: Any, **kwargs: Any) -> Any:
        session_id = self._db.resolve_session_by_title(*args, **kwargs)
        return session_id if self.visible(session_id) else None

    def search_messages(self, *args: Any, limit: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        rows = self._db.search_messages(*args, limit=limit * self._SCAN_FACTOR, **kwargs)
        return [row for row in rows if self.visible(row.get("session_id"))][:limit]

    def list_recent_sessions_bounded(self, *args: Any, limit: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        rows = self._db.list_recent_sessions_bounded(*args, limit=limit * self._SCAN_FACTOR, **kwargs)
        return [row for row in rows if self.visible(row.get("id"))][:limit]


def user_owner(spec: str) -> MemoryOwner:
    """``platform:id`` (as the operator types it, e.g. ``telegram:123456789``) as a user owner."""
    platform, sep, ident = str(spec).partition(":")
    if not (sep and platform.strip() and ident.strip()):
        raise SystemExit(f"--user takes PLATFORM:ID, e.g. telegram:123456789 (got {spec!r})")
    return MemoryOwner("user", platform.strip().lower(), (ident.strip(),))
