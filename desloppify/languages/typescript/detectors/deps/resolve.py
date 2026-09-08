"""Resolution helpers for TypeScript dependency graph extraction."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

from desloppify.base.output.fallbacks import log_best_effort_failure
from desloppify.base.text_utils import strip_c_style_comments

_RESOLVE_EXTENSIONS = ("", ".ts", ".tsx", "/index.ts", "/index.tsx")
_JS_SPECIFIER_EXTENSIONS = {".js", ".mjs", ".cjs"}
logger = logging.getLogger(__name__)


@lru_cache(maxsize=32)
def load_tsconfig_paths_cached(project_root_str: str) -> dict[str, str]:
    """Return cached tsconfig path mappings for a project root."""
    return parse_tsconfig_paths(Path(project_root_str))


def load_tsconfig_paths(project_root: Path) -> dict[str, str]:
    """Parse tsconfig.json compilerOptions.paths into alias-to-directory mappings."""
    return load_tsconfig_paths_cached(str(project_root.resolve()))


def find_tsconfig_root(scan_path: Path, project_root: Path) -> Path:
    """Find the directory containing tsconfig.json, searching scan_path then project_root.

    When the scan path differs from the project root (e.g. monorepos or
    ``--path`` pointing at a subdirectory), the tsconfig may live alongside
    the scanned code rather than at the workspace root.  We check the scan
    path first, then walk up to (and including) the project root.
    """
    resolved_root = project_root.resolve()
    candidate = scan_path.resolve()

    # Walk from scan_path up to project_root looking for tsconfig.json
    while True:
        for name in ("tsconfig.json", "tsconfig.app.json", "jsconfig.json"):
            if (candidate / name).is_file():
                return candidate
        if candidate == resolved_root or candidate == candidate.parent:
            break
        candidate = candidate.parent

    # Fall back to project_root (load_tsconfig_paths will use its own fallback)
    return resolved_root


_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")
_TSCONFIG_NAMES = ("tsconfig.json", "tsconfig.app.json", "jsconfig.json")


def load_tsconfig_json(config_path: Path) -> dict[str, Any] | None:
    """Parse a tsconfig/jsconfig file, tolerating comments and trailing commas (JSONC)."""
    try:
        raw = config_path.read_text(errors="replace")
    except OSError as exc:
        log_best_effort_failure(logger, f"read TypeScript config file {config_path}", exc)
        return None
    text = _TRAILING_COMMA_RE.sub(r"\1", strip_c_style_comments(raw))
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        log_best_effort_failure(logger, f"parse TypeScript config file {config_path}", exc)
        return None
    return data if isinstance(data, dict) else None


def _referenced_config_files(data: dict[str, Any], config_dir: Path) -> list[Path]:
    """Project references (``{"references": [{"path": ...}]}``) as config file paths."""
    refs = data.get("references")
    if not isinstance(refs, list):
        return []
    out: list[Path] = []
    for ref in refs:
        target = ref.get("path") if isinstance(ref, dict) else None
        if not isinstance(target, str):
            continue
        candidate = (config_dir / target).resolve()
        if candidate.is_dir():
            candidate = candidate / "tsconfig.json"
        if candidate.is_file():
            out.append(candidate)
    return out


def _paths_from_config(config_path: Path, project_root: Path, *, depth: int = 0) -> dict[str, str] | None:
    """Paths declared by *config_path*, following ``extends`` and project ``references``.

    Nuxt writes the aliases into generated files: older layouts ``extends``
    ``.nuxt/tsconfig.json``; newer ones keep ``files: []`` at the root and list
    ``.nuxt/tsconfig.app.json`` etc. as references. Referenced configs are
    merged (first declaration of an alias wins).
    """
    if depth > 4:
        return None
    data = load_tsconfig_json(config_path)
    if data is None:
        return None
    result = extract_paths(data, config_path.parent, project_root=project_root)
    if result is not None:
        return result

    extends = data.get("extends")
    if isinstance(extends, str) and not extends.startswith("@"):
        parent_path = (config_path.parent / extends).resolve()
        if parent_path.is_file():
            parent_result = _paths_from_config(parent_path, project_root, depth=depth + 1)
            if parent_result is not None:
                return parent_result

    merged: dict[str, str] = {}
    for ref_path in _referenced_config_files(data, config_path.parent):
        ref_result = _paths_from_config(ref_path, project_root, depth=depth + 1)
        for alias, target in (ref_result or {}).items():
            merged.setdefault(alias, target)
    return merged or None


def parse_tsconfig_paths(project_root: Path) -> dict[str, str]:
    """Parse tsconfig paths from disk. Internal — use ``load_tsconfig_paths``."""
    fallback = {"@/": "src/"}

    for name in _TSCONFIG_NAMES:
        config_path = project_root / name
        if not config_path.is_file():
            continue
        result = _paths_from_config(config_path, project_root)
        return result if result is not None else fallback

    return fallback


def extract_paths(
    data: dict[str, Any],
    base_dir: Path,
    *,
    project_root: Path | None = None,
) -> dict[str, str] | None:
    """Extract paths mapping from a parsed tsconfig.

    ``base_dir`` is the directory of the config that declares the paths;
    targets are resolved against it and stored relative to ``project_root``
    (or to ``base_dir`` when no project root is given).
    """
    compiler_options = data.get("compilerOptions")
    if not isinstance(compiler_options, dict):
        return None
    paths = compiler_options.get("paths")
    if not isinstance(paths, dict):
        return None

    base_url = compiler_options.get("baseUrl", ".")
    if not isinstance(base_url, str):
        base_url = "."

    result: dict[str, str] = {}
    for alias, targets in paths.items():
        if not isinstance(targets, list) or not targets:
            continue
        target = targets[0]
        if not isinstance(target, str):
            continue
        alias_prefix = alias.removesuffix("*")
        target_prefix = target.removesuffix("*")
        target_dir = target_prefix.removeprefix("./")
        if base_url != ".":
            base = base_url.rstrip("/")
            target_dir = base + "/" + target_dir if target_dir else base + "/"
        result[alias_prefix] = _project_relative_target(target_dir, base_dir, project_root)
    return result if result else None


def _project_relative_target(target_dir: str, base_dir: Path, project_root: Path | None) -> str:
    """Rebase a config-relative target directory onto the project root."""
    root = (project_root or base_dir).resolve()
    trailing_slash = target_dir.endswith("/")
    absolute = (base_dir.resolve() / target_dir).resolve() if target_dir else base_dir.resolve()
    rel = os.path.relpath(absolute, root).replace(os.sep, "/")
    if rel == ".":
        return ""
    return rel + "/" if trailing_slash else rel


def iter_resolve_candidates(target: Path) -> Iterator[Path]:
    """Yield filesystem candidates for a module specifier target."""
    seen: set[str] = set()

    def _emit(candidate: Path) -> Iterator[Path]:
        key = str(candidate)
        if key in seen:
            return
        seen.add(key)
        yield candidate

    if target.suffix in {".ts", ".tsx"}:
        yield from _emit(target)
        return

    if target.suffix in _JS_SPECIFIER_EXTENSIONS:
        stem = target.with_suffix("")
        yield from _emit(Path(str(stem) + ".ts"))
        yield from _emit(Path(str(stem) + ".tsx"))
        yield from _emit(Path(str(stem) + "/index.ts"))
        yield from _emit(Path(str(stem) + "/index.tsx"))
        yield from _emit(target)
        return

    for ext in _RESOLVE_EXTENSIONS:
        yield from _emit(Path(str(target) + ext))


def resolve_alias(
    module_path: str,
    tsconfig_paths: dict[str, str],
    project_root: Path,
) -> Path | None:
    """Resolve a tsconfig path alias to an absolute path.

    Prefixes are checked longest-first so that ``@components/*`` is preferred
    over ``@/*`` when both could match.
    """
    for prefix in sorted(tsconfig_paths, key=len, reverse=True):
        if module_path.startswith(prefix):
            target_dir = tsconfig_paths[prefix]
            relative = module_path[len(prefix) :]
            return (project_root / target_dir / relative).resolve()
    return None


_GLOB_CALL_RE = re.compile(
    r"""import\.meta\.glob(?:Eager)?\s*(?:<[^>]*>)?\s*\(\s*(?P<arg>\[[^\]]*\]|'[^']*'|"[^"]*")""",
    re.DOTALL,
)
_GLOB_PATTERN_RE = re.compile(r"""['"]([^'"]+)['"]""")
_GLOB_META = set("*?[{")


def expand_import_meta_glob(
    content: str,
    filepath: str,
    tsconfig_paths: dict[str, str],
    project_root: Path,
    *,
    source_root: Path | None = None,
) -> list[Path]:
    """Files matched by ``import.meta.glob(...)`` / ``globEager`` patterns in *content*.

    Vite resolves these at build time, so the matched modules are real
    dependencies of the importing file even though no static import names them.
    Negated patterns (``!...``) are ignored; aliases resolve through tsconfig.
    """
    relative_root = source_root or project_root
    source_dir = Path(filepath).parent if Path(filepath).is_absolute() else (relative_root / filepath).parent
    matched: list[Path] = []
    for call in _GLOB_CALL_RE.finditer(content):
        for pattern in _GLOB_PATTERN_RE.findall(call.group("arg")):
            if pattern.startswith("!"):
                continue
            if pattern.startswith("."):
                base = source_dir
                rest = pattern
            else:
                aliased = resolve_alias(pattern, tsconfig_paths, project_root)
                if aliased is None:
                    continue
                base = aliased.parent
                rest = aliased.name
                # resolve_alias joined the whole pattern; split it back at the
                # first path segment containing a glob character.
                parts = aliased.parts
                for idx, part in enumerate(parts):
                    if any(ch in _GLOB_META for ch in part):
                        base = Path(*parts[:idx]) if idx else Path("/")
                        rest = "/".join(parts[idx:])
                        break
            segments = [seg for seg in rest.replace("\\", "/").split("/") if seg not in ("", ".")]
            while segments and not any(ch in _GLOB_META for ch in segments[0]):
                base = base / segments.pop(0)
            if not segments:
                if base.is_file():
                    matched.append(base.resolve())
                continue
            try:
                for hit in sorted(base.glob("/".join(segments))):
                    if hit.is_file() and "node_modules" not in hit.parts:
                        matched.append(hit.resolve())
            except (OSError, ValueError):
                continue
    return matched


def resolve_module(
    module_path: str,
    filepath: str,
    tsconfig_paths: dict[str, str],
    project_root: Path,
    graph: dict[str, dict[str, Any]],
    source_resolved: str,
    *,
    source_root: Path | None = None,
) -> None:
    """Resolve an import specifier and add edges to the graph."""
    target: Path | None = None
    if module_path.startswith("."):
        relative_root = source_root or project_root
        source_dir = (
            Path(filepath).parent
            if Path(filepath).is_absolute()
            else (relative_root / filepath).parent
        )
        target = (source_dir / module_path).resolve()
    else:
        target = resolve_alias(module_path, tsconfig_paths, project_root)

    if target is None:
        return

    for candidate in iter_resolve_candidates(target):
        if candidate.is_file():
            target_resolved = str(candidate)
            graph[source_resolved]["imports"].add(target_resolved)
            graph[target_resolved]["importers"].add(source_resolved)
            break
