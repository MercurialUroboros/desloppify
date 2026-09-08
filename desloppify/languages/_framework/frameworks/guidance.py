"""Framework review guidance: collect for detected frameworks and merge into language guidance."""

from __future__ import annotations

from pathlib import Path

from desloppify.languages._framework.base.types import LangRuntimeContract

from .detection import detect_ecosystem_frameworks
from .registry import get_framework_spec


def framework_review_guidance(
    scan_path: Path,
    lang: LangRuntimeContract | None,
    ecosystem: str = "node",
) -> dict[str, dict[str, object]]:
    """Return ``{framework_id: guidance}`` for frameworks present in the scan."""
    detection = detect_ecosystem_frameworks(scan_path, lang, ecosystem)
    out: dict[str, dict[str, object]] = {}
    for framework_id in sorted(detection.present):
        spec = get_framework_spec(framework_id)
        if spec is not None and spec.review_guidance:
            out[framework_id] = dict(spec.review_guidance)
    return out


def merge_review_guidance(
    lang_guidance: dict[str, object],
    framework_guidance: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Merge framework guidance into a copy of the language guidance.

    Lists are concatenated (framework items after language items, de-duplicated),
    strings are joined with a blank line, and the raw per-framework guidance is
    kept under ``frameworks`` so agents can tell which framework a hint targets.
    """
    if not framework_guidance:
        return dict(lang_guidance)

    merged: dict[str, object] = {}
    for key, value in lang_guidance.items():
        merged[key] = list(value) if isinstance(value, list) else value

    for guide in framework_guidance.values():
        for key, value in guide.items():
            existing = merged.get(key)
            if isinstance(value, list):
                items = list(existing) if isinstance(existing, list) else []
                for item in value:
                    if item not in items:
                        items.append(item)
                merged[key] = items
            elif isinstance(value, str):
                merged[key] = f"{existing}\n\n{value}" if isinstance(existing, str) and existing else value
            else:
                merged[key] = value

    merged["frameworks"] = {fid: dict(guide) for fid, guide in framework_guidance.items()}
    return merged


__all__ = ["framework_review_guidance", "merge_review_guidance"]
