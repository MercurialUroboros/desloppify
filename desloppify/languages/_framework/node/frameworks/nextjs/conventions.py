"""Next.js convention files that are entry points without importers."""

from __future__ import annotations

from pathlib import Path

# Files that are entry points when inside an app/ directory
NEXTJS_APP_DIR_CONVENTIONS: frozenset[str] = frozenset({
    "page",
    "layout",
    "loading",
    "error",
    "not-found",
    "global-error",
    "route",
    "template",
    "default",
    "opengraph-image",
    "twitter-image",
    "sitemap",
    "robots",
    "icon",
    "apple-icon",
})

# Files that are entry points at the project root (or src/)
NEXTJS_ROOT_CONVENTIONS: frozenset[str] = frozenset({
    "middleware",
    "instrumentation",
    "instrumentation-client",
})

NEXTJS_EXTENSIONS: frozenset[str] = frozenset({".ts", ".tsx", ".js", ".jsx"})


def is_nextjs_convention_entry(rel_path: str) -> bool:
    """Return True if *rel_path* (package-relative) is a Next.js convention file.

    Checks:
    - Files with convention names inside any ``app/`` directory segment
    - Root-level convention files (middleware, instrumentation)
    """
    p = Path(rel_path)
    if p.suffix not in NEXTJS_EXTENSIONS:
        return False

    stem = p.stem
    parts = p.parts

    # Root-level conventions: middleware.ts, instrumentation.ts, etc.
    # These can live at the project root or inside src/
    if stem in NEXTJS_ROOT_CONVENTIONS and len(parts) <= 2:
        return True

    # App directory conventions: any file inside an app/ segment
    return stem in NEXTJS_APP_DIR_CONVENTIONS and "app" in parts


__all__ = [
    "NEXTJS_APP_DIR_CONVENTIONS",
    "NEXTJS_EXTENSIONS",
    "NEXTJS_ROOT_CONVENTIONS",
    "is_nextjs_convention_entry",
]
