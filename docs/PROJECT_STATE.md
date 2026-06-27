# Project

自动化简报

## Repo path

`/Users/wp/Projects/自动化简报`

## Current version

v0.5.3-alpha news quality tuning, based on `docs/DEVLOG.md`.

## Current status

Local Python automation for daily RSS-based Markdown brief generation. The current chain still generates the normal daily report, syncs it to Obsidian iCloud, sends a Bark notification, and supports click-through to the iPhone Obsidian note. v0.5-alpha added an explicit `market_brief` report type, v0.5.1-alpha added local holdings initialization and validation, v0.5.2-alpha lets explicit market briefs reuse RSS candidate news, and v0.5.3-alpha adds rules-based news quality tuning for relevance scoring, news typing, weak-content filtering, theme aggregation, and precise holdings matching. It remains rules-based and does not call AI APIs.

## Latest completed

v0.5.3-alpha news quality tuning plus quality fix is implemented locally. `market_news.py` now scores and classifies RSS candidates before they can enter market events, industry catalysts, risks, watch points, or holdings-related news, with extra guards for roundup/news-digest articles, title-first IPO/listing classification, stricter policy-regulation classification, risk/watch variable generation, representative-news-only theme clues, and high-precision holdings matching. `market_brief_writer.py` shows news type and relevance score for selected items and no longer displays orphan theme clues. `scripts/run_market_brief.sh` remains the explicit market brief entry point. Runtime stability hotfix remains in place: `scripts/run_daily_digest.sh` uses `caffeinate -dimsu` across the full task chain, stage logging was added, and RSS request timeout behavior was tightened.

## Last verified

2026-06-27

## Next Action

Review the regenerated explicit RSS sample at `output/market-brief-2026-06-27.md`. If the v0.5.3-alpha quality-fix sample is acceptable, the next feature direction can be v0.5-beta real A-share market data; keep that separate from news quality rules and continue avoiding trading recommendations.

## Blockers

No current P0 blocker recorded. The previous product-quality blocker for v0.5.3-alpha news quality has a local rules-based fix and offline smoke coverage. Remaining limitation: `market_brief` still does not connect real market data, so market strength, relative strength, sector strength, and price/volume confirmation remain unavailable until a later v0.5-beta task.

## Important Context

- Git branch、latest commit、working tree 由 project-command-center 实时 Git 扫描读取；PROJECT_STATE.md 不作为这些字段的权威来源。
- README states the current version does not call DeepSeek, Tavily, or any paid search API.
- v0.3.5 verified the Mac sleep -> pmset wake -> launchd -> digest -> Obsidian iCloud -> Bark -> iPhone Obsidian loop.
- v0.4.1 expanded source roles for `global_tech_business`, `ai_industry`, and `ai_tools`.
- v0.4.1.2 addressed delayed morning reports caused by the Mac sleeping during task execution.
- v0.5-alpha adds `market_brief` as an explicit report type only; default `python3 main.py` and `scripts/run_daily_digest.sh` behavior stays on the existing configured daily digest.
- v0.5.1-alpha adds `python3 main.py --report-type market_brief` and `scripts/run_market_brief.sh` as explicit one-off market brief entry points.
- v0.5.2-alpha changes only the explicit `market_brief` path to reuse RSS candidate news; default `python3 main.py` still follows `config.json`, and `scripts/run_daily_digest.sh` remains untouched.
- v0.5.3-alpha changes only `market_brief` news quality rules and rendering. The quality fix specifically downranks roundup news, corrects IPO/listing vs macro/policy classification, removes orphan theme clues, outputs risk/watch variables, and tightens holdings matches. Default `python3 main.py` still follows `config.json`, and `scripts/run_daily_digest.sh` remains untouched.
- `config/holdings.json` is ignored by Git. `config/holdings.example.json` is only an example and must not contain real cost, position size, market value, or loss amounts.
- Initialize local holdings with `python3 scripts/init_holdings_config.py`; validate with `python3 scripts/validate_holdings_config.py`.
- `market_brief` currently uses RSS news plus offline market snapshot placeholders. v0.5-beta should add real A-share market data only after reviewing a v0.5.3-alpha sample, and without adding trading recommendations.
- P1 foundation docs are now split by responsibility: README as entry, PROJECT_STATE as dashboard state, BACKLOG as future work, TESTING as verification checklist, DECISIONS as long-term decisions, and MISSED_CASES as quality tracking.
- Further quality improvements may require evaluating AI-based filtering or ranking rather than continuing small rule tweaks.
- `.env` is used for local Bark / Obsidian configuration and must not be copied into project docs.

## Handoff Prompt

Continue automation-brief from v0.5.3-alpha quality fix by preserving the normal daily digest automation and reviewing `output/market-brief-2026-06-27.md`. The news quality rules now score relevance, classify news type, filter weak related and roundup content, aggregate themes only when representative news exists, output risk/watch variables, and require high-precision holdings matches. Defer v0.5-beta real A-share market data integration until after sample review. Keep holdings dynamic via local `config/holdings.json`, keep real holdings and cost/position/value/profit-loss fields out of Git and docs, and do not add trading recommendations.
