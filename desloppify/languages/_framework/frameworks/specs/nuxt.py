"""Nuxt framework spec (Node ecosystem).

Contributes convention-based entry points (auto-imported components,
composables and Nitro handlers are not orphaned), Vue/Nuxt review guidance,
and heuristic scanner rules for the server/client boundary, runtime config,
data fetching in setup, SSR safety, page conventions and Nitro input
validation.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from desloppify.engine._state.filtering import make_issue
from desloppify.languages._framework.base.types import LangRuntimeContract
from desloppify.languages._framework.node.frameworks.nuxt import (
    NUXT_REVIEW_GUIDANCE,
    NuxtFrameworkInfo,
    is_nuxt_convention_entry,
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
from desloppify.state_io import Issue

from ..types import DetectionConfig, FrameworkSpec, ScannerRule

_INFO_CACHE_PREFIX = "framework.nuxt.info"


def _nuxt_info(scan_root: Path, lang: LangRuntimeContract) -> NuxtFrameworkInfo:
    key = f"{_INFO_CACHE_PREFIX}:{scan_root.resolve().as_posix()}"
    cache = getattr(lang, "runtime_cache", None)
    if isinstance(cache, dict):
        cached = cache.get(key)
        if isinstance(cached, NuxtFrameworkInfo):
            return cached
    info = nuxt_info_from_package_root(scan_root)
    if isinstance(cache, dict):
        cache[key] = info
    return info


def _wrap(
    scan_fn: Callable[[NuxtFrameworkInfo], tuple[list[dict[str, Any]], int]],
) -> Callable[[Path, LangRuntimeContract], tuple[list[dict[str, Any]], int]]:
    def scan(scan_root: Path, lang: LangRuntimeContract) -> tuple[list[dict[str, Any]], int]:
        return scan_fn(_nuxt_info(scan_root, lang))

    return scan


def _line_issue(
    issue_id: str,
    *,
    tier: int,
    confidence: str,
    summary: Callable[[dict[str, Any]], str],
) -> Callable[[dict[str, Any]], Issue]:
    def factory(entry: dict[str, Any]) -> Issue:
        return make_issue(
            "nuxt",
            entry["file"],
            f"{issue_id}::{entry['line']}",
            tier=tier,
            confidence=confidence,
            summary=summary(entry),
            detail={k: v for k, v in entry.items() if k != "file"},
        )

    return factory


NUXT_SCANNERS: tuple[ScannerRule, ...] = (
    ScannerRule(
        id="server_import_in_app",
        scan=_wrap(scan_nuxt_server_imports_in_app),
        issue_factory=_line_issue(
            "server_import_in_app",
            tier=2,
            confidence="high",
            summary=lambda e: (
                f"App code imports server module `{e.get('spec')}` — server code must stay "
                "behind API routes (share pure code via shared/utils)."
            ),
        ),
        log_message=lambda n: f"       nuxt: {n} app files import from server/",
    ),
    ScannerRule(
        id="process_env_in_app",
        scan=_wrap(scan_nuxt_process_env_in_app),
        issue_factory=_line_issue(
            "process_env_in_app",
            tier=3,
            confidence="medium",
            summary=lambda e: (
                f"App code reads process.env.{e.get('var')} — use useRuntimeConfig() "
                "(public keys for the client) so values are set at runtime, not build time."
            ),
        ),
        log_message=lambda n: f"       nuxt: {n} process.env reads in app code",
    ),
    ScannerRule(
        id="vue_router_import",
        scan=_wrap(scan_nuxt_vue_router_imports),
        issue_factory=_line_issue(
            "vue_router_import",
            tier=3,
            confidence="high",
            summary=lambda e: (
                "useRoute/useRouter imported from vue-router — Nuxt auto-imports its own "
                "SSR-aware versions; the vue-router ones can mismatch during hydration."
            ),
        ),
        log_message=lambda n: f"       nuxt: {n} vue-router route imports",
    ),
    ScannerRule(
        id="define_page_meta_outside_pages",
        scan=_wrap(scan_nuxt_define_page_meta_outside_pages),
        issue_factory=_line_issue(
            "define_page_meta_outside_pages",
            tier=3,
            confidence="high",
            summary=lambda e: "definePageMeta() outside pages/ has no effect (compiler macro for page components only).",
        ),
        log_message=lambda n: f"       nuxt: {n} definePageMeta calls outside pages/",
    ),
    ScannerRule(
        id="top_level_fetch_in_setup",
        scan=_wrap(scan_nuxt_top_level_fetch_in_setup),
        issue_factory=_line_issue(
            "top_level_fetch_in_setup",
            tier=3,
            confidence="medium",
            summary=lambda e: (
                "Top-level `await $fetch` in <script setup> runs on the server and again on "
                "hydration — use useFetch/useAsyncData so the payload is reused."
            ),
        ),
        log_message=lambda n: f"       nuxt: {n} top-level $fetch calls in setup",
    ),
    ScannerRule(
        id="browser_global_in_setup",
        scan=_wrap(scan_nuxt_browser_globals_in_setup),
        issue_factory=_line_issue(
            "browser_global_in_setup",
            tier=3,
            confidence="medium",
            summary=lambda e: (
                f"Top-level `{e.get('global')}` access in <script setup> breaks SSR — guard with "
                "onMounted(), import.meta.client, or a .client.vue component."
            ),
        ),
        log_message=lambda n: f"       nuxt: {n} browser globals at setup top level",
    ),
    ScannerRule(
        id="module_state_in_composable",
        scan=_wrap(scan_nuxt_module_state_in_composables),
        issue_factory=_line_issue(
            "module_state_in_composable",
            tier=2,
            confidence="medium",
            summary=lambda e: (
                f"Module-level `{e.get('api')}()` state in a composable is shared across SSR "
                "requests — create it inside the composable, or use useState()/Pinia."
            ),
        ),
        log_message=lambda n: f"       nuxt: {n} module-level reactive state in composables",
    ),
    ScannerRule(
        id="unvalidated_handler_input",
        scan=_wrap(scan_nuxt_unvalidated_handler_input),
        issue_factory=_line_issue(
            "unvalidated_handler_input",
            tier=3,
            confidence="medium",
            summary=lambda e: (
                f"Handler reads `{e.get('api')}()` without validation — use readValidatedBody/"
                "getValidatedQuery with a schema (zod, valibot) before trusting input."
            ),
        ),
        log_message=lambda n: f"       nuxt: {n} handlers read unvalidated input",
    ),
    ScannerRule(
        id="public_runtime_secret",
        scan=_wrap(scan_nuxt_public_runtime_secrets),
        issue_factory=_line_issue(
            "public_runtime_secret",
            tier=2,
            confidence="high",
            summary=lambda e: (
                f"runtimeConfig.public.{e.get('key')} looks like a secret — public runtime config "
                "is shipped to the browser; move it to the private runtimeConfig root."
            ),
        ),
        log_message=lambda n: f"       nuxt: {n} secret-looking keys in runtimeConfig.public",
    ),
)


NUXT_SPEC = FrameworkSpec(
    id="nuxt",
    label="Nuxt",
    ecosystem="node",
    detection=DetectionConfig(
        dependencies=("nuxt",),
        dev_dependencies=("nuxt",),
        config_files=(
            "nuxt.config.ts",
            "nuxt.config.js",
            "nuxt.config.mjs",
        ),
        marker_dirs=("app", "pages", "server", "composables", "layers"),
        script_pattern=r"(?:^|\s)nuxt(?:\s|$)",
        marker_dirs_imply_presence=False,
    ),
    convention_entry=is_nuxt_convention_entry,
    review_guidance=NUXT_REVIEW_GUIDANCE,
    scanners=NUXT_SCANNERS,
)

__all__ = ["NUXT_SCANNERS", "NUXT_SPEC"]
