# Project

自动化简报

## Repo path

`/Users/wp/Projects/自动化简报`

## Current version

v0.5-beta real A-share market data first stage, based on `docs/DEVLOG.md`.

## Current status

Local Python automation for daily RSS-based Markdown brief generation. The current chain still generates the normal daily report, syncs it to Obsidian iCloud, sends a Bark notification, and supports click-through to the iPhone Obsidian note. v0.5-alpha added an explicit `market_brief` report type, v0.5.1-alpha added local holdings initialization and validation, v0.5.2-alpha lets explicit market briefs reuse RSS candidate news, v0.5.3-alpha adds rules-based news quality tuning, and v0.5-beta first stage adds lightweight A-share market quotes for explicit market briefs. It remains rules-based and does not call AI APIs.

## Latest completed

v0.5-beta first stage is implemented locally. `market_data.py` now has a small standard-library data layer for index quotes, holding quotes, structured failures, and offline fallback. Explicit `market_brief` runs try to fetch 上证指数、深成指、创业板指、科创50 and configured holdings quotes; failures downgrade to “数据暂不可用” instead of failing the report. `market_brief_writer.py` now uses the six-section structure with “市场温度” and “我的持仓观察” showing available quote data. `scripts/run_market_brief.sh` remains the explicit market brief entry point. Runtime stability hotfix remains in place: `scripts/run_daily_digest.sh` uses `caffeinate -dimsu` across the full task chain, stage logging was added, and RSS request timeout behavior was tightened.

## Last verified

2026-06-27

## Next Action

Run the full requested verification checklist for v0.5-beta first stage, then generate a manual explicit market brief sample when network is available and review whether the quote fields from the lightweight source are stable enough for continued use.

## Blockers

No current P0 blocker recorded. v0.5-beta first stage now connects lightweight quote data for explicit `market_brief`, but it is not a full research system. Remaining limitations: sector strength and relative strength are not computed, industry/sector comes from local holdings config, and public quote source fields may be missing or temporarily unavailable.

## Important Context

- Git branch、latest commit、working tree 由 project-command-center 实时 Git 扫描读取；PROJECT_STATE.md 不作为这些字段的权威来源。
- README states the current version does not call DeepSeek, Tavily, or any paid search API.
- v0.3.5 verified the Mac sleep -> pmset wake -> launchd -> digest -> Obsidian iCloud -> Bark -> iPhone Obsidian loop.
- v0.4.1 expanded source roles for `global_tech_business`, `ai_industry`, and `ai_tools`.
- v0.4.1.2 addressed delayed morning reports caused by the Mac sleeping during task execution.
- v0.5-alpha adds `market_brief` as an explicit report type only; default `python3 main.py` and `scripts/run_daily_digest.sh` behavior stays on the existing configured daily digest.
- v0.5.1-alpha adds `python3 main.py --report-type market_brief` and `scripts/run_market_brief.sh` as explicit one-off market brief entry points.
- v0.5.2-alpha changes only the explicit `market_brief` path to reuse RSS candidate news; default `python3 main.py` still follows `config.json`, and `scripts/run_daily_digest.sh` remains untouched.
- v0.5.3-alpha changes only `market_brief` news quality rules and rendering. The quality fix specifically downranks roundup news, corrects IPO/listing vs macro/policy classification, removes orphan theme clues, outputs risk/watch variables, and tightens holdings matches.
- v0.5-beta first stage changes only the explicit `market_brief` path to fetch lightweight A-share quote data and downgrade failures. Default `python3 main.py` still follows `config.json`, and `scripts/run_daily_digest.sh` remains untouched.
- `config/holdings.json` is ignored by Git. `config/holdings.example.json` is only an example and must not contain real cost, position size, market value, or loss amounts.
- Initialize local holdings with `python3 scripts/init_holdings_config.py`; validate with `python3 scripts/validate_holdings_config.py`.
- `market_brief` now uses RSS news plus a lightweight A-share quote snapshot when explicitly generated. It still does not calculate complex strategy, sector strength, or trading actions.
- P1 foundation docs are now split by responsibility: README as entry, PROJECT_STATE as dashboard state, BACKLOG as future work, TESTING as verification checklist, DECISIONS as long-term decisions, and MISSED_CASES as quality tracking.
- Further quality improvements may require evaluating AI-based filtering or ranking rather than continuing small rule tweaks.
- `.env` is used for local Bark / Obsidian configuration and must not be copied into project docs.

## Handoff Prompt

Continue automation-brief from v0.5-beta first stage by preserving the normal daily digest automation and reviewing an explicit `market_brief` sample with real quote data when network is available. The market brief now combines RSS news quality rules with lightweight quote data for indexes and configured holdings, while missing quote fields downgrade to “数据暂不可用”. Keep holdings dynamic via local `config/holdings.json`, keep real holdings and cost/position/value/profit-loss fields out of Git and docs, and do not add trading recommendations.
