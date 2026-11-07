"""scripts/fork/relink.py: upstream's references to what Nous hosts point at what this fork hosts."""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import hermes_yaml
from hermes_cli.distribution import DOCKER_IMAGE, DOCKER_PACKAGE_URL


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"fork_{name}", ROOT / "scripts" / "fork" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


relink = _load("relink")


def test_image_references_point_at_the_fork_and_repository_paths_stay():
    text = (
        "docker pull nousresearch/hermes-agent:latest\n"
        "FROM nousresearch/hermes-agent:latest\n"
        "  nousresearch/hermes-agent gateway run\n"
        "runs as a published image (nousresearch/hermes-agent), not a checkout\n"
        "inherits from `nousresearch/hermes-agent` and\n"
        "pinned nousresearch/hermes-agent@sha256:0123\n"
        "IMAGE = \"nousresearch/hermes-agent\"\n"
        "tags at https://hub.docker.com/r/nousresearch/hermes-agent/tags\n"
        "clone https://github.com/nousresearch/hermes-agent.git\n"
        "\"skills-sh/nousresearch/hermes-agent/google-workspace\"\n"
        "grep -Eq '^(https://github\\.com/)nousresearch/hermes-agent(\\.git)?/?$'\n"
    )
    assert relink.relink(text) == (
        f"docker pull {DOCKER_IMAGE}:latest\n"
        f"FROM {DOCKER_IMAGE}:latest\n"
        f"  {DOCKER_IMAGE} gateway run\n"
        f"runs as a published image ({DOCKER_IMAGE}), not a checkout\n"
        f"inherits from `{DOCKER_IMAGE}` and\n"
        f"pinned {DOCKER_IMAGE}@sha256:0123\n"
        f"IMAGE = \"{DOCKER_IMAGE}\"\n"
        f"tags at {DOCKER_PACKAGE_URL}\n"
        "clone https://github.com/nousresearch/hermes-agent.git\n"
        "\"skills-sh/nousresearch/hermes-agent/google-workspace\"\n"
        "grep -Eq '^(https://github\\.com/)nousresearch/hermes-agent(\\.git)?/?$'\n"
    )


def test_lines_describing_nous_hosting_keep_their_wording():
    line = "The Docker image (`nousresearch/hermes-agent`, which also powers Hermes Cloud) is\n"
    assert relink.relink(line) == line


def test_files_keep_their_line_endings(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    compose = tmp_path / "compose.yml"
    compose.write_bytes(b"services:\r\n  agent:\r\n    image: nousresearch/hermes-agent:latest\r\n")
    subprocess.run(["git", "add", "compose.yml"], cwd=tmp_path, check=True)
    monkeypatch.setattr(relink, "ROOT", tmp_path)
    assert relink.run(check=True) == ["compose.yml"]
    assert relink.run(check=False) == ["compose.yml"]
    assert compose.read_bytes() == f"services:\r\n  agent:\r\n    image: {DOCKER_IMAGE}:latest\r\n".encode()
    assert relink.run(check=True) == []


def test_a_merge_counts_a_relinked_line_as_ours():
    """rename.py --resolve takes upstream's side of a conflicted file only when ours is upstream's base
    renamed and relinked; a relinked image reference must not leave the file for a hand."""
    rename = _load("rename")
    base = "services:\n  agent:\n    image: nousresearch/hermes-agent:latest\n"
    assert rename.rename_text("docker-compose.example.yml", base) == base.replace(
        "nousresearch/hermes-agent", DOCKER_IMAGE)


def test_the_helm_chart_runs_the_image_the_cli_points_at():
    values = hermes_yaml.safe_load((ROOT / "deploy" / "helm" / "tuos" / "values.yaml").read_text(encoding="utf-8"))
    assert values["image"]["repository"] == DOCKER_IMAGE
