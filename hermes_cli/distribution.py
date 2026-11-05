"""Where this fork of Hermes Agent is published (see FORK.md).

Installs and updates come from this repository, and its users report problems here. Nous
Research's release infrastructure (stable channel, signed release records, packaged desktop and
Termux builds) stays upstream's: ``hermes_cli.source_releases.OFFICIAL_REPOSITORY`` keeps naming it,
and checkouts of this repository follow their branch because it publishes no releases of its own.
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

# What people see is called tuos (FORK.md, "Rebranded as tuos"). Internal names stay Hermes's:
# packages, HERMES_* variables, ~/.hermes, service names and the `hermes` command (`tuos` runs it).
PRODUCT_NAME = "tuos"

_WORD = "A-Za-z0-9_"
# "Hermes Agent" or "Hermes" as a word, in any language's text (CJK puts letters right next to it).
# Not "Hermes Cloud", Nous Research's hosted service; a Nous model such as "Hermes 3" or "Hermes-4-405B";
# the wake word "Hey Hermes", the phrase the voice listener actually hears; or credit to upstream
# ("built on Hermes Agent", "based on Hermes Agent").
_PRODUCT_RE = re.compile(
    rf"(?<![{_WORD}])(?<!Hey )(?<![Bb]uilt on )(?<![Bb]ased on )"
    rf"Hermes(?:[ -]Agent(?![{_WORD}]))?(?![{_WORD}])(?![ -]?(?:Cloud|\d))")

_HERMES_IDENTITY = "You are Hermes Agent, built by Nous Research."
IDENTITY = f"You are {PRODUCT_NAME}, built on Nous Research's open-source Hermes Agent."


def brand(text: str) -> str:
    """``text`` (user-facing copy written for Hermes) naming the product tuos."""
    return _PRODUCT_RE.sub(PRODUCT_NAME, text)


def brand_identity(text: str) -> str:
    """``text`` with Hermes's persona sentence ("You are Hermes Agent, ...") introducing tuos."""
    return text.replace(_HERMES_IDENTITY, IDENTITY)
