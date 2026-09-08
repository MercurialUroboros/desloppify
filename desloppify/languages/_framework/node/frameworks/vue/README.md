# Vue Framework Support (Guidance)

Spec: `desloppify/languages/_framework/frameworks/specs/vue.py`. Detected from the `vue`
dependency in the nearest `package.json`, so it is present in every Nuxt project too.

`guidance.py` distils the core references of the Vue team's `vue-best-practices` skill
(github.com/vuejs-ai/skills, MIT): reactivity, SFC structure and template safety, component
data flow, composables, state management and list performance. It is merged into review
packets so subjective reviews and refactoring agents apply Vue idioms instead of the React
ones in the TypeScript plugin's default guidance.

No convention entry points: plain Vue apps import components explicitly. Auto-import plugins
(`unplugin-vue-components`, `unplugin-auto-import`) are not modelled.
