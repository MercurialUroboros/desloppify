"""Framework convention entry points and review guidance (Next.js, Nuxt)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from desloppify.base.runtime_state import RuntimeContext, runtime_scope
from desloppify.languages._framework.frameworks import (
    framework_convention_entry,
    framework_review_guidance,
    merge_review_guidance,
)
from desloppify.languages._framework.node.frameworks.nextjs import (
    is_nextjs_convention_entry,
)
from desloppify.languages._framework.node.frameworks.nuxt import (
    NUXT_REVIEW_GUIDANCE,
    is_nuxt_convention_entry,
)
from desloppify.languages._framework.node.frameworks.vue import VUE_REVIEW_GUIDANCE

# ── Next.js (moved out of the engine) ─────────────────────────


@pytest.mark.parametrize(
    "rel_path",
    [
        "app/dashboard/page.tsx",
        "app/layout.tsx",
        "app/shop/items/loading.jsx",
        "app/api/users/route.ts",
        "app/error.tsx",
        "app/not-found.tsx",
        "app/global-error.tsx",
        "app/template.tsx",
        "app/@modal/default.tsx",
        "app/opengraph-image.tsx",
        "app/sitemap.ts",
        "app/robots.ts",
        "middleware.ts",
        "src/middleware.ts",
        "instrumentation.ts",
        "src/instrumentation-client.js",
        "src/app/page.tsx",
    ],
)
def test_nextjs_convention_entries(rel_path):
    assert is_nextjs_convention_entry(rel_path) is True


@pytest.mark.parametrize(
    "rel_path",
    [
        "app/utils/helpers.ts",
        "src/components/page.tsx",
        "src/lib/middleware.ts",
        "app/page.py",
        "app/page.css",
    ],
)
def test_nextjs_non_convention_files(rel_path):
    assert is_nextjs_convention_entry(rel_path) is False


# ── Nuxt ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "rel_path",
    [
        # Nuxt 4 (srcDir = app/)
        "app/app.vue",
        "app/error.vue",
        "app/app.config.ts",
        "app/router.options.ts",
        "app/pages/index.vue",
        "app/pages/blog/[slug].vue",
        "app/layouts/default.vue",
        "app/components/UserCard.vue",
        "app/components/auction/BuzzConsole.vue",
        "app/components/Comments.client.vue",
        "app/composables/useAuth.ts",
        "app/utils/format.ts",
        "app/middleware/auth.global.ts",
        "app/plugins/sentry.client.ts",
        "app/stores/cart.ts",
        # Nuxt 3 (srcDir = root)
        "app.vue",
        "error.vue",
        "pages/index.vue",
        "components/ui/Modal.vue",
        "composables/useFoo.ts",
        "layouts/default.vue",
        # Root-level in both
        "nuxt.config.ts",
        "app.config.ts",
        "modules/my-module/index.ts",
        "server/api/users.get.ts",
        "server/api/championship/[slug]/page.get.ts",
        "server/routes/sitemap.xml.ts",
        "server/middleware/auth.ts",
        "server/plugins/db.ts",
        "server/tasks/cleanup.ts",
        "server/utils/db.ts",
        "shared/utils/capitalize.ts",
        "shared/types/user.ts",
        # Layers mirror either layout
        "layers/base/app/components/Hero.vue",
        "layers/base/server/api/ping.get.ts",
        "layers/base/nuxt.config.ts",
    ],
)
def test_nuxt_convention_entries(rel_path):
    assert is_nuxt_convention_entry(rel_path) is True


@pytest.mark.parametrize(
    "rel_path",
    [
        # Not auto-imported: nested composables/utils must be imported explicitly.
        "app/composables/nested/helper.ts",
        "app/utils/nested/x.ts",
        "server/utils/nested/db.ts",
        "shared/utils/nested/lower.ts",
        "shared/formatters/lower.ts",
        # Regular code outside conventions.
        "src/lib/api.ts",
        "server/db/schema.ts",
        "server/index.ts",
        "emails/Welcome.vue",
        "app/lib/helpers.ts",
        "app/components/README.md",
        "docs/nuxt.config.ts",
        "app/pages.ts",
    ],
)
def test_nuxt_non_convention_files(rel_path):
    assert is_nuxt_convention_entry(rel_path) is False


# ── Composition through detection ─────────────────────────────


def _write(path: Path, text: str = "export const x = 1;\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_predicate_is_none_without_frameworks(tmp_path):
    _write(tmp_path / "package.json", json.dumps({"dependencies": {"vue": "3"}}))
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        assert framework_convention_entry(tmp_path, None) is None


def test_nuxt_predicate_from_package_json(tmp_path):
    _write(tmp_path / "package.json", json.dumps({"dependencies": {"nuxt": "^4.0.0"}}))
    _write(tmp_path / "nuxt.config.ts", "export default defineNuxtConfig({});\n")
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        predicate = framework_convention_entry(tmp_path, None)
        assert predicate is not None
        assert predicate("app/components/UserCard.vue") is True
        assert predicate("server/api/users.get.ts") is True
        assert predicate("src/lib/api.ts") is False
        # Next.js conventions do not leak into a Nuxt project.
        assert predicate("app/page.tsx") is False


def test_monorepo_package_prefix_is_stripped(tmp_path):
    pkg = tmp_path / "apps" / "web"
    _write(pkg / "package.json", json.dumps({"dependencies": {"nuxt": "^3.0.0"}}))
    _write(pkg / "pages" / "index.vue", "<template><div /></template>\n")
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        predicate = framework_convention_entry(pkg, None)
        assert predicate is not None
        assert predicate("apps/web/pages/index.vue") is True
        assert predicate("apps/web/lib/x.ts") is False


def test_scan_target_outside_project_root(tmp_path):
    """`desloppify scan --path ../other` renders files as `../other/...`."""
    project = tmp_path / "tool"
    project.mkdir()
    pkg = tmp_path / "site"
    _write(pkg / "package.json", json.dumps({"dependencies": {"nuxt": "^4.0.0"}}))
    with runtime_scope(RuntimeContext(project_root=project)):
        predicate = framework_convention_entry(pkg, None)
        assert predicate is not None
        assert predicate("../site/app/components/UserCard.vue") is True
        assert predicate("../site/src/lib/api.ts") is False


def test_nextjs_predicate_from_detection(tmp_path):
    _write(tmp_path / "package.json", json.dumps({"dependencies": {"next": "15.0.0"}}))
    _write(tmp_path / "next.config.ts", "export default {};\n")
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        predicate = framework_convention_entry(tmp_path, None)
        assert predicate is not None
        assert predicate("app/page.tsx") is True
        assert predicate("app/utils/helpers.ts") is False


# ── Review guidance ───────────────────────────────────────────


def test_nuxt_guidance_shape():
    assert isinstance(NUXT_REVIEW_GUIDANCE["patterns"], list)
    assert isinstance(NUXT_REVIEW_GUIDANCE["auth"], list)
    assert isinstance(NUXT_REVIEW_GUIDANCE["refactoring"], list)
    assert isinstance(NUXT_REVIEW_GUIDANCE["naming"], str)
    assert any("useFetch" in item for item in NUXT_REVIEW_GUIDANCE["patterns"])


def test_framework_guidance_only_for_detected_frameworks(tmp_path):
    _write(tmp_path / "package.json", json.dumps({"dependencies": {"nuxt": "^4.0.0"}}))
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        guides = framework_review_guidance(tmp_path, None)
    assert list(guides) == ["nuxt"]
    assert guides["nuxt"]["patterns"] == NUXT_REVIEW_GUIDANCE["patterns"]


def test_vue_guidance_for_plain_vue_and_layered_under_nuxt(tmp_path):
    _write(tmp_path / "package.json", json.dumps({"dependencies": {"vue": "^3.5.0"}}))
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        guides = framework_review_guidance(tmp_path, None)
        assert list(guides) == ["vue"]
        assert guides["vue"]["patterns"] == VUE_REVIEW_GUIDANCE["patterns"]
        # Plain Vue apps import components explicitly: no convention entries.
        assert framework_convention_entry(tmp_path, None) is None

    _write(tmp_path / "package.json", json.dumps({"dependencies": {"vue": "^3.5.0", "nuxt": "^4.0.0"}}))
    with runtime_scope(RuntimeContext(project_root=(tmp_path / "other"))):
        guides = framework_review_guidance(tmp_path, None)
    assert list(guides) == ["nuxt", "vue"]
    merged = merge_review_guidance({"patterns": []}, guides)
    assert set(VUE_REVIEW_GUIDANCE["patterns"]) <= set(merged["patterns"])
    assert set(NUXT_REVIEW_GUIDANCE["patterns"]) <= set(merged["patterns"])
    assert set(merged["frameworks"]) == {"nuxt", "vue"}


def test_vue_and_nuxt_guidance_do_not_overlap():
    """Nuxt guidance is the Nuxt-specific layer; generic Vue rules live in the Vue spec."""
    for key in ("patterns", "refactoring"):
        assert not set(VUE_REVIEW_GUIDANCE[key]) & set(NUXT_REVIEW_GUIDANCE[key])


def test_merge_review_guidance_extends_lists_and_keeps_raw_frameworks():
    lang = {"patterns": ["react thing"], "naming": "camelCase", "auth": ["a"]}
    merged = merge_review_guidance(lang, {"nuxt": NUXT_REVIEW_GUIDANCE})

    assert merged["patterns"][0] == "react thing"
    assert NUXT_REVIEW_GUIDANCE["patterns"][0] in merged["patterns"]
    assert merged["naming"].startswith("camelCase\n\n")
    assert merged["refactoring"] == NUXT_REVIEW_GUIDANCE["refactoring"]
    assert merged["frameworks"]["nuxt"]["naming"] == NUXT_REVIEW_GUIDANCE["naming"]
    # Input untouched.
    assert lang["patterns"] == ["react thing"]


def test_merge_review_guidance_without_frameworks_is_a_copy():
    lang = {"patterns": ["x"]}
    merged = merge_review_guidance(lang, {})
    assert merged == lang
    assert merged is not lang


def test_holistic_review_payload_carries_framework_guidance(tmp_path, monkeypatch):
    """`review --prepare` (holistic/blind packet) merges Vue+Nuxt guidance."""
    from desloppify.intelligence.review import prepare_holistic_orchestration as orch

    _write(tmp_path / "package.json", json.dumps({"dependencies": {"nuxt": "^4.0.0", "vue": "^3.5.0"}}))
    captured: dict = {}

    def fake_resolve(lang_name, options, **_kw):
        from desloppify.intelligence.review.prepare_holistic_orchestration import _DimensionContext

        return _DimensionContext(
            dims=["naming"],
            holistic_prompts={"naming": "p"},
            per_file_prompts={"naming": "p"},
            system_prompt="s",
            lang_guide={"patterns": ["react thing"], "naming": "camelCase"},
            invalid_requested=[],
            invalid_default=[],
        )

    monkeypatch.setattr(orch, "_resolve_dimension_context", fake_resolve)
    monkeypatch.setattr(orch, "_resolve_review_files", lambda *a, **k: ([], set()))

    class Ctx:
        codebase_stats = {"total_files": 0}

        def to_dict(self):
            return {}

    monkeypatch.setattr(orch, "_build_review_contexts", lambda *a, **k: (Ctx(), object()))
    monkeypatch.setattr(orch, "_build_selected_prompts", lambda *a, **k: {})

    class Lang:
        name = "typescript"
        runtime_cache: dict = {}

    from desloppify.intelligence.review.prepare import HolisticReviewPrepareOptions

    class Deps:
        is_file_cache_enabled_fn = lambda: True
        enable_file_cache_fn = lambda: None
        disable_file_cache_fn = lambda: None
        build_holistic_context_fn = None
        build_review_context_fn = None
        load_dimensions_for_lang_fn = None
        resolve_dimensions_fn = None
        get_lang_guidance_fn = None
        assemble_holistic_batches_fn = staticmethod(lambda *a, **k: [])
        holistic_batch_deps = None
        serialize_context_fn = staticmethod(lambda ctx: {})

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        payload = orch.prepare_holistic_review_payload(
            tmp_path, Lang(), {}, HolisticReviewPrepareOptions(), deps=Deps()
        )

    assert payload["frameworks"] == ["nuxt", "vue"]
    guide = payload["lang_guidance"]
    assert guide["patterns"][0] == "react thing"
    assert set(VUE_REVIEW_GUIDANCE["patterns"]) <= set(guide["patterns"])
    assert set(NUXT_REVIEW_GUIDANCE["patterns"]) <= set(guide["patterns"])
    assert set(guide["frameworks"]) == {"nuxt", "vue"}
