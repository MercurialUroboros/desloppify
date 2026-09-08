"""Framework horizontal layer (spec-driven, like tree-sitter/tool specs).

Framework support is intentionally spec-driven so it can be enabled from both
deep language plugins (LangConfig classes) and shallow generic_lang plugins.

Public entrypoints:
- framework_phases(lang_name): build DetectorPhase objects
- detect_ecosystem_frameworks(scan_path, lang, ecosystem): framework presence + evidence
- framework_convention_entry(scan_path, lang): orphaned-file entry-point predicate
- framework_review_guidance(scan_path, lang): per-framework review guidance
"""

from __future__ import annotations

from .conventions import framework_convention_entry
from .detection import detect_ecosystem_frameworks
from .guidance import framework_review_guidance, merge_review_guidance
from .phases import framework_phases
from .registry import (
    FRAMEWORK_SPECS,
    get_framework_spec,
    list_framework_specs,
    register_framework_spec,
)
from .types import (
    DetectionConfig,
    EcosystemFrameworkDetection,
    FrameworkSpec,
    ScannerRule,
    ToolIntegration,
)

__all__ = [
    "DetectionConfig",
    "EcosystemFrameworkDetection",
    "FRAMEWORK_SPECS",
    "FrameworkSpec",
    "ScannerRule",
    "ToolIntegration",
    "detect_ecosystem_frameworks",
    "framework_convention_entry",
    "framework_phases",
    "framework_review_guidance",
    "merge_review_guidance",
    "get_framework_spec",
    "list_framework_specs",
    "register_framework_spec",
]
