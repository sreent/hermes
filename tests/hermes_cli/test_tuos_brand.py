"""What people see is called tuos (FORK.md, "Rebranded as tuos"); internal names stay Hermes's."""

import subprocess

import pytest

from hermes_cli.distribution import PRODUCT_NAME, brand


@pytest.mark.parametrize(("text", "shown"), [
    ("Hermes is restarting", "tuos is restarting"),
    ("Welcome to Hermes Agent!", "Welcome to tuos!"),
    ("Hermes-Sitzung", "tuos-Sitzung"),
    ("Hermesを再起動", "tuosを再起動"),
    ("Run `hermes setup`, then hermes -p work chat", "Run `tuos setup`, then tuos -p work chat"),
    ("then run hermes {profile_arg}sessions recover", "then run tuos {profile_arg}sessions recover"),
])
def test_copy_written_for_hermes_names_tuos(text, shown):
    assert brand(text) == shown


@pytest.mark.parametrize("text", [
    "Managed by Hermes Cloud",  # Nous Research's hosted service
    "Nous Research Hermes 3 & 4 models",  # Nous's models
    "Hermes-4-405B",
    "Toggle the 'Hey Hermes' wake word",  # what the voice listener hears
    "Built on Hermes Agent by Nous Research",  # credit to upstream
    "Edit ~/.hermes/config.yaml or HERMES_HOME; pip install hermes-agent; python -m hermes_cli",  # internal names
    "Logs are in ~/Library/Application Support/Hermes/logs; quit Hermes.app first",  # paths and app names
    "Certificate name (default: Hermes Local Signing)",  # the keychain certificate's name
    "Send the X-Hermes-Session-Id header",  # a hyphenated name
    "Load the `hermes-agent` skill with skill_view(name='hermes-agent')",  # the skill keeps its name
])
def test_names_that_are_not_the_product_stay(text):
    assert brand(text) == text


def test_shipped_catalogs_name_tuos_in_every_language():
    from agent import i18n

    for lang in i18n.supported_languages():
        catalog = i18n._load_bundled(lang)
        assert any(PRODUCT_NAME in text for text in catalog.values()), lang
        assert all(brand(text) == text for text in catalog.values()), lang


def test_agent_introduces_itself_as_tuos():
    from agent.prompt_builder import DEFAULT_AGENT_IDENTITY, PLATFORM_HINTS
    from hermes_cli.default_soul import DEFAULT_SOUL_MD

    # Fails loudly if upstream rewords the persona sentence brand_identity() replaces.
    assert DEFAULT_AGENT_IDENTITY.startswith(f"You are {PRODUCT_NAME},")
    assert DEFAULT_SOUL_MD == DEFAULT_AGENT_IDENTITY
    assert "tuos desktop app" in PLATFORM_HINTS["desktop"]


def test_untouched_hermes_persona_upgrades_and_a_written_one_stays(tmp_path):
    from hermes_cli.config import _ensure_default_soul_md
    from hermes_cli.default_soul import _HERMES_SOUL_MD, DEFAULT_SOUL_MD

    seeded, written = tmp_path / "seeded", tmp_path / "written"
    seeded.mkdir(), written.mkdir()
    (seeded / "SOUL.md").write_text(_HERMES_SOUL_MD, encoding="utf-8")
    (written / "SOUL.md").write_text("You are Hermes, my pirate.", encoding="utf-8")

    _ensure_default_soul_md(seeded)
    _ensure_default_soul_md(written)

    assert (seeded / "SOUL.md").read_text(encoding="utf-8") == DEFAULT_SOUL_MD
    assert (written / "SOUL.md").read_text(encoding="utf-8") == "You are Hermes, my pirate."


def test_cli_help_and_banner_name_tuos():
    from hermes_cli._parser import build_top_level_parser
    from hermes_cli.skin_engine import load_skin

    help_text = build_top_level_parser()[0].format_help()
    assert help_text.startswith("usage: tuos ")
    assert "Hermes" not in help_text
    assert load_skin("default").branding["agent_name"] == PRODUCT_NAME


@pytest.mark.platforms("linux", "macos")
def test_tuos_command_runs_the_hermes_launcher(tmp_path):
    from hermes_cli._launchers import _publish_conveniences

    root, user_bin = tmp_path / "root", tmp_path / "bin"
    hermes = root / ".hermes" / "bin" / "hermes"
    hermes.parent.mkdir(parents=True)
    hermes.write_text('#!/bin/sh\nprintf "%s|" "$0" "$@"\n', encoding="utf-8")
    hermes.chmod(0o755)

    _publish_conveniences(root, user_bin, ("tuos",))
    out = subprocess.run([str(user_bin / "tuos"), "gateway", "run", "--replace"],
                         capture_output=True, text=True, check=True).stdout

    # The process is the hermes launcher (what process checks recognise), with the arguments as given.
    assert out == f"{hermes}|gateway|run|--replace|"
    # A refresh recognises the command as this installation's and keeps it.
    assert _publish_conveniences(root, user_bin, ("tuos",)) == {user_bin / "tuos": False}


def test_windows_tuos_cmd_starts_the_hermes_beside_it(tmp_path):
    from hermes_cli._launchers import _publish_windows_tuos

    assert _publish_windows_tuos(tmp_path) == tmp_path / "tuos.cmd"
    assert (tmp_path / "tuos.cmd").read_bytes() == b'@"%~dp0hermes" %*\r\n'


def test_shell_completion_covers_tuos():
    from hermes_cli._parser import build_top_level_parser
    from hermes_cli.completion import generate_bash, generate_fish, generate_zsh

    parser = build_top_level_parser()[0]
    assert "complete -F _hermes_completion hermes tuos" in generate_bash(parser)
    assert "compdef _hermes hermes tuos" in generate_zsh(parser)
    assert "complete -c tuos -w hermes" in generate_fish(parser)


@pytest.mark.platforms("linux", "macos")
def test_tuos_console_script_starts_the_hermes_installed_beside_it(tmp_path, monkeypatch):
    """pip and Nix installs: the process becomes that hermes, with the arguments as given."""
    import os
    import sys

    from hermes_cli import tuos_command

    bin_dir = tmp_path / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "hermes").write_text("#!/bin/sh\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(sys, "argv", [str(bin_dir / "tuos"), "gateway", "run"])
    monkeypatch.setattr(os, "execv", lambda path, argv: calls.append((path, argv)))
    tuos_command.main()
    assert calls == [(str(bin_dir / "hermes"), [str(bin_dir / "hermes"), "gateway", "run"])]
