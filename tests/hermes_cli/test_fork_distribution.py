"""This fork's installs update from its own repository and keep following its branch (FORK.md)."""

import subprocess

import pytest

from hermes_cli import distribution
from hermes_cli.update_channel import CHANNEL_MAIN, CHANNEL_STABLE, default_channel
from hermes_cli.update_cmd_git import _is_fork

NOUS = "https://github.com/NousResearch/hermes-agent.git"


@pytest.mark.parametrize("origin", [*sorted(distribution.REPO_URLS), f"https://github.com/{distribution.REPOSITORY}/"])
def test_a_checkout_of_this_fork_is_not_offered_another_upstream(origin):
    assert not _is_fork(origin)


@pytest.mark.parametrize("origin", [NOUS, "https://github.com/someone/hermes.git"])
def test_a_checkout_of_another_repository_is_still_a_fork(origin):
    assert _is_fork(origin)


def _checkout(root, origin):
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", origin], check=True)
    return root


def test_this_fork_follows_its_branch_because_it_publishes_no_releases(tmp_path):
    assert default_channel(_checkout(tmp_path / "fork", distribution.REPO_URL)) == CHANNEL_MAIN
    # Control: a checkout of Nous's repository keeps upstream's stable channel.
    assert default_channel(_checkout(tmp_path / "nous", NOUS)) == CHANNEL_STABLE
