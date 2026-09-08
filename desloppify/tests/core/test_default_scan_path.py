"""Default scan path falls back to the project root when default_src is absent."""

from __future__ import annotations

from desloppify.base.discovery.paths import get_default_path, get_default_scan_path


def test_default_src_used_when_present(tmp_path):
    (tmp_path / "src").mkdir()
    assert get_default_scan_path(project_root=tmp_path, default_src="src") == tmp_path / "src"


def test_project_root_when_default_src_missing(tmp_path):
    (tmp_path / "app").mkdir()  # Nuxt 4 layout: no src/
    assert get_default_scan_path(project_root=tmp_path, default_src="src") == tmp_path
    assert get_default_path(project_root=tmp_path) == tmp_path
