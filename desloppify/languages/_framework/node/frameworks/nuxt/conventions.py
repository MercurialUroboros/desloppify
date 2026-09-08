"""Nuxt convention files that are entry points without importers.

Nuxt (and Nitro underneath it) wires most of an application by file location:
pages, layouts, components, composables and server handlers are discovered and
auto-imported, so nothing imports them explicitly. Without this knowledge the
orphaned-file detector reports a well-structured Nuxt app as mostly dead code.

Scan rules follow the Nuxt 4 docs (directory-structure, auto-imports, server):

- Nuxt 3 keeps app directories at the package root; Nuxt 4 moves them under
  ``app/`` (``srcDir``). ``server/``, ``shared/``, ``modules/``, ``layers/`` and
  ``nuxt.config.*`` stay at the root in both.
- ``components/`` and ``pages/`` are scanned recursively.
- ``composables/``, ``utils/``, ``server/utils/``, ``shared/utils/`` and
  ``shared/types/`` are scanned at top level only; nested files must be
  imported explicitly, so a nested file with no importers really is orphaned.
- ``layouts/``, ``middleware/`` and ``plugins/`` are registered at top level.
- ``server/api``, ``server/routes``, ``server/middleware``, ``server/plugins``
  and ``server/tasks`` are file-routed at any depth.
- ``layers/<name>/`` mirrors either layout.

A custom ``srcDir`` (for example ``src/``) is not detected.
"""

from __future__ import annotations

from pathlib import Path

NUXT_EXTENSIONS: frozenset[str] = frozenset({
    ".vue", ".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs",
})

# Client directories scanned recursively (relative to srcDir).
NUXT_CLIENT_DIRS_RECURSIVE: frozenset[str] = frozenset({"pages", "components"})

# Client directories scanned at top level only (relative to srcDir).
NUXT_CLIENT_DIRS_TOP_LEVEL: frozenset[str] = frozenset({
    "composables",
    "utils",
    "layouts",
    "middleware",
    "plugins",
    "stores",  # @pinia/nuxt
})

# Nitro directories file-routed at any depth.
NUXT_SERVER_DIRS_RECURSIVE: frozenset[str] = frozenset({
    "api",
    "routes",
    "middleware",
    "plugins",
    "tasks",
})

# Nitro directories auto-imported at top level only.
NUXT_SERVER_DIRS_TOP_LEVEL: frozenset[str] = frozenset({"utils"})

# shared/ directories auto-imported (top level only) in both app and server.
NUXT_SHARED_DIRS_TOP_LEVEL: frozenset[str] = frozenset({"utils", "types"})

# Convention files at srcDir or package root.
NUXT_ROOT_FILES: frozenset[str] = frozenset({"app.vue", "error.vue"})
NUXT_ROOT_STEMS: frozenset[str] = frozenset({
    "app.config",
    "nuxt.config",
    "router.options",
    "i18n.config",
    "content.config",
})

NUXT_MODULES_DIR = "modules"
NUXT_SRC_DIR = "app"
NUXT_LAYERS_DIR = "layers"
NUXT_SHARED_DIR = "shared"


def _strip_layer_prefix(parts: tuple[str, ...]) -> tuple[str, ...]:
    if len(parts) > 2 and parts[0] == NUXT_LAYERS_DIR:
        return parts[2:]
    return parts


def _is_root_convention_file(parts: tuple[str, ...], stem: str) -> bool:
    return len(parts) == 1 and (parts[0] in NUXT_ROOT_FILES or stem in NUXT_ROOT_STEMS)


def _in_scanned_dir(
    parts: tuple[str, ...],
    *,
    recursive: frozenset[str],
    top_level: frozenset[str],
) -> bool:
    if len(parts) < 2:
        return False
    if parts[0] in recursive:
        return True
    return parts[0] in top_level and len(parts) == 2


def is_nuxt_convention_entry(rel_path: str) -> bool:
    """Return True if *rel_path* (package-relative) is a Nuxt convention file."""
    p = Path(rel_path)
    if p.suffix not in NUXT_EXTENSIONS:
        return False

    parts = _strip_layer_prefix(p.parts)
    if not parts:
        return False

    # Package-root conventions.
    if _is_root_convention_file(parts, p.stem):
        return True
    if parts[0] == NUXT_MODULES_DIR:
        return len(parts) > 1
    if parts[0] == "server":
        return _in_scanned_dir(
            parts[1:],
            recursive=NUXT_SERVER_DIRS_RECURSIVE,
            top_level=NUXT_SERVER_DIRS_TOP_LEVEL,
        )
    if parts[0] == NUXT_SHARED_DIR:
        return _in_scanned_dir(
            parts[1:],
            recursive=frozenset(),
            top_level=NUXT_SHARED_DIRS_TOP_LEVEL,
        )

    # Client conventions: at package root (Nuxt 3) or under app/ (Nuxt 4).
    if parts[0] == NUXT_SRC_DIR:
        parts = parts[1:]
        if _is_root_convention_file(parts, p.stem):
            return True
    return _in_scanned_dir(
        parts,
        recursive=NUXT_CLIENT_DIRS_RECURSIVE,
        top_level=NUXT_CLIENT_DIRS_TOP_LEVEL,
    )


__all__ = [
    "NUXT_CLIENT_DIRS_RECURSIVE",
    "NUXT_CLIENT_DIRS_TOP_LEVEL",
    "NUXT_EXTENSIONS",
    "NUXT_ROOT_FILES",
    "NUXT_ROOT_STEMS",
    "NUXT_SERVER_DIRS_RECURSIVE",
    "NUXT_SERVER_DIRS_TOP_LEVEL",
    "NUXT_SHARED_DIRS_TOP_LEVEL",
    "is_nuxt_convention_entry",
]
