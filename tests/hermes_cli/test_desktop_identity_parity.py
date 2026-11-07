"""The CLI looks for the desktop app under the names its build gives it (FORK.md, "Rebranded as tuos").

`tuos desktop`, doctor, update and uninstall find the app, its bundle id and its state folder through
``hermes_cli.distribution`` and ``gui_uninstall``; apps/desktop/product-identity.cjs and package.json
decide what the build produces. A drift leaves them looking for an app that is never built.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hermes_cli import distribution, linux_desktop_entry
from hermes_cli.gui_uninstall import desktop_userdata_dir

ROOT = Path(__file__).resolve().parents[2]


def _stable_identity() -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")
    probe = "console.log(JSON.stringify(require('./apps/desktop/product-identity.cjs')))"
    env = {"PATH": str(Path(node).parent)}  # no HERMES_DESKTOP_VARIANT, tag or commit: the stable app
    result = subprocess.run([node, "-e", probe], cwd=ROOT, env=env, capture_output=True, text=True,
                            timeout=60, check=False)
    if result.returncode != 0:
        pytest.skip(f"product-identity.cjs did not evaluate: {result.stderr.strip()[:200]}")
    return json.loads(result.stdout)


def test_the_cli_names_the_app_the_build_produces():
    identity = _stable_identity()
    assert identity["displayName"] == distribution.DESKTOP_APP_NAME  # tuos.app, Linux executable
    assert identity["windowsExecutableName"] == distribution.DESKTOP_APP_NAME  # tuos.exe
    assert identity["appId"] == distribution.DESKTOP_APP_ID


def test_the_linux_launcher_entry_names_the_same_app():
    """linux_desktop_entry.py keeps its own copy: nix/desktop.nix imports it without hermes_cli."""
    assert linux_desktop_entry.APP_ID == distribution.DESKTOP_APP_ID
    assert linux_desktop_entry.APP_NAME == distribution.DESKTOP_APP_NAME


def test_uninstall_removes_the_state_folder_the_app_uses():
    """Electron names the folder after package.json's productName, which the rename leaves as it was."""
    package = json.loads((ROOT / "apps" / "desktop" / "package.json").read_text(encoding="utf-8"))
    assert desktop_userdata_dir().name == package["productName"]


def test_uninstall_knows_the_setup_installer_bundle_id():
    tauri = json.loads((ROOT / "apps" / "bootstrap-installer" / "src-tauri" / "tauri.conf.json")
                       .read_text(encoding="utf-8"))
    assert tauri["identifier"] == f"{distribution.DESKTOP_APP_ID}.setup"
