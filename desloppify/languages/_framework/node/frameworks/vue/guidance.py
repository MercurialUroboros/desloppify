"""Vue review guidance merged into review packets when Vue is detected.

Distilled from the Vue team's skills collection (github.com/vuejs-ai/skills,
MIT): ``vue-best-practices`` (reactivity, SFC structure, component data flow,
composables, state management, list performance), ``vue-pinia-best-practices``,
``vue-router-best-practices`` and ``vue-testing-best-practices``, plus the
``pinia`` and ``vueuse-functions`` skills from github.com/antfu/skills. Nuxt adds its
own layer on top (see ``../nuxt/guidance.py``); these rules apply to any Vue 3
codebase, Nuxt or not.
"""

from __future__ import annotations

VUE_REVIEW_GUIDANCE: dict[str, object] = {
    "patterns": [
        # Reactivity
        "Flag derived state kept in sync by `watch`/`watchEffect` assignments — it should be a `computed`",
        "Flag filtering/sorting/formatting logic inline in templates — move derivations to `computed` in `<script setup>`",
        "Flag `computed` getters with side effects (fetches, emits, mutations); side effects belong in watchers",
        "Flag destructuring of `reactive()` objects (loses reactivity) — use `toRefs` or keep the object",
        "Flag watchers that duplicate an initial call instead of `immediate: true`, and async watchers without cleanup (`onCleanup`/abort)",
        # SFC structure and template safety
        "Flag `v-for` without a stable primitive `:key` (index or object keys count as unstable)",
        "Flag `v-if` and `v-for` on the same element — wrap in `<template v-if>` or filter in a `computed`",
        "Flag `v-html` bound to user-provided or remote content without sanitization",
        "Flag SFCs mixing Options API and `<script setup>`; new code should be Composition API with `<script setup lang=\"ts\">`",
        "Flag unscoped `<style>` blocks in components and element selectors inside `<style scoped>`",
        "Flag `$refs`/`ref<HTMLElement>()` DOM access in Vue 3.5+ code where `useTemplateRef()` applies",
        # Component data flow
        "Flag props mutated inside a child (`props.x = ...`, `props.list.push`) — emit an event or use `defineModel`",
        "Flag parents that call methods on child component refs for data flow — reserve refs for imperative APIs (focus, scroll)",
        "Flag untyped `defineProps`/`defineEmits` in TypeScript projects — use the type-based generic form",
        "Flag prop drilling deeper than ~3 layers — use `provide`/`inject` with an `InjectionKey`, or a store",
        "Flag `provide` of raw mutable state without explicit actions — consumers should not mutate injected state directly",
        # Components and composables
        "Flag components with more than one clear responsibility (data orchestration + several UI sections, 3+ distinct sections, repeated template blocks) — split into container + presentational children",
        "Flag route views/entry components that own full feature implementations — keep them thin composition surfaces",
        "Flag composables with long positional parameter lists — use an options object; and pure helpers named `useXxx` that hold no state (keep them plain utilities)",
        "Flag composables returning writable state that should be `readonly` with explicit action functions",
        # State management
        "Flag module-level `ref`/`reactive` exported as shared state — leaks across SSR requests and hides mutations; use Pinia or a `createGlobalState`-style composable in SPAs",
        "Flag global stores used for state that only one feature reads — keep state local first",
        # Performance
        "Flag wrapper components that add no value inside large `v-for` lists — flatten to native elements in hot paths",
        # Pinia
        "Flag plain destructuring of a Pinia store (`const { items } = useStore()`) — breaks reactivity; use `storeToRefs` for state/getters and destructure actions only",
        "Flag setup stores that create state but do not return it — invisible to DevTools and dropped from SSR hydration",
        "Flag `useStore()` called at module scope (before the app installs Pinia) — call it inside setup, guards or actions",
        "Flag ephemeral UI state (filters, sort, pagination, open tabs) kept in a store when it should live in the URL query so it survives refresh and is shareable",
        # Vue Router
        "Flag navigation guards that still call `next()` — return a value/`false`/route instead (Router 4)",
        "Flag guards that redirect without a terminating condition (infinite loop risk) and guards that call APIs without awaiting them",
        "Flag route components that load data in `onMounted`/`created` only — same-route param changes do not remount; watch `route.params` or use `onBeforeRouteUpdate`",
        "Flag `beforeEnter`/`beforeRouteEnter` code relying on `this` or on re-triggering for param-only changes",
        "Flag global listeners, timers or subscriptions added in route components without cleanup on unmount",
    ],
    "testing": [
        "Vue components should be tested black-box with Vue Test Utils/Vitest: render, interact, assert on DOM/emits — flag tests asserting on internal refs, `vm` state or implementation details",
        "Flag snapshot-only component tests; they pass while behaviour breaks",
        "Flag async component tests without `await nextTick()`/`flushPromises()` (or `<Suspense>` wrapping for async setup) — intermittent failures",
        "Composables using lifecycle hooks, `inject` or Pinia must be tested inside a wrapper component with `setActivePinia(createPinia())`",
        "Prefer Vitest for unit tests and Playwright for E2E; browser-mode runners only when real layout/computed styles matter",
    ],
    "naming": (
        "Vue conventions: components PascalCase in filenames and templates (`UserCard.vue`, `<UserCard />`), "
        "composables `useXxx`, Pinia stores `useXxxStore`, props camelCase in script and kebab-case in "
        "templates, emitted events kebab-case. Flag composables without the `use` prefix and components "
        "with generic names (`Item.vue`, `Wrapper.vue`)."
    ),
    "refactoring": [
        "Split a mega component into: container (state + orchestration), form/input, list + item, footer/status children with typed props/emits",
        "Extract stateful or side-effect-heavy logic into `composables/use<Feature>.ts`; keep pure helpers in `utils/`",
        "Replace watcher-maintained derived refs with `computed`; replace template expressions with named `computed`s",
        "Replace `v-model` emulation (`:value` + `@input`) with `defineModel()` (Vue 3.4+)",
        "Organise by feature (`components/<feature>/`, `composables/use<Feature>.ts`) instead of by type when a feature has several files",
        "Prefer Pinia setup stores (`defineStore(id, () => {...})`) over option stores when a store needs composables, watchers or complex logic; add `acceptHMRUpdate` for dev",
        "Replace hand-rolled browser/state utilities with VueUse equivalents (`useLocalStorage`, `useDebounceFn`, `useIntersectionObserver`, `useEventListener`, `useFetch`-style helpers) before writing a custom composable",
    ],
}

__all__ = ["VUE_REVIEW_GUIDANCE"]
