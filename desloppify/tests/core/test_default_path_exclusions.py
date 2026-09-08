"""Nested default exclusions (git worktrees under .claude/) are pruned."""

from __future__ import annotations

from desloppify.base.discovery.source import find_source_files
from desloppify.base.runtime_state import RuntimeContext, runtime_scope


def _write(path, text="export const x = 1;\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_claude_worktrees_are_not_scanned(tmp_path):
    keep = tmp_path / "src" / "a.ts"
    _write(keep)
    _write(tmp_path / ".claude" / "worktrees" / "feature-x" / "src" / "a.ts")
    _write(tmp_path / ".claude" / "settings.ts")  # sibling content still scanned

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        found = sorted(find_source_files(tmp_path, [".ts"]))

    assert [f.replace(str(tmp_path) + "/", "") for f in found] == [
        ".claude/settings.ts",
        "src/a.ts",
    ]


def test_worktrees_dir_elsewhere_is_scanned(tmp_path):
    other = tmp_path / "tools" / "worktrees" / "b.ts"
    _write(other)
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        found = find_source_files(tmp_path, [".ts"])
    assert [f.replace(str(tmp_path) + "/", "") for f in found] == ["tools/worktrees/b.ts"]


def test_worktrees_pruned_when_scan_target_is_outside_project_root(tmp_path):
    """`desloppify scan --path ../site` renders dirs as `../site/...`."""
    project = tmp_path / "tool"
    project.mkdir()
    site = tmp_path / "site"
    _write(site / "src" / "a.ts")
    _write(site / ".claude" / "worktrees" / "wt" / "src" / "a.ts")

    with runtime_scope(RuntimeContext(project_root=project)):
        found = find_source_files(site, [".ts"])

    assert [f.split("site/", 1)[1] for f in found] == ["src/a.ts"]
