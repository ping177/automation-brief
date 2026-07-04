# Project

自动化简报

## Repo path

`/Users/wp/Projects/自动化简报`

## Current version

v0.5-beta.3.1 policy ranking and theme threshold hotfix, based on `docs/DEVLOG.md`.

## Current status

项目已打通本地定时生成、Obsidian 同步和 Bark 推送链路，并开始升级为面向 A 股观察的市场投研晨报。当前阶段已接入轻量 A 股行情观察，并继续优化显式 market_brief 的行情、新闻事件和持仓观察表达；仍保持规则驱动，不调用 AI API。

## Latest completed

v0.5-beta.3.1 已完成 market_brief 真实样例 hotfix：证监会再融资 / 定增储架发行制度变量排序继续提高，泛“监管”分类收紧，观察理由关键词去重，今日主线 `relevance < 70` 候选不再渲染，券商业绩预告排序提高，风险与反证明确覆盖再融资和定增储架发行变量。v0.5-beta.3.1 修复已纳入本轮收口。

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

## Last verified

2026-07-04

## Next Action

继续观察 1-2 个真实交易日的手动显式 market_brief 样例，重点看再融资 / 定增储架发行政策是否稳定排在普通 IPO / 融资前，泛“监管”是否不再误归政策监管，低相关产业新闻是否不再硬凑今日主线，券商业绩预告和政策风险变量是否仍符合预期。普通 daily brief 自动链路继续保持不变，不把 market_brief 接入 Bark / Obsidian / launchd。

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
- `config/holdings.json` is ignored by Git. `config/holdings.example.json` is only an example and must not contain real cost, position size, market value, or loss amounts.
- Initialize local holdings with `python3 scripts/init_holdings_config.py`; validate with `python3 scripts/validate_holdings_config.py`.
- `market_brief` now uses RSS news plus a lightweight A-share quote snapshot when explicitly generated. It still does not calculate complex strategy, sector strength, or trading actions.
- P1 foundation docs are now split by responsibility: README as entry, PROJECT_STATE as dashboard state, BACKLOG as future work, TESTING as verification checklist, DECISIONS as long-term decisions, and MISSED_CASES as quality tracking.
- Further quality improvements may require evaluating AI-based filtering or ranking rather than continuing small rule tweaks.
- `.env` is used for local Bark / Obsidian configuration and must not be copied into project docs.

## Handoff Prompt

Continue automation-brief from v0.5-beta.3.1 by preserving the normal daily digest automation and reviewing 1-2 more manually generated explicit `market_brief` samples. The market brief now separates news-confirmed themes from market-led observations, can flag 科创50 index-level strength, classifies holdings relative moves with anomaly wording, consolidates same-topic CSRC refinancing / private-placement policy events, ranks A-share refinancing / private-placement system variables ahead of ordinary IPO noise, avoids generic “监管” false positives, hides today-theme candidates below relevance 70, and keeps weak holdings news as observation variables rather than direct company explanations. Keep holdings dynamic via local `config/holdings.json`, keep real holdings and cost/position/value/profit-loss fields out of Git and docs, and do not add trading recommendations.
