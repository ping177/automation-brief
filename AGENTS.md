# AGENTS.md

This file defines how Codex and other development agents should work in this project. Keep changes small, scoped, and aligned with the existing project style.

## Start-of-task context

Before starting a task, read the relevant project context when available:

- `README.md`
- `docs/PROJECT_STATE.md`
- `docs/BACKLOG.md`
- `docs/DEVLOG.md`
- `docs/DECISIONS.md`
- `docs/TESTING.md` if present

If a file is missing, state that it is missing. Do not invent project state.

## Project State Maintenance

After any meaningful code, documentation, configuration, planning, testing, or deployment change, check whether `docs/PROJECT_STATE.md` needs updating.

Update `docs/PROJECT_STATE.md` when any of these changed:

- current version or phase
- current status
- latest completed work
- next recommended action
- blockers
- important context
- handoff prompt
- ports / environment assumptions
- deployment or verification status

Do not update `PROJECT_STATE.md` for trivial formatting-only changes unless the status actually changed.

`PROJECT_STATE.md` should keep stable headings that project-command-center can read:

- Current version
- Current status
- Latest completed
- Next Action
- Blockers
- Important Context
- Handoff Prompt

Git branch, latest commit, and working tree are live Git data in project-command-center and should not be treated as the source of truth from `PROJECT_STATE.md`.

## Documentation mapping

When relevant, update the right documentation:

- `docs/DEVLOG.md` for completed work and verification notes
- `docs/BACKLOG.md` for scope, priority, or future task changes
- `docs/DECISIONS.md` for product, architecture, API, or workflow decisions
- `docs/PROJECT_STATE.md` for the current dashboard-facing state
- `docs/TESTING.md` for test strategy or smoke checklist changes, if present

Do not duplicate large amounts of content across docs. Keep `PROJECT_STATE.md` concise and dashboard-oriented.

## Local dev ports

For local web projects:

- keep dev ports explicit and stable
- use `strictPort: true` for Vite projects
- local APIs should prefer `127.0.0.1`
- do not silently change dev ports

If a project dev port changes, mention that `project-command-center/config/projects.json` may also need updating.

## Secrets and safety

Never read, print, or commit secrets:

- `.env`
- `.env.local`
- API keys
- tokens
- private credentials

Do not put commercial API keys in frontend code. Do not commit `node_modules`, `dist`, build output, or local environment files.

## Git workflow

Do not commit or push unless the user explicitly asks.

Before finishing a task, run or request the appropriate status checks:

- `git branch --show-current`
- `git status --short`
- `git log --oneline -5` when useful

If on a non-main branch, clearly state the current branch and whether it has an upstream.

## Verification

Run the smallest relevant verification for the type of change:

- Vite / React code changes: `npm run build`
- Node syntax-sensitive files: `node --check` where applicable
- Python changes: `python -m py_compile` or the project test command where applicable
- docs-only changes: `git diff --check` is enough unless docs tooling exists

Do not run unnecessary heavy checks for docs-only changes.

## Final response format

At the end of each task, report:

- modified files
- whether business code changed
- whether external project files changed
- whether secrets were read or printed
- verification run and result
- git status summary
- whether `PROJECT_STATE.md` was updated or why it was not needed
- whether commit is recommended
- next suggested action
