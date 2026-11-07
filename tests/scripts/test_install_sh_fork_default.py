"""A default install clones this fork and follows its branch: the fork publishes no releases (FORK.md).

The fork's URL is redirected to a local origin. Any release lookup would ask Nous's repository, so
`curl` fails every request instead of answering one.
"""
from pathlib import Path
import os
import subprocess

import pytest

from hermes_cli import distribution

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.platforms("posix")


def _git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=cwd, check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    ).stdout.strip()


def test_a_default_install_clones_this_fork_and_follows_main(tmp_path):
    origin, home, bin_dir = tmp_path / "origin", tmp_path / "home", tmp_path / "bin"
    install = home / ".hermes" / "hermes-agent"
    for d in (origin, home, bin_dir):
        d.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    _git(origin, "commit", "-q", "--allow-empty", "-m", "release")
    _git(origin, "tag", "-a", "v1.2.3", "-m", "release")  # a release tag must not pull the install back
    _git(origin, "commit", "-q", "--allow-empty", "-m", "newer")
    tip = _git(origin, "rev-parse", "HEAD")
    (home / ".gitconfig").write_text(f'[url "file://{origin}"]\n  insteadOf = {distribution.REPO_URL}\n',
                                     encoding="utf-8")
    (bin_dir / "curl").write_text("#!/bin/sh\nexit 22\n", encoding="utf-8")
    (bin_dir / "curl").chmod(0o755)
    env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "HOME": str(home), "NO_COLOR": "1",
           "GIT_CONFIG_NOSYSTEM": "1"}

    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "install.sh"), "--stage", "repository", "--dir", str(install),
         "--hermes-home", str(home / ".hermes"), "--non-interactive"],
        check=False, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120, env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _git(install, "rev-parse", "HEAD") == tip, result.stdout + result.stderr
    assert _git(install, "config", "--get", "remote.origin.url") == distribution.REPO_URL
