"""Public framework facade for non-language-package consumers.

Use this module from app/engine layers instead of importing
``desloppify.languages._framework`` directly.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from desloppify.languages._framework.base.types import (
    BoundaryRule,
    DetectorCoverageRecord,
    DetectorCoverageStatus,
    DetectorPhase,
    FixerConfig,
    FixResult,
    LangConfig,
    LangRuntimeContract,
    LangSecurityResult,
    ScanCoverageRecord,
)
from desloppify.languages._framework.registry import discovery as _discovery_mod
from desloppify.languages._framework.registry import state as registry_state
from desloppify.languages._framework.registry.resolution import (
    auto_detect_lang,
    available_langs,
    get_lang,
    make_lang_config,
)
from desloppify.languages._framework.runtime_support.runtime import (
    LangRun,
    LangRunOverrides,
    make_lang_run,
)

load_all = _discovery_mod.load_all


def shared_phase_labels() -> set[str]:
    """Return generic shared phase labels lazily to avoid import cycles."""
    from desloppify.languages._framework.generic_support.capabilities import (
        SHARED_PHASE_LABELS,
    )

    return SHARED_PHASE_LABELS


def capability_report(cfg: LangRun) -> tuple[list[str], list[str]] | None:
    """Return capability report lazily without importing generic internals eagerly."""
    from desloppify.languages._framework.generic_support.capabilities import (
        capability_report as _capability_report,
    )

    return _capability_report(cfg)


def framework_convention_entry(scan_path: Path, lang: LangRun | None) -> Callable[[str], bool] | None:
    """Predicate for framework convention entry points (Next.js pages, Nuxt handlers, ...)."""
    from desloppify.languages._framework.frameworks import (
        framework_convention_entry as _framework_convention_entry,
    )

    return _framework_convention_entry(scan_path, lang)


def framework_review_guidance(scan_path: Path, lang: LangRun | None) -> dict[str, dict[str, object]]:
    """Per-framework review guidance for frameworks detected in the scan."""
    from desloppify.languages._framework.frameworks import (
        framework_review_guidance as _framework_review_guidance,
    )

    return _framework_review_guidance(scan_path, lang)


def merge_review_guidance(
    lang_guidance: dict[str, object],
    framework_guidance: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Merge framework guidance into a copy of language guidance."""
    from desloppify.languages._framework.frameworks import (
        merge_review_guidance as _merge_review_guidance,
    )

    return _merge_review_guidance(lang_guidance, framework_guidance)


def treesitter_coverage_prerequisites(language: str) -> list[DetectorCoverageStatus]:
    """Reduced-coverage entries when a language's tree-sitter grammar cannot load."""
    from desloppify.languages._framework.treesitter import (
        treesitter_coverage_prerequisites as _prerequisites,
    )

    return _prerequisites(language)


def enable_parse_cache() -> None:
    """Enable tree-sitter parse cache via facade boundary."""
    from desloppify.languages._framework.treesitter import (
        enable_parse_cache as _enable_parse_cache,
    )

    _enable_parse_cache()


def disable_parse_cache() -> None:
    """Disable tree-sitter parse cache via facade boundary."""
    from desloppify.languages._framework.treesitter import (
        disable_parse_cache as _disable_parse_cache,
    )

    _disable_parse_cache()


def reset_script_import_caches(scan_path: str | None = None) -> None:
    """Reset script import resolver caches via the public framework boundary."""
    from desloppify.languages._framework.treesitter import (
        reset_script_import_caches as _reset_script_import_caches,
    )

    _reset_script_import_caches(scan_path)


def prewarm_review_phase_detectors(path, lang, phases) -> None:
    """Prime expensive shared review detectors for overlap during scan."""
    from desloppify.languages._framework.base.shared_phases_review import (
        prewarm_review_phase_detectors as _prewarm_review_phase_detectors,
    )

    _prewarm_review_phase_detectors(path, lang, phases)


def clear_review_phase_prefetch(lang) -> None:
    """Clear in-memory shared review detector prefetch state."""
    from desloppify.languages._framework.base.shared_phases_review import (
        clear_review_phase_prefetch as _clear_review_phase_prefetch,
    )

    _clear_review_phase_prefetch(lang)


__all__ = [
    "BoundaryRule",
    "LangConfig",
    "LangRun",
    "LangRunOverrides",
    "DetectorCoverageRecord",
    "DetectorCoverageStatus",
    "DetectorPhase",
    "FixerConfig",
    "FixResult",
    "LangRuntimeContract",
    "LangSecurityResult",
    "ScanCoverageRecord",
    "auto_detect_lang",
    "available_langs",
    "capability_report",
    "clear_review_phase_prefetch",
    "disable_parse_cache",
    "enable_parse_cache",
    "framework_convention_entry",
    "framework_review_guidance",
    "merge_review_guidance",
    "get_lang",
    "load_all",
    "make_lang_run",
    "make_lang_config",
    "prewarm_review_phase_detectors",
    "reset_script_import_caches",
    "registry_state",
    "shared_phase_labels",
    "treesitter_coverage_prerequisites",
]
