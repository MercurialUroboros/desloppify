"""Dependency graph + coupling analysis (fan-in/fan-out) + dynamic imports."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from desloppify.base.discovery.file_paths import rel, resolve_path
from desloppify.base.discovery.paths import get_project_root
from desloppify.base.discovery.source import (
    find_source_files,
    find_ts_and_tsx_files,
    read_file_text,
)
from desloppify.base.output.terminal import colorize, print_table
from desloppify.base.search.grep import grep_files
from desloppify.engine.detectors.graph import (
    detect_cycles,
    finalize_graph,
    get_coupling_score,
)
from desloppify.languages.typescript.detectors.deps.resolve import (
    expand_import_meta_glob as _expand_import_meta_glob,
)
from desloppify.languages.typescript.detectors.deps.resolve import (
    find_tsconfig_root as _find_tsconfig_root,
)
from desloppify.languages.typescript.detectors.deps.resolve import (
    load_tsconfig_paths as _load_tsconfig_paths,
)
from desloppify.languages.typescript.detectors.deps.resolve import (
    resolve_module as _resolve_module,
)
from desloppify.languages.typescript.detectors.deps.runtime import (
    build_dynamic_import_targets as _build_dynamic_import_targets,
)
from desloppify.languages.typescript.detectors.deps.runtime import (
    ts_alias_resolver as _ts_alias_resolver,
)

_FRAMEWORK_EXTENSIONS = (".svelte", ".vue", ".astro")
_IMPORT_SPEC_RE = re.compile(
    r"""(?:from\s+|import\s+)(?:type\s+)?['"]([^'"]+)['"]"""
)
_DENO_EXTERNAL_PREFIXES = ("http://", "https://", "npm:", "jsr:")
_IMPORT_GREP_PATTERN = r"""(?:\bfrom\s+['"]|\bimport\s+['"])"""
# One whole `import ... from '...'` / `export ... from '...'` statement, possibly
# spanning lines. The clause admits only binding syntax and comments, so a
# match never starts inside an unrelated statement.
_FROM_STATEMENT_RE = re.compile(
    r"""(?:^|[;>])[ \t]*(?:import|export)\b"""
    r"""(?P<clause>(?:[\w$*{},\s]|//[^\n]*|/\*.*?\*/)*?)"""
    r"""\bfrom\s*['"](?P<spec>[^'"]+)['"]""",
    re.MULTILINE | re.DOTALL,
)
_SIDE_EFFECT_IMPORT_RE = re.compile(
    r"""(?:^|[;>])[ \t]*import\s*['"](?P<spec>[^'"]+)['"]""", re.MULTILINE
)
_CLAUSE_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_TYPE_CLAUSE_RE = re.compile(r"type(?=[\s{*])")
# `type X`, `type X as Y`, `type as`; but `type as X` is the value binding `type`.
_TYPE_BINDING_RE = re.compile(r"type\s+(?!as\s+[\w$]+$)[\w$]")


def _extract_module_specifiers(line: str) -> list[str]:
    """Extract static import/export module specifiers from one source line."""
    return [match.group(1) for match in _IMPORT_SPEC_RE.finditer(line)]


def _is_type_only_clause(clause: str) -> bool:
    """True for `type ...` clauses and brace lists whose every binding is `type`."""
    text = _CLAUSE_COMMENT_RE.sub(" ", clause).strip()
    if _TYPE_CLAUSE_RE.match(text):
        return True
    if not (text.startswith("{") and text.endswith("}")):
        return False
    bindings = [name.strip() for name in text[1:-1].split(",") if name.strip()]
    return bool(bindings) and all(_TYPE_BINDING_RE.match(name) for name in bindings)


def _type_only_specifiers(content: str) -> set[str]:
    """Specifiers that *content* imports or re-exports only through type-only statements.

    TypeScript erases those statements, so they carry no runtime dependency.
    A specifier also named by any value statement is not type-only.
    """
    type_specs: set[str] = set()
    value_specs = {m.group("spec") for m in _SIDE_EFFECT_IMPORT_RE.finditer(content)}
    for match in _FROM_STATEMENT_RE.finditer(content):
        bucket = type_specs if _is_type_only_clause(match.group("clause")) else value_specs
        bucket.add(match.group("spec"))
    return type_specs - value_specs


def build_dep_graph(
    path: Path,
    roslyn_cmd: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Build a dependency graph: for each file, who it imports and who imports it.

    Returns {resolved_path: {"imports": set[str], "importers": set[str], "import_count": int, "importer_count": int}}
    ``type_imports`` is the subset of ``imports`` reached only through
    type-only statements; cycle detection ignores it, every other consumer
    reads ``imports``/``importers`` unchanged.
    """
    del roslyn_cmd
    graph: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "imports": set(),
            "importers": set(),
            "external_imports": set(),
            "type_imports": set(),
        }
    )
    project_root = get_project_root()
    tsconfig_root = _find_tsconfig_root(path, project_root)
    tsconfig_paths = _load_tsconfig_paths(tsconfig_root)

    ts_files = find_ts_and_tsx_files(path)
    fw_files = find_source_files(path, list(_FRAMEWORK_EXTENSIONS))
    for files in (ts_files, fw_files):
        if not files:
            continue
        _add_static_import_edges(
            grep_files(_IMPORT_GREP_PATTERN, files),
            graph,
            tsconfig_paths=tsconfig_paths,
            tsconfig_root=tsconfig_root,
            project_root=project_root,
        )

    _add_glob_import_edges(
        [*ts_files, *fw_files],
        graph,
        tsconfig_paths=tsconfig_paths,
        tsconfig_root=tsconfig_root,
        project_root=project_root,
    )

    return finalize_graph(dict(graph))


def _add_static_import_edges(
    hits: list[tuple[str, int, str]],
    graph: dict[str, dict[str, Any]],
    *,
    tsconfig_paths: dict[str, str],
    tsconfig_root: Path,
    project_root: Path,
) -> None:
    """Add edges for static import/export specifiers found on grep *hits*."""
    type_only_by_file: dict[str, set[str]] = {}
    for filepath, _lineno, content in hits:
        source_resolved = resolve_path(filepath)
        graph[source_resolved]  # ensure entry exists
        if source_resolved not in type_only_by_file:
            text = read_file_text(source_resolved)
            type_only_by_file[source_resolved] = _type_only_specifiers(text or "")
        type_only = type_only_by_file[source_resolved]
        for module_path in _extract_module_specifiers(content):
            if module_path.startswith(_DENO_EXTERNAL_PREFIXES):
                graph[source_resolved]["external_imports"].add(module_path)
                continue
            _resolve_module(
                module_path,
                filepath,
                tsconfig_paths,
                tsconfig_root,
                graph,
                source_resolved,
                source_root=project_root,
                type_only=module_path in type_only,
            )


def _add_glob_import_edges(
    files: list[str],
    graph: dict[str, dict[str, Any]],
    *,
    tsconfig_paths: dict[str, str],
    tsconfig_root: Path,
    project_root: Path,
) -> None:
    """Add edges for modules loaded through ``import.meta.glob`` (Vite/Nuxt)."""
    for filepath, _lineno, _content in grep_files(r"import\.meta\.glob", files):
        content = read_file_text(resolve_path(filepath))
        if content is None:
            continue
        source_resolved = resolve_path(filepath)
        graph[source_resolved]  # ensure entry exists
        for target in _expand_import_meta_glob(
            content,
            filepath,
            tsconfig_paths,
            tsconfig_root,
            source_root=project_root,
        ):
            target_resolved = str(target)
            if target_resolved == source_resolved:
                continue
            graph[source_resolved]["imports"].add(target_resolved)
            graph[source_resolved]["type_imports"].discard(target_resolved)
            graph[target_resolved]["importers"].add(source_resolved)


def cmd_deps(args: Any) -> None:
    """Show dependency info for a specific file or top coupled files."""
    graph = build_dep_graph(Path(args.path))

    if hasattr(args, "file") and args.file:
        # Single file mode
        coupling = get_coupling_score(args.file, graph)
        if args.json:
            print(json.dumps({"file": rel(args.file), **coupling}, indent=2))
            return
        print(colorize(f"\nDependency info: {rel(args.file)}\n", "bold"))
        print(f"  Fan-in (importers):  {coupling['fan_in']}")
        print(f"  Fan-out (imports):   {coupling['fan_out']}")
        print(f"  Instability:         {coupling['instability']}")
        if coupling["importers"]:
            print(colorize(f"\n  Imported by ({coupling['fan_in']}):", "cyan"))
            for p in coupling["importers"][:20]:
                print(f"    {p}")
        if coupling["imports"]:
            print(colorize(f"\n  Imports ({coupling['fan_out']}):", "cyan"))
            for p in coupling["imports"][:20]:
                print(f"    {p}")
        return

    # Top coupled files mode
    scored = []
    for filepath, entry in graph.items():
        total = entry["import_count"] + entry["importer_count"]
        if total > 5:
            scored.append(
                {
                    "file": filepath,
                    "fan_in": entry["importer_count"],
                    "fan_out": entry["import_count"],
                    "total": total,
                }
            )
    scored.sort(key=lambda x: -x["total"])

    if args.json:
        print(
            json.dumps(
                {
                    "count": len(scored),
                    "entries": [
                        {**s, "file": rel(s["file"])} for s in scored[: args.top]
                    ],
                },
                indent=2,
            )
        )
        return

    print(colorize(f"\nMost coupled files: {len(scored)} with >5 connections\n", "bold"))
    rows = []
    for s in scored[: args.top]:
        rows.append(
            [rel(s["file"]), str(s["fan_in"]), str(s["fan_out"]), str(s["total"])]
        )
    print_table(["File", "In", "Out", "Total"], rows, [60, 5, 5, 6])


def cmd_cycles(args: Any) -> None:
    """Show import cycles in the codebase."""
    graph = build_dep_graph(Path(args.path))
    cycles, _ = detect_cycles(graph)

    if args.json:
        print(
            json.dumps(
                {
                    "count": len(cycles),
                    "cycles": [
                        {"length": cy["length"], "files": [rel(f) for f in cy["files"]]}
                        for cy in cycles
                    ],
                },
                indent=2,
            )
        )
        return

    if not cycles:
        print(colorize("\nNo import cycles found.", "green"))
        return

    print(colorize(f"\nImport cycles: {len(cycles)}\n", "bold"))
    for i, cy in enumerate(cycles[: args.top]):
        files = [rel(f) for f in cy["files"]]
        print(
            colorize(
                f"  Cycle {i + 1} ({cy['length']} files):",
                "red" if cy["length"] > 3 else "yellow",
            )
        )
        for f in files[:8]:
            print(f"    {f}")
        if len(files) > 8:
            print(f"    ... +{len(files) - 8} more")
        print()


def build_dynamic_import_targets(path: Path, extensions: list[str]) -> set[str]:
    """Find files referenced by dynamic imports (import('...')) and side-effect imports."""
    return _build_dynamic_import_targets(
        path,
        extensions,
        framework_extensions=_FRAMEWORK_EXTENSIONS,
        grep_files_fn=grep_files,
        find_source_files_fn=find_source_files,
    )


def ts_alias_resolver(target: str) -> str:
    """Resolve TS path aliases using tsconfig.json paths."""
    return _ts_alias_resolver(
        target,
        load_paths_fn=_load_tsconfig_paths,
        project_root=get_project_root(),
    )
