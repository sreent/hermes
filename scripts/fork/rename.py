#!/usr/bin/env python3
"""Rename what people see from Hermes to tuos in code and docs (FORK.md, "Rebranded as tuos").

Re-run it after every upstream merge (FORK.md, "Pulling upstream changes"). It applies
``hermes_cli.distribution.brand`` (the product name and ``hermes <command>`` hints, with its
exceptions: Nous's services and models, the wake word, credit to upstream, paths and app names) to:

* Python: strings that calls show a person: ``print`` and ``input``, the CLI's say/info/fail helpers,
  doctor checks, ``sys.stdout``/``sys.stderr`` writes, anything raised, slash-command descriptions, and
  keyword arguments named for copy (``help=``, ``description=``, ``detail=``...). Docstrings, logging,
  data structures and comparisons are left alone: some of those strings are matched against stored data.
* Python tests: an expectation quoting copy the code now shows renamed follows it (``follow_tests``).
* The desktop app, web dashboard, TUI and docs site's pages: JSX text and string literals in copy
  positions (``scripts/fork/rename_ts.mjs``).
* Docs pages: prose and shell blocks. A line that credits Nous Research keeps its wording.

Files in ``NEVER`` are not touched, nor text in ``KEEP``. Translation catalogs are not rewritten
here: each app brands them as it loads them.

Text renamed in one place but matched as it was in another (a comparison, a search, a list of
markers) would break the match. Each run names such conflicts and exits 3 until they are resolved,
usually by adding the text to ``KEEP``.

    python scripts/fork/rename.py            # rewrite
    python scripts/fork/rename.py --check    # change nothing; exit 1 if anything would change
    python scripts/fork/rename.py --report   # also list strings left as they are, and patterns to review
    python scripts/fork/rename.py --resolve  # mid-merge: settle conflicts the rename caused, then rewrite
"""

from __future__ import annotations

import argparse
import ast
import functools
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hermes_cli.distribution import PRODUCT_NAME, brand

PYTHON_DIRS = ("hermes_cli", "gateway", "tui_gateway", "cron", "tools", "agent", "plugins", "acp_adapter")
PYTHON_FILES = ("cli.py",)
DOC_DIRS = ("website/docs", "website/i18n/zh-Hans/docusaurus-plugin-content-docs/current")

# Never rewritten: the rule itself, text matched against stored data, and the persona/markers the
# fork brands at runtime (agent/prompt_builder.py's block at its end).
NEVER = {
    "hermes_cli/distribution.py", "hermes_cli/default_soul.py", "hermes_cli/brand_art.py",
    "hermes_cli/tuos_command.py", "hermes_cli/left_core_migration.py", "agent/prompt_builder.py",
    "tools/memory_sharing.py", "scripts/fork/rename.py",
}
# Text that keeps its wording: code elsewhere matches on it, or it names something that is not the
# product. Python's and the apps' (scripts/fork/rename_ts.mjs) lists are separate.
KEEP: tuple[str, ...] = ()

# Calls whose string arguments are shown to a person.
OUTPUT_CALLS = {
    "print", "cprint", "_cprint", "input", "color", "echo",
    "print_info", "print_success", "print_warning", "print_error", "print_header", "print_step",
    "_info", "_say", "say", "_err", "_fail", "fail", "_fail_and_issue", "_warn", "warn",
    "check_ok", "check_warn", "check_info", "check_fail", "_print_info_lines", "_plines", "_vlines",
    "log_info", "log_success", "log_warn", "log_error",
    "RuntimeError", "ValueError", "SystemExit", "AuthError", "PluginOperationError", "tool_error",
    "_cli_hint", "Panel", "Text", "CommandDef",
}
# ...as are the arguments of anything raised (``...Error``, ``...Exception``), and keyword arguments
# whose names say they hold copy (``help=``, ``description=``, ``detail=``, ``install_hint=``).
COPY_WORDS = {"caption", "description", "detail", "details", "epilog", "help", "hint", "instructions",
              "label", "message", "note", "placeholder", "remedy", "summary", "text", "title", "tooltip"}
DATA_WORDS = {"cmd", "command", "env", "header", "headers", "id", "key", "kind", "path", "pattern", "prompt",
              "type", "url"}
_STREAMS = {"stdout", "stderr"}
_LOGGERS = re.compile(r"_?(log|logger|logging|LOG|LOGGER)")


def _holds_copy(name: str) -> bool:
    words = set(re.split(r"[^a-z0-9]+", re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()))
    return bool(words & COPY_WORDS) and not words & DATA_WORDS


def _callee(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Attribute):
        owner = func.value
        # sys.stdout.write / sys.stderr.write print; any other .write writes data.
        if func.attr == "write":
            return "write" if isinstance(owner, ast.Attribute) and owner.attr in _STREAMS else ""
        # logger.warn(...), logging.info(...): logs, not copy.
        return "" if isinstance(owner, ast.Name) and _LOGGERS.fullmatch(owner.id) else func.attr
    return func.id if isinstance(func, ast.Name) else ""


def _strings_in(node: ast.AST):
    """String constants (f-string parts included) under an output call's argument, not descending
    into calls that are not themselves output calls."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node
    elif isinstance(node, ast.Call):
        if _callee(node) in OUTPUT_CALLS | {"write", "str", "format", "join", "strip"}:
            for child in (*node.args, *(k.value for k in node.keywords)):
                yield from _strings_in(child)
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"format", "join", "strip"}:
            yield from _strings_in(node.func.value)
    elif isinstance(node, ast.Subscript):  # MESSAGES["key"]: the key is data
        yield from _strings_in(node.value)
    elif isinstance(node, ast.Dict):
        for value in node.values:
            yield from _strings_in(value)
    elif not isinstance(node, (ast.Lambda, ast.Compare)):
        for child in ast.iter_child_nodes(node):
            yield from _strings_in(child)


def _offsets(source: str) -> list[int]:
    starts, total = [0], 0
    for line in source.splitlines(keepends=True):
        total += len(line)
        starts.append(total)
    return starts


def _char_offset(source_lines: list[str], starts: list[int], lineno: int, col_bytes: int) -> int:
    line = source_lines[lineno - 1]
    return starts[lineno - 1] + len(line.encode("utf-8")[:col_bytes].decode("utf-8", "replace"))


_MATCH_CALLS = {"startswith", "endswith", "find", "rfind", "index", "rindex", "count", "search", "match",
                "fullmatch", "compile", "sub", "split", "replace", "removeprefix", "removesuffix"}


def _texts(node: ast.AST | None) -> list[ast.Constant]:
    """A string constant, or the strings of a tuple/list/set of them (``x in ("a", "b")``)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node]
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return [elt for elt in node.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"frozenset", "set", "tuple"}:
        return _texts(node.args[0]) if node.args else []
    return []


def _compares(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Compare) or (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                                              and n.func.attr in _MATCH_CALLS) for n in ast.walk(node))


def matchers(tree: ast.AST) -> list[ast.Constant]:
    """String constants code matches text against: comparisons, searches, and named collections of
    markers it loops over to compare (``any(marker in text for marker in MARKERS)``)."""
    named = {target.id: node.value for node in ast.walk(tree) if isinstance(node, (ast.Assign, ast.AnnAssign))
             for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
             if isinstance(target, ast.Name) and _texts(node.value)}
    found: list[ast.Constant] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            found += [c for part in (node.left, *node.comparators) for c in _texts(part)]
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _MATCH_CALLS:
            found += [c for part in (node.func.value, *node.args) for c in _texts(part)]
        elif isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
            found += [c for gen in node.generators if isinstance(gen.iter, ast.Name) and gen.iter.id in named
                      and (_compares(node.elt) or any(map(_compares, gen.ifs))) for c in _texts(named[gen.iter.id])]
        elif isinstance(node, ast.For) and isinstance(node.iter, ast.Name) and node.iter.id in named:
            found += _texts(named[node.iter.id]) if any(map(_compares, node.body)) else []
    return found


def _phrase(text: str) -> bool:
    return len(text.strip()) >= 16 and re.search(r"\S\s+\S", text) is not None


def overlaps(renamed: str, kept: str) -> bool:
    """Whether a matcher for ``kept`` would see ``renamed``'s old wording (or the other way round)."""
    return (kept in renamed and _phrase(kept)) or (renamed in kept and _phrase(renamed))


class Result(NamedTuple):
    text: str                          # the source with output strings renamed
    renamed: list[tuple[int, str]]     # (line, old wording) of each renamed string
    left: list[tuple[int, str]]        # strings brand() would change that stay: outside output contexts
    matched: list[tuple[int, str]]     # of those, the ones code matches text against
    shown: list[str]                   # every string in an output context, as it now reads


def _shown(tree: ast.AST):
    """String constants in contexts that show them to a person."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = _callee(node)
        if callee in OUTPUT_CALLS or callee == "write" or callee.endswith(("Error", "Exception")):
            shown = [*node.args, *(k.value for k in node.keywords)]
        else:
            shown = [k.value for k in node.keywords if k.arg and _holds_copy(k.arg)]
        yield from (const for arg in shown for const in _strings_in(arg))


def _rebrand(source: str, constants) -> tuple[str, dict[tuple[int, int], tuple[str, ast.Constant]]]:
    """``source`` with each of ``constants`` branded where it is written (KEEP wording stays)."""
    lines, starts = source.splitlines(keepends=True), _offsets(source)
    spans: dict[tuple[int, int], tuple[str, ast.Constant]] = {}
    for const in constants:
        if const.end_lineno is None or const.end_col_offset is None:
            continue
        start = _char_offset(lines, starts, const.lineno, const.col_offset)
        end = _char_offset(lines, starts, const.end_lineno, const.end_col_offset)
        segment = source[start:end]
        if (renamed := brand(segment)) != segment and not any(text in segment for text in KEEP):
            spans[(start, end)] = (renamed, const)
    for (start, end), (renamed, _) in sorted(spans.items(), reverse=True):
        source = source[:start] + renamed + source[end:]
    return source, spans


def rename_python(source: str) -> Result:
    """``source`` with the strings it shows a person renamed."""
    tree = ast.parse(source)
    shown = list(_shown(tree))
    out, spans = _rebrand(source, shown)
    docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                  and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    done = {id(const) for _, const in spans.values()}
    left = [const for const in ast.walk(tree)
            if isinstance(const, ast.Constant) and isinstance(const.value, str) and id(const) not in docstrings
            and id(const) not in done and brand(const.value) != const.value]
    kept = {id(const) for const in left}
    return Result(out, [(const.lineno, const.value) for _, const in spans.values()],
                  [(const.lineno, const.value) for const in left],
                  [(const.lineno, const.value) for const in matchers(tree) if id(const) in kept],
                  [brand(const.value) for const in shown])


def _searched(node: ast.AST):
    """The strings a test looks for in output: ``"..." in text`` / ``not in`` (also nested in another
    comparison, ``and``/``or``/``not``, ``any(...)``), and ``text.count("...")``-style searches. Not
    equality: an exact value is more often data the code returns than copy it shows."""
    if isinstance(node, ast.Compare):
        operands = [node.left, *node.comparators]
        for left, op in zip(operands, node.ops):
            if isinstance(op, (ast.In, ast.NotIn)):
                yield from _parts(left)
        for operand in operands:
            yield from _searched(operand)
    elif isinstance(node, (ast.BoolOp, ast.UnaryOp)):
        for child in ast.iter_child_nodes(node):
            yield from _searched(child)
    elif isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
        yield from _searched(node.elt)
    elif isinstance(node, ast.Call):
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if name in {"any", "all"}:
            for arg in node.args:
                yield from _searched(arg)
        elif name in {"count", "startswith", "endswith", "find", "index"}:
            for arg in node.args:
                yield from _parts(arg)


def _parts(node: ast.AST):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node
    elif isinstance(node, ast.JoinedStr):
        yield from (part for part in node.values if isinstance(part, ast.Constant))


def _expected(tree: ast.AST):
    """String constants a test expects to see: searched for in an ``assert``, a message (naming the
    product) passed to a mock's ``assert_*``, or ``pytest.raises(match=...)``."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            yield from _searched(node.test)
        elif isinstance(node, ast.Compare):  # `offered = "..." in detail`, asserted later
            yield from (const for left, op in zip([node.left, *node.comparators], node.ops)
                        if isinstance(op, (ast.In, ast.NotIn)) for const in _parts(left))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr.startswith("assert_"):
                yield from (const for arg in (*node.args, *(k.value for k in node.keywords)) for const in _parts(arg)
                            if re.search(r"\bHermes\b", const.value))
            elif node.func.attr in {"raises", "warns"}:
                yield from (k.value for k in node.keywords if k.arg == "match" and isinstance(k.value, ast.Constant))


def follow_tests(source: str, produced: Produced) -> str:
    """A test's expectations quoting copy the code now shows renamed renamed with it, positive and negative
    alike. Its inputs and fixtures stay as written, and so does an expectation the test also passes in
    itself (it checks its own input comes through) or wording the code still keeps somewhere (a log, a
    JSON field: the test may be reading that)."""
    tree = ast.parse(source)
    expected = list({id(const): const for const in _expected(tree) if isinstance(const.value, str)}.values())
    prose = {id(n.body[0].value) for n in ast.walk(tree)  # docstrings and assert messages describe, not feed
             if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
             and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    # Whatever an assertion holds is expected output, followed or not (an exact comparison stays as written).
    asserted = {id(c) for n in ast.walk(tree) if isinstance(n, ast.Assert) or (
                    isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and (n.func.attr.startswith("assert_") or n.func.attr in {"raises", "warns"}))
                for c in ast.walk(n)}
    ids = {id(const) for const in expected} | prose | asserted
    inputs = [node.value for node in ast.walk(tree)
              if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in ids]
    return _rebrand(source, [const for const in expected
                             if len(const.value.strip()) >= 8 and (branded := brand(const.value)) != const.value
                             and re.search(r"[A-Za-z]{3}", branded.replace(PRODUCT_NAME, ""))  # more than the name
                             and branded in produced.shown and const.value not in produced.kept
                             and not any(const.value in text and branded in brand(text) for text in inputs)])[0]


_FENCE = re.compile(r"^(\s*)(```+|~~~+)(.*)$")
_SHELL = {"", "bash", "sh", "shell", "console", "zsh", "fish", "powershell", "ps1", "pwsh", "cmd", "bat", "text"}
_KEEP_LINE = re.compile(r"Nous Research|NousResearch")


_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$")
_HEADING_ID = re.compile(r"\{#([^}]+)\}\s*$")


def _slug(heading: str) -> str:
    """The anchor Docusaurus gives a heading: github-slugger over its text, where HTML tags are markup
    but ``<prompt>`` inside a code span is text."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = "".join(part if odd else re.sub(r"<[^>]+>", "", part) for odd, part in
                   ((index % 2, part) for index, part in enumerate(text.split("`"))))
    return re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")


def _brand_line(line: str) -> str:
    return line if _KEEP_LINE.search(line) or any(text in line for text in KEEP) else brand(line)


def rename_markdown(text: str) -> str:
    """Prose and shell blocks renamed; other code blocks (YAML, JSON, Python...) and lines crediting
    Nous Research as they are. A renamed heading keeps its anchor, so links to it still land."""
    out, fence, shell, seen = [], None, False, {}
    in_front = text.startswith("---\n")
    for index, line in enumerate(text.splitlines(keepends=True)):
        if in_front:
            if index and line.strip() == "---":
                in_front = False
            elif re.match(r"\s*(title|description|sidebar_label)\s*:", line):
                line = _brand_line(line)
            out.append(line)
            continue
        if match := _FENCE.match(line):
            if fence is None:
                fence, shell = match.group(2)[:3], match.group(3).strip().split(" ")[0].lower() in _SHELL
            elif match.group(2).startswith(fence) and not match.group(3).strip():
                fence = None
            out.append(line)
            continue
        if fence is None and (heading := _HEADING.match(line)):
            explicit = _HEADING_ID.search(heading.group(1))
            anchor = explicit.group(1) if explicit else _slug(heading.group(1))
            seen[anchor] = seen.get(anchor, -1) + 1
            anchor += f"-{seen[anchor]}" if seen[anchor] else ""
            if (branded := _brand_line(line)) != line and not explicit:
                branded = f"{branded.rstrip()} {{#{anchor}}}" + line[len(line.rstrip()):]
            out.append(branded)
            continue
        out.append(_brand_line(line) if fence is None or shell else line)
    return "".join(out)


def _git_files(*patterns: str) -> list[Path]:
    listed = subprocess.run(["git", "ls-files", "--", *patterns], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", check=True, timeout=120)
    return [ROOT / name for name in dict.fromkeys(listed.stdout.splitlines())]  # mid-merge: once per side


def python_files() -> list[Path]:
    return [path for path in _git_files(*PYTHON_FILES, *(f"{d}/*.py" for d in PYTHON_DIRS))
            if "tests" not in path.relative_to(ROOT).parts and path.relative_to(ROOT).as_posix() not in NEVER]


def doc_files() -> list[Path]:
    return _git_files(*(f"{d}/*.md" for d in DOC_DIRS), *(f"{d}/*.mdx" for d in DOC_DIRS))


def test_files() -> list[Path]:
    return _git_files("tests/*.py")


class Produced(NamedTuple):
    shown: str  # what the code now shows people, joined: renamed output and the branded English catalogs
    kept: str   # the Hermes wording it still has elsewhere (logs, data, prompts), joined


def produced_copy(shown: list[str], kept: list[str]) -> Produced:
    try:
        from agent import i18n_layers
        catalogs = [brand(text) for name in ("en.yaml", "en.tui.yaml") if (ROOT / "locales" / name).is_file()
                    for text in i18n_layers.parse_locale_file(ROOT / "locales" / name).values()]
    except ImportError:  # outside the project's environment: the code's own strings still count
        catalogs = []
    return Produced("\0".join([*shown, *catalogs]), "\0".join(kept))


@functools.cache
def _produced_now() -> Produced:
    results = [rename_python(path.read_text(encoding="utf-8-sig")) for path in python_files()]
    return produced_copy([text for result in results for text in result.shown],
                         [text for result in results for _, text in result.left])


def rename_text(name: str, text: str) -> str:
    """``text`` renamed as the repository file ``name`` would be (unchanged outside the rename's scope)."""
    parts = PurePosixPath(name).parts
    if parts[0] == "tests" and name.endswith(".py"):
        try:
            return follow_tests(text, _produced_now())
        except SyntaxError:
            return text
    if (name.endswith(".py") and (name in PYTHON_FILES or parts[0] in PYTHON_DIRS) and "tests" not in parts
            and name not in NEVER):
        try:
            return rename_python(text).text
        except SyntaxError:
            return text
    if name.endswith((".md", ".mdx")) and any(name.startswith(f"{d}/") for d in DOC_DIRS):
        return rename_markdown(text)
    if name.endswith((".ts", ".tsx")):
        return subprocess.run(["node", str(ROOT / "scripts/fork/rename_ts.mjs"), "--stdin", name], input=text,
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True, timeout=300).stdout
    return text


def _git(*args: str, data: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, input=data, capture_output=True, check=False, timeout=120)


def resolve() -> tuple[list[str], list[str]]:
    """Mid-merge, take upstream's side of each conflicted file whose only change on our side is the
    rename (the rewrite that follows renames it again). Returns (taken, left for a hand)."""
    taken, left = [], []
    for name in _git("diff", "--name-only", "--diff-filter=U").stdout.decode().split():
        base, ours, theirs = (_git("show", f":{stage}:{name}") for stage in (1, 2, 3))
        if all(side.returncode == 0 for side in (base, ours, theirs)) and \
                rename_text(name, base.stdout.decode("utf-8", "surrogateescape")) == ours.stdout.decode("utf-8", "surrogateescape"):
            (ROOT / name).write_bytes(theirs.stdout)
            _git("add", "--", name)
            taken.append(name)
        else:
            left.append(name)
    return taken, left


def _rename_apps(args: argparse.Namespace, renamed: list[tuple[str, int, str]]) -> tuple[list[str], int]:
    """scripts/fork/rename_ts.mjs: the files it changed (or would) and whether it found conflicts,
    including apps' patterns that recognised a backend message ``renamed`` changes."""
    flags = [flag for flag, on in (("--check", args.check), ("--report", args.report)) if on]
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as backend:
        json.dump([{"at": f"{name}:{line}", "old": text, "new": brand(text)} for name, line, text in renamed], backend)
        backend.flush()
        ts = subprocess.run(["node", str(ROOT / "scripts/fork/rename_ts.mjs"), *flags, "--backend-renames", backend.name],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False, timeout=1800)
    sys.stderr.write(ts.stderr)
    if ts.returncode not in (0, 3):
        raise SystemExit(2)
    return ts.stdout.split(), ts.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="change nothing; exit 1 if anything would change")
    parser.add_argument("--report", action="store_true", help="also list strings left as they are")
    parser.add_argument("--resolve", action="store_true", help="mid-merge: take upstream's side where ours only renamed")
    args = parser.parse_args()
    taken, unmerged = resolve() if args.resolve else ([], [])
    changed: list[str] = []
    renamed: list[tuple[str, int, str]] = []
    matched: list[tuple[str, int, str]] = []
    shown: list[str] = []
    kept: list[str] = []
    for path in python_files():
        name = path.relative_to(ROOT).as_posix()
        result = rename_python(path.read_text(encoding="utf-8-sig"))
        renamed += [(name, line, text) for line, text in result.renamed]
        matched += [(name, line, text) for line, text in result.matched]
        shown += result.shown
        kept += [text for _, text in result.left]
        if result.renamed:
            changed.append(name)
            if not args.check:
                path.write_text(result.text, encoding="utf-8")
        if args.report:
            for line, text in result.left:
                print(f"left: {name}:{line}: {text.strip()[:100]!r}", file=sys.stderr)
    produced = produced_copy(shown, kept)
    for path in test_files():
        text = path.read_text(encoding="utf-8-sig")
        if (followed := follow_tests(text, produced)) != text:
            changed.append(path.relative_to(ROOT).as_posix())
            if not args.check:
                path.write_text(followed, encoding="utf-8")
    conflicts = [f"conflict: {a}:{la} renames text {b}:{lb} keeps: {kept!r}"
                 for a, la, text in renamed for b, lb, kept in matched if overlaps(text, kept)]
    print(*conflicts, sep="\n", file=sys.stderr) if conflicts else None
    for path in doc_files():
        text = path.read_text(encoding="utf-8-sig")
        if (branded := rename_markdown(text)) != text:
            changed.append(path.relative_to(ROOT).as_posix())
            if not args.check:
                path.write_text(branded, encoding="utf-8")
    apps, apps_status = _rename_apps(args, renamed)
    changed += apps
    print(f"{'would rename' if args.check else 'renamed'} {len(changed)} file(s)")
    if args.resolve:
        _git("add", "--", *taken) if taken else None
        print(f"took upstream's side of {len(taken)} conflicted file(s) and renamed them again")
        print(*(f"    resolve by hand: {name}" for name in unmerged), sep="\n") if unmerged else None
    if conflicts or apps_status == 3:
        return 3
    return 1 if (args.check and changed) or unmerged else 0


if __name__ == "__main__":
    raise SystemExit(main())
