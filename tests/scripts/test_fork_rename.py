"""scripts/fork/rename.py: copy people see is renamed; data, logs, matchers and test inputs are not."""

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("fork_rename", ROOT / "scripts" / "fork" / "rename.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rename = _load()

SOURCE = '''\
import logging
logger = logging.getLogger(__name__)
HINT = "Run `hermes setup` first"


def run(path, status):
    print(f"Hermes saved {path}. Run `hermes doctor` to check it.")
    logger.warning("Hermes could not read %s", path)
    if status == "Hermes is paused":
        raise RuntimeError("Hermes is paused; run `hermes resume`")
    parser.add_argument("--home", help="Hermes home (default: ~/.hermes)")
    return {"Hermes": path, "agent": "Hermes"}
'''


def test_output_strings_are_renamed_and_data_is_not():
    out = rename.rename_python(SOURCE).text
    assert 'print(f"tuos saved {path}. Run `tuos doctor` to check it.")' in out
    assert 'raise RuntimeError("tuos is paused; run `tuos resume`")' in out
    assert 'help="tuos home (default: ~/.hermes)"' in out
    # Logs, comparisons, constants and data keep their wording.
    assert 'logger.warning("Hermes could not read %s", path)' in out
    assert 'if status == "Hermes is paused":' in out
    assert 'HINT = "Run `hermes setup` first"' in out
    assert 'return {"Hermes": path, "agent": "Hermes"}' in out
    assert rename.rename_python(out).text == out  # a second run changes nothing


def test_renamed_text_that_code_matches_on_is_reported():
    source = 'def f(line):\n    print("Run `hermes doctor` for details")\n    return line.startswith("Run `hermes doctor`")\n'
    result = rename.rename_python(source)
    assert any(rename.overlaps(old, kept) for _, old in result.renamed for _, kept in result.matched)


def test_docs_rename_prose_and_shell_but_keep_config_credit_and_anchors():
    page = (
        "## Installing Hermes\n\nRun `hermes setup`.\n\n```bash\nhermes gateway install\n```\n\n"
        "```yaml\nagent_name: Hermes\n```\n\nHermes Agent is built by Nous Research.\n"
    )
    out = rename.rename_markdown(page)
    assert "## Installing tuos {#installing-hermes}\n" in out
    assert "Run `tuos setup`." in out and "tuos gateway install\n" in out
    assert "agent_name: Hermes\n" in out
    assert "Hermes Agent is built by Nous Research.\n" in out
    assert rename.rename_markdown(out) == out


def test_tests_follow_searched_expectations_only():
    test = (
        'def test_it(out, cmd):\n'
        '    assert "hermes doctor" in out\n'
        '    assert "hermes update" not in out\n'
        '    assert cmd == "hermes doctor"\n'
        '    assert parse("hermes doctor --fix") is not None\n'
    )
    produced = rename.Produced("Run `tuos doctor` to check it.\0Run `tuos update` to update.", "")
    out = rename.follow_tests(test, produced)
    assert '    assert "tuos doctor" in out\n' in out and '    assert "tuos update" not in out\n' in out
    # An exact value and a test's input stay as written.
    assert '    assert cmd == "hermes doctor"\n' in out
    assert '    assert parse("hermes doctor --fix") is not None\n' in out


@pytest.mark.skipif(shutil.which("node") is None or not (ROOT / "node_modules" / "typescript").is_dir(),
                    reason="needs node and the repository's node_modules")
def test_apps_rename_copy_but_not_headers_logs_or_commands():
    source = (
        "const HEADER = { 'X-Hermes-Session-Token': token, 'User-Agent': 'Hermes-Desktop' }\n"
        "console.error('Hermes failed to load')\n"
        "export const Title = () => <h1 title=\"Hermes settings\">Welcome to Hermes</h1>\n"
        "throw new Error('Hermes gateway is not connected')\n"
        "const script = ['Get-Command hermes -CommandType Application'].join(';')\n"
    )
    out = subprocess.run(["node", str(ROOT / "scripts/fork/rename_ts.mjs"), "--stdin", "apps/desktop/src/example.tsx"],
                         input=source, capture_output=True, text=True, encoding="utf-8", check=True, timeout=120).stdout
    assert '<h1 title="tuos settings">Welcome to tuos</h1>' in out
    assert "new Error('tuos gateway is not connected')" in out
    assert "'X-Hermes-Session-Token': token, 'User-Agent': 'Hermes-Desktop'" in out
    assert "console.error('Hermes failed to load')" in out
    assert "Get-Command hermes -CommandType Application" in out


def test_tests_keep_wording_the_code_still_has_or_feeds_in():
    test = (
        'def test_it(out, log):\n'
        '    assert "hermes webapp" in out\n'
        '    assert "restart Hermes to finish" in log\n'
        '    fake = Error("google installed; restart Hermes to finish")\n'
    )
    produced = rename.Produced("Run `tuos webapp`.\0Then restart tuos to finish.", '{"error": "Run: hermes webapp"}')
    assert rename.follow_tests(test, produced) == test

