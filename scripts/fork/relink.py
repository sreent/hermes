#!/usr/bin/env python3
"""Point upstream's references to what Nous Research hosts at what this fork hosts (FORK.md, "Hosted by
this fork").

Each rule rewrites one kind of reference in every tracked text file, code, tests and docs alike:

* The Docker image ``nousresearch/hermes-agent``, wherever it is pulled, run, built ``FROM`` or named,
  becomes ``hermes_cli.distribution.DOCKER_IMAGE``, and its Docker Hub page the fork's package page.
  The same words inside a path (``github.com/nousresearch/hermes-agent``, ``.../hermes-agent/skills``)
  name the repository, not the image, and stay.

Files in ``NEVER`` are not touched, nor any line containing text in ``KEEP``.

``scripts/fork/rename.py`` runs this after its own rewrite, and its ``--resolve`` treats a relinked line as
ours, so the steps after an upstream merge stay the same.

    python scripts/fork/relink.py            # rewrite
    python scripts/fork/relink.py --check    # change nothing; exit 1 if anything would change
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hermes_cli.distribution import DOCKER_IMAGE, DOCKER_PACKAGE_URL

# Never rewritten: the record of what this fork changed, and the rules and their tests.
NEVER = {"FORK.md", "scripts/fork/relink.py", "tests/scripts/test_fork_relink.py"}
# A line containing any of these keeps its wording: it describes Nous's own hosting.
KEEP: tuple[str, ...] = (
    "which also powers Hermes Cloud",  # website/docs/user-guide/features/bot-screen.md: Nous's image
    "nousresearch/hermes-agent:test image",  # scripts/run_tests_parallel.py: upstream's CI
)

RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"https://hub\.docker\.com/r/nousresearch/hermes-agent(?:/tags)?/?"), DOCKER_PACKAGE_URL),
    # As an image reference: followed by a tag, a digest, or the end of the word (never ``/``, ``.git``
    # or a regular expression's next group).
    (re.compile(r"(?<![\w/.-])nousresearch/hermes-agent(?=[:@\s\"'`,)]|$)", re.MULTILINE), DOCKER_IMAGE),
)


def relink(text: str) -> str:
    """``text`` with every rule applied, except on lines that mention something in ``KEEP``."""
    if not any(rule.search(text) for rule, _ in RULES):
        return text
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if any(kept in line for kept in KEEP):
            continue
        for rule, replacement in RULES:
            line = rule.sub(replacement, line)
        lines[index] = line
    return "".join(lines)


def relink_file(name: str, text: str) -> str:
    """``text`` relinked as the repository file ``name`` would be."""
    return text if name in NEVER else relink(text)


def tracked_files() -> list[str]:
    """Tracked files that mention something a rule rewrites (``git grep``, so binaries are skipped)."""
    words = ("nousresearch/hermes-agent",)
    result = subprocess.run(["git", "grep", "-l", "-I", "-F", *(arg for word in words for arg in ("-e", word))],
                            cwd=ROOT, capture_output=True, text=True, check=False, timeout=120)
    if result.returncode not in (0, 1):
        raise SystemExit(f"git grep failed: {result.stderr.strip()}")
    return [name for name in result.stdout.splitlines() if name not in NEVER]


def run(check: bool) -> list[str]:
    """Relink every tracked file (or, with ``check``, only report). Returns the files that changed."""
    changed = []
    for name in tracked_files():
        path = ROOT / name
        with path.open(encoding="utf-8", errors="surrogateescape", newline="") as source:  # keeps CRLF files CRLF
            text = source.read()
        if (linked := relink(text)) != text:
            changed.append(name)
            if not check:
                with path.open("w", encoding="utf-8", errors="surrogateescape", newline="") as out:
                    out.write(linked)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="change nothing; exit 1 if anything would change")
    args = parser.parse_args()
    changed = run(args.check)
    print(f"{'would relink' if args.check else 'relinked'} {len(changed)} file(s)")
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
