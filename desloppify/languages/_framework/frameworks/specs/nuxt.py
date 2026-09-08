"""Nuxt framework spec (Node ecosystem).

Currently contributes convention-based entry points (so auto-imported
components, composables and Nitro handlers are not reported as orphaned) and
Vue/Nuxt review guidance. Scanner rules are the next extension point.
"""

from __future__ import annotations

from desloppify.languages._framework.node.frameworks.nuxt import (
    NUXT_REVIEW_GUIDANCE,
    is_nuxt_convention_entry,
)

from ..types import DetectionConfig, FrameworkSpec

NUXT_SPEC = FrameworkSpec(
    id="nuxt",
    label="Nuxt",
    ecosystem="node",
    detection=DetectionConfig(
        dependencies=("nuxt",),
        dev_dependencies=("nuxt",),
        config_files=(
            "nuxt.config.ts",
            "nuxt.config.js",
            "nuxt.config.mjs",
        ),
        marker_dirs=("app", "pages", "server", "composables", "layers"),
        script_pattern=r"(?:^|\s)nuxt(?:\s|$)",
        marker_dirs_imply_presence=False,
    ),
    convention_entry=is_nuxt_convention_entry,
    review_guidance=NUXT_REVIEW_GUIDANCE,
)

__all__ = ["NUXT_SPEC"]
