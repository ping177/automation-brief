# Project

自动化简报

## Repo path

`/Users/wp/Projects/自动化简报`

## Current version

v0.5-beta.5 important news relevance and classification polish, based on `docs/DEVLOG.md`.

## Current status

项目已打通本地定时生成、Obsidian 同步和 Bark 推送链路，并开始升级为面向 A 股观察的市场投研晨报。v0.5-beta.5 已完成显式 market_brief 的重要新闻相关度、分类和市场/持仓优先观察 polish；普通 daily digest 展示与自动化链路保持不变，仍保持规则驱动，不调用 AI API。

## Latest completed

v0.5-beta.5 已完成 market_brief 新闻层 polish：重要新闻增加来源与融资类型限额，融资/财报按标题主动作处理，AI 应用不再推断为算力或数据中心电力，投资机构名册与政府监管统计误分类已纳入离线 regression，并让风险与今日继续观察优先跟随市场和持仓异常。v0.5-beta.5 修复已纳入本轮收口，准备随当前 commit/push 收口。

## Deployment

Status: unknown
Public URL: none
Provider: none
Notes: 暂无人工维护的公网部署信息。

## Version Index

- v0.2 — 规则版日报
- v0.3.1 — 本地定时运行
- v0.3.2 — Bark 推送接入
- v0.3.3-alpha — Obsidian 同步
- v0.3.3-beta — Bark 点击直达
- v0.3.4 — Bark 推送重试
- v0.3.5 — 自动唤醒运行
- v0.4.1 — RSS 覆盖扩展
- v0.4.1.2 — 运行防睡眠保护
- v0.5-alpha — 市场晨报骨架
- v0.5.1-alpha — 持仓配置体验
- v0.5.2-alpha — RSS 驱动市场晨报
- v0.5.3-alpha — 新闻质量调优
- v0.5-beta — A 股行情验证
- v0.5-beta.1 — 行情展示修正
- v0.5-beta.2 — 行情主线与持仓异常
- v0.5-beta.3 — 新闻事件排序与合并
- v0.5-beta.3.1 — 政策排序和主线阈值 hotfix
- v0.5-beta.4 — 普通日报阅读体验 polish
- v0.5-beta.5 — 重要新闻相关度与分类 polish

## Last verified

2026-07-10

## Next Action

继续观察后续真实 market_brief 样例，重点看来源限额、融资类型限额、AI 主题直接证据、投资机构名册 / 榜单降权、政府监管统计分类，以及市场 / 持仓异常是否优先进入风险与今日继续观察；不把 market_brief 接入 Bark / Obsidian / launchd。

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
- v0.5-beta.3 changes only explicit `market_brief` news quality rules and rendering around policy event ranking/consolidation, stricter IPO / financing classification, holdings related-news confidence, and policy risk variables. Default `python3 main.py` still follows `config.json`, and `scripts/run_daily_digest.sh` remains untouched.
- v0.5-beta.3.1 changes only explicit `market_brief` news quality rules and rendering around A-share policy ranking, generic regulation classification, reason keyword de-duplication, today-theme relevance threshold, broker earnings ranking, and policy risk wording. Default `python3 main.py` still follows `config.json`, and `scripts/run_daily_digest.sh` remains untouched.
- v0.5-beta.4 changes only ordinary `digest` Markdown item rendering. It uses existing RSS summary fields and does not add AI summary, new sources, external APIs, or automation-chain changes.
- v0.5-beta.5 changes only explicit `market_brief` news selection, classification, theme evidence, risk, and watch wording. It also covers investment directory / ranking items and government enforcement statistics with offline regressions. It adds no AI rerank, new data source, external API, or market_brief automation.
- `config/holdings.json` is ignored by Git. `config/holdings.example.json` is only an example and must not contain real cost, position size, market value, or loss amounts.
- Initialize local holdings with `python3 scripts/init_holdings_config.py`; validate with `python3 scripts/validate_holdings_config.py`.
- `market_brief` now uses RSS news plus a lightweight A-share quote snapshot when explicitly generated. It still does not calculate complex strategy, sector strength, or trading actions.
- P1 foundation docs are now split by responsibility: README as entry, PROJECT_STATE as dashboard state, BACKLOG as future work, TESTING as verification checklist, DECISIONS as long-term decisions, and MISSED_CASES as quality tracking.
- Further quality improvements may require evaluating AI-based filtering or ranking rather than continuing small rule tweaks.
- `.env` is used for local Bark / Obsidian configuration and must not be copied into project docs.

## Handoff Prompt

Continue automation-brief from v0.5-beta.5 by preserving the normal daily digest automation and observing future explicit/manual market_brief samples. Important news now uses source and financing-type caps; financing/earnings classification follows title actions; investment directory / ranking items are downgraded unless they contain concrete capital events; government enforcement statistics classify as policy regulation; compute and data-center-power themes require direct evidence; market and holding anomalies lead risk/watch wording. Keep holdings dynamic via local `config/holdings.json`, keep real holdings and cost/position/value/profit-loss fields out of Git and docs, and do not add AI summaries, new data sources, external APIs, or trading recommendations.
