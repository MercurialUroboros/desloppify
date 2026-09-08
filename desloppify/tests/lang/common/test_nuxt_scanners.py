"""Nuxt scanner rules on a synthetic Nuxt 4 project."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from desloppify.base.runtime_state import RuntimeContext, runtime_scope
from desloppify.languages._framework.frameworks.specs.nuxt import (
    NUXT_SCANNERS,
    NUXT_SPEC,
)
from desloppify.languages._framework.node.frameworks.nuxt import (
    nuxt_info_from_package_root,
    scan_nuxt_browser_globals_in_setup,
    scan_nuxt_define_page_meta_outside_pages,
    scan_nuxt_module_state_in_composables,
    scan_nuxt_process_env_in_app,
    scan_nuxt_public_runtime_secrets,
    scan_nuxt_server_imports_in_app,
    scan_nuxt_top_level_fetch_in_setup,
    scan_nuxt_unvalidated_handler_input,
    scan_nuxt_vue_router_imports,
)
from desloppify.languages.typescript.test_coverage import (
    has_testable_logic,
    is_thin_nitro_handler,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def nuxt4(tmp_path: Path) -> Path:
    root = tmp_path / "site"
    _write(root / "package.json", json.dumps({"dependencies": {"nuxt": "^4.0.0"}}))
    _write(
        root / "nuxt.config.ts",
        """// config
export default defineNuxtConfig({
  runtimeConfig: {
    stripeSecret: process.env.STRIPE_SECRET,
    public: {
      siteUrl: 'https://example.com',
      supabaseKey: process.env.SUPABASE_KEY,
      serviceRoleToken: '',
      paddleClientToken: 'test_',
      apiBaseUrl: '/api',
    },
  },
})
""",
    )
    _write(root / "app" / "app.vue", "<template><NuxtPage /></template>\n")
    _write(
        root / "app" / "components" / "Bad.vue",
        """<template>
  <div>{{ data }}</div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import type { Payload } from '~~/server/api/data.get'
import { helper } from '~~/server/utils/helper'
definePageMeta({ layout: 'x' })
const data = await $fetch('/api/data')
const width = window.innerWidth
const token = process.env.API_TOKEN
const env = process.env.NODE_ENV
function later() {
  const w = window.innerWidth
  return w
}
</script>
""",
    )
    _write(
        root / "app" / "pages" / "index.vue",
        """<script setup lang="ts">
definePageMeta({ layout: 'default' })
const { data } = await useFetch('/api/data')
</script>
<template><div>{{ data }}</div></template>
""",
    )
    _write(
        root / "app" / "composables" / "useCart.ts",
        """import { ref } from 'vue'
const items = ref<string[]>([])   // shared across requests!
export function useCart() {
  const count = ref(0)
  return { items, count }
}
""",
    )
    _write(
        root / "server" / "api" / "orders.post.ts",
        """/**
 * Creates an order.
 * Multi-line comment: must not shift reported line numbers.
 */
export default defineEventHandler(async (event) => {
  const body = await readBody(event) // raw
  return createOrder(body)
})
""",
    )
    _write(root / "app" / "plugins" / "auth.server.ts", "import { x } from '~~/server/utils/auth'\nexport default defineNuxtPlugin(() => x)\n")
    _write(root / "app" / "composables" / "__tests__" / "useCart.test.ts", "const items = ref([])\n")
    _write(root / "server" / "api" / "upload.post.ts", "export default defineEventHandler(async (event) => {\n  const form = await readFormData(event)\n  return save(form)\n})\n")
    _write(
        root / "server" / "api" / "users.post.ts",
        """import { z } from 'zod'
const schema = z.object({ name: z.string() })
export default defineEventHandler(async (event) => {
  const body = await readValidatedBody(event, schema.parse)
  return createUser(body)
})
""",
    )
    return root


def _rel(entries: list[dict], root: Path) -> list[tuple[str, int]]:
    out = []
    for e in entries:
        p = Path(e["file"])
        rel = p.relative_to(root).as_posix() if p.is_absolute() else e["file"].split("site/", 1)[-1]
        out.append((rel, e["line"]))
    return sorted(out)


def test_layout_detection(nuxt4: Path):
    info = nuxt_info_from_package_root(nuxt4)
    assert info.src_dir == "app"
    assert info.is_app_code("app/components/Bad.vue")
    assert not info.is_app_code("server/api/x.ts")
    assert info.is_page("app/pages/index.vue")
    assert info.is_composable("app/composables/useCart.ts")


def test_scanners_on_nuxt4_project(nuxt4: Path):
    info = nuxt_info_from_package_root(nuxt4)
    with runtime_scope(RuntimeContext(project_root=nuxt4)):
        server_imports, _ = scan_nuxt_server_imports_in_app(info)
        env, _ = scan_nuxt_process_env_in_app(info)
        router, _ = scan_nuxt_vue_router_imports(info)
        page_meta, _ = scan_nuxt_define_page_meta_outside_pages(info)
        fetch, _ = scan_nuxt_top_level_fetch_in_setup(info)
        globals_, _ = scan_nuxt_browser_globals_in_setup(info)
        module_state, _ = scan_nuxt_module_state_in_composables(info)
        unvalidated, _ = scan_nuxt_unvalidated_handler_input(info)
        secrets, _ = scan_nuxt_public_runtime_secrets(info)

    # `import type` from server files is erased at build time: not flagged.
    assert _rel(server_imports, nuxt4) == [("app/components/Bad.vue", 8)]
    assert server_imports[0]["spec"] == "~~/server/utils/helper"
    # NODE_ENV is allowed; API_TOKEN is not.
    assert _rel(env, nuxt4) == [("app/components/Bad.vue", 12)]
    assert _rel(router, nuxt4) == [("app/components/Bad.vue", 6)]
    # pages/index.vue is a page: allowed.
    assert _rel(page_meta, nuxt4) == [("app/components/Bad.vue", 9)]
    assert _rel(fetch, nuxt4) == [("app/components/Bad.vue", 10)]
    # Only the top-level window access, not the one inside later().
    assert _rel(globals_, nuxt4) == [("app/components/Bad.vue", 11)]
    assert _rel(module_state, nuxt4) == [("app/composables/useCart.ts", 2)]
    assert _rel(unvalidated, nuxt4) == [("server/api/orders.post.ts", 6)]
    # supabaseKey and paddleClientToken are publishable: allowed. serviceRoleToken is not.
    assert [(e["key"], e["line"]) for e in secrets] == [("serviceRoleToken", 8)]


def test_scanner_rules_are_wired_with_unique_ids():
    ids = [rule.id for rule in NUXT_SCANNERS]
    assert len(ids) == len(set(ids)) == 9
    assert NUXT_SPEC.scanners == NUXT_SCANNERS
    for rule in NUXT_SCANNERS:
        assert rule.scan is not None and rule.issue_factory is not None


def test_scanner_issue_factories_build_issues(nuxt4: Path):

    class FakeLang:
        runtime_cache: dict = {}

    with runtime_scope(RuntimeContext(project_root=nuxt4)):
        for rule in NUXT_SCANNERS:
            entries, scanned = rule.scan(nuxt4, FakeLang())
            assert scanned >= 1, rule.id
            for entry in entries:
                issue = rule.issue_factory(entry)
                assert issue["detector"] == "nuxt"
                assert issue["id"].startswith(f"nuxt::")
                assert issue["detail"]["line"] == entry["line"]


# ── Thin Nitro handlers and test coverage ─────────────────────


def test_thin_handler_is_not_a_unit_test_target():
    thin = "export default defineEventHandler(async (event) => {\n  return listUsers(event)\n})\n"
    assert is_thin_nitro_handler("server/api/users.get.ts", thin) is True
    assert has_testable_logic("server/api/users.get.ts", thin) is False
    # Same file outside server/api is judged normally.
    assert is_thin_nitro_handler("server/utils/users.ts", thin) is False


def test_fat_handler_still_needs_tests():
    body = "export default defineEventHandler(async (event) => {\n"
    body += "".join(f"  const v{i} = compute{i}(event, {i})\n  if (v{i} > {i}) throw createError({{ statusCode: 400 }})\n" for i in range(30))
    body += "  return ok\n})\n"
    assert is_thin_nitro_handler("server/api/big.post.ts", body) is False
    assert has_testable_logic("server/api/big.post.ts", body) is True


def test_blank_js_ts_comments_keeps_layout():
    from desloppify.languages._framework.node.js_text import blank_js_ts_comments

    src = "const a = 1 // note\n/* multi\n   line */ const url = 'http://x' /* t */\nconst b = 2\n"
    out = blank_js_ts_comments(src)
    assert len(out) == len(src)
    assert out.count("\n") == src.count("\n")
    assert "note" not in out and "multi" not in out
    assert "'http://x'" in out  # strings untouched, including // inside them
    assert out.splitlines()[3] == "const b = 2"
