"""Type-only imports are erased by TypeScript, so they cannot close a runtime import cycle."""

from __future__ import annotations

from pathlib import Path

from desloppify.base.runtime_state import RuntimeContext, runtime_scope
from desloppify.engine.detectors.graph import detect_cycles
from desloppify.engine.detectors.orphaned import detect_orphaned_files
from desloppify.languages.typescript.detectors.deps import build_dep_graph
from desloppify.languages.typescript.detectors.deps.resolve import load_tsconfig_paths_cached


def _project(root: Path, files: dict[str, str]) -> dict:
    for name, text in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    load_tsconfig_paths_cached.cache_clear()
    with runtime_scope(RuntimeContext(project_root=root)):
        return build_dep_graph(root)


def _cycle_files(root: Path, graph: dict) -> list[list[str]]:
    cycles, _ = detect_cycles(graph)
    return [sorted(Path(f).name for f in cycle["files"]) for cycle in cycles]


def _node(root: Path, graph: dict, name: str) -> dict:
    return graph[str((root / name).resolve())]


def test_import_type_does_not_close_a_cycle(tmp_path):
    graph = _project(tmp_path, {
        "a.ts": "import type { B } from './b'\nexport const a = 1\n",
        "b.ts": "import { a } from './a'\nexport interface B { n: number }\nexport const b = a\n",
    })
    assert _cycle_files(tmp_path, graph) == []
    # The edge still exists for every other consumer of the graph.
    assert _node(tmp_path, graph, "b.ts")["importer_count"] == 1


def test_value_cycle_is_still_reported(tmp_path):
    graph = _project(tmp_path, {
        "a.ts": "import { b } from './b'\nexport const a = 1\n",
        "b.ts": "import { a } from './a'\nexport const b = a\n",
    })
    assert _cycle_files(tmp_path, graph) == [["a.ts", "b.ts"]]


def test_multiline_import_type_is_type_only(tmp_path):
    graph = _project(tmp_path, {
        "a.ts": "import type {\n  B,\n  C,\n} from './b'\nexport const a = 1\n",
        "b.ts": "import { a } from './a'\nexport type B = number\nexport type C = string\n",
    })
    assert _cycle_files(tmp_path, graph) == []


def test_export_type_from_is_type_only(tmp_path):
    graph = _project(tmp_path, {
        "a.ts": "export type {\n  B,\n} from './b'\nexport const a = 1\n",
        "b.ts": "import { a } from './a'\nexport type B = number\n",
    })
    assert _cycle_files(tmp_path, graph) == []


def test_all_type_named_bindings_are_type_only(tmp_path):
    graph = _project(tmp_path, {
        "a.ts": "import { type B, type C as D } from './b'\nexport const a = 1\n",
        "b.ts": "import { a } from './a'\nexport type B = number\nexport type C = string\n",
    })
    assert _cycle_files(tmp_path, graph) == []


def test_mixed_named_bindings_are_a_value_edge(tmp_path):
    graph = _project(tmp_path, {
        "a.ts": "import { type B, c } from './b'\nexport const a = c\n",
        "b.ts": "import { a } from './a'\nexport type B = number\nexport const c = 1\n",
    })
    assert _cycle_files(tmp_path, graph) == [["a.ts", "b.ts"]]


def test_same_target_imported_as_value_and_type_is_a_value_edge(tmp_path):
    graph = _project(tmp_path, {
        "a.ts": "import type { B } from './b'\nimport { c } from './b.ts'\nexport const a = c\n",
        "b.ts": "import { a } from './a'\nexport type B = number\nexport const c = a\n",
    })
    assert _cycle_files(tmp_path, graph) == [["a.ts", "b.ts"]]


def test_side_effect_import_is_a_value_edge(tmp_path):
    graph = _project(tmp_path, {
        "a.ts": "import './b'\nexport const a = 1\n",
        "b.ts": "import { a } from './a'\nexport const b = a\n",
    })
    assert _cycle_files(tmp_path, graph) == [["a.ts", "b.ts"]]


def test_framework_file_type_import_does_not_close_a_cycle(tmp_path):
    graph = _project(tmp_path, {
        "Card.vue": (
            '<script setup lang="ts">\nimport type {\n  CardProps,\n} from "./card"\n'
            "defineProps<CardProps>()\n</script>\n<template><div /></template>\n"
        ),
        "card.ts": "import Card from './Card.vue'\nexport interface CardProps { n: number }\nexport default Card\n",
    })
    assert _cycle_files(tmp_path, graph) == []
    assert _node(tmp_path, graph, "card.ts")["importer_count"] == 1


def test_interface_file_imported_only_by_type_is_not_orphaned(tmp_path):
    graph = _project(tmp_path, {
        "main.ts": "import type { Shape } from './shapes'\nexport const area = (s: Shape) => s.w * s.h\n",
        "shapes.ts": "export interface Shape { w: number; h: number }\n",
    })
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_orphaned_files(tmp_path, graph, extensions=[".ts"])
    orphaned = {Path(e["file"]).name for e in entries}
    assert "shapes.ts" not in orphaned
