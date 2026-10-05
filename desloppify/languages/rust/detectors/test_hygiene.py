"""Rust test-hygiene detector.

Rules follow the `rust-testing` skill and chapter 5 of `rust-best-practices`:
no sleeping in tests, `#[ignore]` carries a reason, `#[should_panic]` names the
expected panic, and equality goes through `assert_eq!`/`assert_ne!`.
"""

from __future__ import annotations

import re
from pathlib import Path

from desloppify.base.discovery.file_paths import resolve_path
from desloppify.languages.rust.support import (
    describe_rust_file,
    find_rust_files,
    read_text_or_none,
    strip_rust_comments,
)

from ._shared import (
    _entry,
    _find_block_start,
    _find_matching_brace,
    _find_matching_delimiter,
    _inline_test_module_line_ranges,
    _line_number,
    _preceding_attributes,
)

_FN_RE = re.compile(
    r"(?m)^[ \t]*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)"
)
_TEST_ATTR_RE = re.compile(r"#\[\s*(?:\w+::)*(?:test|rstest|test_case)\b")
_BARE_IGNORE_RE = re.compile(r"#\[\s*ignore\s*\]")
_BARE_SHOULD_PANIC_RE = re.compile(r"#\[\s*should_panic\s*\]")
_SLEEP_RE = re.compile(
    r"(?<![\w.:])(?:(?:std::)?thread::sleep|(?:tokio::)?time::sleep|sleep)\s*\("
)
_PAUSED_CLOCK_RE = re.compile(r"\bstart_paused\b|\btime::(?:pause|advance)\s*\(")
_ASSERT_RE = re.compile(r"\bassert!\s*\(")
_EQUALITY_RE = re.compile(r"(?<![=!<>])==(?!=)|!=")
_BOOLEAN_LOGIC_RE = re.compile(r"&&|\|\|")


def detect_test_hygiene(path: Path) -> tuple[list[dict], int]:
    """Flag flaky or low-signal constructs in Rust tests."""
    entries: list[dict] = []
    files = find_rust_files(path)
    for filepath in files:
        absolute = Path(resolve_path(filepath))
        content = read_text_or_none(absolute)
        if content is None or "test" not in content:
            continue

        stripped = strip_rust_comments(content, preserve_lines=True)
        test_ranges = _test_line_ranges(absolute, stripped)
        if not test_ranges:
            continue
        for match in _FN_RE.finditer(stripped):
            line = _line_number(stripped, match.start())
            if not any(start <= line <= end for start, end in test_ranges):
                continue
            attrs = _preceding_attributes(stripped, match.start())
            if not _TEST_ATTR_RE.search(attrs):
                continue
            body_start = _find_block_start(stripped, match.end())
            if body_start is None:
                continue
            body_end = _find_matching_brace(stripped, body_start)
            if body_end is None:
                continue
            entries.extend(
                _test_entries(
                    absolute,
                    name=match.group(1),
                    line=line,
                    attrs=attrs,
                    body=stripped[body_start : body_end + 1],
                )
            )
    return entries, len(files)


def _test_line_ranges(absolute: Path, stripped: str) -> list[tuple[int, int]]:
    """Whole file for integration tests, inline test modules otherwise."""
    context = describe_rust_file(absolute)
    try:
        relative = context.source_file.relative_to(context.manifest_dir)
    except ValueError:
        relative = None
    if relative is not None and relative.parts and relative.parts[0] == "tests":
        return [(1, stripped.count("\n") + 1)]
    return _inline_test_module_line_ranges(stripped)


def _test_entries(
    absolute: Path, *, name: str, line: int, attrs: str, body: str
) -> list[dict]:
    entries: list[dict] = []

    def add(kind: str, summary: str, confidence: str) -> None:
        entries.append(
            _entry(
                absolute,
                line=line,
                name=f"{kind}::{name}",
                summary=summary,
                tier=3,
                confidence=confidence,
            )
        )

    if _SLEEP_RE.search(body) and not _PAUSED_CLOCK_RE.search(f"{attrs}\n{body}"):
        add(
            "sleep_in_test",
            f"Test `{name}` sleeps on the wall clock; synchronize with a channel/barrier "
            "or a paused runtime clock (`tokio::time::pause`)",
            "medium",
        )
    if _BARE_IGNORE_RE.search(attrs):
        add(
            "ignore_without_reason",
            f'Test `{name}` is `#[ignore]`d without a reason; fix it or write `#[ignore = "why"]`',
            "medium",
        )
    if _BARE_SHOULD_PANIC_RE.search(attrs):
        add(
            "should_panic_without_expected",
            f"Test `{name}` uses bare `#[should_panic]`, which passes on any panic; "
            "add `expected = \"...\"` or assert on a returned `Err`",
            "medium",
        )
    equality_asserts = _count_equality_asserts(body)
    if equality_asserts:
        add(
            "assert_equality",
            f"Test `{name}` compares with `assert!(a == b)` {equality_asserts}x; "
            "`assert_eq!`/`assert_ne!` print both values on failure",
            "low",
        )
    return entries


def _count_equality_asserts(body: str) -> int:
    count = 0
    for match in _ASSERT_RE.finditer(body):
        open_paren = match.end() - 1
        close_paren = _find_matching_delimiter(body, open_paren, "(", ")")
        if close_paren is None:
            continue
        condition = _top_level_first_argument(body[open_paren + 1 : close_paren])
        if _EQUALITY_RE.search(condition) and not _BOOLEAN_LOGIC_RE.search(condition):
            count += 1
    return count


def _top_level_first_argument(args: str) -> str:
    """Return the first macro argument with nested delimiters dropped."""
    depth = 0
    kept: list[str] = []
    for char in args:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif depth == 0:
            if char == ",":
                break
            kept.append(char)
    return "".join(kept)


__all__ = ["detect_test_hygiene"]
