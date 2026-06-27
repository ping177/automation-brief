# Project

自动化简报

## Repo path

`/Users/wp/Projects/自动化简报`

## Current version

v0.5-beta.1 market brief quote polish, based on `docs/DEVLOG.md`.

## Current status

Local Python automation for daily RSS-based Markdown brief generation. The current chain still generates the normal daily report, syncs it to Obsidian iCloud, sends a Bark notification, and supports click-through to the iPhone Obsidian note. v0.5-alpha added an explicit `market_brief` report type, v0.5.1-alpha added local holdings initialization and validation, v0.5.2-alpha lets explicit market briefs reuse RSS candidate news, v0.5.3-alpha adds rules-based news quality tuning, v0.5-beta first stage adds lightweight A-share market quotes, and v0.5-beta.1 polishes quote-date handling, IPO noise, empty sections, and holdings relative observations. It remains rules-based and does not call AI APIs.

## Latest completed

v0.5-beta.1 small fix is implemented locally. `market_data.py` now separates report date from market data date and treats the public quote source成交额 field as unavailable until its口径 is verified. `market_news.py` limits IPO / financing items to at most two and drops overseas IPO items that cannot map to A-share industries or the current theme. `market_brief_writer.py` avoids empty “暂无可展示内容” templates in 今日主线 and adds light holdings relative descriptions versus major index average. `scripts/run_market_brief.sh` remains the explicit market brief entry point. Runtime stability hotfix remains in place: `scripts/run_daily_digest.sh` uses `caffeinate -dimsu` across the full task chain, stage logging was added, and RSS request timeout behavior was tightened.

## Last verified

2026-06-27

## Next Action

Run the full requested verification checklist for v0.5-beta.1, then regenerate a manual explicit market brief sample and confirm the weekend/report-date wording, IPO volume, risk de-duplication, and holdings relative observations are acceptable.

## Blockers

No current P0 blocker recorded. v0.5-beta.1 still uses lightweight quote data only for explicit `market_brief`, not the normal daily brief. Remaining limitations: sector strength is not computed, industry/sector comes from local holdings config, 成交额 is intentionally shown as unavailable until field口径 is verified, and public quote source fields may be missing or temporarily unavailable.

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
- v0.5-beta.1 changes only explicit `market_brief` output quality around quote dates, IPO noise, risk de-duplication, and holdings relative observation. Default `python3 main.py` still follows `config.json`, and `scripts/run_daily_digest.sh` remains untouched.
- `config/holdings.json` is ignored by Git. `config/holdings.example.json` is only an example and must not contain real cost, position size, market value, or loss amounts.
- Initialize local holdings with `python3 scripts/init_holdings_config.py`; validate with `python3 scripts/validate_holdings_config.py`.
- `market_brief` now uses RSS news plus a lightweight A-share quote snapshot when explicitly generated. It still does not calculate complex strategy, sector strength, or trading actions.
- P1 foundation docs are now split by responsibility: README as entry, PROJECT_STATE as dashboard state, BACKLOG as future work, TESTING as verification checklist, DECISIONS as long-term decisions, and MISSED_CASES as quality tracking.
- Further quality improvements may require evaluating AI-based filtering or ranking rather than continuing small rule tweaks.
- `.env` is used for local Bark / Obsidian configuration and must not be copied into project docs.

## Handoff Prompt

Continue automation-brief from v0.5-beta.1 by preserving the normal daily digest automation and reviewing a regenerated explicit `market_brief` sample. The market brief now separates report date and market data date, treats unverified成交额口径 as unavailable, limits IPO / financing noise, de-duplicates risk variables, and adds light holdings relative observations without trading actions. Keep holdings dynamic via local `config/holdings.json`, keep real holdings and cost/position/value/profit-loss fields out of Git and docs, and do not add trading recommendations.
