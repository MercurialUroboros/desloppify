"""console_error_no_throw honours process.exit; magic_number means >1000."""

from __future__ import annotations

import re
from collections import defaultdict

from desloppify.languages.typescript.detectors.smells.catalog import TS_SMELL_CHECKS
from desloppify.languages.typescript.detectors.smells.detector_flow import (
    _detect_error_no_throw,
)
from desloppify.languages.typescript.detectors.smells.helpers import _FileContext


def _errors(source: str) -> list[dict]:
    lines = source.splitlines()
    counts: dict[str, list[dict]] = defaultdict(list)
    _detect_error_no_throw(_FileContext("cli.ts", source, lines, {}), counts)
    return counts["console_error_no_throw"]


def test_console_error_then_process_exit_is_handled():
    assert _errors("if (!ok) {\n  console.error('usage')\n  process.exit(1)\n}\n") == []


def test_console_error_alone_is_still_flagged():
    assert len(_errors("if (!ok) {\n  console.error('usage')\n}\nrun()\n")) == 1


def _magic() -> re.Pattern[str]:
    check = next(c for c in TS_SMELL_CHECKS if c["id"] == "magic_number")
    return re.compile(check["pattern"])


def test_exactly_one_thousand_is_not_magic():
    assert _magic().search("const s = ms / 1000") is None
    assert _magic().search("const ms = s * 1000") is None
    assert _magic().search("/** Points for the day, 0-1000. */") is None


def test_numbers_above_one_thousand_are_still_magic():
    assert _magic().search("if (n > 1001) return") is not None
    assert _magic().search("const t = ms / 10000") is not None
    assert _magic().search("wait(x * 1000.5)") is not None


def test_named_constant_declarations_are_not_magic(tmp_path, monkeypatch):
    from desloppify.languages.typescript.detectors.smells import detect_smells

    src = tmp_path / "limits.ts"
    src.write_text(
        "export const CHUNK_MAX_EVENTS = 5000\n"
        "const WINDOW_MS = 24 * 3600\n"
        "export function over(n: number) { return n > 3999 }\n"
    )
    monkeypatch.chdir(tmp_path)
    issues, _ = detect_smells(tmp_path)
    magic = [i for i in issues if i.get("id") == "magic_number"]
    lines = sorted(m["line"] for issue in magic for m in issue.get("matches", [issue]))
    assert magic, "the bare 3999 in logic is still magic"
    assert all(line == 3 for line in lines)
