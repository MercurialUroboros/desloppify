"""Vue SFC script view: line-preserving, served through the shared readers."""

from __future__ import annotations

from pathlib import Path

import pytest

from desloppify.base.discovery.source import read_file_text
from desloppify.base.runtime_state import RuntimeContext, runtime_scope
from desloppify.base.source_views import has_source_view, source_view, vue_script_view

SFC = """<template>
  <div v-for="item in items" :key="item.id">{{ item.name }}</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
const items = ref<{ id: number; name: string }[]>([])
function load() {
  console.log("[Loader] loading")
  const next = items.value.length + 1
  items.value.push({ id: next, name: `item ${next}` })
  return next
}
</script>

<style scoped>
.a { color: red }
</style>
"""


def test_script_view_keeps_length_lines_and_columns():
    view = vue_script_view(SFC)
    assert len(view) == len(SFC)
    assert view.count("\n") == SFC.count("\n")
    lines = view.splitlines()
    # Script body lines are untouched and stay on their original line numbers.
    assert lines[5] == 'import { ref } from "vue"'
    assert lines[8] == '  console.log("[Loader] loading")'
    # Template and style are blanked, not removed.
    assert lines[1].strip() == ""
    assert lines[13].strip() == ""
    assert "<script" not in view and "</script>" not in view


def test_script_view_keeps_both_script_blocks():
    sfc = "<script>\nexport default { name: 'X' }\n</script>\n<script setup>\nconst a = 1\n</script>\n<template><p/></template>\n"
    view = vue_script_view(sfc)
    assert "export default { name: 'X' }" in view
    assert "const a = 1" in view
    assert "<template>" not in view


def test_script_view_without_script_is_blank_but_same_shape():
    sfc = "<template>\n  <p>hi</p>\n</template>\n"
    view = vue_script_view(sfc)
    assert view.strip() == ""
    assert view.count("\n") == 3


def test_source_view_only_applies_to_vue_files():
    assert has_source_view("app/components/UserCard.vue") is True
    assert has_source_view("src/app.ts") is False
    assert source_view("src/app.ts", SFC) == SFC


def test_read_file_text_serves_view_by_default_and_raw_on_request(tmp_path: Path):
    sfc = tmp_path / "UserCard.vue"
    sfc.write_text(SFC)
    ts = tmp_path / "a.ts"
    ts.write_text("export const a = 1\n")

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        view = read_file_text(str(sfc))
        raw = read_file_text(str(sfc), raw=True)
        assert read_file_text(str(ts)) == "export const a = 1\n"

    assert raw == SFC
    assert view != SFC
    assert "<template>" not in view
    assert len(view) == len(SFC)


def test_cached_reads_keep_raw_and_view_apart(tmp_path: Path):
    from desloppify.base.discovery.source import disable_file_cache, enable_file_cache

    sfc = tmp_path / "X.vue"
    sfc.write_text(SFC)
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        enable_file_cache()
        try:
            first_view = read_file_text(str(sfc))
            first_raw = read_file_text(str(sfc), raw=True)
            assert read_file_text(str(sfc)) == first_view
            assert read_file_text(str(sfc), raw=True) == first_raw
        finally:
            disable_file_cache()
    assert first_raw == SFC
    assert "<template>" not in first_view


def test_missing_file_is_none_in_both_flavours(tmp_path: Path):
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        assert read_file_text(str(tmp_path / "nope.vue")) is None
        assert read_file_text(str(tmp_path / "nope.vue"), raw=True) is None


# ── Downstream consumers ─────────────────────────────────────


def test_vue_component_is_not_a_unit_test_target():
    from desloppify.languages.typescript.test_coverage import has_testable_logic

    assert has_testable_logic("app/components/UserCard.vue", "const x = compute(1)") is False
    assert has_testable_logic("app/utils/x.ts", "export function f(a) { return a * 2 }") is True


def test_ts_function_extraction_reads_vue_script_view(tmp_path: Path):
    from desloppify.languages.typescript.extractors_functions import (
        extract_ts_functions,
    )

    sfc = tmp_path / "Comp.vue"
    sfc.write_text(SFC)
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        functions = extract_ts_functions(str(sfc))
    assert [f.name for f in functions] == ["load"]
    assert functions[0].line == 8


def test_tagged_logs_detected_inside_vue_script(tmp_path: Path):
    from desloppify.languages.typescript.detectors.logs import detect_logs

    (tmp_path / "Comp.vue").write_text(SFC)
    (tmp_path / "plain.ts").write_text('console.log("[Plain] x")\n')
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        result = detect_logs(tmp_path)
    found = {(Path(e["file"]).name, e["line"]) for e in result.entries}
    assert ("Comp.vue", 9) in found
    assert ("plain.ts", 1) in found


@pytest.mark.skipif(
    not __import__("desloppify.languages._framework.treesitter", fromlist=["is_available"]).is_available(),
    reason="tree-sitter-language-pack not installed",
)
def test_treesitter_parses_vue_script_view_with_tsx_grammar(tmp_path: Path):
    from desloppify.languages._framework.treesitter.analysis.extractors import (
        ts_extract_functions,
    )
    from desloppify.languages._framework.treesitter.specs.scripting import (
        TYPESCRIPT_SPEC,
    )

    sfc = tmp_path / "Comp.vue"
    sfc.write_text(SFC)
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        functions = ts_extract_functions(tmp_path, TYPESCRIPT_SPEC, [str(sfc)])
    names = {f.name: f for f in functions}
    assert "load" in names
    assert names["load"].line == 8
