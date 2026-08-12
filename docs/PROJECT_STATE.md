# Project

自动化简报

## Repo path

`/Users/wp/Projects/自动化简报`

## Current version

v0.6.2 — AI Curator Shadow Evaluation（Phase 3B real-provider gate completed）

## Current status

v0.6.2 Phase 3A 已完成 DeepSeek configuration、OpenAI-compatible response boundary 和 no-transport preflight；Phase 3B offline safety preparation、failed validator diagnostic repair、Prompt Contract Alignment 及 fixture-only real-provider one-shot gate 均已完成。Phase 4A 已完成 snapshot contract correction 和离线 payload decomposition：fixture loader 现在忠实接受 linked `published_at:null`，保存的 159-candidate snapshot 已通过正式 loader replay；完整 current provider body 为 `492741` bytes，transport calls=`0`。整体 `v0.6.2 — AI Curator Shadow Evaluation` 尚未完成；未修改 window semantics、production entry 或 daily digest / `market_brief` 行为。

## Latest completed

v0.6.2 Phase 4A 已完成：`published_at:null` fixture/live contract 修正、targeted regression、159-candidate snapshot formal replay 和 exact provider payload decomposition。Full current summary body 为 `492741` bytes；title-only 为 `97583`，summary 300/500/1000-char counterfactual 分别为 `132770` / `138482` / `152332`。少量超长 summary，尤其 GitHub Trending 与 VentureBeat AI，主导 payload；这些只是 Phase 4 hard-limit 的事实依据，不是已冻结的 candidate cap 或 summary cap。

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
- v0.6.2 — AI Curator Shadow Evaluation（进行中；Phase 3B real-provider gate 已完成）

## Last verified

2026-08-12

## Next Action

Phase 4 下一步：基于 Phase 4A 的 candidate-count / summary-size 测量，单独评估并冻结 live hard-limit 方案，再决定是否进行真实 DeepSeek shadow；继续保持 shadow-only，不切换 daily digest / `market_brief` 生产路径。不要直接复用 Phase 3B `2 / 4096` limits，也不要在本轮 measurement 结果上自动实施 truncation 或 pruning。

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
- v0.6.2 Phase 3A 已完成配置与 preflight boundary；Phase 3B real-provider one-shot gate 已用 exactly 2-candidate fixture 成功完成，整体 shadow evaluation 尚未完成，也未进行 production 切换。
- Phase 3B 成功样例的 Phase 4 evaluation item：检查 `why_important` 的 fact / interpretation boundary、unsupported causal inference、unsupported market implication 和 uncertainty handling；当前不修改 validator、关键词或 content scoring。
- Phase 4 仍保持 shadow-only；Bark、Obsidian、launchd、pmset、daily digest 和 `market_brief` 生产行为不变，AI failure 不得影响 production。Phase 3B 的 `2 / 4096` fixture limits 不得直接复用为 live RSS / production limits。
- Phase 3B fixture one-shot gate 仅由显式 `--real-provider deepseek` path 使用：`max_candidate_count=2`、`max_provider_request_body_bytes=4096`、`max_attempts=2`、`max_tokens=8192`、`timeout=90s`；这些不是 live RSS / production limits，也不是通用 provider 默认值。
- Phase 4A snapshot contract correction 允许 linked `published_at:null` candidate fixture，正式 replay 的 live snapshot 有 `159` candidates；完整 current provider body=`492741` bytes，title-only=`97583`，summary 300/500/1000-char counterfactual=`132770`/`138482`/`152332`，transport calls=`0`。GitHub Trending Python Daily 占 candidate serialized article bytes 的 `62.7564%`，VentureBeat AI 占 `16.1705%`；这些不是 source policy 或正式 limit。
- Phase 4A 未修改 `main.py` window semantics：digest cutoff 仍在逐 article processing 时动态调用 `datetime.now(timezone.utc)`；`CuratorRequest.window_start/end` 仍使用候选最早/最晚 non-null `published_at`。由于 shared collector 同时服务 legacy path，后续 window change 需单独 production-impact review。
- `.env` is used for local Bark / Obsidian configuration and must not be copied into project docs.

## Handoff Prompt

Continue automation-brief from v0.6.2 Phase 4A snapshot contract correction and payload decomposition. The product is a personal overnight global news brief (Overnight Brief); preserve normal daily digest automation and explicit/manual `market_brief` behavior. The linked `published_at:null` fixture/live boundary is now covered and the saved live snapshot replays as exactly 159 candidates. Exact current DeepSeek body measurement is 492741 bytes; title-only and 300/500/1000-character summary scenarios are measurement-only, not production caps. The next bounded step is to review candidate-count versus summary-size hard-limit options, then separately decide whether to run a real DeepSeek shadow. Do not modify window semantics without a legacy production-impact review, do not reuse Phase 3B `2 / 4096` limits, and do not switch daily digest / `market_brief`, Bark, Obsidian, launchd, or pmset. Keep secrets and real holdings out of Git and docs. Blockers remain `暂无明确阻塞。`.
