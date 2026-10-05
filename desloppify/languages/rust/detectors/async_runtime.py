"""Rust async-runtime hazards: blocking the executor and unbounded task spawning.

Rules follow the `rust-async-patterns` skill ("Don't block", "Don't spawn
unboundedly"); lock guards held across awaits live in ``safety.py``.
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
    _ASYNC_FN_RE,
    _blank_inline_test_modules,
    _blank_span,
    _entry,
    _find_block_start,
    _find_matching_brace,
    _find_matching_delimiter,
    _function_body_spans,
    _is_runtime_source_file,
    _line_number,
)

# Closures handed to these run off the executor, so blocking inside them is fine.
_OFF_EXECUTOR_CALL_RE = re.compile(
    r"\b(?:spawn_blocking|block_in_place|thread::spawn|thread::scope|rayon::spawn)\s*\("
)
_BLOCKING_CALLS: tuple[tuple[str, re.Pattern[str], str, str], ...] = (
    (
        "blocking_sleep",
        re.compile(r"\b(?:std::)?thread::sleep\s*\("),
        "calls `std::thread::sleep`, which parks an executor thread; use the runtime's async sleep",
        "high",
    ),
    (
        "nested_block_on",
        re.compile(r"\bblock_on\s*\("),
        "calls `block_on` from async code; await the future instead of starting a nested executor",
        "high",
    ),
    (
        "blocking_io",
        re.compile(r"\bstd::fs::\w+|\breqwest::blocking\b|\bstd::net::(?:TcpStream|TcpListener|UdpSocket)\b"),
        "does blocking std I/O on an executor thread; use the runtime's async I/O or `spawn_blocking`",
        "low",
    ),
)
_FOR_LOOP_RE = re.compile(r"\bfor\s+[^;{}]*?\bin\b")
_DETACHED_SPAWN_RE = re.compile(
    r"(?m)^[ \t]*(?:let\s+_\s*=\s*)?(?:tokio::(?:task::)?|task::)spawn\s*\("
)
_SPAWN_LIMITER_RE = re.compile(
    r"\b(?:Semaphore|JoinSet|TaskTracker|FuturesUnordered|buffer_unordered|buffered|acquire(?:_owned)?)\b"
)


def detect_async_runtime(path: Path) -> tuple[list[dict], int]:
    """Flag blocking calls in async functions and unbounded detached spawns."""
    entries: list[dict] = []
    files = find_rust_files(path)
    for filepath in files:
        absolute = Path(resolve_path(filepath))
        content = read_text_or_none(absolute)
        if content is None:
            continue
        if not _is_runtime_source_file(describe_rust_file(absolute)):
            continue

        stripped = _blank_inline_test_modules(
            strip_rust_comments(content, preserve_lines=True)
        )
        if "async" in stripped:
            entries.extend(_blocking_call_entries(absolute, stripped))
        if "spawn" in stripped:
            entries.extend(_unbounded_spawn_entries(absolute, stripped))
    return entries, len(files)


def _blocking_call_entries(absolute: Path, stripped: str) -> list[dict]:
    entries: list[dict] = []
    for match in _ASYNC_FN_RE.finditer(stripped):
        body_start = _find_block_start(stripped, match.end())
        if body_start is None:
            continue
        body_end = _find_matching_brace(stripped, body_start)
        if body_end is None:
            continue
        name = match.group(1)
        body = _blank_off_executor_closures(stripped[body_start : body_end + 1])
        for kind, pattern, problem, confidence in _BLOCKING_CALLS:
            hit = pattern.search(body)
            if hit is None:
                continue
            entries.append(
                _entry(
                    absolute,
                    line=_line_number(stripped, body_start + hit.start()),
                    name=f"{kind}::{name}",
                    summary=f"Async function `{name}` {problem}",
                    tier=3,
                    confidence=confidence,
                )
            )
    return entries


def _blank_off_executor_closures(body: str) -> str:
    cursor = 0
    while True:
        match = _OFF_EXECUTOR_CALL_RE.search(body, cursor)
        if match is None:
            return body
        open_paren = match.end() - 1
        close_paren = _find_matching_delimiter(body, open_paren, "(", ")")
        if close_paren is None:
            cursor = match.end()
            continue
        body = _blank_span(body, open_paren + 1, close_paren)
        cursor = close_paren


def _unbounded_spawn_entries(absolute: Path, stripped: str) -> list[dict]:
    entries: list[dict] = []
    function_spans: list[tuple[int, int]] | None = None
    for match in _FOR_LOOP_RE.finditer(stripped):
        body_start = _find_block_start(stripped, match.end())
        if body_start is None:
            continue
        body_end = _find_matching_brace(stripped, body_start)
        if body_end is None:
            continue
        spawn = _DETACHED_SPAWN_RE.search(stripped, body_start, body_end)
        if spawn is None:
            continue
        if function_spans is None:
            function_spans = _function_body_spans(stripped)
        scope_start, scope_end = _innermost_span(function_spans, body_start) or (
            body_start,
            body_end,
        )
        if _SPAWN_LIMITER_RE.search(stripped, scope_start, scope_end + 1):
            continue
        line = _line_number(stripped, spawn.start())
        entries.append(
            _entry(
                absolute,
                line=line,
                name=f"unbounded_spawn::{line}",
                summary=(
                    "Loop spawns a detached task per item with no concurrency limit; "
                    "bound it with a `Semaphore`/`buffer_unordered` or track the tasks in a `JoinSet`"
                ),
                tier=3,
                confidence="medium",
            )
        )
    return entries


def _innermost_span(
    spans: list[tuple[int, int]], offset: int
) -> tuple[int, int] | None:
    containing = [span for span in spans if span[0] <= offset <= span[1]]
    if not containing:
        return None
    return min(containing, key=lambda span: span[1] - span[0])


__all__ = ["detect_async_runtime"]
