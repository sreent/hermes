"""``tuos``: this distribution's name for the ``hermes`` command (FORK.md, "Rebranded as tuos").

Installed as a console script for pip and Nix installs. It starts the ``hermes`` installed beside it
instead of running the CLI under a second name: gateway, update and restart checks recognise processes
by the ``hermes`` executable (``gateway/status.py``). Installer-managed installs publish a shell
forwarder for the same reason (``hermes_cli/_launchers.py``)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


def hermes_beside(argv0: str, executable: str) -> Optional[str]:
    """The ``hermes`` command installed with this one: next to it, next to its Python, else on PATH."""
    from hermes_platform.resolver import locate_command

    name = "hermes.exe" if os.name == "nt" else "hermes"
    for directory in (Path(argv0).parent if argv0 else None, Path(executable).parent):
        if directory is not None and (candidate := directory / name).is_file():
            return str(candidate)
    found = locate_command("hermes").command
    return found[0] if found else None


def main() -> int:
    hermes = hermes_beside(sys.argv[0] if sys.argv else "", sys.executable)
    if hermes is None:
        sys.stderr.write("tuos: the hermes command it starts is not installed beside it or on PATH\n")
        return 127
    argv = [hermes, *sys.argv[1:]]
    if os.name == "nt":  # Windows has no exec: run it and pass its exit status on
        return subprocess.call(argv)  # health: allow HX006 -- it is the user's command, for as long as it runs
    os.execv(hermes, argv)
    return 0  # not reached: execv replaces this process
