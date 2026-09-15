"""nested_closure leaves hook/composable factories alone."""

from __future__ import annotations

from collections import defaultdict

from desloppify.languages.typescript.detectors.smells.detector_flow import (
    _detect_nested_closures,
)
from desloppify.languages.typescript.detectors.smells.helpers import _FileContext

_BODY = """{
  function a() { return 1 }
  function b() { return 2 }
  watch(x, async () => {
    await a()
  })
  return { a, b }
}
"""


def _smells(source: str) -> list[dict]:
    lines = source.splitlines()
    counts: dict[str, list[dict]] = defaultdict(list)
    _detect_nested_closures(_FileContext("a.ts", source, lines, {}), counts)
    return counts["nested_closure"]


def test_composable_with_handlers_is_not_flagged():
    assert _smells("export function useArchiveGate(opts: Options) " + _BODY) == []


def test_plain_function_with_the_same_closures_is_flagged():
    assert len(_smells("export function buildArchiveGate(opts: Options) " + _BODY)) == 1


def test_lowercase_after_use_is_not_a_hook():
    assert len(_smells("export function useless(opts: Options) " + _BODY)) == 1
