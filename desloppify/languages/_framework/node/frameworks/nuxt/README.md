# Nuxt Framework Support (Conventions + Guidance)

Spec: `desloppify/languages/_framework/frameworks/specs/nuxt.py`. Detected from the `nuxt`
dependency, `nuxt.config.*`, or a `nuxt` script in the nearest `package.json`.

## What it does today

- **Convention entry points** (`conventions.py`): tells the orphaned-file detector which files
  Nuxt/Nitro wires by location so auto-imported components, composables, layouts, plugins,
  middleware, `shared/` helpers and every `server/api|routes|middleware|plugins|tasks` handler
  stop showing up as dead code. Supports Nuxt 3 (root `srcDir`), Nuxt 4 (`app/`) and `layers/`.
  Follows the documented scan rules: `composables/`, `utils/`, `server/utils/` and `shared/*`
  only auto-import top-level files, so nested files with no importers stay reported.
- **Review guidance** (`guidance.py`): Nuxt-specific rules (data fetching, SSR/hydration,
  Nitro handlers, runtime config, layout) merged into `query.json` under `lang_guidance` and
  listed in `frameworks`. Generic Vue rules come from the Vue spec, which is always detected
  alongside Nuxt.

- **Scanner rules** (`scanners.py`, wired in the spec as `nuxt::*` issues): server imports in
  app code, `process.env` in app code, `useRoute`/`useRouter` from vue-router, `definePageMeta`
  outside `pages/`, top-level `await $fetch` in `<script setup>`, top-level browser globals in
  setup, module-level `ref`/`reactive` state in composables, Nitro handlers reading unvalidated
  input, and secret-looking keys under `runtimeConfig.public`. All regex/heuristic and
  precision-first; Vue components are read through the script view so line numbers match.
- **Test coverage**: thin Nitro handlers (`server/api|routes`, `defineEventHandler`, ≤40 code
  lines) do not count as untested modules; fat handlers still do.

## Not modelled yet

- A custom `srcDir` (for example `src/`) or `imports.dirs` overrides.
- More scanner rules (route rules, lazy hydration, `useAsyncData` keys) and a `nuxt typecheck`
  tool integration.
- Template analysis. `.vue` files are TypeScript sources through their *script view*
  (`desloppify.base.source_views`): the TypeScript detectors, complexity signals, duplicate
  detection and tree-sitter cohesion see the `<script>`/`<script setup>` blocks with original
  line numbers; reviewers see the whole file. `<template>` blocks are not yet analysed.
