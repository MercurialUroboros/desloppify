"""Scan-coverage preflight for tree-sitter-backed detectors.

Every tree-sitter phase degrades to "no findings" when the parser or the
grammar cannot be loaded, so a scan run without them would look identical to a
clean codebase. These prerequisites make that gap visible in scan coverage.
"""

from __future__ import annotations

import logging

from desloppify.languages._framework.base.types_shared import DetectorCoverageStatus

logger = logging.getLogger(__name__)

# Detector ids emitted only by tree-sitter phases (see ``phases.py``).
TREESITTER_BACKED_DETECTORS: tuple[str, ...] = ("smells", "responsibility_cohesion", "unused")

_IMPACT = (
    "Empty catches, unreachable code, responsibility cohesion, unused imports, and "
    "function-level complexity are not measured; a clean result here does not mean "
    "the code is clean."
)


def _reduced(language: str, *, summary: str, remediation: str, reason: str) -> list[DetectorCoverageStatus]:
    return [
        DetectorCoverageStatus(
            detector=detector,
            status="reduced",
            confidence=0.5,
            summary=summary.format(detector=detector, language=language),
            impact=_IMPACT,
            remediation=remediation,
            tool="tree-sitter-language-pack",
            reason=reason,
        )
        for detector in TREESITTER_BACKED_DETECTORS
    ]


def treesitter_coverage_prerequisites(language: str) -> list[DetectorCoverageStatus]:
    """Return reduced-coverage entries when ``language``'s grammar cannot be loaded.

    Covers two failure modes:

    - ``tree-sitter-language-pack`` is not installed at all.
    - The pack is installed but the grammar cannot be loaded. Packs from 1.8 on
      download grammars on first use, so an offline sandbox hits this.
    """
    from desloppify.languages._framework import treesitter as treesitter_pkg

    spec = treesitter_pkg.get_spec(language)
    if spec is None:
        return []

    if not treesitter_pkg.is_available():
        return _reduced(
            language,
            summary=(
                "tree-sitter-language-pack is not installed — AST-based "
                "`{detector}` detection is skipped for {language}."
            ),
            remediation='Install the parser: pip install "desloppify[treesitter]"',
            reason="missing_dependency",
        )

    from desloppify.languages._framework.treesitter.analysis.extractors import (
        _get_parser,
    )

    try:
        _get_parser(spec.grammar)
    except treesitter_pkg.PARSE_INIT_ERRORS as exc:
        logger.debug("tree-sitter grammar %r unavailable: %s", spec.grammar, exc)
        return _reduced(
            language,
            summary=(
                f"tree-sitter grammar `{spec.grammar}` could not be loaded ({exc}) — "
                "AST-based `{detector}` detection is skipped for {language}."
            ),
            remediation=(
                "Run one scan with network access so tree-sitter-language-pack can "
                f"cache the `{spec.grammar}` grammar, or prefetch it: python -c "
                f"\"import tree_sitter_language_pack as t; t.prefetch(['{spec.grammar}'])\""
            ),
            reason="grammar_unavailable",
        )
    return []


__all__ = ["TREESITTER_BACKED_DETECTORS", "treesitter_coverage_prerequisites"]
