# Project

自动化简报

## Repo path

`/Users/wp/Projects/自动化简报`

## Current version

v0.5-beta.2 market-led theme and holdings anomaly polish, based on `docs/DEVLOG.md`.

## Current status

项目已打通本地定时生成、Obsidian 同步和 Bark 推送链路，并开始升级为面向 A 股观察的市场投研晨报。当前阶段已接入轻量 A 股行情观察，并继续优化显式 market_brief 的行情与新闻融合表达；仍保持规则驱动，不调用 AI API。

## Latest completed

v0.5-beta.2 已完成 market_brief 的轻量行情主线与持仓异常表达 polish：新闻主线增加置信度门槛，科创50显著强势时单独输出行情层面观察，持仓相对观察区分小幅 / 明显 / 逆势，持仓异常且 RSS 无相关新闻时输出观察变量说明，财报 / 营收类新闻不再归入 IPO / 融资。

## Deployment

Status: unknown
Public URL: none
Provider: none
Notes: 暂无人工维护的公网部署信息。

## Last verified

2026-06-29

## Next Action

继续观察 1-2 个真实交易日的手动显式 market_brief 样例，重点看行情层面观察是否克制、新闻主线置信度是否避免单条弱新闻误判、持仓异常提示是否有用且不变成交易建议。普通 daily brief 自动链路继续保持不变，不把 market_brief 接入 Bark / Obsidian / launchd。

## Blockers

暂无明确阻塞；`market_brief` 仍只用于显式生成，不并入日常 Bark / Obsidian / launchd 链路。

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
- v0.5-beta.2 changes only explicit `market_brief` quality polish around cautious news themes, market-led 科创50 observation, holdings anomaly wording, and company operating / earnings classification. Default `python3 main.py` still follows `config.json`, and `scripts/run_daily_digest.sh` remains untouched.
- `config/holdings.json` is ignored by Git. `config/holdings.example.json` is only an example and must not contain real cost, position size, market value, or loss amounts.
- Initialize local holdings with `python3 scripts/init_holdings_config.py`; validate with `python3 scripts/validate_holdings_config.py`.
- `market_brief` now uses RSS news plus a lightweight A-share quote snapshot when explicitly generated. It still does not calculate complex strategy, sector strength, or trading actions.
- P1 foundation docs are now split by responsibility: README as entry, PROJECT_STATE as dashboard state, BACKLOG as future work, TESTING as verification checklist, DECISIONS as long-term decisions, and MISSED_CASES as quality tracking.
- Further quality improvements may require evaluating AI-based filtering or ranking rather than continuing small rule tweaks.
- `.env` is used for local Bark / Obsidian configuration and must not be copied into project docs.

## Handoff Prompt

Continue automation-brief from v0.5-beta.2 by preserving the normal daily digest automation and reviewing 1-2 more manually generated explicit `market_brief` samples. The market brief now separates news-confirmed themes from market-led observations, can flag 科创50 index-level strength, classifies holdings relative moves with anomaly wording, and keeps RSS-missing explanations as observation variables rather than trading actions. Keep holdings dynamic via local `config/holdings.json`, keep real holdings and cost/position/value/profit-loss fields out of Git and docs, and do not add trading recommendations.
