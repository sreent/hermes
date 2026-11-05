"""Diagnostics stay on the machine running Hermes: the debug bundle is saved as a local archive.

This fork uploads nothing (FORK.md). ``hermes debug share``, the CLI and chat ``/debug`` commands, the
dashboard's debug report action and the desktop's "Save diagnostics" each write a zip under the
profile's ``logs/debug-reports/`` and report its path, for the user to review and attach to an issue.
Logs can hold conversation content, so archives are created owner-only.
"""

from __future__ import annotations

import datetime
import os
import zipfile
from pathlib import Path

from hermes_constants import get_hermes_home, mkdir_under_hermes_home


def debug_reports_dir() -> Path:
    return get_hermes_home() / "logs" / "debug-reports"


def save_debug_archive(bundle: dict[str, str]) -> Path:
    """Write ``bundle`` (label -> text, from ``collect_share_bundle`` plus any attached files) to a new
    zip in :func:`debug_reports_dir` and return its path. ``report`` becomes ``report.txt``; every
    other label already names its file (``agent.log``, ``client/desktop.log``)."""
    directory = mkdir_under_hermes_home(debug_reports_dir())
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d-%H%M%S")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    for attempt in range(100):
        path = directory / f"hermes-debug-{stamp}{f'-{attempt}' if attempt else ''}.zip"
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(fd, "wb") as handle, zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive:
            for label, text in bundle.items():
                if text:
                    archive.writestr("report.txt" if label == "report" else label, text)
        return path
    raise FileExistsError(f"no free debug report name left in {directory} for {stamp}")
