"""Nuxt framework support shared across JS/TS scans."""

from __future__ import annotations

from .conventions import is_nuxt_convention_entry
from .guidance import NUXT_REVIEW_GUIDANCE

__all__ = ["NUXT_REVIEW_GUIDANCE", "is_nuxt_convention_entry"]
