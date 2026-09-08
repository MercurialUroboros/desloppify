"""Nuxt framework support shared across JS/TS scans."""

from __future__ import annotations

from .conventions import is_nuxt_convention_entry
from .guidance import NUXT_REVIEW_GUIDANCE
from .info import NuxtFrameworkInfo, nuxt_info_from_package_root
from .scanners import (
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

__all__ = [
    "NUXT_REVIEW_GUIDANCE",
    "NuxtFrameworkInfo",
    "is_nuxt_convention_entry",
    "nuxt_info_from_package_root",
    "scan_nuxt_browser_globals_in_setup",
    "scan_nuxt_define_page_meta_outside_pages",
    "scan_nuxt_module_state_in_composables",
    "scan_nuxt_process_env_in_app",
    "scan_nuxt_public_runtime_secrets",
    "scan_nuxt_server_imports_in_app",
    "scan_nuxt_top_level_fetch_in_setup",
    "scan_nuxt_unvalidated_handler_input",
    "scan_nuxt_vue_router_imports",
]
