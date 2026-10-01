"""high_cyclomatic_complexity measures a composable's handlers, not their sum."""

from __future__ import annotations

from collections import defaultdict

from desloppify.languages.typescript.detectors.smells.detector_flow import (
    _detect_high_cyclomatic_complexity,
)
from desloppify.languages.typescript.detectors.smells.helpers import _FileContext

_BRANCHES = "\n".join(f"  if (a === {i}) return {i}" for i in range(20))
_BODY = "{\n" + _BRANCHES + "\n  return null\n}\n"


def _smells(source: str) -> list[dict]:
    lines = source.splitlines()
    counts: dict[str, list[dict]] = defaultdict(list)
    _detect_high_cyclomatic_complexity(_FileContext("a.ts", source, lines, {}), counts)
    return counts["high_cyclomatic_complexity"]


def test_composable_body_is_not_summed():
    assert _smells("export function usePlanOptions(a: number) " + _BODY) == []


def test_plain_function_with_the_same_branches_is_flagged():
    assert len(_smells("export function planOptions(a: number) " + _BODY)) == 1


def test_handler_inside_a_composable_is_still_measured():
    inner = "  function pick(a: number) " + _BODY.replace("\n", "\n  ")
    source = "export function usePlanOptions() {\n" + inner + "\n  return { pick }\n}\n"
    assert len(_smells(source)) == 1


def test_optional_chaining_and_nullish_defaults_are_not_a_branch_each():
    from desloppify.languages.typescript.detectors.smells.detector_core import (
        _compute_ts_cyclomatic_complexity,
    )

    straight = "{\n  a.value = data.value?.board?.cells ?? null\n}\n"
    assert _compute_ts_cyclomatic_complexity(straight) == 2
    typed = "{\n  function f(x?: number, y?: string) { return x }\n}\n"
    assert _compute_ts_cyclomatic_complexity(typed) == 1
    ternary = "{\n  return a ? b : c && d\n}\n"
    assert _compute_ts_cyclomatic_complexity(ternary) == 3
