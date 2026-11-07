"""Where this fork of Hermes Agent is published (see FORK.md).

Installs and updates come from this repository, and its users report problems here. It hosts its
own docs, Docker image and desktop apps. Nous Research's release infrastructure (stable channel,
signed release records, Termux builds) stays upstream's: ``hermes_cli.source_releases.OFFICIAL_REPOSITORY``
keeps naming it, so checkouts of this repository follow their branch.
"""

import re

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

# The container image this repository publishes (.github/workflows/tuos-docker.yml) and its page.
# scripts/fork/relink.py writes it wherever upstream's code and docs name Nous's image.
DOCKER_IMAGE = "ghcr.io/sreent/tuos"
DOCKER_PACKAGE_URL = f"https://github.com/{REPOSITORY}/pkgs/container/tuos"
# The docs site, on GitHub Pages (.github/workflows/tuos-docs.yml), with upstream's page paths:
# Nous's https://hermes-agent.nousresearch.com/docs/<page> is DOCS_URL/<page> here.
DOCS_URL = "https://sreent.github.io/hermes"
# Where the desktop apps are downloaded (.github/workflows/tuos-desktop.yml attaches them to releases).
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"

# What people see is called tuos (FORK.md, "Rebranded as tuos"). Internal names stay Hermes's:
# packages, HERMES_* variables, ~/.hermes, service names and the `hermes` command (`tuos` runs it).
PRODUCT_NAME = "tuos"

# The desktop app's packaging identity, as apps/desktop/product-identity.cjs builds the stable app (keep
# the two in step; a test compares them). The name is the macOS bundle (tuos.app) and the Windows and
# Linux executable (tuos.exe, tuos); the id is its macOS bundle id and Linux app id, and the setup
# installer's is `<id>.setup`. Its state folder keeps Hermes's name (gui_uninstall.desktop_userdata_dir).
DESKTOP_APP_NAME = "tuos"
DESKTOP_APP_ID = "io.github.sreent.tuos"

_WORD = "A-Za-z0-9_"
# "Hermes Agent" or "Hermes" as a word, in any language's text (CJK puts letters right next to it).
# Not "Hermes Cloud", Nous Research's hosted service; a Nous model such as "Hermes 3" or "Hermes-4-405B";
# the wake word "Hey Hermes", the phrase the voice listener actually hears; or credit to upstream
# ("built on Hermes Agent", "based on Hermes Agent").
# Nor a path or app name ("Application Support/Hermes", "Hermes.app", "Hermes.exe"), the middle of a
# hyphenated name such as the X-Hermes-Session-Id header, or the macOS signing certificate's name in the
# keychain ("Hermes Local Signing").
_PRODUCT_RE = re.compile(
    rf"(?<![{_WORD}/\\])(?<!Hey )(?<![Bb]uilt on )(?<![Bb]ased on )(?!(?<=[{_WORD}]-)Hermes-[{_WORD}])"
    rf"Hermes(?:[ -]Agent(?![{_WORD}]))?(?![{_WORD}/\\])(?!\.[A-Za-z])(?![ -]?(?:Cloud|\d)| Local Signing)")
# The command, wherever copy tells someone to run it: `hermes setup`, `hermes -p work ...`, a template's
# `hermes {profile_arg}doctor`, `hermes` in backticks, "the hermes command". Not a path, package or module
# (~/.hermes, /opt/hermes/, hermes-agent, hermes_cli, hermes.exe).
_COMMAND_RE = re.compile(rf"(?<![{_WORD}./\\`-])hermes(?=\s(?:-{{1,2}}[A-Za-z]|[a-z{{])|`)|(?<=`)hermes(?=`|\s)")

_HERMES_IDENTITY = "You are Hermes Agent, built by Nous Research."
IDENTITY = f"You are {PRODUCT_NAME}, built on Nous Research's open-source Hermes Agent."


def brand(text: str) -> str:
    """``text`` (user-facing copy written for Hermes) naming the product, and its command, tuos."""
    return _COMMAND_RE.sub(PRODUCT_NAME, _PRODUCT_RE.sub(PRODUCT_NAME, text))


def brand_identity(text: str) -> str:
    """``text`` with Hermes's persona sentence ("You are Hermes Agent, ...") introducing tuos."""
    return text.replace(_HERMES_IDENTITY, IDENTITY)
