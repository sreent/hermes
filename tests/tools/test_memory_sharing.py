"""memory.sharing: whose MEMORY.md / USER.md a conversation reads and writes (tools/memory_sharing.py)."""

import json
import pytest

from tools import memory_sharing as ms
from tools.memory_sharing import MemoryOwner, owner_from_identity


def _home(tmp_path, monkeypatch, sharing):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(f"memory:\n  sharing: {sharing}\n", encoding="utf-8")
    return {"sharing": sharing}


class _Agent:
    """What agent_init leaves on an agent: platform, gateway identity, memory flags."""

    def __init__(self, platform="cli", **identity):
        self.platform, self._memory_enabled, self._user_profile_enabled = platform, True, True
        for name, value in identity.items():
            setattr(self, f"_{name}", value)


_agent = _Agent


ALICE = dict(platform="telegram", user_id="1001", chat_type="dm", chat_id="1001",
             gateway_session_key="agent:main:telegram:dm:1001")
BOB = dict(platform="telegram", user_id="2002", chat_type="dm", chat_id="2002",
           gateway_session_key="agent:main:telegram:dm:2002")


@pytest.mark.parametrize(("raw", "mode"), [(None, "shared"), ("per_user", "per_user"), ("per-user", "per_user"),
                                           ("Hybrid", "hybrid")])
def test_sharing_setting(raw, mode):
    assert ms.sharing_mode({"sharing": raw} if raw else {}) == mode


def test_unknown_sharing_setting_is_refused():
    with pytest.raises(ValueError, match="memory.sharing"):
        ms.sharing_mode({"sharing": "everyone"})


def test_owner_of_each_kind_of_conversation():
    dm = owner_from_identity(platform="telegram", user_id="1001", chat_type="dm", chat_id="1001",
                             session_key="agent:main:telegram:dm:1001")
    # A group session isolated per participant (the gateway default) ends its key with the sender.
    member = owner_from_identity(platform="discord", user_id="77", chat_type="group", chat_id="900",
                                 session_key="agent:main:discord:group:900:77")
    # A thread is shared by everyone in it unless thread_sessions_per_user is on.
    thread = owner_from_identity(platform="discord", user_id="77", chat_type="thread", chat_id="900",
                                 thread_id="55", session_key="agent:main:discord:thread:900:55")
    assert dm.key == "users/telegram/1001"
    assert member.key == "users/discord/77"
    assert thread.key == "chats/discord/900/55"
    assert owner_from_identity(platform="cli") is None  # the operator


@pytest.mark.parametrize("user_id", ["@alice:matrix.org", "a/b", "..", "+44 7700 900123"])
def test_any_platform_id_makes_one_safe_folder(user_id):
    owner = MemoryOwner("user", "matrix", (user_id,))
    assert owner.key.count("/") == 2 and ".." not in owner.key.split("/")
    assert MemoryOwner.from_key(owner.key) == owner


def test_per_user_keeps_each_users_memory_apart(tmp_path, monkeypatch):
    config = _home(tmp_path, monkeypatch, "per_user")
    alice = ms.store_for_agent(_agent(**ALICE), config)
    assert alice.add("memory", "Alice deploys on Fridays.")["success"]
    assert alice.add("user", "Alice prefers short answers.")["success"]

    bob = ms.store_for_agent(_agent(**BOB), config)
    operator = ms.store_for_agent(_agent(), config)
    assert bob.memory_entries == bob.user_entries == []
    assert operator.memory_entries == operator.user_entries == []
    assert (tmp_path / "memories/users/telegram/1001/USER.md").read_text(encoding="utf-8") == "Alice prefers short answers."
    assert not (tmp_path / "memories/MEMORY.md").exists() or not (tmp_path / "memories/MEMORY.md").read_text()


def test_hybrid_shares_the_agents_notes_and_keeps_user_profiles_private(tmp_path, monkeypatch):
    config = _home(tmp_path, monkeypatch, "hybrid")
    alice = ms.store_for_agent(_agent(**ALICE), config)
    assert alice.add("memory", "The staging cluster is in eu-west-1.")["success"]
    assert alice.add("user", "Alice is the on-call lead.")["success"]

    bob = ms.store_for_agent(_agent(**BOB), config)
    assert bob.memory_entries == ["The staging cluster is in eu-west-1."]
    assert bob.user_entries == []
    assert ms.store_for_agent(_agent(), config).memory_entries == ["The staging cluster is in eu-west-1."]


def test_shared_is_one_memory_for_everyone(tmp_path, monkeypatch):
    config = _home(tmp_path, monkeypatch, "shared")
    assert ms.store_for_agent(_agent(**ALICE), config).add("user", "Prefers metric units.")["success"]
    assert ms.store_for_agent(_agent(**BOB), config).user_entries == ["Prefers metric units."]
    assert (tmp_path / "memories/USER.md").exists()


def test_a_subagent_and_a_cron_job_use_the_memory_of_the_conversation_behind_them(tmp_path, monkeypatch):
    import weakref

    config = _home(tmp_path, monkeypatch, "per_user")
    ms.store_for_agent(_agent(**ALICE), config).add("user", "Alice's timezone is UTC+2.")
    parent = _agent(**ALICE)
    child = _agent(platform="subagent")
    child._delegate_parent_ref = weakref.ref(parent)
    assert ms.owner_for_agent(child).key == "users/telegram/1001"

    job_agent = _agent(platform="cron")
    job_agent._memory_store = ms.store_for_agent(job_agent, config)
    ms.apply_job_owner(job_agent, {"origin": {"memory_owner": "users/telegram/1001"}})
    assert job_agent._memory_store.user_entries == ["Alice's timezone is UTC+2."]


def test_a_job_made_in_a_chat_records_whose_memory_it_uses(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch, "per_user")
    from gateway.session_context import clear_session_vars, set_session_vars

    tokens = set_session_vars(platform="telegram", chat_id="1001", chat_type="dm", user_id="1001",
                              session_key="agent:main:telegram:dm:1001")
    try:
        assert ms.origin_memory_owner() == {"memory_owner": "users/telegram/1001"}
    finally:
        clear_session_vars(tokens)


def test_pending_writes_are_seen_and_applied_as_their_owner(tmp_path, monkeypatch):
    config = _home(tmp_path, monkeypatch, "per_user")
    from tools import write_approval as wa
    from tools.memory_tool import apply_memory_pending, load_on_disk_store

    alice_owner = MemoryOwner("user", "telegram", ("1001",))
    alice = ms.store_for_agent(_agent(**ALICE), config)
    record = wa.stage_write(wa.MEMORY, ms.with_owner({"action": "add", "target": "user",
                                                      "content": "Alice is allergic to peanuts."}, alice),
                            summary="add", origin="foreground")

    with ms.viewing_as(MemoryOwner("user", "telegram", ("2002",))):
        assert wa.list_pending(wa.MEMORY) == [] and wa.get_pending(wa.MEMORY, record["id"]) is None
        assert not wa.discard_pending(wa.MEMORY, record["id"])
    with ms.viewing_as(alice_owner):
        assert [r["id"] for r in wa.list_pending(wa.MEMORY)] == [record["id"]]
    assert [r["id"] for r in wa.list_pending(wa.MEMORY)] == [record["id"]]  # the operator sees all

    # Approving from the operator's store writes Alice's memory, not the operator's.
    assert apply_memory_pending(record["payload"], load_on_disk_store())["success"]
    assert ms.store_for_agent(_agent(**ALICE), config).user_entries == ["Alice is allergic to peanuts."]
    assert load_on_disk_store().user_entries == []
    assert load_on_disk_store(alice_owner).user_entries == ["Alice is allergic to peanuts."]


def test_session_search_finds_only_the_owners_conversations(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from hermes_state import SessionDB
    from tools.session_search_tool import session_search

    db = SessionDB(db_path=tmp_path / "state.db")
    for sid, source, user, key in (
            ("s-alice", "telegram", "1001", "agent:main:telegram:dm:1001"),
            ("s-bob", "telegram", "2002", "agent:main:telegram:dm:2002"),
            ("s-cli", "cli", None, None)):
        db.create_session(sid, source, user_id=user, session_key=key, chat_id=user, chat_type="dm" if user else None)
        db.append_message(sid, "user", f"what did we decide about the quokka budget ({sid})")
        db.append_message(sid, "assistant", "We agreed on the quokka budget.")

    def found(viewer):
        payload = json.loads(session_search(query="quokka", limit=10, db=db, viewer=viewer))
        return {r["session_id"] for r in payload.get("results", [])}

    assert found("users/telegram/1001") == {"s-alice"}
    assert found(None) == {"s-alice", "s-bob", "s-cli"}  # the operator
    read_other = json.loads(session_search(session_id="s-bob", db=db, viewer="users/telegram/1001"))
    assert read_other.get("success") is False
    cross_profile = json.loads(session_search(query="quokka", profile="other", db=db, viewer="users/telegram/1001"))
    assert cross_profile.get("success") is False


def test_bucket_objects_keep_each_users_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from tools.memory_storage import MemoryMirror

    mirror = MemoryMirror(remote=None, prefix="team", namespace="agent")
    assert mirror.key_for(tmp_path / "memories/MEMORY.md") == "team/agent/memories/MEMORY.md"
    assert mirror.key_for(tmp_path / "memories/users/telegram/1001/USER.md") == \
        "team/agent/memories/users/telegram/1001/USER.md"


def test_memory_command_in_a_chat_acts_for_its_sender_only_when_users_are_kept_apart(tmp_path, monkeypatch):
    from types import SimpleNamespace

    source = SimpleNamespace(platform=SimpleNamespace(value="slack"), user_id="U42", user_id_alt=None,
                             chat_type="dm", chat_id="D42", thread_id=None)
    _home(tmp_path, monkeypatch, "shared")
    assert ms.owner_for_source(source, "agent:main:slack:dm:D42") is None
    _home(tmp_path, monkeypatch, "hybrid")
    assert ms.owner_for_source(source, "agent:main:slack:dm:D42").key == "users/slack/U42"
