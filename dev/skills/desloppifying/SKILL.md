---
name: desloppifying
description: Use when asked to run desloppify, raise a codebase's health score, work a desloppify queue, run or import a desloppify review, or fix findings desloppify reported, in any language or framework.
---

# Desloppifying

## Overview

desloppify scans a codebase, scores it, and hands out a work queue. It detects the language and frameworks itself (Nuxt, Vue, Next.js, Python, ...), so this skill is not framework-specific: it keeps you on the local build, routes refactoring to the matching framework skills, and keeps the score honest.

**The local build is the only desloppify.** `command -v desloppify` must resolve to `~/.local/bin/desloppify`, a symlink into `~/Desktop/persona/desloppify/.venv`. Never `pip install`, `uvx`, or `desloppify update-skill` (it downloads docs from the upstream repo). Code changes in that checkout apply immediately.

## Workflow

1. **Follow the project's own skill doc** for the phases: `.claude/skills/desloppify/SKILL.md` in the project (scan and review, plan, execute). If it is missing, read `~/Desktop/persona/desloppify/docs/SKILL.md` and `docs/CLAUDE.md` instead. Run commands from inside the project so state lands in its `.desloppify/`.
2. **Load the framework skills before refactoring.** Decide from the manifest: `package.json` dependencies or `pyproject.toml`. (`.desloppify/query.json` is rewritten by every command; only right after `desloppify review --prepare` does it carry `frameworks` and `lang_guidance`, with a `refactoring` list.) Then load:

| Detected | Load |
|---|---|
| nuxt | `nuxt`, `nuxt4-patterns`; `nuxt-ui` if `@nuxt/ui` is a dependency |
| vue (also every Nuxt app) | `vue-best-practices`. If it is not installed, run `npx skills add https://github.com/vuejs-ai/skills --skill vue-best-practices` (expected, one-time, network) and load it. Add `vue-pinia-best-practices`, `vue-router-best-practices`, `vue-testing-best-practices` when those libraries appear |
| drizzle, supabase | `drizzle`, `supabase-postgres-best-practices` |
| typescript | `typescript-advanced-types` for type-level findings, `coding-standards` for naming |
| svelte | `svelte-code-writer` |
| any | `test-driven-development` for fixes that change behavior, `systematic-debugging` for bug-class findings, `verification-before-completion` before resolving |

3. **Verify a finding before touching code.** `desloppify show <id>`, then open the file at the reported line. Detectors are heuristics: if the finding is wrong, `desloppify plan skip <id> --false-positive --note "<why>"`. If one detector is wrong across many files, fix the detector in `~/Desktop/persona/desloppify` (see below) instead of skipping dozens of items.
4. **Fix, then resolve with a truthful attestation.** The `--attest` text must describe the actual change. Run the project's tests after each batch. A score that drops after a fix is normal; keep going.
5. **Reviews with subagents** follow the Claude overlay in the project doc. The blind packet already carries the merged language and framework guidance, so give reviewers the packet path and nothing from this conversation. If `review --prepare` refuses because the objective backlog is not drained, work the objective queue first; do not force a rerun.
6. **Queue views differ by design.** `desloppify next` is the single next action; `desloppify plan queue` lists the whole execution queue, including subjective-review items with no file. `desloppify show <detector>` lists everything open. Scans rewrite `scorecard.png`; pass `--no-badge` when you are not going to commit.

## When desloppify itself is wrong

Fix it in the local checkout, not a temp clone:

```bash
cd ~/Desktop/persona/desloppify
.venv/bin/python -m pytest -q desloppify/tests      # ~35 s
.venv/bin/python -m ruff check . --select E9,F63,F7,F82
```

Then rescan the project and compare a few findings against their source lines before trusting a new rule. Commit there on `main`.

## Red flags

- Resolving an item without a diff, or editing `.desloppify/state.json` by hand.
- Attestations that restate the finding instead of the fix.
- Skipping many findings from one detector as false positives without checking why.
- Refactoring Vue or Nuxt code with React idioms (hooks, `use client`), or Python with TypeScript ones: load the matching skill first.
- Running `desloppify scan --path ../other` from a different directory: state and paths end up in the wrong place.
- Guessing subcommands: `desloppify <command> --help` first (`zone show`, not `zone list`).
