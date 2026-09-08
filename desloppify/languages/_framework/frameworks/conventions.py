"""Compose framework convention entry-point predicates for a scan."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from desloppify.base.discovery.file_paths import rel
from desloppify.languages._framework.base.types import LangRuntimeContract

from .detection import detect_ecosystem_frameworks
from .registry import get_framework_spec


def _package_prefix(package_root: Path) -> str:
    """Project-relative prefix of the package root, as ``rel()`` would render file paths.

    ``rel()`` falls back to ``../pkg`` style paths when the scan target sits
    outside the project root (``desloppify scan --path ../other``), so the same
    helper is used here to keep the prefix and the file paths consistent.
    """
    prefix = rel(package_root)
    return "" if prefix in ("", ".") else prefix + "/"


def framework_convention_entry(
    scan_path: Path,
    lang: LangRuntimeContract | None,
    ecosystem: str = "node",
) -> Callable[[str], bool] | None:
    """Return a predicate over project-relative paths, or None when no framework applies.

    The predicate strips the package prefix (monorepo sub-packages) before
    delegating to each detected framework's ``convention_entry``.
    """
    detection = detect_ecosystem_frameworks(scan_path, lang, ecosystem)
    predicates: list[Callable[[str], bool]] = []
    for framework_id in detection.present:
        spec = get_framework_spec(framework_id)
        if spec is not None and spec.convention_entry is not None:
            predicates.append(spec.convention_entry)
    if not predicates:
        return None

    prefix = _package_prefix(detection.package_root)

    def is_convention_entry(rel_path: str) -> bool:
        path = rel_path.replace("\\", "/")
        if prefix and path.startswith(prefix):
            path = path[len(prefix):]
        return any(predicate(path) for predicate in predicates)

    return is_convention_entry


__all__ = ["framework_convention_entry"]
