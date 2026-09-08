# Agent skills kept in this repo

Personal Claude Code skills that drive desloppify, versioned here so their history lives with the tool.

- `desloppifying/` — general workflow skill: pins the local build, routes refactoring to framework skills, verifies findings before fixing.

Install by symlinking the skill directory into your agent's skills folder, so edits here are picked up immediately:

```bash
ln -s "$(pwd)/dev/skills/desloppifying" ~/.claude/skills/desloppifying
```

These are separate from `docs/*.md`, which are the runner skill documents desloppify installs into projects.
