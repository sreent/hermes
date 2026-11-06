"""Icon generation reports per-target failures without hiding later targets."""
import importlib.util
import io
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from PIL import Image


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
@pytest.mark.parametrize("editor_export", [False, True])
def test_svg_readers_accept_bom_without_rewriting_assets(tmp_path, monkeypatch, bom, editor_export):
    monkeypatch.setitem(sys.modules, "resvg_py", ModuleType("resvg_py"))
    script = Path(__file__).resolve().parents[2] / "scripts/generate_icons.py"
    spec = importlib.util.spec_from_file_location("icon_readers_under_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "art.svg"
    element = '<path d="M0 0 L1 1" aria-label="café 東京"/>'
    declaration = '<?xml version="1.0" encoding="UTF-8"?>\n' if editor_export else ""
    namespaces = ' xmlns="http://www.w3.org/2000/svg" xmlns:editor="urn:editor"'
    metadata = '<editor:namedview editor:zoom="1"/>' if editor_export else ""
    document = f'<svg{namespaces} viewBox="0 0 20 30">{metadata}{element}</svg>'
    raw = bom + (declaration + document).encode("utf-8")
    path.write_bytes(raw)
    art = SimpleNamespace(backgrounds=tmp_path, colors=None)
    inner, width, height = module.background_inner(art, path.name)
    composed = ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{inner}</svg>')
    assert (width, height) == (20, 30)
    assert [ET.tostring(child) for child in composed] == [
        ET.tostring(child) for child in ET.fromstring(document)
    ]
    assert path.read_bytes() == raw
    path.write_bytes(bom + b"<svg/>")
    with pytest.raises(AssertionError, match="viewBox"):
        module.background_inner(art, path.name)


@pytest.mark.parametrize("failure", [None, "render", "directory", "verify"])
def test_write_status_includes_every_target(tmp_path, monkeypatch, capsys, failure):
    # The renderer is build-only. This test injects failures at its byte boundary.
    monkeypatch.setitem(sys.modules, "resvg_py", ModuleType("resvg_py"))
    script = Path(__file__).resolve().parents[2] / "scripts" / "generate_icons.py"
    spec = importlib.util.spec_from_file_location("icon_generator_under_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "immutable source"
    source.mkdir()
    monkeypatch.setattr(module, "IconArt", lambda root: root)
    monkeypatch.setattr(sys, "argv", [str(script), "--source", str(source), "--out", str(tmp_path)])

    image = io.BytesIO()
    Image.new("RGBA", (2, 2), (0, 0, 0, 0)).save(image, "PNG")
    good_bytes = image.getvalue()
    first = "blocked/icon.png" if failure == "directory" else "first.png"
    if failure == "directory":
        (tmp_path / "blocked").write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(module, "TARGETS", [(first, "png", "first"), ("last.png", "png", "last")])

    def target_bytes(art, kind, target):
        assert art == source
        assert not list(source.iterdir())
        if target == "first":
            if failure == "render":
                raise RuntimeError("injected render failure")
            if failure == "verify":
                return b"not an image"
        return good_bytes

    monkeypatch.setattr(module, "target_bytes", target_bytes)
    code = 0
    try:
        module.main()
    except SystemExit as stopped:
        code = stopped.code
    assert bool(code) is (failure is not None)
    assert (tmp_path / "last.png").read_bytes() == good_bytes
    output = capsys.readouterr().out
    assert "last.png: PNG (2, 2)" in output
    assert ("FAILED" in output) is (failure is not None)


def _generator(monkeypatch, name):
    monkeypatch.setitem(sys.modules, "resvg_py", ModuleType("resvg_py"))
    script = Path(__file__).resolve().parents[2] / "scripts/generate_icons.py"
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("platform", ["", "mac-"])
@pytest.mark.parametrize("appearance,ink", [("light", "black"), ("dark", "white")])
@pytest.mark.parametrize("colors", [None, ("#f5cc32", "#443808"), ("#e34850", "#4a1117")])
def test_mark_sits_centered_on_the_plain_tile_inside_the_outer_silhouette(monkeypatch, platform, appearance, ink, colors):
    """The tile keeps the background's own geometry and fill with no stroke
    (the ring is disabled), and the mark is centered on it at MARK_FRACTION of
    its width, inside the same clip as the commit badge."""
    module = _generator(monkeypatch, "icon_geometry_under_test")
    assert module.BORDER_ENABLED is False
    source = Path(__file__).resolve().parents[2]
    art = SimpleNamespace(backgrounds=source / "assets/backgrounds", colors=colors, commit="0123456")
    name = f"squircle-{platform}{appearance}.svg"
    ns = {"svg": "http://www.w3.org/2000/svg"}
    original = ET.parse(art.backgrounds / name).find("svg:rect", ns)
    result = ET.fromstring(module.compose_svg(art, ink, name))
    tile = result.find("svg:rect", ns)
    assert original is not None and tile is not None
    geometry = tuple(float(original.attrib[key]) for key in ("x", "y", "width", "height", "rx"))
    assert tuple(float(tile.attrib[key]) for key in ("x", "y", "width", "height", "rx")) == geometry
    assert tile.get("stroke") is None and tile.get("stroke-width") is None
    expected_fill = (colors or ("#ffffff", module.DARK_HEX))[appearance == "dark"]
    assert tile.get("fill") == expected_fill
    clip = result.find("svg:defs/svg:clipPath/svg:rect", ns)
    assert clip is not None
    assert tuple(float(clip.attrib[key]) for key in ("x", "y", "width", "height", "rx")) == geometry
    group = result[-1]
    clip_path = result.find("svg:defs/svg:clipPath", ns)
    assert clip_path is not None and group.get("clip-path") == f"url(#{clip_path.attrib['id']})"
    # The commit badge rides inside the same clip, so its anti-aliased edge can
    # never add alpha outside the plate (visible at targetsize-16..30).
    assert [child.tag for child in group] == [f"{{{ns['svg']}}}g", f"{{{ns['svg']}}}svg"]
    mark = group[-1]
    x, y, width, height, _ = geometry
    box = tuple(float(mark.attrib[key]) for key in ("x", "y", "width", "height"))
    side = width * module.MARK_FRACTION
    assert box == pytest.approx((x + (width - side) / 2, y + (height - side) / 2, side, side))
    assert mark.get("preserveAspectRatio") == "xMidYMid meet"
    assert mark[0].get("fill") == module.INKS[ink]


def test_every_mark_cell_is_one_the_renderer_draws(monkeypatch):
    """A glyph is three rows of three cells, each empty or a known cell shape,
    so a redesigned glyph can never shift its neighbours or draw nothing."""
    module = _generator(monkeypatch, "icon_glyphs_under_test")
    for glyph, rows in module.MARK_GLYPHS.items():
        assert len(rows) == 3 and all(len(row) == 3 for row in rows), glyph
        assert {cell for row in rows for cell in row} <= {".", *module.MARK_CELLS}, glyph
    for layout in (module.MARK_LAYOUT, module.WORDMARK_LAYOUT):
        d, width, height = module.mark_geometry(layout)
        glyphs = [glyph for row in layout for glyph in row]
        assert d.count("M") == sum(cell != "." for glyph in glyphs for row in module.MARK_GLYPHS[glyph] for cell in row)
        assert (width, height) == (len(layout[0]) * 4 - 1, len(layout) * 4 - 1)
        xs = [float(v) for v in re.findall(r"[ML]([\d.]+) ", d)]
        assert min(xs) == 0 and max(xs) == width  # the layout fills its own box
