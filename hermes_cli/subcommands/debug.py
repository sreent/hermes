"""``hermes debug`` subcommand parser."""

from __future__ import annotations

import argparse
from typing import Callable


def build_debug_parser(subparsers, *, cmd_debug: Callable) -> None:
    """Attach the ``debug`` subcommand to ``subparsers``."""
    debug_parser = subparsers.add_parser(
        "debug", help="Debug tools — save logs and system info for support",
        description="Debug utilities for Hermes Agent. Use 'hermes debug share' to "
        "save a debug report (system info + recent logs) as an archive on this "
        "machine. Nothing is uploaded: review the archive, then attach it to an "
        "issue if you are reporting a problem.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
    hermes debug share              Save a debug report archive and print its path
    hermes debug share --lines 500  Include more log lines
    hermes debug share --local      Print the report instead of saving an archive
    hermes debug share --no-redact  Keep secrets in the report
    hermes debug delete <url>       Delete a paste an earlier version uploaded
""")
    debug_sub = debug_parser.add_subparsers(dest="debug_command")
    share_parser = debug_sub.add_parser(
        "share", help="Save a debug report as an archive on this machine and print its path")
    share_parser.add_argument(
        "--lines", type=int, default=200,
        help="Number of log lines to include per log file (default: 200)")
    share_parser.add_argument(
        "--local", action="store_true", help="Print the report instead of saving an archive")
    share_parser.add_argument(
        "--no-redact", action="store_true",
        help="Disable secret redaction (default: redact). Logs are normally run through "
            "agent.redact.redact_sensitive_text with force=True so credentials stay out of "
            "the report.")
    delete_parser = debug_sub.add_parser(
        "delete", help="Delete a paste uploaded by an earlier version's 'hermes debug share'")
    delete_parser.add_argument(
        "urls", nargs="*", default=[],
        help="One or more paste URLs to delete (e.g. https://paste.rs/abc123)")
    debug_parser.set_defaults(func=cmd_debug)
