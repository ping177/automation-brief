# Project

自动化简报

## Repo path

`/Users/wp/Projects/自动化简报`

## Current version

v0.6.2 — AI Curator Shadow Evaluation（Phase 3B offline safety preparation）

## Current status

v0.6.2 Phase 3A 已完成 DeepSeek configuration、OpenAI-compatible response boundary 和 no-transport preflight；Phase 3B offline safety preparation 已完成 fixture one-shot hard-limit gate、离线回归、failed validator diagnostic repair 和 Prompt Contract Alignment。第二次 real-provider one-shot 已到达本地 validation，但因真实输出缺少 `events[].canonical_title` 失败；本轮只补强 system prompt 的 exact CuratorResponse contract，整体 `v0.6.2 — AI Curator Shadow Evaluation` 尚未完成。产品定位为个人隔夜全球要闻晨报（Overnight Brief）；feed language metadata / normalization 已落地，`CandidateArticle.language` 已接通 source-language metadata，`CuratorRequest.target_language` 固定为 `zh-CN`。本轮未再次调用真实 AI/RSS、未读取 holdings，article identity 与 legacy production behavior 保持不变，daily digest / `market_brief` 生产输出未切换。

## Latest completed

v0.6.2 Phase 3B offline safety preparation：显式 `--real-provider deepseek` 必须使用 `--candidate-fixture`，且 dry-run 与 actual path 共享 `max_candidate_count=2`、`max_provider_request_body_bytes=4096` gate；超限在 API key/HTTP transport 前 fail closed，不截断 candidates/payload，也不退回 feeds/RSS。prompt-aligned baseline fixture measurement 为 `candidate_count=2`、`curator_request_bytes=1178`、`provider_request_body_bytes=3944`，仍在 4096 gate 内，dry-run transport calls 保持 `0`。此外，validator/content-policy failure 保留 bounded rule/path diagnostic，仍不保存 raw provider response 或完整模型 payload。未执行第三次真实 provider，未切换生产输出。

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
- v0.6.0-alpha — AI Curator shadow foundation
- v0.6.1 — Product Reset + Language Boundary
- v0.6.2 — AI Curator Shadow Evaluation（进行中；Phase 3B offline safety preparation 已完成）

## Last verified

2026-08-12

## Next Action

等待用户明确执行下一次 Phase 3B fixture one-shot real-provider command；当前不调用真实 API/RSS/holdings，不进入下一次 one-shot execution，不替换当前生产晨报。

## Blockers

暂无明确阻塞。

## Important Context

- Git branch、latest commit、working tree 由 project-command-center 实时 Git 扫描读取；PROJECT_STATE.md 不作为这些字段的权威来源。
- README states the current v0.6.1 release does not call DeepSeek、Tavily 或任何真实 AI provider / paid search API。
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
- v0.6.0-alpha adds AI Curator shadow plumbing only: keyword-pre-gate candidates, data contract, fixture provider, validator, trace, fully offline candidate fixtures, and preview. It does not pass holdings, legacy scores, matched keywords, or market data into the Global Event Curator request.
- Runtime data root is `~/Projects/_project-data/automation-brief/` with `reports/`, `runs/daily-news.log`, `runs/ai-curator-shadow/`, `manual-inputs/holdings.json`, and metadata-only `migration-records/`. Migration `migration-20260808T095613Z` copied 68 reports plus the log and holdings; legacy sources remain unchanged.
- `config/holdings.json` is ignored by Git and retained only as legacy source data. Runtime lookup uses canonical `manual-inputs/holdings.json`, then `config/holdings.example.json`, then an empty config. The example must not contain real cost, position size, market value, or loss amounts.
- Initialize local holdings with `python3 scripts/init_holdings_config.py`; validate with `python3 scripts/validate_holdings_config.py`.
- `market_brief` now uses RSS news plus a lightweight A-share quote snapshot when explicitly generated. It still does not calculate complex strategy, sector strength, or trading actions.
- P1 foundation docs are now split by responsibility: README as entry, PROJECT_STATE as dashboard state, BACKLOG as future work, TESTING as verification checklist, DECISIONS as long-term decisions, and MISSED_CASES as quality tracking.
- Further quality improvements should use the AI Curator shadow path instead of continuing small rule tweaks in `_score_article` or digest classification.
- v0.6.1 产品与语言合同已完成：输入可为 `zh-CN` / `en` / `und`，最终 Curator 输出为 `zh-CN`；语言不进入 article identity，也不进入 legacy path。
- v0.6.1 已为 `feeds.json` / `feeds.example.json` 增加可选 language metadata；旧配置缺失、空或非法 language 时归一化为 `und`，所有 16 个 active feed 的 name / url / mode / role / 顺序保持不变。
- v0.6.2 Phase 3A 已完成配置与 preflight boundary；Phase 3B 已完成 offline fixture gate preparation、失败诊断修复与 Prompt Contract Alignment；整体 shadow evaluation 尚未完成，第二次真实 provider 运行失败后未进行下一次质量评估或生产切换。
- Phase 3B fixture one-shot gate 仅由显式 `--real-provider deepseek` path 使用：`max_candidate_count=2`、`max_provider_request_body_bytes=4096`、`max_attempts=2`、`max_tokens=8192`、`timeout=90s`；这些不是 live RSS / production limits，也不是通用 provider 默认值。
- `.env` is used for local Bark / Obsidian configuration and must not be copied into project docs.

## Handoff Prompt

Continue automation-brief from v0.6.2 Phase 3B offline safety preparation. The product is a personal overnight global news brief (Overnight Brief); preserve the normal daily digest automation and explicit/manual `market_brief` behavior. Phase 3A configuration, Phase 3B fixture gate/preflight measurements, safe failed-validator diagnostics, and exact CuratorResponse prompt alignment are complete, but the overall v0.6.2 shadow evaluation is not complete. The next explicit user action may run the next one-shot DeepSeek command against the existing two-candidate fixture; do not call real API/RSS/holdings or replace the current production brief during preparation. Runtime artifacts default to `~/Projects/_project-data/automation-brief/`; explicit CLI/function overrides and `AUTOMATION_BRIEF_DATA_ROOT` remain supported. Keep real holdings and cost/position/value/profit-loss fields out of Git and docs. Do not connect provider output to production automation or make trading recommendations.
