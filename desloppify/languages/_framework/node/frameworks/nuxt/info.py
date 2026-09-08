"""Nuxt project layout derived from framework detection evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_SRC_DIR_MARKERS = ("app.vue", "pages", "components", "layouts", "composables", "error.vue")


@dataclass(frozen=True)
class NuxtFrameworkInfo:
    package_root: Path
    src_dir: str  # "app" for Nuxt 4, "" for the Nuxt 3 root layout

    @property
    def src_root(self) -> Path:
        return self.package_root / self.src_dir if self.src_dir else self.package_root

    def is_app_code(self, rel_path: str) -> bool:
        """True for files under srcDir that are not server/shared/module code."""
        parts = Path(rel_path).parts
        if not parts:
            return False
        if self.src_dir:
            return parts[0] == self.src_dir
        return parts[0] not in {"server", "shared", "modules", "layers", "public", "node_modules"}

    def is_server_code(self, rel_path: str) -> bool:
        parts = Path(rel_path).parts
        return len(parts) > 1 and parts[0] == "server"

    def is_page(self, rel_path: str) -> bool:
        parts = Path(rel_path).parts
        if self.src_dir:
            return len(parts) > 2 and parts[0] == self.src_dir and parts[1] == "pages"
        return len(parts) > 1 and parts[0] == "pages"

    def is_composable(self, rel_path: str) -> bool:
        parts = Path(rel_path).parts
        if self.src_dir:
            return len(parts) > 2 and parts[0] == self.src_dir and parts[1] == "composables"
        return len(parts) > 1 and parts[0] == "composables"


def nuxt_info_from_package_root(package_root: Path) -> NuxtFrameworkInfo:
    """Detect the Nuxt 3 (root) vs Nuxt 4 (``app/``) layout."""
    app_dir = package_root / "app"
    if app_dir.is_dir() and any((app_dir / marker).exists() for marker in _SRC_DIR_MARKERS):
        return NuxtFrameworkInfo(package_root=package_root, src_dir="app")
    return NuxtFrameworkInfo(package_root=package_root, src_dir="")


__all__ = ["NuxtFrameworkInfo", "nuxt_info_from_package_root"]
