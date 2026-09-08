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

## Not modelled yet

- A custom `srcDir` (for example `src/`) or `imports.dirs` overrides.
- Scanner rules (the Next.js spec has ~20; the same `ScannerRule` mechanism applies).
- `.vue` single-file components are still not parsed by the TypeScript detectors; only their
  static imports feed the dependency graph.
