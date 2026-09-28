"""A literal import('...') is an edge loaded at call time: an importer, never a cycle."""

from __future__ import annotations

from pathlib import Path

from desloppify.base.runtime_state import RuntimeContext, runtime_scope
from desloppify.engine.detectors.graph import detect_cycles
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


def _node(root: Path, graph: dict, name: str) -> dict:
    return graph[str((root / name).resolve())]


def test_dynamic_import_counts_as_an_importer(tmp_path):
    graph = _project(tmp_path, {
        "route.ts": "export default () => 1\n",
        "route.test.ts": "const mod = (await import('./route')).default\nexport const t = mod\n",
    })
    route = _node(tmp_path, graph, "route.ts")
    assert route["importer_count"] == 1
    test = _node(tmp_path, graph, "route.test.ts")
    assert str((tmp_path / "route.ts").resolve()) in test["deferred_imports"]


def test_dynamic_import_does_not_close_a_cycle(tmp_path):
    graph = _project(tmp_path, {
        "a.ts": "export async function a() { return (await import('./b')).b }\n",
        "b.ts": "import { a } from './a'\nexport const b = a\n",
    })
    cycles, _ = detect_cycles(graph)
    assert cycles == []
    assert _node(tmp_path, graph, "b.ts")["importer_count"] == 1


def test_static_import_beside_a_dynamic_one_stays_a_value_edge(tmp_path):
    graph = _project(tmp_path, {
        "a.ts": "import { b } from './b'\nexport async function a() { return (await import('./b')).b }\n",
        "b.ts": "import { a } from './a'\nexport const b = a\n",
    })
    cycles, _ = detect_cycles(graph)
    assert [sorted(Path(f).name for f in c["files"]) for c in cycles] == [["a.ts", "b.ts"]]


def test_template_literal_dynamic_import_is_not_an_edge(tmp_path):
    graph = _project(tmp_path, {
        "route.ts": "export default () => 1\n",
        "route.test.ts": "const name = 'route'\nexport const t = await import(`./${name}`)\n",
    })
    route = graph.get(str((tmp_path / "route.ts").resolve()), {})
    assert route.get("importer_count", 0) == 0
