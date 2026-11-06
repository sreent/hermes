#!/usr/bin/env python3
"""Generate every app icon, logo and banner in the repo from the tuos mark + platform backgrounds.

Usage (from repo root):
    node scripts/generate-icons.mjs           # write
    node scripts/generate-icons.mjs --check   # verify structure

Sources of truth — two axes, composed per target:
  The mark:           MARK_GLYPHS below (FORK.md, "Rebranded as tuos"): the outlines of four
                      blocky glyphs, t u over o s, with square ends and 45-degree corner cuts.
                      Drawn as vector outlines, so every size renders the same geometry
                      without fonts. The wordmark sets the same glyphs in one row.

  Backgrounds (per platform surface, light/dark):
                      assets/backgrounds/squircle-light.svg   white rounded
                      assets/backgrounds/squircle-dark.svg    #0d1117 rounded
                      assets/backgrounds/squircle-mac-light.svg   mac HIG grid
                      assets/backgrounds/squircle-mac-dark.svg    mac HIG grid
                      Their #ffffff (light) and #0d1117 (dark) fills are slots: TILE_COLORS
                      fills both with tuos's navy, canary and commit builds bring their own
                      pairs, and the mark's ink follows the tile (mark_ink).

  The master SVGs (assets/icon-master.svg light, assets/icon-master-dark.svg
  dark) are GENERATED artifacts — squircle background + the mark centered on
  it at MARK_FRACTION of the plate's width. The light master drives every
  squircle target; the dark master drives the dark-appearance targets. macOS
  is the exception: its icns targets render from an in-memory mac master that
  puts the same squircle on Apple's 824x824 (r=185.4) grid — centered in 1024
  with 100px margins — so the icon matches the size of Apple-template
  neighbors. macOS 26 additionally gets apps/desktop/assets/icon.icon, an Icon
  Composer package of canvas-filling layers (the mark light/dark, plus a
  grayscale mono layer for Clear and Tinted) that the system masks into its
  own squircle; electron-builder compiles it to Assets.car next to the .icns,
  which macOS <= 15 keeps showing.

Desktop build identity comes from HERMES_PAYLOAD_TAG / HERMES_BUILD_COMMIT:
Canary uses yellow/dark-yellow backgrounds. Commit builds use red/dark-red
and a seven-character SHA badge. The mark and tile geometry do not change.
Only apps/desktop outputs use this identity, and not the DMG's volume icon or
background: an installer's disk looks the same on every channel. Website,
bootstrap, dashboard, the banners and the shared master SVGs retain the
default brand.

GENERATED OUTPUTS ARE COMMITTED. Regular builds and installs consume them and
never render; flavored release bundles (canary/commit) render to a product dir.

Rendering: resvg (resvg-py) for SVG -> PNG fidelity at every size.
Containers: Pillow for multi-size .ico, .icns and the two-resolution DMG .tiff.

Dependencies:
    Pillow and resvg-py are core runtime dependencies; run this file with a
    Hermes runtime interpreter (scripts/generate-icons.mjs uses HERMES_PYTHON).

Outputs (102 files):
  assets/icon-master.svg                              generated light master
  assets/icon-master-dark.svg                         generated dark master
  assets/banner.png                                   1145x196 wordmark banner (README)
  apps/desktop/assets/icon.png                        1024x1024 squircle (light)
  apps/desktop/assets/icon.ico                        16,24,32,48,64,128,256
  apps/desktop/assets/icon.icns                       16..1024 (real ICNS)
  apps/desktop/assets/icon-dark.png                   1024x1024 squircle (dark)
  apps/desktop/assets/icon-dark.ico                   16,24,32,48,64,128,256
  apps/desktop/assets/icon-dark.icns                  16..1024 (real ICNS)
  apps/desktop/packaging/dmg-volume.icns              16..1024, a drive with the mark on it (DMG volume)
  apps/desktop/packaging/dmg-background.tiff          769x457 + 1538x914, the DMG window's background
  apps/desktop/assets/icon.icon/icon.json             Icon Composer manifest (macOS 26)
  apps/desktop/assets/icon.icon/Assets/art-*.png      1024 mark (+ commit badge), light/dark
  apps/desktop/assets/icon.icon/Assets/mono.png       1024 Clear/Tinted material (the mark in white)
  apps/bootstrap-installer/src-tauri/icons/icon.icon/**  same package, unbranded (Tauri bundle.icon)
  apps/desktop/assets/appx/<Logo>[.scale-N].png       MSIX logos at 100/125/150/200/400% (wide: squircle centered)
  apps/desktop/assets/appx/Square44x44Logo.targetsize-N[_altform-(light)unplated].png
                                                      taskbar/Start bitmaps 16..256; unplated = dark tile
  apps/desktop/public/apple-touch-icon.png            1024x1024 squircle
  apps/desktop/public/tuos-mark.png                   256x256 squircle, light appearance
  apps/desktop/public/tuos-mark-dark.png              256x256 squircle, dark appearance
  apps/bootstrap-installer/src-tauri/icons/32x32.png       32x32
  apps/bootstrap-installer/src-tauri/icons/128x128.png     128x128
  apps/bootstrap-installer/src-tauri/icons/128x128@2x.png  256x256
  apps/bootstrap-installer/src-tauri/icons/icon.ico        16,32,64,128,256
  apps/bootstrap-installer/src-tauri/icons/icon.icns       16..1024
  apps/bootstrap-installer/public/tuos-mark.png   256x256 squircle mark (light)
  website/static/img/logo.png                     1772x1799 the navy mark alone, transparent (light surfaces)
  website/static/img/logo-dark.png                1772x1799 the white mark alone, transparent (dark surfaces)
  website/static/img/tuos-logo.png                150x150 on white (opaque)
  website/static/img/tuos-logo-dark.png           150x150 on #0d1117 (opaque)
  website/static/img/tuos-banner.png              1145x196 wordmark banner (social card)
  website/static/img/favicon-16x16.png            16x16
  website/static/img/favicon-32x32.png            32x32
  website/static/img/apple-touch-icon.png         180x180
  website/static/img/favicon.ico                  16,32,48
  website/static/img/favicon.svg                  copy of the light master
  web/public/favicon.ico                          16,32,48
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable

from PIL import Image

try:
    import resvg_py
except ImportError:
    sys.exit(
        "resvg-py is missing: run the generator with a Hermes runtime interpreter\n"
        "  (HERMES_PYTHON=<hermes venv python> node scripts/generate-icons.mjs)"
    )

# Copy of hermes_cli.update_channel._CANARY_TAG_RE: builders run this renderer
# on the runtime dependencies without the application package installed
# (Docker, bundles). tests/scripts/test_icon_flavors.py pins it to the canonical one.
_CANARY_TAG_RE = re.compile(
    r"^v(?:0|[1-9]\d{0,2})\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"\+canary\.20\d{6}T\d{6}Z$"
)

# The dark background (#0d1117) behind the opaque dark logo.
DARK_HEX = "#0d1117"
DARK_RGB = (13, 17, 23)
# tuos's navy (FORK.md, "Rebranded as tuos"): the app tile in light and dark appearance alike.
NAVY_HEX = "#13294b"
# The tile fills of the light and dark appearance. The background SVGs are templates whose
# #ffffff (light) and #0d1117 (dark) fills take these; canary and commit builds bring their own.
TILE_COLORS = (NAVY_HEX, NAVY_HEX)
BORDER_FRACTION = 0.0407747197
# The brand ring is switched off everywhere (tiles and the macOS 26 layers):
# a flat plate reads better beside macOS 26's own icons. The ring code stays
# so it can be turned back on in one place.
BORDER_ENABLED = False

# ─── the tuos mark ──────────────────────────────────────────────────────────
#
# Four glyphs (FORK.md, "Rebranded as tuos"), each a list of outlines in units
# of its 13-unit cell: strokes 4 units wide with square ends, a 45-degree cut
# of 2.75 units on each outer corner where a stroke would curve, and counters
# as narrow as 1.5 units (under the t's crossbar, and in the s). The mark is
# filled even-odd, so the o's second outline is its counter. Redesign the mark
# here: every icon, logo, banner and the DMG artwork render from these
# outlines, and hermes_cli/brand_art.py and ui-tui/src/banner.ts draw them in
# quadrant blocks.
MARK_GLYPHS: dict[str, tuple[tuple[tuple[float, float], ...], ...]] = {
    "t": (((3, 0), (7, 0), (7, 3.5), (12, 3.5), (12, 7.5), (7, 7.5), (7, 9), (12, 9), (12, 13),
           (5.75, 13), (3, 10.25), (3, 7.5), (0, 7.5), (0, 3.5), (3, 3.5)),),
    "u": (((0, 0), (4, 0), (4, 9), (9, 9), (9, 0), (13, 0), (13, 10.25), (10.25, 13), (2.75, 13),
           (0, 10.25)),),
    "o": (((2.75, 0), (10.25, 0), (13, 2.75), (13, 10.25), (10.25, 13), (2.75, 13), (0, 10.25),
           (0, 2.75)),
          ((4, 4), (9, 4), (9, 9), (4, 9))),
    "s": (((2.75, 0), (13, 0), (13, 3.25), (4, 3.25), (4, 4.75), (13, 4.75), (13, 10.25),
           (10.25, 13), (0, 13), (0, 9.75), (9, 9.75), (9, 8.25), (0, 8.25), (0, 2.75)),),
}
GLYPH_CELL = 13  # each glyph's square cell; the t is a unit narrower and sits at its left
GLYPH_GAP = 4  # between neighbouring cells, across and down
MARK_LAYOUT = (("t", "u"), ("o", "s"))   # icons and logos: two by two
WORDMARK_LAYOUT = (("t", "u", "o", "s"),)  # banners: one row
# The mark's width as a share of the plate it is centered on.
MARK_FRACTION = 0.62
INKS = {"black": "#000000", "white": "#ffffff"}


def mark_ink(fill: str) -> str:
    """The ink with more contrast against the tile `fill` (WCAG): white on the navy and
    the dark flavour tiles, black on the light canary and commit tiles."""
    value = fill.lstrip("#")
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "black" if (luminance + 0.05) / 0.05 > 1.05 / (luminance + 0.05) else "white"


def appearance_ink(colors: tuple[str, str] | None, appearance: str) -> str:
    """The mark's ink on the light or dark appearance's tile."""
    light, dark = colors or TILE_COLORS
    return mark_ink(dark if appearance == "dark" else light)
# The README banner and the docs site's social card.
BANNER_SIZE = (1145, 196)
# The DMG window's background (electron-builder.config.cjs `dmg`), in window points at 1x; the
# TIFF carries a 2x frame too. The app sits at x=253 and the Applications link at x=512, near y=236.
DMG_BACKGROUND_SIZE = (769, 457)

# ─── MSIX (Windows) asset catalog ───────────────────────────────────────────
# The manifest names only the base files; Windows resolves each through
# resource qualifiers. targetsize-* is what the taskbar, Start and search
# draw — an exact bitmap per slot, so nothing is ever upscaled (the bare 44px
# tile was) — and altform-unplated / altform-lightunplated are the dark- and
# light-theme forms Windows requires to exist even when identical (without
# them it plates the icon itself). electron-builder runs makepri + `makeappx
# /l` as soon as one qualified asset is staged (app-builder-lib
# winAppUtil.isScaledAssetsProvided), so the qualifiers alone wire this in.
APPX_DIR = "apps/desktop/assets/appx"
APPX_SCALES = (100, 125, 150, 200, 400)
APPX_TARGET_SIZES = (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256)
# Base size at scale-100; the wide tile keeps its 100px squircle centered.
APPX_LOGOS: dict[str, int | tuple[int, int]] = {
    "Square44x44Logo": 44,
    "Square150x150Logo": 150,
    "StoreLogo": 50,
    "Wide310x150Logo": (310, 150),
}
# Theme-qualified taskbar forms: (qualifier suffix, render kind). Dark theme
# gets the dark tile like macOS dark mode does; the unqualified file stays the
# light tile for hosts that ignore qualifiers.
APPX_ALTFORMS = (("", "png"), ("_altform-unplated", "png_dark"), ("_altform-lightunplated", "png"))


def appx_scaled(base: int, scale: int) -> int:
    # Microsoft's tables round up (150 @ 125% = 188, 50 @ 125% = 63).
    return math.ceil(base * scale / 100 - 1e-9)


def appx_targets() -> list[tuple[str, str, object]]:
    targets: list[tuple[str, str, object]] = []
    for name, base in APPX_LOGOS.items():
        for scale in APPX_SCALES:
            qualifier = "" if scale == 100 else f".scale-{scale}"
            if isinstance(base, tuple):
                w, h = base
                arg: object = (appx_scaled(w, scale), appx_scaled(h, scale), appx_scaled(100, scale))
                targets.append((f"{APPX_DIR}/{name}{qualifier}.png", "wide", arg))
            else:
                targets.append((f"{APPX_DIR}/{name}{qualifier}.png", "png", appx_scaled(base, scale)))
    for size in APPX_TARGET_SIZES:
        for suffix, kind in APPX_ALTFORMS:
            targets.append((f"{APPX_DIR}/Square44x44Logo.targetsize-{size}{suffix}.png", kind, size))
    return targets


APPX_TARGETS = appx_targets()


def _appx_check_sizes() -> dict[str, tuple[str, tuple[int, int]]]:
    sizes: dict[str, tuple[str, tuple[int, int]]] = {}
    for rel, kind, arg in APPX_TARGETS:
        if kind == "wide":
            w, h, _tile = arg  # type: ignore[misc]
            sizes[rel] = ("PNG", (w, h))
        else:
            sizes[rel] = ("PNG", (arg, arg))  # type: ignore[arg-type]
    return sizes


# Target sizes for --check's structural verification: relpath -> (format, size)
CHECK_SIZES: dict[str, tuple[str, tuple[int, int]]] = {
    **_appx_check_sizes(),
    "apps/desktop/assets/icon.png": ("PNG", (1024, 1024)),
    "apps/desktop/assets/icon-dark.png": ("PNG", (1024, 1024)),
    "apps/desktop/packaging/dmg-volume.icns": ("ICNS", (1024, 1024)),
    "apps/desktop/packaging/dmg-background.tiff": ("TIFF", DMG_BACKGROUND_SIZE),
    "assets/banner.png": ("PNG", BANNER_SIZE),
    "website/static/img/tuos-banner.png": ("PNG", BANNER_SIZE),
    **({"apps/desktop/assets/icon.icon/Assets/border-light.png": ("PNG", (1024, 1024)),
        "apps/desktop/assets/icon.icon/Assets/border-dark.png": ("PNG", (1024, 1024))} if BORDER_ENABLED else {}),
    "apps/desktop/assets/icon.icon/Assets/mono.png": ("PNG", (1024, 1024)),
    "apps/bootstrap-installer/src-tauri/icons/icon.icon/Assets/art-light.png": ("PNG", (1024, 1024)),
    "apps/bootstrap-installer/src-tauri/icons/icon.icon/Assets/art-dark.png": ("PNG", (1024, 1024)),
    "apps/bootstrap-installer/src-tauri/icons/icon.icon/Assets/mono.png": ("PNG", (1024, 1024)),
    "apps/desktop/assets/icon.icon/Assets/art-light.png": ("PNG", (1024, 1024)),
    "apps/desktop/assets/icon.icon/Assets/art-dark.png": ("PNG", (1024, 1024)),
    "apps/desktop/public/apple-touch-icon.png": ("PNG", (1024, 1024)),
    "apps/desktop/public/tuos-mark.png": ("PNG", (256, 256)),
    "apps/desktop/public/tuos-mark-dark.png": ("PNG", (256, 256)),
    "apps/bootstrap-installer/src-tauri/icons/32x32.png": ("PNG", (32, 32)),
    "apps/bootstrap-installer/src-tauri/icons/128x128.png": ("PNG", (128, 128)),
    "apps/bootstrap-installer/src-tauri/icons/128x128@2x.png": ("PNG", (256, 256)),
    "apps/bootstrap-installer/public/tuos-mark.png": ("PNG", (256, 256)),
    "website/static/img/logo.png": ("PNG", (1772, 1799)),
    "website/static/img/logo-dark.png": ("PNG", (1772, 1799)),
    "website/static/img/tuos-logo.png": ("PNG", (150, 150)),
    "website/static/img/tuos-logo-dark.png": ("PNG", (150, 150)),
    "website/static/img/favicon-16x16.png": ("PNG", (16, 16)),
    "website/static/img/favicon-32x32.png": ("PNG", (32, 32)),
    "website/static/img/apple-touch-icon.png": ("PNG", (180, 180)),
}

# (relpath, kind, arg)
TARGETS: list[tuple[str, str, object]] = [
    ("assets/icon-master.svg", "svg", None),
    ("assets/icon-master-dark.svg", "svg_dark", None),
    ("assets/banner.png", "banner", None),
    ("apps/desktop/assets/icon.png", "png", 1024),
    ("apps/desktop/assets/icon.ico", "ico", [16, 24, 32, 48, 64, 128, 256]),
    ("apps/desktop/assets/icon.icns", "icns", None),
    ("apps/desktop/assets/icon-dark.png", "png_dark", 1024),
    ("apps/desktop/assets/icon-dark.ico", "ico_dark", [16, 24, 32, 48, 64, 128, 256]),
    ("apps/desktop/assets/icon-dark.icns", "icns_dark", None),
    # The DMG volume icon: a drive with the mark on its face, one artwork for
    # light and dark (volume icons have no appearance variants).
    ("apps/desktop/packaging/dmg-volume.icns", "dmg_volume", None),
    ("apps/desktop/packaging/dmg-background.tiff", "dmg_background", None),
    ("apps/desktop/assets/icon.icon/icon.json", "icon_manifest", None),
    *([("apps/desktop/assets/icon.icon/Assets/border-light.png", "icon_border", "#000000"),
       ("apps/desktop/assets/icon.icon/Assets/border-dark.png", "icon_border", "#ffffff")] if BORDER_ENABLED else []),
    ("apps/desktop/assets/icon.icon/Assets/art-light.png", "icon_art", "light"),
    ("apps/desktop/assets/icon.icon/Assets/art-dark.png", "icon_art", "dark"),
    ("apps/desktop/assets/icon.icon/Assets/mono.png", "icon_mono", None),
    *APPX_TARGETS,
    ("apps/desktop/public/apple-touch-icon.png", "png", 1024),
    # The dev-run Dock icon (app.dock.setIcon): same mac grid as the icns.
    ("apps/desktop/assets/icon-mac.png", "png_mac", 1024),
    ("apps/desktop/public/tuos-mark.png", "mark_light", 256),
    ("apps/desktop/public/tuos-mark-dark.png", "mark_dark", 256),
    ("apps/bootstrap-installer/src-tauri/icons/32x32.png", "png", 32),
    ("apps/bootstrap-installer/src-tauri/icons/128x128.png", "png", 128),
    ("apps/bootstrap-installer/src-tauri/icons/128x128@2x.png", "png", 256),
    ("apps/bootstrap-installer/src-tauri/icons/icon.ico", "ico", [16, 32, 64, 128, 256]),
    ("apps/bootstrap-installer/src-tauri/icons/icon.icns", "icns", None),
    # Tauri's bundler compiles an Icon Composer package from `bundle.icon`
    # (actool >= 26) into Assets.car; the unbranded twin of the desktop package.
    ("apps/bootstrap-installer/src-tauri/icons/icon.icon/icon.json", "icon_manifest", None),
    ("apps/bootstrap-installer/src-tauri/icons/icon.icon/Assets/art-light.png", "icon_art", "light"),
    ("apps/bootstrap-installer/src-tauri/icons/icon.icon/Assets/art-dark.png", "icon_art", "dark"),
    ("apps/bootstrap-installer/src-tauri/icons/icon.icon/Assets/mono.png", "icon_mono", None),
    ("apps/bootstrap-installer/public/tuos-mark.png", "mark_light", 256),
    ("website/static/img/logo.png", "logo", None),
    ("website/static/img/logo-dark.png", "logo_dark", None),
    ("website/static/img/tuos-logo.png", "png_white", 150),
    ("website/static/img/tuos-logo-dark.png", "png_dark_white", 150),
    ("website/static/img/tuos-banner.png", "banner", None),
    ("website/static/img/favicon-16x16.png", "png", 16),
    ("website/static/img/favicon-32x32.png", "png", 32),
    ("website/static/img/apple-touch-icon.png", "png", 180),
    ("website/static/img/favicon.ico", "ico", [16, 32, 48]),
    ("website/static/img/favicon.svg", "svg_copy", None),
    ("web/public/favicon.ico", "ico", [16, 32, 48]),
]

# ─── the mark as vector cells ───────────────────────────────────────────────

class IconArt:
    """One generation's rendering inputs; never writes to source."""

    def __init__(self, source: Path, *, colors: tuple[str, str] | None = None, commit: str = ""):
        self.source = source
        self.colors = colors
        self.commit = commit
        self.backgrounds = source / "assets" / "backgrounds"
        self.master = compose_svg(self, "squircle-light.svg")
        self.master_dark = compose_svg(self, "squircle-dark.svg")
        # macOS icons sit on Apple's 824-on-1024 grid, not the full-bleed
        # squircle: same art, mac-grid backgrounds, icns targets only.
        self.master_mac = compose_svg(self, "squircle-mac-light.svg")
        self.master_mac_dark = compose_svg(self, "squircle-mac-dark.svg")
        # Badge-free twins for direct renders below BADGE_MIN_SIZE.
        self.master_small = compose_svg(self, "squircle-light.svg", badge=False)
        self.master_dark_small = compose_svg(self, "squircle-dark.svg", badge=False)


def mark_geometry(layout: tuple[tuple[str, ...], ...] = MARK_LAYOUT) -> tuple[str, int, int]:
    """Path data of a glyph layout in units, and its width and height. Each glyph sits in its cell,
    GLYPH_GAP from its neighbours; one path, so the whole layout fills in one pass."""
    pitch = GLYPH_CELL + GLYPH_GAP
    parts = []
    for row, glyphs in enumerate(layout):
        for col, glyph in enumerate(glyphs):
            for outline in MARK_GLYPHS[glyph]:
                points = " L".join(f"{col * pitch + x:g} {row * pitch + y:g}" for x, y in outline)
                parts.append(f"M{points}Z")
    width = len(layout[0]) * pitch - GLYPH_GAP
    height = len(layout) * pitch - GLYPH_GAP
    return "".join(parts), width, height


def mark_layer(
    ink: str, box: tuple[float, float, float, float],
    layout: tuple[tuple[str, ...], ...] = MARK_LAYOUT,
) -> str:
    """Nested-svg layer: the glyph layout fitted into `box`, centered; 'meet'
    keeps its proportions. `ink` is "black", "white" or a colour."""
    d, width, height = mark_geometry(layout)
    x, y, w, h = box
    return (
        f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="0 0 {width} {height}" '
        'preserveAspectRatio="xMidYMid meet">\n'
        f'    <path fill="{INKS.get(ink, ink)}" fill-rule="evenodd" d="{d}"/>\n'
        "  </svg>"
    )


def plate_box(x: float, y: float, width: float, height: float) -> tuple[float, float, float, float]:
    """The square the mark fills on a plate: MARK_FRACTION of its width, centered."""
    side = width * MARK_FRACTION
    return (x + (width - side) / 2, y + (height - side) / 2, side, side)


def background_inner(art: IconArt, name: str) -> tuple[str, int, int]:
    """Inner content + (width, height) of a background SVG asset."""
    text = (art.backgrounds / name).read_text(encoding="utf-8-sig")
    light, dark = art.colors or TILE_COLORS
    text = text.replace('fill="#ffffff"', f'fill="{light}"').replace(f'fill="{DARK_HEX}"', f'fill="{dark}"')
    root = ET.fromstring(text)
    m = re.fullmatch(r"0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)", root.get("viewBox", ""))
    assert m, f"cannot parse viewBox of {name}"
    w, h = float(m.group(1)), float(m.group(2))
    # Editor exports include XML declarations and root-scoped namespaces.
    # Parse away the prolog and retain child namespaces when embedding.
    inner = "".join(ET.tostring(child, encoding="unicode") for child in root)
    return inner, int(w), int(h)


# Five-by-seven lowercase hexadecimal glyphs, one five-bit row at a time.
# Vector cells keep release builds deterministic without any installed fonts.
HEX_GLYPHS = {
    "0": (14, 17, 19, 21, 25, 17, 14),
    "1": (4, 12, 4, 4, 4, 4, 14),
    "2": (14, 17, 1, 2, 4, 8, 31),
    "3": (30, 1, 1, 14, 1, 1, 30),
    "4": (2, 6, 10, 18, 31, 2, 2),
    "5": (31, 16, 16, 30, 1, 1, 30),
    "6": (14, 16, 16, 30, 17, 17, 14),
    "7": (31, 1, 2, 4, 8, 8, 8),
    "8": (14, 17, 17, 14, 17, 17, 14),
    "9": (14, 17, 17, 15, 1, 1, 14),
    "a": (0, 0, 14, 1, 15, 17, 15),
    "b": (16, 16, 30, 17, 17, 17, 30),
    "c": (0, 0, 14, 16, 16, 17, 14),
    "d": (1, 1, 15, 17, 17, 17, 15),
    "e": (0, 0, 14, 17, 31, 16, 14),
    "f": (6, 9, 8, 28, 8, 8, 8),
}


# Commit badge plate and glyph origin on the 1024 canvas.
BADGE_RECT = (160, 28, 704, 152)
BADGE_GLYPH_ORIGIN = (184, 48)
# Below this edge length a direct render carries no badge: the plate's top
# row is then under one device pixel from the badge, whose anti-aliased edge
# would stack coverage on the tile's own corner pixels and change the alpha
# channel between flavors. Nobody reads a SHA at 16px anyway.
BADGE_MIN_SIZE = 32


def commit_layer(commit: str, bg: str) -> str:
    cells = []
    gx, gy = BADGE_GLYPH_ORIGIN
    for index, char in enumerate(commit[:7]):
        for row, bits in enumerate(HEX_GLYPHS[char]):
            for col in range(5):
                if bits & (1 << (4 - col)):
                    x, y = gx + (index * 6 + col) * 16, gy + row * 16
                    cells.append(f"M{x} {y}h16v16h-16z")
    # The badge follows the tile's mac HIG inset, never the outer canvas.
    transform = f' transform="translate(100 100) scale({824 / 1024})"' if "-mac-" in bg else ""
    bx, by, bw, bh = BADGE_RECT
    return (
        f'<g{transform}><rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="24" fill="#000000"/>'
        f'<path fill="#ffffff" d="{"".join(cells)}"/></g>'
    )


def compose_svg(art: IconArt, bg: str, *, badge: bool = True) -> str:
    """Full svg text: background + the mark centered on its plate, in the
    background's native coordinate space (resvg scales to whatever output size
    is requested, so the composition is size-agnostic). The mark's ink follows
    the plate's fill."""
    inner, w, h = background_inner(art, bg)
    background = ET.fromstring(f"<g>{inner}</g>")
    tile = background.find("{http://www.w3.org/2000/svg}rect")
    assert tile is not None, f"no background rectangle in {bg}"
    geometry = {key: float(tile.attrib[key]) for key in ("x", "y", "width", "height", "rx")}
    silhouette = ET.Element("rect", {key: str(value) for key, value in geometry.items()})
    ink = mark_ink(tile.attrib["fill"])
    if BORDER_ENABLED:
        thickness = geometry["width"] * BORDER_FRACTION
        # An inward stroke keeps the outer platform geometry unchanged. Subtracting
        # the same inset from rx (not scaling rx) keeps the corner thickness uniform.
        inset = {"x": 1, "y": 1, "width": -2, "height": -2, "rx": -1}
        for key, value in geometry.items():
            tile.set(key, str(value + inset[key] * thickness / 2))
        tile.set("stroke", INKS[ink])
        tile.set("stroke-width", str(thickness))
    inner = "".join(ET.tostring(child, encoding="unicode") for child in background)
    clip = ET.tostring(silhouette, encoding="unicode")
    mark = mark_layer(ink, plate_box(geometry["x"], geometry["y"], geometry["width"], geometry["height"]))
    # The badge shares the mark's clip so it can never paint past the plate.
    badge_svg = commit_layer(art.commit, bg) if art.commit and badge else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">\n'
        f'  <defs><clipPath id="icon-silhouette">{clip}</clipPath></defs>\n'
        f"  {inner.strip()}\n"
        f'  <g clip-path="url(#icon-silhouette)">{badge_svg}{mark}</g>\n'
        "</svg>\n"
    )


# ─── macOS 26 layered icon (.icon → Assets.car) ─────────────────────────────
#
# macOS 26 clips every app icon to its own mask and shows legacy .icns art
# inside a glass plate, so a ring drawn around our tile no longer follows the
# visible outline. The .icon package gives the system canvas-filling layers
# to mask itself: the border layer is a band whose OUTER edge is the canvas
# (the system's mask becomes the outline) and whose INNER edge is the mask
# offset inward by the border thickness — constant thickness by construction.
#
# The mask is Apple's smoothed rounded square: a circular arc flanked by two
# cubic easing segments (the Figma corner-smoothing construction). Fitted to
# macOS 26.6.2's own render of a system icon on the 824-on-1024 grid:
# radius 214px, smoothing 0.645 (rms 0.32px, worst 0.81px). Layers are
# placed on that grid by the system, so in layer coordinates the mask fills
# the canvas.
MAC_MASK_RADIUS_FRACTION = 214.0 / 824.0
MAC_MASK_SMOOTHING = 0.645
ICON_CANVAS = 1024


def _cubic(p0, p1, p2, p3, t: float) -> tuple[float, float]:
    u = 1.0 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])


def _mask_corner(side: float, samples: int) -> list[tuple[float, float]]:
    """Top-left corner with the tile corner at the origin, running clockwise
    from the left edge (0, p) around to the top edge (p, 0)."""
    radius = side * MAC_MASK_RADIUS_FRACTION
    smoothing = MAC_MASK_SMOOTHING
    p = min((1 + smoothing) * radius, side / 2)
    arc_measure = 90 * (1 - smoothing)
    arc_len = math.sin(math.radians(arc_measure / 2)) * radius * math.sqrt(2)
    angle_alpha = (90 - arc_measure) / 2
    p3p4 = radius * math.tan(math.radians(angle_alpha / 2))
    angle_beta = 45 * smoothing
    c = p3p4 * math.cos(math.radians(angle_beta))
    d = c * math.tan(math.radians(angle_beta))
    b = (p - arc_len - c - d) / 3
    a = 2 * b
    # Trace the construction's top-right corner (corner at the origin, x <= 0):
    # easing cubic, circular arc, easing cubic.
    pts: list[tuple[float, float]] = []
    p0 = (-p, 0.0)
    p1, p2, p3 = (p0[0] + a, 0.0), (p0[0] + a + b, 0.0), (p0[0] + a + b + c, d)
    for i in range(samples):
        pts.append(_cubic(p0, p1, p2, p3, i / samples))
    length = math.hypot(c, d)
    nx, ny = -d / length, c / length
    cx, cy = p3[0] + nx * radius, p3[1] + ny * radius
    start = math.atan2(p3[1] - cy, p3[0] - cx)
    for i in range(samples):
        angle = start + math.radians(arc_measure) * i / samples
        pts.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    p4 = (p3[0] + arc_len, p3[1] + arc_len)
    p5, p6, p7 = (p4[0] + d, p4[1] + c), (p4[0] + d, p4[1] + b + c), (0.0, p)
    for i in range(samples + 1):
        pts.append(_cubic(p4, p5, p6, p7, i / samples))
    # Mirror into the top-left corner and reverse so the run is clockwise.
    return [(-x, y) for x, y in reversed(pts)]


def mac_mask_outline(side: float, samples: int = 96) -> list[tuple[float, float]]:
    """Closed clockwise outline of the macOS 26 icon mask for a tile of `side`."""
    tl = _mask_corner(side, samples)
    tr = [(side - y, x) for x, y in tl]
    br = [(side - x, side - y) for x, y in tl]
    bl = [(y, side - x) for x, y in tl]
    outline: list[tuple[float, float]] = []
    for point in tl + tr + br + bl:
        if not outline or math.hypot(point[0] - outline[-1][0], point[1] - outline[-1][1]) > 1e-9:
            outline.append(point)
    return outline


def offset_inward(points: list[tuple[float, float]], distance: float) -> list[tuple[float, float]]:
    """Parallel curve `distance` inside a convex closed outline."""
    count = len(points)
    cx = sum(x for x, _ in points) / count
    cy = sum(y for _, y in points) / count
    result = []
    for i, (x, y) in enumerate(points):
        px, py = points[i - 1]
        qx, qy = points[(i + 1) % count]
        tx, ty = qx - px, qy - py
        length = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / length, tx / length
        if (cx - x) * nx + (cy - y) * ny < 0:
            nx, ny = -nx, -ny
        result.append((x + nx * distance, y + ny * distance))
    return result


def closed_path(points: list[tuple[float, float]]) -> str:
    """SVG path through the points as a closed Catmull-Rom spline (cubic Beziers)."""
    count = len(points)
    parts = [f"M{points[0][0]:.3f} {points[0][1]:.3f}"]
    for i in range(count):
        p0, p1 = points[(i - 1) % count], points[i]
        p2, p3 = points[(i + 1) % count], points[(i + 2) % count]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        parts.append(f"C{c1[0]:.3f} {c1[1]:.3f} {c2[0]:.3f} {c2[1]:.3f} {p2[0]:.3f} {p2[1]:.3f}")
    parts.append("Z")
    return "".join(parts)


def icon_border_svg(ink: str) -> str:
    """Border layer: the canvas minus the mask's inward offset (even-odd)."""
    thickness = ICON_CANVAS * BORDER_FRACTION
    inner = closed_path(offset_inward(mac_mask_outline(float(ICON_CANVAS)), thickness))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ICON_CANVAS} {ICON_CANVAS}">\n'
        f'  <path d="M0 0H{ICON_CANVAS}V{ICON_CANVAS}H0Z {inner}" fill="{ink}" fill-rule="evenodd"/>\n'
        "</svg>\n"
    )


def icon_art_svg(art: IconArt, ink: str) -> str:
    """Art layer: the mark centered on the canvas-filling plate, as on the
    squircle; the commit badge rides along for commit builds."""
    bg = "icon.icon"  # the plate is the canvas; the system supplies the grid
    badge = f"  {commit_layer(art.commit, bg)}\n" if art.commit else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ICON_CANVAS} {ICON_CANVAS}">\n'
        f"{badge}"
        f"  {mark_layer(ink, plate_box(0, 0, ICON_CANVAS, ICON_CANVAS))}\n"
        "</svg>\n"
    )


def icon_color(hex_color: str) -> str:
    """Icon Composer colour literal for an opaque sRGB hex colour."""
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return f"srgb:{r:.5f},{g:.5f},{b:.5f},1.00000"


# Mono (Clear/Tinted) materials, as luminance + opacity: the mark is white,
# fully visible, and the ring (when enabled) is a soft light glass.
MONO_MARK = (1.0, 1.0)
MONO_RING = (0.82, 0.75)


def icon_mono_image(art: IconArt) -> Image.Image:
    """The single grayscale layer behind Clear light/dark and Tinted light/dark
    (Apple's "tinted" specialization). One image, each pixel painted once, so
    translucent materials never stack where the mark meets the ring."""
    def coverage(svg: str) -> Image.Image:
        return render_svg(svg, ICON_CANVAS).convert("RGBA").getchannel("A")

    def material(tone: float, opacity: float, alpha: Image.Image) -> Image.Image:
        grey = round(tone * 255)
        layer = Image.new("RGBA", alpha.size, (grey, grey, grey, 0))
        layer.putalpha(alpha.point(lambda v: round(v * opacity)))
        return layer

    out = Image.new("RGBA", (ICON_CANVAS, ICON_CANVAS), (0, 0, 0, 0))
    paints = [(coverage(icon_art_svg(art, "white")), MONO_MARK)]
    if BORDER_ENABLED:
        paints.append((coverage(icon_border_svg("#ffffff")), MONO_RING))
    for alpha, (tone, opacity) in paints:
        # paste, not composite: a later material replaces an earlier one
        out.paste(material(tone, opacity, alpha), (0, 0), alpha.point(lambda v: 255 if v > 127 else 0))
    return out


def icon_manifest(art: IconArt) -> str:
    """icon.json: flat brand fill (flavoured for canary/commit builds), the
    art layer (and ring, when enabled) with light/dark variants, and the mono
    layer that replaces them under Clear and Tinted."""
    light, dark = art.colors or TILE_COLORS

    def layer(name: str) -> dict:
        # No fixed "image-name": actool treats it as the image for every
        # appearance and drops the specializations, so the dark variant would
        # never reach Assets.car (a black mark on the dark fill).
        return {
            "name": name,
            "image-name-specializations": [
                {"value": f"{name}-light.png"},
                {"appearance": "dark", "value": f"{name}-dark.png"},
            ],
            "glass": False,
            "hidden-specializations": [{"value": False}, {"appearance": "tinted", "value": True}],
        }

    # "tinted" is the single mono annotation behind Clear light/dark and
    # Tinted light/dark: the system reads luminance as visibility and tints it.
    mono = {
        "name": "mono",
        "image-name": "mono.png",
        "glass": True,
        "hidden-specializations": [{"value": True}, {"appearance": "tinted", "value": False}],
    }
    layers = ([layer("border")] if BORDER_ENABLED else []) + [layer("art"), mono]

    manifest = {
        "fill-specializations": [
            {"value": {"solid": icon_color(light)}},
            {"appearance": "dark", "value": {"solid": icon_color(dark)}},
        ],
        "groups": [{
            "lighting": "individual",
            "specular": False,
            "translucency": {"enabled": False, "value": 0},
            "shadow": {"kind": "none", "opacity": 0},
            "blur-material": None,
            "layers": layers,
        }],
        "supported-platforms": {"squares": "shared"},
    }
    return json.dumps(manifest, indent=2) + "\n"


# ─── rendering ──────────────────────────────────────────────────────────────

def render(master: str, size: int, *, background: str | None = None) -> Image.Image:
    """Render a master to an RGBA PNG of `size`x`size`."""
    data = resvg_py.svg_to_bytes(
        svg_string=master, width=size, height=size, background=background
    )
    return Image.open(io.BytesIO(data)).convert("RGBA")


def render_svg(svg: str, size: int | tuple[int, int]) -> Image.Image:
    if isinstance(size, int):
        w = h = size
    else:
        w, h = size
    data = resvg_py.svg_to_bytes(svg_string=svg, width=w, height=h)
    return Image.open(io.BytesIO(data)).convert("RGBA")


def paste_centered(canvas: Image.Image, img: Image.Image) -> None:
    x = (canvas.width - img.width) // 2
    y = (canvas.height - img.height) // 2
    canvas.alpha_composite(img, (x, y))


def save_png(img: Image.Image, buf: io.BytesIO) -> None:
    """Save with alpha preserved. Flat art quantizes losslessly to an 8-bit
    palette (tRNS per-index alpha keeps the AA edges), so use that when the
    palette round-trips pixel-identically; fall back to RGBA otherwise."""
    if img.mode != "RGBA":
        img.convert("RGBA").save(buf, "PNG", optimize=True)
        return
    quantized = img.quantize(colors=256, method=Image.FASTOCTREE, dither=Image.NONE)
    if quantized.convert("RGBA").tobytes() == img.tobytes():
        quantized.save(buf, "PNG", optimize=True)
    else:
        img.save(buf, "PNG", optimize=True)


def mark_tile(art: IconArt, kind: str, size: int) -> Image.Image:
    """The mark in the app-icon squircle (BrandMark asset): the mark IS the
    icon shape, on the light (mark_light) or dark (mark_dark) appearance's tile."""
    bg = "squircle-light.svg" if kind == "mark_light" else "squircle-dark.svg"
    return render_svg(compose_svg(art, bg), size)


def build_logo_image(art: IconArt, dark: bool = False) -> Image.Image:
    """1772x1799 logo: the mark alone on transparency (no frame), centered.
    Light = navy mark, dark = white mark — the consuming surface's background
    shows through."""
    W, H = 1772, 1799
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">\n  {mark_layer("white" if dark else NAVY_HEX, (0, 0, W, H))}\n</svg>\n'
    return render_svg(svg, (W, H))


def dot_grid(width: float, height: float, pitch: float, dot: float, fill: str) -> str:
    """A regular grid of square dots: the pixel paper the banner and the DMG artwork sit on."""
    offset = (pitch - dot) / 2
    cells = "".join(
        f"M{x * pitch + offset:g} {y * pitch + offset:g}h{dot:g}v{dot:g}h{-dot:g}z"
        for y in range(math.ceil(height / pitch)) for x in range(math.ceil(width / pitch))
    )
    return f'<path fill="{fill}" d="{cells}"/>'


def banner_svg() -> str:
    """The wordmark in white on navy, half the banner's height."""
    W, H = BANNER_SIZE
    _, width, height = mark_geometry(WORDMARK_LAYOUT)
    h = H / 2
    w = h * width / height
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">\n'
        f'  <rect width="{W}" height="{H}" fill="{NAVY_HEX}"/>\n'
        f"  {dot_grid(W, H, 28, 4, '#1d3760')}\n"
        f"  {mark_layer('white', ((W - w) / 2, (H - h) / 2, w, h), WORDMARK_LAYOUT)}\n"
        "</svg>\n"
    )


# The DMG artwork's paper and ink. Light paper keeps Finder's black icon labels readable.
DMG_PAPER = "#f4f4f1"
DMG_DOTS = "#e3e3df"
DMG_INK = NAVY_HEX


def dmg_background_svg() -> str:
    """The DMG window: an arrow from the app to the Applications link, 45-degree
    head like the mark's corner cuts, and the wordmark above, on pixel paper."""
    W, H = DMG_BACKGROUND_SIZE
    cx, cy = (253 + 512) / 2, 226  # between the two icons, level with their art
    length, shaft, head = 80, 12, 22
    x0, x1 = cx - length / 2, cx + length / 2
    arrow = (f"M{x0} {cy - shaft / 2}H{x1 - head}V{cy - head}L{x1} {cy}L{x1 - head} {cy + head}"
             f"V{cy + shaft / 2}H{x0}Z")
    _, width, height = mark_geometry(WORDMARK_LAYOUT)
    word_height = 21
    word_width = word_height * width / height
    word = (cx - word_width / 2, 64, word_width, word_height)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">\n'
        f'  <rect width="{W}" height="{H}" fill="{DMG_PAPER}"/>\n'
        f"  {dot_grid(W, H, 24, 3, DMG_DOTS)}\n"
        f'  <path fill="{DMG_INK}" d="{arrow}"/>\n'
        f"  {mark_layer(DMG_INK, word, WORDMARK_LAYOUT)}\n"
        "</svg>\n"
    )


def dmg_background_tiff() -> bytes:
    """A 1x frame at 72 dpi and a 2x frame at 144 dpi in one TIFF, which dmgbuild
    hands to Finder untouched. Each frame is a direct render, not a resample."""
    W, H = DMG_BACKGROUND_SIZE
    svg = dmg_background_svg()
    frames = []
    for scale, dpi in ((1, 72), (2, 144)):
        single = io.BytesIO()
        render_svg(svg, (W * scale, H * scale)).convert("RGB").save(
            single, "TIFF", compression="tiff_lzw", dpi=(dpi, dpi))
        frames.append(Image.open(io.BytesIO(single.getvalue())))
    out = io.BytesIO()
    # No `dpi` here: each frame keeps the resolution its own encode recorded.
    frames[0].save(out, "TIFF", compression="tiff_lzw", save_all=True, append_images=frames[1:])
    return out.getvalue()


def dmg_volume_svg() -> str:
    """The DMG's volume icon: a light drive with 45-degree corners and the mark on its face."""
    c = ICON_CANVAS
    x, y, w, h, cut = 208, 120, 608, 784, 72
    body = (f"M{x + cut} {y}H{x + w - cut}L{x + w} {y + cut}V{y + h - cut}L{x + w - cut} {y + h}"
            f"H{x + cut}L{x} {y + h - cut}V{y + cut}Z")
    band = y + h - 128
    side = 340
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {c} {c}">\n'
        '  <defs><linearGradient id="drive" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#fbfbfa"/><stop offset="1" stop-color="#e4e4e1"/></linearGradient>'
        f'<clipPath id="body"><path d="{body}"/></clipPath></defs>\n'
        f'  <path d="{body}" fill="url(#drive)" stroke="#b9b9b5" stroke-width="6"/>\n'
        f'  <rect x="{x}" y="{band}" width="{w}" height="{h}" fill="#d6d6d2" clip-path="url(#body)"/>\n'
        f'  <rect x="{x + w - 120}" y="{band + 52}" width="48" height="24" fill="#3c3c3c"/>\n'
        f"  {mark_layer(NAVY_HEX, ((c - side) / 2, y + 150, side, side))}\n"
        "</svg>\n"
    )


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _quantized_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    save_png(img, buf)
    return buf.getvalue()


def _icns(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    frames = [img.resize((s, s), Image.LANCZOS) for s in (16, 32, 64, 128, 256, 512, 1024)]
    img.save(buf, format="ICNS", append_images=frames[1:])
    return buf.getvalue()


# Whole-image artwork: one picture per kind, with no per-target argument.
ARTWORK: dict[str, Callable[[IconArt], bytes]] = {
    "logo": lambda art: _png(build_logo_image(art, dark=False)),
    "logo_dark": lambda art: _png(build_logo_image(art, dark=True)),
    "banner": lambda art: _quantized_png(render_svg(banner_svg(), BANNER_SIZE)),
    "dmg_background": lambda art: dmg_background_tiff(),
    "dmg_volume": lambda art: _icns(render_svg(dmg_volume_svg(), ICON_CANVAS)),
}


def target_bytes(art: IconArt, kind: str, arg: object) -> bytes:
    """Produce the exact bytes for one target. Shared by write + check."""
    if kind == "svg":
        return art.master.encode("utf-8")
    if kind == "svg_dark":
        return art.master_dark.encode("utf-8")
    if kind == "svg_copy":
        return art.master.encode("utf-8")
    if kind == "icon_manifest":
        return icon_manifest(art).encode("utf-8")
    if kind in ARTWORK:
        return ARTWORK[kind](art)

    buf = io.BytesIO()
    if kind == "png":
        save_png(render(art.master if arg >= BADGE_MIN_SIZE else art.master_small, arg), buf)
    elif kind == "png_mac":
        save_png(render(art.master_mac, arg), buf)
    elif kind == "png_dark":
        save_png(render(art.master_dark if arg >= BADGE_MIN_SIZE else art.master_dark_small, arg), buf)
    elif kind == "png_white":
        render(art.master, arg, background="#ffffff").convert("RGB").save(buf, "PNG", optimize=True)
    elif kind == "png_dark_white":
        render(art.master_dark, arg, background=DARK_HEX).convert("RGB").save(buf, "PNG", optimize=True)
    elif kind in ("mark_light", "mark_dark"):
        save_png(mark_tile(art, kind, arg), buf)
    elif kind == "icon_border":
        save_png(render_svg(icon_border_svg(arg), ICON_CANVAS), buf)
    elif kind == "icon_art":
        save_png(render_svg(icon_art_svg(art, appearance_ink(art.colors, arg)), ICON_CANVAS), buf)
    elif kind == "icon_mono":
        save_png(icon_mono_image(art), buf)
    elif kind == "ico":
        img = render(art.master, max(arg))
        img.save(buf, format="ICO", sizes=[(s, s) for s in arg])
    elif kind == "ico_dark":
        img = render(art.master_dark, max(arg))
        img.save(buf, format="ICO", sizes=[(s, s) for s in arg])
    elif kind == "icns":
        img = render(art.master_mac, 1024)
        frames = [img.resize((s, s), Image.LANCZOS) for s in (16, 32, 64, 128, 256, 512, 1024)]
        img.save(buf, format="ICNS", append_images=frames[1:])
    elif kind == "icns_dark":
        img = render(art.master_mac_dark, 1024)
        frames = [img.resize((s, s), Image.LANCZOS) for s in (16, 32, 64, 128, 256, 512, 1024)]
        img.save(buf, format="ICNS", append_images=frames[1:])
    elif kind == "wide":
        w, h, tile = arg
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        paste_centered(canvas, render(art.master, tile))
        canvas.save(buf, "PNG")
    else:
        raise ValueError(f"unknown kind {kind!r}")
    return buf.getvalue()


def build_art(source: Path) -> tuple[IconArt, IconArt]:
    """Only desktop outputs carry build identity. Shared branding stays stable."""
    art = IconArt(source)
    tag = os.environ.get("HERMES_PAYLOAD_TAG", "")
    commit = os.environ.get("HERMES_BUILD_COMMIT", "")
    if commit:
        if tag:
            raise ValueError("Commit builds cannot also select HERMES_PAYLOAD_TAG")
        if not re.fullmatch(r"[a-f0-9]{40}", commit):
            raise ValueError("HERMES_BUILD_COMMIT requires an exact full 40-character SHA")
        return art, IconArt(source, colors=("#e34850", "#4a1117"), commit=commit)
    if _CANARY_TAG_RE.match(tag.strip()):
        return art, IconArt(source, colors=("#f5cc32", "#443808"))
    return art, art


def cmd_write(source: Path, out: Path) -> int:
    """Return failure when any target cannot be generated or verified."""
    art, desktop_art = build_art(source)
    written = 0
    failures = 0
    for rel, kind, arg in TARGETS:
        path = out / rel
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            selected = desktop_art if rel.startswith("apps/desktop/") else art
            path.write_bytes(target_bytes(selected, kind, arg))
            written += 1
        except Exception as exc:
            failures += 1
            print(f"  !! {rel}: FAILED ({exc})")
    print(f"[write] wrote {written}/{len(TARGETS)} files")

    print("\n[verify]")
    for rel, kind, arg in TARGETS:
        path = out / rel
        try:
            if kind in ("svg", "svg_dark", "svg_copy", "icon_manifest"):
                print(f"  {rel}: {path.stat().st_size} bytes {'JSON' if kind == 'icon_manifest' else 'SVG'}")
                continue
            im = Image.open(path)
            if kind in ("ico", "ico_dark"):
                sizes = []
                try:
                    for i in range(im.n_frames):
                        im.seek(i)
                        sizes.append(im.size)
                except Exception:
                    sizes = [im.size]
                print(f"  {rel}: ICO {sorted(set(sizes))}")
            elif kind in ("icns", "icns_dark", "dmg_volume"):
                print(f"  {rel}: ICNS {im.size} (container)")
            else:
                print(f"  {rel}: {im.format} {im.size}")
        except Exception as exc:
            failures += 1
            print(f"  {rel}: VERIFY FAILED ({exc})")

    return int(failures > 0)


def cmd_check(source: Path, out: Path) -> int:
    """Structural verification: regenerate every target in memory and assert
    the invariants that actually matter (there are no committed bytes to
    byte-compare — outputs are generated on demand)."""
    art, desktop_art = build_art(source)
    problems: list[str] = []

    # every target must generate without error
    for rel, kind, arg in TARGETS:
        try:
            selected = desktop_art if rel.startswith("apps/desktop/") else art
            target_bytes(selected, kind, arg)
        except Exception as exc:
            problems.append(f"{rel}: REGENERATE FAILED ({exc})")

    # PNG targets must have the expected format + size
    for rel, (fmt, size) in CHECK_SIZES.items():
        path = out / rel
        if not path.exists():
            problems.append(f"{rel}: MISSING (expected generated file)")
            continue
        try:
            im = Image.open(path)
            if im.format != fmt or im.size != size:
                problems.append(f"{rel}: got {im.format} {im.size}, expected {fmt} {size}")
        except Exception as exc:
            problems.append(f"{rel}: UNREADABLE ({exc})")

    # squircles must keep transparent corners (alpha extrema include 0)
    for rel in (
        "apps/desktop/assets/icon.png",
        "apps/desktop/assets/icon-dark.png",
        "apps/desktop/public/tuos-mark.png",
        "apps/desktop/public/tuos-mark-dark.png",
        "apps/desktop/public/apple-touch-icon.png",
    ):
        path = out / rel
        if not path.exists():
            continue
        alpha = Image.open(path).convert("RGBA").getchannel("A")
        lo, hi = alpha.getextrema()
        if lo != 0 or hi != 255:
            problems.append(f"{rel}: alpha extrema {alpha.getextrema()}, expected (0, 255) transparent corners")

    # containers must have the right frame sets (parse ICO headers directly —
    # PIL's ICO n_frames is unreliable across versions)
    def ico_sizes(path: Path) -> list[int]:
        data = path.read_bytes()
        count = int.from_bytes(data[4:6], "little")
        sizes = []
        for i in range(count):
            entry = data[6 + i * 16 : 6 + (i + 1) * 16]
            w = entry[0] or 256
            sizes.append(w)
        return sorted(set(sizes))

    for rel, sizes in (
        ("apps/desktop/assets/icon.ico", [16, 24, 32, 48, 64, 128, 256]),
        ("apps/desktop/assets/icon-dark.ico", [16, 24, 32, 48, 64, 128, 256]),
        ("apps/bootstrap-installer/src-tauri/icons/icon.ico", [16, 32, 64, 128, 256]),
    ):
        path = out / rel
        if not path.exists():
            problems.append(f"{rel}: MISSING")
            continue
        try:
            got = ico_sizes(path)
            if got != sizes:
                problems.append(f"{rel}: ICO frames {got}, expected {sizes}")
        except Exception as exc:
            problems.append(f"{rel}: UNREADABLE ({exc})")

    if not problems:
        print(f"[ok] all {len(TARGETS)} targets generate and pass structural checks")
        return 0

    print(f"[check] {len(problems)} problem(s):")
    for line in problems:
        print(f"  - {line}")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--out", type=Path, help="Output root (defaults to source for developer builds)")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    out = (args.out or source).resolve()
    command = cmd_check if args.check else cmd_write
    sys.exit(command(source, out))


if __name__ == "__main__":
    main()
