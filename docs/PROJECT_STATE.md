# Project

自动化简报

## Repo path

`/Users/wp/Projects/自动化简报`

## Current version

v0.4.1.2 runtime stability hotfix, based on `docs/DEVLOG.md`.

## Current status

Local Python automation for daily RSS-based Markdown brief generation. The current chain generates a daily report, syncs it to Obsidian iCloud, sends a Bark notification, and supports click-through to the iPhone Obsidian note. It remains rules-based and does not call AI APIs.

## Latest completed

P1 foundation docs have been filled in: `docs/BACKLOG.md`, `docs/TESTING.md`, and `docs/DECISIONS.md` now define the backlog, verification checklist, and long-term decisions. Runtime stability hotfix remains in place: `scripts/run_daily_digest.sh` uses `caffeinate -dimsu` across the full task chain, stage logging was added, and RSS request timeout behavior was tightened.

## Last verified

2026-06-25

## Next Action

Observe real morning runs for stability and review whether the v0.4.1 RSS/source-role expansion catches important AI commerce, payments, and global tech business events without adding too much noise. Use `docs/BACKLOG.md`, `docs/TESTING.md`, `docs/DECISIONS.md`, and `docs/MISSED_CASES.md` as the P1 documentation baseline. 后续重点不是继续小修规则，而是评估是否做 AI 筛选/质量提升。

## Blockers

No current P0 blocker recorded. Continue validating real morning runs and use missed coverage records before changing rules.

## Important Context

- Git branch、latest commit、working tree 由 project-command-center 实时 Git 扫描读取；PROJECT_STATE.md 不作为这些字段的权威来源。
- README states the current version does not call DeepSeek, Tavily, or any paid search API.
- v0.3.5 verified the Mac sleep -> pmset wake -> launchd -> digest -> Obsidian iCloud -> Bark -> iPhone Obsidian loop.
- v0.4.1 expanded source roles for `global_tech_business`, `ai_industry`, and `ai_tools`.
- v0.4.1.2 addressed delayed morning reports caused by the Mac sleeping during task execution.
- P1 foundation docs are now split by responsibility: README as entry, PROJECT_STATE as dashboard state, BACKLOG as future work, TESTING as verification checklist, DECISIONS as long-term decisions, and MISSED_CASES as quality tracking.
- Further quality improvements may require evaluating AI-based filtering or ranking rather than continuing small rule tweaks.
- `.env` is used for local Bark / Obsidian configuration and must not be copied into project docs.

## Handoff Prompt

Continue automation-brief by reviewing several real generated daily reports after the caffeinate hotfix. Treat further tiny rule tweaks cautiously; the next larger decision is whether AI filtering or quality improvement is worth introducing.
