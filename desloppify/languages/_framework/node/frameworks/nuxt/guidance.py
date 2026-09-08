"""Nuxt review guidance merged into review packets when Nuxt is detected.

Nuxt-specific rules only: SSR/hydration, data fetching, Nitro handlers, runtime
config and the auto-import layout. Generic Vue rules come from the Vue spec
(``../vue/guidance.py``), which is also detected in every Nuxt project.

Sources: the Nuxt 4 docs (directory structure, data fetching, SSR best
practices, server routes) as captured in the ``nuxt`` and ``nuxt4-patterns``
skills.
"""

from __future__ import annotations

NUXT_REVIEW_GUIDANCE: dict[str, object] = {
    "patterns": [
        # Data fetching
        "Flag top-level `$fetch` in `<script setup>` for initial page data (runs on server and again on hydration) — use `useFetch`/`useAsyncData`",
        "Flag `useAsyncData` without a stable key, or `useFetch`/`useAsyncData` keys that omit a reactive input (route param, query) — causes stale cache or double fetching",
        "Flag `useAsyncData` handlers with side effects (state writes, navigation) — they run during SSR and hydration",
        "Flag non-critical data fetched eagerly without `lazy: true` and without `status === 'pending'` UI",
        "Flag `$fetch` used for SEO-relevant page data with `server: false`",
        # SSR / hydration
        "Flag `Date.now()`, `Math.random()`, `window`/`document`/`localStorage` reads in SSR-rendered template state — move behind `onMounted`, `import.meta.client`, `<ClientOnly>` or a `.client.vue` component",
        "Flag `useRoute` imported from `vue-router` instead of Nuxt's auto-imported `useRoute`, and `route.fullPath` driving SSR markup (fragments are client-only)",
        "Flag composables holding module-level singleton state (`const state = ref()` outside the function) — shared across requests on the server; use `useState('key', ...)` or Pinia",
        "Flag `ssr: false` route rules or `<ClientOnly>` used as a blanket fix for hydration mismatches instead of fixing the non-deterministic render",
        # Layout and auto-imports
        "Flag `definePageMeta` outside `pages/`, and files in `composables/` or `utils/` nested subfolders that are never imported (Nuxt only auto-imports top-level files)",
        "Flag imports from `~~/server/**` or `#server` inside `app/**` — server code must stay behind API routes; share pure code via `shared/utils`",
        "Flag `<a href>` for internal navigation — use `<NuxtLink>` so routes and payloads prefetch",
        "Flag heavy below-the-fold components rendered eagerly — prefer `Lazy*` components with `v-if` or lazy hydration (`hydrate-on-visible`)",
        # Nitro
        "Flag Nitro handlers reading raw `readBody`/`getQuery` without `readValidatedBody`/`getValidatedQuery` (zod/valibot) for user input",
        "Flag business logic inside `server/api/**` handlers — move it to `server/utils/` (auto-imported, unit-testable) and keep handlers thin",
        "Flag `navigateTo`/`useRouter` or Vue composables used inside `server/**`",
    ],
    "auth": [
        "Sibling handlers under `server/api/**` should share one guard (`requireUserSession`, `getUserSession`, or a `server/middleware` check) — flag mixed patterns",
        "Flag `runtimeConfig.public.*` entries that look like secrets (keys, tokens, service-role) — they ship to the browser",
        "Flag `process.env.*` in `app/**` — client code must read `useRuntimeConfig().public`",
        "Flag route middleware that trusts client-side state (cookie/localStorage flags) for authorization decisions",
    ],
    "naming": (
        "Nuxt conventions: components are auto-registered with their folder prefix "
        "(`components/auction/BuzzConsole.vue` -> `<AuctionBuzzConsole>`), Nitro handlers "
        "`name.<method>.ts` (`users.get.ts`, `[id].put.ts`), route middleware `*.global.ts` "
        "when it must run everywhere, `*.client.ts`/`*.server.ts` plugin suffixes for one side only. "
        "Flag handlers without a method suffix that branch on `event.method`."
    ),
    "refactoring": [
        "Extract repeated `useFetch` + loading/error handling into one composable per resource, keyed on its reactive inputs",
        "Move business rules out of Nitro handlers into `server/utils/` and share pure helpers with the app through `shared/utils/`",
        "Move shared reactive state from deep `provide/inject` chains into Pinia or `useState`",
        "Split page components over ~200 lines: keep data loading in the page, move markup into `components/` and logic into `composables/`",
        "Pick `routeRules` per route group (prerender marketing pages, `swr`/`isr` catalogs, `ssr: false` admin) instead of one global rendering mode",
        "Extract large `<script setup>` blocks into auto-imported `utils/` (top-level files only) so logic is unit-testable without mounting",
    ],
}

__all__ = ["NUXT_REVIEW_GUIDANCE"]
