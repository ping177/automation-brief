# Project

自动化简报

## Repo path

`/Users/wp/Projects/自动化简报`

## Current version

v0.5-alpha market research brief skeleton, based on `docs/DEVLOG.md`.

## Current status

Local Python automation for daily RSS-based Markdown brief generation. The current chain still generates the normal daily report, syncs it to Obsidian iCloud, sends a Bark notification, and supports click-through to the iPhone Obsidian note. v0.5-alpha adds an explicit `market_brief` report type for a market research brief skeleton using offline sample data and configurable holdings. It remains rules-based and does not call AI APIs.

## Latest completed

v0.5-alpha market brief skeleton is in place: `report_type: "market_brief"` generates `market-brief-YYYY-MM-DD.md`, holdings are loaded from `config/holdings.json` with fallback to `config/holdings.example.json`, and business code no longer hard-codes the example holdings. Runtime stability hotfix remains in place: `scripts/run_daily_digest.sh` uses `caffeinate -dimsu` across the full task chain, stage logging was added, and RSS request timeout behavior was tightened.

## Last verified

2026-06-26

## Next Action

Keep observing normal daily digest automation for stability. For the market research direction, the next recommended step is v0.5-beta: connect real A-share market data behind the existing market data interface while keeping the current no-trading-advice boundary.

## Blockers

No current P0 blocker recorded. v0.5-alpha does not connect real market data yet, so market strength, relative strength, and catalysts remain placeholders.

## Important Context

- Git branch、latest commit、working tree 由 project-command-center 实时 Git 扫描读取；PROJECT_STATE.md 不作为这些字段的权威来源。
- README states the current version does not call DeepSeek, Tavily, or any paid search API.
- v0.3.5 verified the Mac sleep -> pmset wake -> launchd -> digest -> Obsidian iCloud -> Bark -> iPhone Obsidian loop.
- v0.4.1 expanded source roles for `global_tech_business`, `ai_industry`, and `ai_tools`.
- v0.4.1.2 addressed delayed morning reports caused by the Mac sleeping during task execution.
- v0.5-alpha adds `market_brief` as an explicit report type only; default `python main.py` and `scripts/run_daily_digest.sh` behavior stays on the existing configured daily digest.
- `config/holdings.json` is ignored by Git. `config/holdings.example.json` is only an example and must not contain real cost, position size, market value, or loss amounts.
- `market_brief` currently uses offline sample data only. v0.5-beta should add real market data integration without adding trading recommendations.
- P1 foundation docs are now split by responsibility: README as entry, PROJECT_STATE as dashboard state, BACKLOG as future work, TESTING as verification checklist, DECISIONS as long-term decisions, and MISSED_CASES as quality tracking.
- Further quality improvements may require evaluating AI-based filtering or ranking rather than continuing small rule tweaks.
- `.env` is used for local Bark / Obsidian configuration and must not be copied into project docs.

## Handoff Prompt

Continue automation-brief from v0.5-alpha by preserving the normal daily digest automation and preparing v0.5-beta real A-share market data integration for `market_brief`. Keep holdings dynamic via `config/holdings.json`, keep real holdings out of Git, and do not add trading recommendations.
