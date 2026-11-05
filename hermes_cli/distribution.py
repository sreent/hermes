"""Where this fork of Hermes Agent is published (see FORK.md).

Installs and updates come from this repository, and its users report problems here. Nous
Research's release infrastructure (stable channel, signed release records, packaged desktop and
Termux builds) stays upstream's: ``hermes_cli.source_releases.OFFICIAL_REPOSITORY`` keeps naming it,
and checkouts of this repository follow their branch because it publishes no releases of its own.
"""

REPOSITORY = "sreent/hermes"
REPO_URL = f"https://github.com/{REPOSITORY}.git"
REPO_URLS = frozenset({
    REPO_URL,
    f"git@github.com:{REPOSITORY}.git",
    f"https://github.com/{REPOSITORY}",
    f"git@github.com:{REPOSITORY}",
})
ISSUES_URL = f"https://github.com/{REPOSITORY}/issues"

# Served from the default branch, so they install what `main` holds.
_SCRIPTS = f"https://raw.githubusercontent.com/{REPOSITORY}/main/scripts"
INSTALL_SH_URL = f"{_SCRIPTS}/install.sh"
INSTALL_PS1_URL = f"{_SCRIPTS}/install.ps1"
INSTALL_SH_COMMAND = f"curl -fsSL {INSTALL_SH_URL} | bash"
INSTALL_PS1_COMMAND = f"iex (irm {INSTALL_PS1_URL})"
