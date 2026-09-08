"""Nuxt-generated tsconfig aliases, import.meta.glob edges, and data-only modules."""

from __future__ import annotations

import json
from pathlib import Path

from desloppify.base.runtime_state import RuntimeContext, runtime_scope
from desloppify.languages.typescript.detectors.deps import build_dep_graph
from desloppify.languages.typescript.detectors.deps.resolve import (
    expand_import_meta_glob,
    extract_paths,
    load_tsconfig_paths_cached,
    parse_tsconfig_paths,
    resolve_alias,
)
from desloppify.languages.typescript.test_coverage import (
    has_testable_logic,
    is_data_only_module,
    resolve_import_spec,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _nuxt_project(root: Path) -> None:
    """Nuxt 4 layout: root tsconfig extends the generated .nuxt/tsconfig.json."""
    _write(root / "package.json", json.dumps({"dependencies": {"nuxt": "^4.0.0"}}))
    _write(root / "tsconfig.json", json.dumps({"extends": "./.nuxt/tsconfig.json"}))
    _write(
        root / ".nuxt" / "tsconfig.json",
        json.dumps({
            "compilerOptions": {
                "paths": {
                    "~": ["../app"], "~/*": ["../app/*"],
                    "@": ["../app"], "@/*": ["../app/*"],
                    "~~": [".."], "~~/*": ["../*"],
                    "#shared": ["../shared"], "#shared/*": ["../shared/*"],
                }
            }
        }),
    )
    _write(root / "app" / "pages" / "index.vue", '<script setup lang="ts">\nimport { BLOG_POSTS } from "~/content/blog"\n</script>\n<template><div>{{ BLOG_POSTS.length }}</div></template>\n')
    _write(root / "app" / "content" / "blog" / "index.ts", 'import type { BlogPost } from "./types"\nconst modules = import.meta.glob<{ default: BlogPost }>("./posts/*.ts", { eager: true })\nexport const BLOG_POSTS = Object.values(modules).map((m) => m.default)\nexport function readingMinutes(words: number) {\n  return Math.max(1, Math.round(words / 200))\n}\n')
    _write(root / "app" / "content" / "blog" / "types.ts", "export interface BlogPost { slug: string; title: string; body: string }\n")
    _write(root / "app" / "content" / "blog" / "posts" / "a.ts", 'import type { BlogPost } from "../types"\n\n// content entry\nconst post: BlogPost = {\n  slug: "a",\n  title: "A",\n  body: "prose " + "prose",\n}\nexport default post\n')
    _write(root / "app" / "content" / "blog" / "posts" / "b.ts", 'import type { BlogPost } from "../types"\nconst post: BlogPost = { slug: "b", title: "B", body: "x" }\nexport default post\n')
    _write(root / "shared" / "utils" / "slug.ts", "export const slugify = (s: string) => s.toLowerCase()\n")
    _write(root / "app" / "utils" / "use-slug.ts", 'import { slugify } from "#shared/utils/slug"\nexport const x = slugify("A")\n')


def test_generated_tsconfig_targets_are_rebased_onto_project_root(tmp_path):
    _nuxt_project(tmp_path)
    load_tsconfig_paths_cached.cache_clear()
    paths = parse_tsconfig_paths(tmp_path)
    assert paths["~/"] == "app/"
    assert paths["@/"] == "app/"
    assert paths["~~/"] == ""
    assert paths["#shared/"] == "shared/"
    assert resolve_alias("~/content/blog", paths, tmp_path) == (tmp_path / "app" / "content" / "blog").resolve()
    assert resolve_alias("~~/server/x", paths, tmp_path) == (tmp_path / "server" / "x").resolve()


def test_jsonc_root_with_project_references(tmp_path):
    """Newer Nuxt layout: commented root tsconfig with files: [] and references."""
    _write(
        tmp_path / "tsconfig.json",
        """{
  // https://nuxt.com/docs/guide/concepts/typescript
  "files": [],
  "references": [
    { "path": "./.nuxt/tsconfig.app.json" },
    { "path": "./.nuxt/tsconfig.server.json" },
  ],
}
""",
    )
    _write(tmp_path / ".nuxt" / "tsconfig.app.json", json.dumps({"compilerOptions": {"paths": {"~/*": ["../app/*"], "#shared/*": ["../shared/*"]}}}))
    _write(tmp_path / ".nuxt" / "tsconfig.server.json", json.dumps({"compilerOptions": {"paths": {"~~/*": ["../*"], "#shared/*": ["../shared-server/*"]}}}))
    load_tsconfig_paths_cached.cache_clear()
    paths = parse_tsconfig_paths(tmp_path)
    assert paths["~/"] == "app/"
    assert paths["~~/"] == ""
    assert paths["#shared/"] == "shared/"  # first reference wins


def test_extract_paths_without_project_root_is_relative_to_config_dir(tmp_path):
    data = {"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./src/*"], "#root": ["."]}}}
    paths = extract_paths(data, tmp_path)
    assert paths == {"@/": "src/", "#root": ""}


def test_import_meta_glob_expands_relative_and_aliased_patterns(tmp_path):
    _nuxt_project(tmp_path)
    load_tsconfig_paths_cached.cache_clear()
    paths = parse_tsconfig_paths(tmp_path)
    index = tmp_path / "app" / "content" / "blog" / "index.ts"
    content = index.read_text() + '\nconst more = import.meta.globEager(["~/content/blog/posts/*.ts", "!~/content/blog/posts/b.ts"])\n'
    matched = expand_import_meta_glob(content, str(index), paths, tmp_path)
    names = sorted(p.name for p in matched)
    # "./posts/*.ts" matches both; the aliased array matches both too (negation ignored).
    assert names == ["a.ts", "a.ts", "b.ts", "b.ts"]


def test_dep_graph_counts_alias_and_glob_importers(tmp_path):
    _nuxt_project(tmp_path)
    load_tsconfig_paths_cached.cache_clear()
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        graph = build_dep_graph(tmp_path)

    def importers(rel: str) -> int:
        return graph[str((tmp_path / rel).resolve())]["importer_count"]

    assert importers("app/content/blog/index.ts") == 1  # pages/index.vue via ~/
    assert importers("app/content/blog/posts/a.ts") == 1  # import.meta.glob
    assert importers("app/content/blog/posts/b.ts") == 1
    assert importers("shared/utils/slug.ts") == 1  # #shared alias


def test_resolve_import_spec_uses_tsconfig_aliases(tmp_path):
    _nuxt_project(tmp_path)
    load_tsconfig_paths_cached.cache_clear()
    production = {str((tmp_path / "app" / "content" / "blog" / "index.ts").resolve())}
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        resolved = resolve_import_spec("~/content/blog", str(tmp_path / "tests" / "blog.test.ts"), production)
    assert resolved in production


def test_data_only_modules_have_no_testable_logic(tmp_path):
    _nuxt_project(tmp_path)
    post = (tmp_path / "app" / "content" / "blog" / "posts" / "a.ts").read_text()
    index = (tmp_path / "app" / "content" / "blog" / "index.ts").read_text()
    assert is_data_only_module(post) is True
    assert has_testable_logic("app/content/blog/posts/a.ts", post) is False
    assert is_data_only_module(index) is False
    assert has_testable_logic("app/content/blog/index.ts", index) is True
    # Calls and control flow make it logic, even without functions.
    assert is_data_only_module("export const NOW = new Date()\n") is False
    assert is_data_only_module("export const X = { a: compute(1) }\n") is False
    assert is_data_only_module("import type { T } from './t'\n") is False  # nothing exported
    # Named runtime exports keep the existing treatment (testable surface).
    assert is_data_only_module("export const VERSION = '1.0.0'\n") is False
    assert is_data_only_module("export const TABLE = { a: 1 }\nexport default TABLE\n") is False
