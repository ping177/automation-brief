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

## Local persistent data governance

- 本项目稳定 `projectId` 为：`automation-brief`。
- Filesystem-level persistent runtime/user data 的 canonical root 为：`/Users/wp/Projects/_project-data/automation-brief/`。
- Canonical data directories：`reports/` 保存正式 Daily / Market reports；`runs/` 保存 runtime logs / AI Curator shadow artifacts；`manual-inputs/` 保存敏感人工输入（例如 holdings）；`migration-records/` 保存 filesystem migration provenance。
- 未经明确治理审查，不得把长期数据重新默认写回 repo 内的 `output/`、`data/` 等目录。新增长期 filesystem data 时，应优先纳入 canonical data root，并通过统一 resolver `project_paths.py` 获取路径；业务代码中不得散落 `/Users/wp/...` absolute paths。
- tests 必须使用 temp / injected data root，不得写入真实 `/Users/wp/Projects/_project-data/automation-brief/`，也不得读取真实 holdings。
- Obsidian / iCloud 是 downstream export，不是 canonical data source。
- legacy repo copies 当前仍属于 rollback retained data；不得因为发现重复文件就擅自删除。
- 项目自身仍拥有业务 schema 和 AI Curator 语义；Project Command Center 统一的只是 filesystem-level data location/governance。

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
- Deployment
- Version Index
- Next Action
- Blockers
- Important Context
- Handoff Prompt

Git branch, latest commit, and working tree are live Git data in project-command-center and should not be treated as the source of truth from `PROJECT_STATE.md`.

## Version Governance

- New formal version tokens must be pure numeric canonical versions such as `v0.8`, `v0.8.2`, or a numeric corrective version such as `v0.6.6.1`.
- The v0.7 Morning Brief route uses numeric subversions: its former three stages map to `v0.7.1`, `v0.7.2`, and `v0.7.3`; do not introduce phase labels as formal version/stage names. The top-level `v0.7 — Morning Brief` milestone may remain.
- `Version Index` records numeric versions / milestones only. Existing legacy pseudo-version entries are historical facts and must not be rewritten.
- Use the existing PCC canonicalization and validation contract; do not copy a parser into this repository or use an LLM to repair versions.

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

Before every `git push`, review `docs/PROJECT_STATE.md` and update stale facts: `Current version`, `Current status`, `Next Action`, `Blockers`, `Version Index`, and `Deployment` when the work affects it. Replace completed Next Action entries, remove resolved blockers, write `暂无明确阻塞。` exactly when there is no blocker, and add a Version Index item only for a new version or formal milestone. If review confirms that no text change is needed, do not create a meaningless document edit; use `Project-State-Review: verified-current`.

When this repository's Project State Push Gate is installed, the final commit of every pushed branch must contain exactly one `Project-State-Review: updated` or `Project-State-Review: verified-current` trailer. `updated` means the final tree differs from the remote branch tree at `docs/PROJECT_STATE.md`; `verified-current` means it does not. The gate does not validate document content. A pushed tag only needs to peel to a commit with one legal trailer and is not classified by tree diff. This local gate does not replace the rule that only an explicit user request permits a commit or push.

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
