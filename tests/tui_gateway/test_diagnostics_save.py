"""diagnostics.save RPC — Desktop "Save diagnostics" path. Nothing is uploaded (FORK.md).

Contract pinned:
* Reuses the CLI ``hermes debug share`` pipeline (collect_share_bundle → save_debug_archive) with
  redaction FORCED on — the client cannot disable it.
* ``error_context`` and ``extra_files`` are redacted server-side, labels
  sanitized, sizes capped.
* Save failures return a structured ``{ok: False, error}`` envelope, never a
  JSON-RPC error (the desktop renders them inline in the modal).
"""

from __future__ import annotations

import zipfile

import pytest

from tui_gateway import server


def _handler():
    fn = server._methods.get("diagnostics.save")
    assert fn is not None, "diagnostics.save not registered"
    return fn


def _files(result: dict) -> dict[str, str]:
    """The archive a successful call saved, as entry name -> text."""
    payload = result["result"]
    assert payload["ok"] is True, payload
    with zipfile.ZipFile(payload["path"]) as archive:
        return {name: archive.read(name).decode("utf-8") for name in archive.namelist()}


def test_save_writes_a_redacted_archive_under_the_profile():
    from hermes_constants import get_hermes_home

    result = _handler()("rid-1", {})
    files = _files(result)

    reports = get_hermes_home() / "logs" / "debug-reports"
    assert result["result"]["path"].startswith(str(reports))
    assert "secrets redacted when this report was collected" in files["report.txt"]


def test_save_attaches_redacted_error_context():
    secret = "sk-abc123def456ghi789jkl012mno345pqr678"
    result = _handler()(
        "rid-2",
        {"error_context": f"layer: provider\ncode: rate_limit\nkey was {secret}"},
    )
    files = _files(result)
    context = files.get("error-context.txt", "")
    assert "layer: provider" in context
    assert secret not in context, "secret leaked through error_context redaction"


def test_save_client_text_gets_support_safe_log_redaction():
    """Client artifacts must ride the SAME redactor as backend logs
    (redact_debug_support_text): secrets AND email addresses — not just the bare
    secret pass, which leaves emails through (review finding on #92020)."""
    secret = "sk-abc123def456ghi789jkl012mno345pqr678"
    result = _handler()(
        "rid-2b",
        {
            "error_context": "user reported by alice@example.com",
            "extra_files": {"desktop.log": f"login bob@example.com token={secret}"},
        },
    )
    files = _files(result)
    assert "alice@example.com" not in files["error-context.txt"]
    assert "[REDACTED_EMAIL]" in files["error-context.txt"]
    assert "bob@example.com" not in files["client/desktop.log"]
    assert secret not in files["client/desktop.log"]


def test_redacted_support_report_scrubs_structured_values_and_errors(monkeypatch):
    from hermes_constants import get_hermes_home

    canaries = {
        "url": "r36_REDACTED_url_canary_0123456789",
        "header": "r36_REDACTED_header_canary_0123456789",
        "env": "r36_REDACTED_env_canary_0123456789",
        "argv": "r36_REDACTED_argv_canary_0123456789",
        "bearer": "r36_REDACTED_bearer_canary_0123456789",
        "error": "r36_REDACTED_error_canary_0123456789",
    }
    home = get_hermes_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(
        "fallback_providers:\n"
        "  - provider: custom\n"
        "    model: support-fixture\n"
        "    base_url: 'https://outer.invalid/?next=https://inner.invalid/"
        f"?accessToken={canaries['url']}'\n"
        "    extra_headers:\n"
        f"      X-API-Key: {canaries['header']}\n"
        "    env:\n"
        f"      AWS_SECRET_ACCESS_KEY: {canaries['env']}\n"
        f"    args: ['--api-key', '{canaries['argv']}']\n",
        encoding="utf-8",
    )
    structured = (
        f"headers={{'Proxy-Authorization': 'Basic {canaries['header']}'}} "
        f"Command ['provider', '--api-key', '{canaries['argv']}'] "
        f"Bearer {canaries['bearer']} "
        f"https://a.invalid/?next=%2Fx%3Ffoo%26token%3D{canaries['url']}"
    )

    result = _handler()(
        "rid-structured",
        {"error_context": structured, "extra_files": {"desktop.log": structured}},
    )

    files = _files(result)
    assert "secrets redacted when this report was collected" in files["report.txt"]
    rendered = "\n".join(f"{name}\n{text}" for name, text in sorted(files.items()))
    assert "support-fixture" in rendered
    assert not [canary for canary in canaries.values() if canary in rendered]

    # An oversized client value is scrubbed through a bounded window (line-aligned
    # when a line ends in [2x, 3x) cap), with the same capped output as a full scrub.
    import hermes_cli.debug_redaction as dr

    real_redact, scrubbed_sizes = dr.redact_debug_support_text, []

    def _spy(value, **kwargs):
        scrubbed_sizes.append(len(value))
        return real_redact(value, **kwargs)

    line = f"cookie={canaries['header']} " + "x" * 40 + "\n"
    monkeypatch.setattr(dr, "redact_debug_support_text", _spy)
    big = _handler()("rid-big", {"error_context": line * 2_000})
    monkeypatch.setattr(dr, "redact_debug_support_text", real_redact)
    big_context = _files(big)["error-context.txt"]
    assert max(scrubbed_sizes) <= 2 * 8_000 + len(line)
    assert big_context == real_redact((line * 2_000).strip(), max_chars=8_000)
    scrubbed_sizes.clear()
    monkeypatch.setattr(dr, "redact_debug_support_text", _spy)
    one_line = f"cookie={canaries['header']} " + "x" * 2_000_000
    assert _handler()("rid-one-line", {"error_context": one_line})["result"]["ok"] is True
    monkeypatch.setattr(dr, "redact_debug_support_text", real_redact)
    assert max(scrubbed_sizes) <= 3 * 8_000

    import hermes_cli.debug_archive as da

    def _fail(_bundle: dict) -> str:
        # The tail is already scrubbed (a wrapped inner error); re-scrubbing it
        # must be idempotent, not turn ``[REDACTED]`` into ``[REDACTED]]``.
        raise RuntimeError(
            "write https://storage.invalid/?X-Amz-Security-Token="
            f"{canaries['error']} headers={{'X-API-Key': '{canaries['header']}'}} "
            f"x-api-key: Basic {canaries['header']} "
            + real_redact(f"cookie={canaries['error']}; --api-key {canaries['error']} "
                          f"--header X-API-Key {canaries['error']}")
            + " --header X-API-Key Basic [REDACTED]"
        )

    monkeypatch.setattr(da, "save_debug_archive", _fail)
    failure = _handler()("rid-structured-error", {})["result"]
    assert failure["ok"] is False
    assert canaries["error"] not in failure["error"]
    assert canaries["header"] not in failure["error"]
    assert "[REDACTED]]" not in failure["error"]
    assert failure["error"].endswith(" --header X-API-Key Basic [REDACTED]")
    assert real_redact(failure["error"]) == failure["error"]
    # Prose after an already-masked value is not a key: kept, and a fixed point.
    benign = real_redact("x-api-key: *** see docs")
    assert benign.endswith(" see docs") and real_redact(benign) == benign
    for prose in ("see: documentation", "time: 12:30:45"):
        kept = real_redact(f"x-api-key: *** {prose}")
        assert kept.endswith(f" {prose}") and real_redact(kept) == kept
    # An RFC 6750 challenge is auth-params, not a token.
    assert real_redact('Bearer realm="api"') == 'Bearer realm="api"'
    # Short, colon-bearing and double-encoded keys are keys, not prose.
    for leaky, key in (
        ("x-api-key: Bearer abc1234", "abc1234"),
        ("-H 'x-auth-token: *** s3cr3t'", "s3cr3t"),
        ('Bearer qwertyuiopas="v"', "qwertyuiopas"),
        ("x-api-key: *** qwertyuiopas", "qwertyuiopas"),
        ("--header x-api-key *** abc1234", "abc1234"),
        ("x-api-key: *** " + "q" * 32, "q" * 32),
        ("--header x-api-key *** " + "Q" * 32, "Q" * 32),
        ("x-api-key: *** sk-abc:xyz123456", "xyz123456"),
        ("Basic user:passw0rd", "passw0rd"),
        ("Bearer abcd1234=efgh5678 x", "efgh5678"),
        ("?r=x%2526access_token%253Dtok123456789", "tok123456789"),
    ):
        assert key not in real_redact(leaky)


def test_save_extra_files_sanitized_and_redacted():
    secret = "sk-abc123def456ghi789jkl012mno345pqr678"
    result = _handler()(
        "rid-3",
        {
            "extra_files": {
                "desktop.log": f"boot ok\ntoken={secret}\n",
                "../../etc/passwd": "nope",
                "ok name (1).txt": "fine",
                7: "not-a-str-label",
                "empty": "   ",
            }
        },
    )
    files = _files(result)
    assert "client/desktop.log" in files
    assert secret not in files["client/desktop.log"]
    # Path separators are stripped from labels; traversal shapes can't survive.
    assert not any("/etc/passwd" in k or ".." in k for k in files)
    assert "client/ok name (1).txt" in files
    # Non-string labels and blank bodies are dropped.
    assert not any(k.startswith("client/7") for k in files)
    assert "client/empty" not in files


def test_save_failure_is_structured(monkeypatch):
    import hermes_cli.debug_archive as da

    def _boom(bundle: dict) -> str:
        raise OSError("disk full")

    monkeypatch.setattr(da, "save_debug_archive", _boom)

    result = _handler()("rid-4", {})
    payload = result["result"]
    assert payload["ok"] is False
    assert "disk full" in payload["error"]
