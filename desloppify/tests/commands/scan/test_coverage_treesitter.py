"""Scan coverage must drop when tree-sitter-backed detectors cannot run."""

from __future__ import annotations

import pytest

from desloppify.app.commands.scan import coverage as scan_coverage_mod
from desloppify.languages._framework import treesitter as treesitter_pkg
from desloppify.languages._framework.treesitter import coverage as ts_coverage_mod

DETECTORS = list(ts_coverage_mod.TREESITTER_BACKED_DETECTORS)


def test_no_entries_for_language_without_treesitter_spec(monkeypatch):
    monkeypatch.setattr(treesitter_pkg, "is_available", lambda: False)
    assert ts_coverage_mod.treesitter_coverage_prerequisites("python") == []


def test_missing_pack_reduces_every_treesitter_backed_detector(monkeypatch):
    monkeypatch.setattr(treesitter_pkg, "is_available", lambda: False)

    entries = ts_coverage_mod.treesitter_coverage_prerequisites("nim")

    assert [e.detector for e in entries] == DETECTORS
    for entry in entries:
        assert entry.status == "reduced"
        assert entry.confidence < 1.0
        assert entry.reason == "missing_dependency"
        assert "desloppify[treesitter]" in entry.remediation
        assert "nim" in entry.summary


def test_grammar_load_failure_reduces_coverage(monkeypatch):
    monkeypatch.setattr(treesitter_pkg, "is_available", lambda: True)
    monkeypatch.setattr(treesitter_pkg, "PARSE_INIT_ERRORS", (RuntimeError,))
    from desloppify.languages._framework.treesitter.analysis import extractors

    def boom(grammar):
        raise RuntimeError(f"Download error: {grammar}")

    monkeypatch.setattr(extractors, "_get_parser", boom)

    entries = ts_coverage_mod.treesitter_coverage_prerequisites("nim")

    assert [e.detector for e in entries] == DETECTORS
    assert all(e.reason == "grammar_unavailable" for e in entries)
    assert "Download error: nim" in entries[0].summary
    assert "prefetch" in entries[0].remediation


def test_loadable_grammar_reports_full_coverage():
    if not treesitter_pkg.is_available():
        pytest.skip("tree-sitter-language-pack not installed")
    assert ts_coverage_mod.treesitter_coverage_prerequisites("go") == []


def test_seed_runtime_warnings_includes_treesitter_entries(monkeypatch):
    monkeypatch.setattr(treesitter_pkg, "is_available", lambda: False)

    class FakeLang:
        name = "nim"

        def __init__(self):
            self.detector_coverage: dict = {}
            self.coverage_warnings: list = []

        def scan_coverage_prerequisites(self):
            return []

    lang = FakeLang()
    warnings = scan_coverage_mod.seed_runtime_coverage_warnings(lang)

    assert {w["detector"] for w in warnings} == set(DETECTORS)
    assert all(w["status"] == "reduced" for w in warnings)
    assert set(lang.detector_coverage) == set(DETECTORS)
