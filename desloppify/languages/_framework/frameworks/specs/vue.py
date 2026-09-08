"""Vue framework spec (Node ecosystem).

Contributes Vue review guidance to review packets. Vue is also present in every
Nuxt project, so Nuxt guidance layers on top of this one rather than repeating
it. No convention entry points: plain Vue apps import components explicitly
(auto-import plugins such as unplugin-vue-components are not modelled).
"""

from __future__ import annotations

from desloppify.languages._framework.node.frameworks.vue import VUE_REVIEW_GUIDANCE

from ..types import DetectionConfig, FrameworkSpec

VUE_SPEC = FrameworkSpec(
    id="vue",
    label="Vue",
    ecosystem="node",
    detection=DetectionConfig(
        dependencies=("vue",),
        config_files=(),
        marker_dirs=(),
        marker_dirs_imply_presence=False,
    ),
    review_guidance=VUE_REVIEW_GUIDANCE,
)

__all__ = ["VUE_SPEC"]
