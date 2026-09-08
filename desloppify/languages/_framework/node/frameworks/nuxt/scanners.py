"""Nuxt-specific scanners (regex/heuristic, no AST required).

Each scanner returns ``(entries, scanned_count)``. Entries carry ``file`` (as
enumerated by discovery) and ``line`` (1-based, in the on-disk file — Vue
components are read through their script view, which keeps line numbers).

Rules follow the Nuxt 4 docs and the ``nuxt``/``nuxt4-patterns`` skills:
server/client boundary, runtime config, data fetching in setup, SSR safety,
page conventions and Nitro input validation.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path

from desloppify.base.discovery.file_paths import resolve_path
from desloppify.base.discovery.source import find_source_files, read_file_text
from desloppify.languages._framework.node.js_text import (
    blank_js_ts_comments as _strip_comments,
)
from desloppify.languages._framework.node.js_text import (
    code_text as _code_text,
)

from .info import NuxtFrameworkInfo

logger = logging.getLogger(__name__)

NUXT_SOURCE_EXTENSIONS = [".vue", ".ts", ".tsx", ".js", ".mjs"]

_SERVER_IMPORT_RE = re.compile(
    r"""(?P<stmt>import\s+type\s+[^'"]*?|import\s+[^'"]*?|export\s+type\s+[^'"]*?|export\s+[^'"]*?|import\s*\(\s*)['"](?P<spec>(?:~~|@@|#server|~|@)/server/[^'"]*|(?:\.\./)+server/[^'"]*)['"]""",
    re.DOTALL,
)
_TYPE_ONLY_IMPORT_RE = re.compile(r"""^\s*(?:import|export)\s+type\b""")
_SERVER_ONLY_FILE_RE = re.compile(r"""\.server\.(?:ts|js|mjs|vue)$""")
_TEST_FILE_RE = re.compile(r"""(?:^|/)(?:__tests__|__mocks__)/|\.(?:test|spec)\.[cm]?[jt]sx?$""")
_PROCESS_ENV_RE = re.compile(r"""\bprocess\.env(?:\.(?P<dot>[A-Za-z0-9_]+)|\[\s*['"](?P<bracket>[A-Za-z0-9_]+)['"]\s*\])""")
_CLIENT_ENV_ALLOWLIST = {"NODE_ENV"}
_VUE_ROUTER_ROUTE_IMPORT_RE = re.compile(
    r"""import\s*\{[^}]*\b(?:useRoute|useRouter)\b[^}]*\}\s*from\s*['"]vue-router['"]"""
)
_DEFINE_PAGE_META_RE = re.compile(r"""\bdefinePageMeta\s*\(""")
_TOP_LEVEL_FETCH_RE = re.compile(r"""^(?:const|let|var)\s+[^=]+=\s*await\s+\$fetch\s*[(<]|^await\s+\$fetch\s*[(<]""")
_BROWSER_GLOBAL_RE = re.compile(
    r"""^(?:const|let|var)\s+\w+\s*=\s*(?P<global>window|document|localStorage|sessionStorage|navigator)\b|^(?P<global2>window|document|localStorage|sessionStorage|navigator)\s*[.\[]"""
)
_MODULE_STATE_RE = re.compile(r"""^(?:export\s+)?(?:const|let)\s+\w+\s*=\s*(?P<api>ref|reactive|shallowRef|shallowReactive)\s*[(<]""")
_RAW_BODY_RE = re.compile(r"""\b(?P<api>readBody|getQuery)\s*\(""")
_VALIDATION_RE = re.compile(r"""\b(?:readValidatedBody|getValidatedQuery|getValidatedRouterParams|safeParse|parse|parseAsync|assert|validate|validateSync)\s*\(|\bz\.|\bv\.|zod|valibot|yup|joi|arktype|typebox""")
_SCRIPT_SETUP_RE = re.compile(r"""<script\b[^>]*\bsetup\b[^>]*>""", re.IGNORECASE)
# Precision first: `apiKey`/`supabaseKey` are often publishable keys, so only
# names that are unambiguously server-side are flagged.
_SECRET_KEY_RE = re.compile(r"""(?i)(?:secret|private|service_?role|token|password|passwd|signing|webhook)""")
_PUBLIC_SAFE_KEY_RE = re.compile(
    r"""^(?:site|app|base|public|nuxt)?(?:url|name|title|env|version|locale|domain)$"""
    r"""|(?:client|public|publishable|anon|browser|frontend)""",
    re.IGNORECASE,
)


def _iter_files(info: NuxtFrameworkInfo) -> list[tuple[str, str]]:
    """Yield ``(filepath, package_relative_path)`` for source files in the package."""
    root = info.package_root.resolve()
    out: list[tuple[str, str]] = []
    for filepath in find_source_files(info.package_root, NUXT_SOURCE_EXTENSIONS):
        full = Path(resolve_path(filepath))
        try:
            rel = full.relative_to(root).as_posix()
        except ValueError:
            continue
        out.append((filepath, rel))
    return out


def _read(filepath: str, *, raw: bool = False) -> str | None:
    return read_file_text(resolve_path(filepath), raw=raw)


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _scan_lines(
    info: NuxtFrameworkInfo,
    *,
    select: Callable[[str], bool],
    check: Callable[[str, str], list[dict]],
) -> tuple[list[dict], int]:
    entries: list[dict] = []
    scanned = 0
    for filepath, rel in _iter_files(info):
        if not select(rel):
            continue
        content = _read(filepath)
        if content is None:
            continue
        scanned += 1
        for entry in check(rel, content):
            entry["file"] = filepath
            entries.append(entry)
    return entries, scanned


# ── Server/client boundary ─────────────────────────────────────


def scan_nuxt_server_imports_in_app(info: NuxtFrameworkInfo) -> tuple[list[dict], int]:
    """App code importing from server/ (bundled into the client or broken at build)."""

    def select(rel: str) -> bool:
        return info.is_app_code(rel) and not _SERVER_ONLY_FILE_RE.search(rel)

    def check(rel: str, content: str) -> list[dict]:
        # Specifiers live inside strings (which code_text blanks), so scan the
        # comment-blanked text and locate lines from it.
        stripped = _strip_comments(content)
        found: list[dict] = []
        for m in _SERVER_IMPORT_RE.finditer(stripped):
            if _TYPE_ONLY_IMPORT_RE.match(m.group("stmt")):
                continue  # `import type` is erased at build time
            found.append({"line": _line_of(stripped, m.start("spec")), "spec": m.group("spec")})
        return found

    return _scan_lines(info, select=select, check=check)


def scan_nuxt_process_env_in_app(info: NuxtFrameworkInfo) -> tuple[list[dict], int]:
    """``process.env`` in app code; client code must use ``useRuntimeConfig().public``."""

    def check(rel: str, content: str) -> list[dict]:
        code = _code_text(_strip_comments(content))
        found: list[dict] = []
        for m in _PROCESS_ENV_RE.finditer(code):
            name = m.group("dot") or m.group("bracket") or ""
            if name in _CLIENT_ENV_ALLOWLIST:
                continue
            found.append({"line": _line_of(code, m.start()), "var": name})
        return found

    return _scan_lines(info, select=info.is_app_code, check=check)


def scan_nuxt_vue_router_imports(info: NuxtFrameworkInfo) -> tuple[list[dict], int]:
    """``useRoute``/``useRouter`` imported from vue-router instead of Nuxt's auto-imports."""

    def check(rel: str, content: str) -> list[dict]:
        stripped = _strip_comments(content)
        return [{"line": _line_of(stripped, m.start())} for m in _VUE_ROUTER_ROUTE_IMPORT_RE.finditer(stripped)]

    return _scan_lines(info, select=info.is_app_code, check=check)


# ── Page and setup conventions ────────────────────────────────


def scan_nuxt_define_page_meta_outside_pages(info: NuxtFrameworkInfo) -> tuple[list[dict], int]:
    """``definePageMeta`` only works in page components."""

    def select(rel: str) -> bool:
        return rel.endswith(".vue") and info.is_app_code(rel) and not info.is_page(rel)

    def check(rel: str, content: str) -> list[dict]:
        code = _code_text(_strip_comments(content))
        return [{"line": _line_of(code, m.start())} for m in _DEFINE_PAGE_META_RE.finditer(code)]

    return _scan_lines(info, select=select, check=check)


def _is_script_setup(filepath: str) -> bool:
    raw = _read(filepath, raw=True) or ""
    return bool(_SCRIPT_SETUP_RE.search(raw))


def scan_nuxt_top_level_fetch_in_setup(info: NuxtFrameworkInfo) -> tuple[list[dict], int]:
    """Top-level ``await $fetch`` in ``<script setup>`` runs on the server and again on hydration."""
    entries: list[dict] = []
    scanned = 0
    for filepath, rel in _iter_files(info):
        if not (rel.endswith(".vue") and info.is_app_code(rel)):
            continue
        content = _read(filepath)
        if content is None or not _is_script_setup(filepath):
            continue
        scanned += 1
        code = _code_text(_strip_comments(content))
        for idx, line in enumerate(code.splitlines(), start=1):
            if _TOP_LEVEL_FETCH_RE.match(line):
                entries.append({"file": filepath, "line": idx})
    return entries, scanned


def scan_nuxt_browser_globals_in_setup(info: NuxtFrameworkInfo) -> tuple[list[dict], int]:
    """Top-level browser globals in ``<script setup>`` break SSR."""
    entries: list[dict] = []
    scanned = 0
    for filepath, rel in _iter_files(info):
        if not (rel.endswith(".vue") and info.is_app_code(rel)):
            continue
        content = _read(filepath)
        if content is None or not _is_script_setup(filepath):
            continue
        scanned += 1
        code = _code_text(_strip_comments(content))
        for idx, line in enumerate(code.splitlines(), start=1):
            m = _BROWSER_GLOBAL_RE.match(line)
            if m:
                entries.append({"file": filepath, "line": idx, "global": m.group("global") or m.group("global2")})
    return entries, scanned


def scan_nuxt_module_state_in_composables(info: NuxtFrameworkInfo) -> tuple[list[dict], int]:
    """Module-level ``ref``/``reactive`` in composables is shared across SSR requests."""

    def select(rel: str) -> bool:
        return info.is_composable(rel) and not rel.endswith(".vue") and not _TEST_FILE_RE.search(rel)

    def check(rel: str, content: str) -> list[dict]:
        code = _code_text(_strip_comments(content))
        return [
            {"line": idx, "api": m.group("api")}
            for idx, line in enumerate(code.splitlines(), start=1)
            if (m := _MODULE_STATE_RE.match(line))
        ]

    return _scan_lines(info, select=select, check=check)


# ── Nitro ─────────────────────────────────────────────────────


def scan_nuxt_unvalidated_handler_input(info: NuxtFrameworkInfo) -> tuple[list[dict], int]:
    """Nitro handlers reading raw body/query with no validation in the file."""

    def select(rel: str) -> bool:
        parts = Path(rel).parts
        return len(parts) > 2 and parts[0] == "server" and parts[1] in {"api", "routes"}

    def check(rel: str, content: str) -> list[dict]:
        code = _code_text(_strip_comments(content))
        if _VALIDATION_RE.search(code):
            return []
        found: list[dict] = []
        for m in _RAW_BODY_RE.finditer(code):
            found.append({"line": _line_of(code, m.start()), "api": m.group("api")})
            break  # one finding per handler
        return found

    return _scan_lines(info, select=select, check=check)


# ── Runtime config ────────────────────────────────────────────


def _public_runtime_config_block(text: str) -> tuple[int, str] | None:
    """Return ``(offset, block_text)`` of the ``runtimeConfig.public`` object, if any."""
    rc = re.search(r"""\bruntimeConfig\s*:\s*\{""", text)
    if not rc:
        return None
    start = rc.end()
    depth = 1
    i = start
    while i < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    rc_block = text[start : i - 1]
    pub = re.search(r"""\bpublic\s*:\s*\{""", rc_block)
    if not pub:
        return None
    pstart = pub.end()
    depth = 1
    j = pstart
    while j < len(rc_block) and depth:
        depth += {"{": 1, "}": -1}.get(rc_block[j], 0)
        j += 1
    return start + pstart, rc_block[pstart : j - 1]


def scan_nuxt_public_runtime_secrets(info: NuxtFrameworkInfo) -> tuple[list[dict], int]:
    """Secret-looking keys under ``runtimeConfig.public`` ship to the browser."""
    entries: list[dict] = []
    scanned = 0
    for name in ("nuxt.config.ts", "nuxt.config.js", "nuxt.config.mjs"):
        config = info.package_root / name
        if not config.is_file():
            continue
        content = read_file_text(str(config), raw=True)
        if content is None:
            continue
        scanned += 1
        stripped = _strip_comments(content)
        block = _public_runtime_config_block(stripped)
        if block is None:
            continue
        offset, text = block
        for m in re.finditer(r"""^\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:""", text, re.MULTILINE):
            key = m.group("key")
            if _PUBLIC_SAFE_KEY_RE.search(key) or not _SECRET_KEY_RE.search(key):
                continue
            entries.append({"file": str(config), "line": _line_of(stripped, offset + m.start("key")), "key": key})
    return entries, scanned


__all__ = [
    "NUXT_SOURCE_EXTENSIONS",
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
