"""Shared helpers and constants for TypeScript smell detectors."""

from __future__ import annotations

import re

from .helpers import (
    _code_text,
    _strip_ts_comments,
)

_MONSTER_FUNCTION_LOC = 150
_HIGH_CYCLOMATIC_THRESHOLD = 15
_NESTED_CLOSURE_THRESHOLD = 3
_CATCH_DEFAULT_FIELD_THRESHOLD = 2
_SWITCH_CASE_MINIMUM = 2

_MAX_CATCH_BODY = 1000
_MAX_SWITCH_BODY_SCAN = 5000

_ERROR_HANDLER_BASENAMES = ("logger", "errorpresentation", "errorhandler", "errorreporting")
_PRECEDING_SKIP_PATTERNS = re.compile(
    r"componentDidCatch|import\.meta\.env\.DEV|process\.env\.NODE_ENV"
)
_HANDLED_RE = re.compile(
    r"\b(?:throw|return)\b|process\.exit\(|toast\(|normalizeAndPresentError\(|presentError\(|rethrow"
)

_FUNC_RE = re.compile(r"\bfunction\s*[\w(]")
# An empty `() => {}` is a no-op callback, not a closure worth hoisting.
_ARROW_RE = re.compile(r"=>\s*\{(?!\s*\})")

_TS_BRANCH_PATTERNS = (
    re.compile(r"\bif\s*\("),
    re.compile(r"\belse\s+if\s*\("),
    re.compile(r"\bcase\s+"),
    re.compile(r"\bcatch\s*\("),
    re.compile(r"\bfor\s*\("),
    re.compile(r"\bwhile\s*\("),
)

# `??` is one branch, a ternary `?` is one; `?.` access and the `?` of an
# optional parameter or member (`x?: T`, `[a?, b?]`) are not paths to follow.
_OPERATOR_BRANCH_RE = re.compile(r"&&|\|\||\?\?|(?<!\?)\?(?![?.:=,)\]])")

_IF_START = re.compile(r"(?:else\s+)?if\s*\(")
_SINGLE_EMPTY_IF = re.compile(r"(?:else\s+)?if\s*\([^)]*\)\s*\{\s*\}\s*$")
_SINGLE_EMPTY_ELSE_IF = re.compile(r"else\s+if\s*\([^)]*\)\s*\{\s*\}\s*$")
_SINGLE_EMPTY_ELSE = re.compile(r"(?:\}\s*)?else\s*\{\s*\}\s*$")
_MULTI_IF_OPEN = re.compile(r"(?:else\s+)?if\s*\([^)]*\)\s*\{\s*$")
_MULTI_ELSE_IF_OPEN = re.compile(r"\}\s*else\s+if\s*\([^)]*\)\s*\{\s*$")
_MULTI_ELSE_OPEN = re.compile(r"\}\s*else\s*\{\s*$")
_ELSE_CONT = re.compile(r"else\s")


def _emit(
    smell_counts: dict[str, list[dict]],
    key: str,
    ctx,
    line: int,
    content: str,
) -> None:
    """Append a smell issue."""
    smell_counts[key].append({"file": ctx.filepath, "line": line, "content": content})


def _find_function_start(line: str, next_lines: list[str]) -> str | None:
    """Return function name for declarations/assignments, else None."""
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith(("interface ", "type ", "enum ", "class ")):
        return None

    declaration_match = re.match(
        r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)\s*\(",
        stripped,
    )
    if declaration_match:
        return declaration_match.group(1)

    assignment_match = re.match(
        r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\b",
        stripped,
    )
    if not assignment_match:
        return None

    combined = "\n".join([stripped] + [next_line.strip() for next_line in next_lines[:2]])
    eq_pos = combined.find("=", assignment_match.end())
    if eq_pos == -1:
        return None
    after_eq = combined[eq_pos + 1 :].lstrip()
    if re.match(r"(?:async\s+)?\([^)]*\)\s*=>", after_eq):
        return assignment_match.group(1)
    if re.match(r"function\b", after_eq):
        return assignment_match.group(1)
    return None


def _find_body_brace(
    lines: list[str], start: int, *, window: int = 40,
) -> tuple[int, int] | None:
    """Return ``(line, col)`` of the ``{`` opening the body of the function at *start*.

    Braces inside the parameter list (destructuring, inline object types, default
    values) sit at paren depth > 0 and are skipped: the body brace is the first one
    at depth 0. Strings and comments are blanked first so a quote in prose cannot
    hide it.
    """
    depth = 0
    angle = 0
    for idx in range(start, min(start + window, len(lines))):
        code = _code_text(lines[idx])
        prev = ""
        for col, ch in enumerate(code):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(0, depth - 1)
            elif ch == "<":
                angle += 1
            elif ch == ">" and prev != "=":
                # A return type such as ``Promise<{ ok: true }>`` carries braces of
                # its own; ``=>`` is the arrow, not a closing angle bracket.
                angle = max(0, angle - 1)
            elif ch == "{" and depth == 0 and angle == 0:
                return idx, col
            prev = ch
    return None


def _match_body_end(
    lines: list[str], brace_line: int, brace_col: int, *, max_scan: int = 2000,
) -> tuple[int, int] | None:
    """Return ``(line, col)`` of the ``}`` matching the brace at ``(brace_line, brace_col)``."""
    depth = 0
    for idx in range(brace_line, min(brace_line + max_scan, len(lines))):
        code = _code_text(lines[idx])
        first = brace_col if idx == brace_line else 0
        for col in range(first, len(code)):
            ch = code[col]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return idx, col
    return None


def _find_opening_brace_line(lines: list[str], start: int, *, window: int = 40) -> int | None:
    """Line index of the brace opening the body of the function declared at *start*."""
    pos = _find_body_brace(lines, start, window=window)
    return None if pos is None else pos[0]


def _function_body_span(
    lines: list[str], start: int, *, max_scan: int = 2000,
) -> tuple[int, int] | None:
    """Return ``(body_brace_line, closing_brace_line)`` for the function at *start*."""
    pos = _find_body_brace(lines, start)
    if pos is None:
        return None
    end = _match_body_end(lines, pos[0], pos[1], max_scan=max_scan)
    if end is None:
        return None
    return pos[0], end[0]


def _extract_function_body(
    lines: list[str], start_line: int, *, max_scan: int = 2000,
) -> str | None:
    """Extract the inner body text of a function starting at start_line."""
    pos = _find_body_brace(lines, start_line)
    if pos is None:
        return None
    brace_line, brace_col = pos
    end = _match_body_end(lines, brace_line, brace_col, max_scan=max_scan)
    if end is None:
        return None
    end_line, end_col = end
    if brace_line == end_line:
        return lines[brace_line][brace_col + 1 : end_col]
    parts = [lines[brace_line][brace_col + 1 :], *lines[brace_line + 1 : end_line], lines[end_line][:end_col]]
    return "\n".join(parts)


def _count_pattern_in_body(body: str, pattern: re.Pattern[str]) -> int:
    """Count regex matches in body that are not inside string literals."""
    return len(pattern.findall(_code_text(body)))


def _compute_ts_cyclomatic_complexity(body: str) -> int:
    """Compute cyclomatic complexity for a TypeScript function body string."""
    stripped = _strip_ts_comments(body)
    complexity = 1
    for pattern in _TS_BRANCH_PATTERNS:
        complexity += len(pattern.findall(stripped))
    complexity += len(_OPERATOR_BRANCH_RE.findall(stripped))
    return complexity


__all__ = [
    "_ARROW_RE",
    "_CATCH_DEFAULT_FIELD_THRESHOLD",
    "_ELSE_CONT",
    "_ERROR_HANDLER_BASENAMES",
    "_FUNC_RE",
    "_HANDLED_RE",
    "_HIGH_CYCLOMATIC_THRESHOLD",
    "_IF_START",
    "_MAX_CATCH_BODY",
    "_MAX_SWITCH_BODY_SCAN",
    "_MONSTER_FUNCTION_LOC",
    "_MULTI_ELSE_IF_OPEN",
    "_MULTI_ELSE_OPEN",
    "_MULTI_IF_OPEN",
    "_NESTED_CLOSURE_THRESHOLD",
    "_PRECEDING_SKIP_PATTERNS",
    "_SINGLE_EMPTY_ELSE",
    "_SINGLE_EMPTY_ELSE_IF",
    "_SINGLE_EMPTY_IF",
    "_SWITCH_CASE_MINIMUM",
    "_count_pattern_in_body",
    "_compute_ts_cyclomatic_complexity",
    "_emit",
    "_extract_function_body",
    "_function_body_span",
    "_find_function_start",
    "_find_opening_brace_line",
]
