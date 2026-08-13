# Project

自动化简报

## Repo path

`/Users/wp/Projects/自动化简报`

## Current version

v0.6.2 — AI Curator Shadow Evaluation（closed）

## Current status

v0.6.2 已完成并关闭。Phase 4 证明了 real DeepSeek shadow、159/140-candidate 大池请求、validation / artifacts / failure isolation 与 production isolation；最终架构为 simple single-pass selected-only Curator。GitHub-only boundary 已在真实 Flash run 验证。内容质量实验显示 major-event recall / ranking 仍不稳定：Flash 在此 snapshot 约覆盖 4/8 known major events；Pro 只有边际提升且成本更高。因此 AI Curator 继续 shadow-only，不以继续堆叠 prompt、规则或多阶段架构解决该限制。v0.7 未开始。

## Latest completed

v0.6.2 closeout：保留 simple single-pass、Phase 4 scoped `max_events=10`、summary / candidate / body safety limits、selected-only canonicalization、编辑质量 policy、GitHub-only exact exclusion，以及窄 gold/evaluator 开发回归。最终 cleaned Flash real shadow 成功处理 159 条原始候选中的 140 条 provider-facing candidates；所有 production daily digest / `market_brief` 路径保持隔离。一次性 Pro comparison profile 已移除，runtime 固定 Flash。

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
- v0.6.2 — AI Curator Shadow Evaluation（completed / shadow-only）

## Last verified

2026-08-13

## Next Action

进入 `v0.7 — Unified Overnight Brief` 的产品设计与实现规划；不得在本次 closeout 中开始实现，也不得将 AI Curator 切换为 production default。

## Blockers

暂无明确阻塞。

## Important Context

- Git branch、latest commit、working tree 由 project-command-center 实时 Git 扫描读取；PROJECT_STATE.md 不作为这些字段的权威来源。
- README states production daily digest / `market_brief` do not call DeepSeek、Tavily 或任何真实 AI provider / paid search API；Phase 4 real shadow remains explicit and shadow-only。
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
- Phase 4A snapshot contract correction 允许 linked `published_at:null` candidate fixture，正式 replay 的 live snapshot 有 `159` candidates；完整 current provider body=`492741` bytes，title-only=`97583`，summary 300/500/1000-char counterfactual=`132770`/`138482`/`152332`，transport calls=`0`。后续 candidate-pool audit 仅将 GitHub Trending Python Daily 定义为 Phase 4 daily-main-pool 的 exact source exclusion；Investing.com 中文财经 保留为普通新闻 source。这不是 collector、feed 或通用 source ranking policy。
- Phase 4A 未修改 `main.py` window semantics：digest cutoff 仍在逐 article processing 时动态调用 `datetime.now(timezone.utc)`；`CuratorRequest.window_start/end` 仍使用候选最早/最晚 non-null `published_at`。由于 shared collector 同时服务 legacy path，后续 window change 需单独 production-impact review。
- Phase 4B 已冻结 explicit `phase4_live` input mode、summary cap=`500`、candidate limit=`200` 和 provider body limit=`200000`；第二轮 tuning 仅把该 mode 的 runner default capacity 改为 10。projection 只作用于 Provider-facing copy，`request.json` 保存 projected request，原始 live snapshot 保持独立完整且不被修改。
- Phase 4B candidate/body overflow 必须在 API-key lookup 和 HTTP transport 前 fail closed；不自动截断 candidate、不迭代缩短 summary、不提高 limit。Phase 3B `2 / 4096` 仍是独立 fixture-only mode。
- 真实 Phase 4 shadow 的 input/transport 正常；selected-only live output 先因 `duplicate_rejected_article_id`、随后因 `duplicate_evidence_article_id` 在 response validation fail closed。Prompt Alignment 未修改 validator；当前仅增加 phase4_live evidence exact-dedupe，rejection list 仍不 dedupe、不选 reason、不保存 rejection bookkeeping。
- Phase 4 live product decision 已改为 selected-only Curator semantics：模型只选择/聚合重要 events 与 evidence；未被 evidence 使用的 candidate 由程序推导，rejection enumeration 不再收集。显式 phase4_live provider boundary 将 rejection 字段 canonicalize 为 `[]`，并将同一 event 内完全相同的 evidence ID 保序 canonicalize 后再进入现有 validator；unknown/empty/different IDs、event/schema/content/finish_reason 等 contract 继续严格 fail closed。default/full 与 Phase 3B rejection/evidence contract 保持原样。
- cleaned-pool single-pass phase4_live dry-run 为 `159 / 140 / 19 / 6 / 134 / 108264 / 119868 / 0`（original / provider-facing / source-excluded / capped / unchanged / curator bytes / provider bytes / transport calls），request `max_events=10`；原始 snapshot 继续独立完整，SHA-256 未变化。
- two-pass real validation 的唯一明确收益是第二段未把一篇无关 Pass A evidence 写进最终 response；但 must-include 覆盖降至 3/8，且仍有错误 grouping / evidence contamination / 分类问题，因此该路径已移除。`phase4_live` 重新使用一个 200000-byte preflight 和一段最多两次 transient retry 的 provider call；成功 run 只写 `request.json`、`response.json`、`trace.json`、`review.md` 和 `run.json`。
- DeepSeek runtime 配置固定为 `deepseek-v4-flash`；一次性 Pro same-snapshot artifact 仅作为 v0.6.2 实验记录保留，不需要 runtime profile 才能读取。
- `.env` is used for local Bark / Obsidian configuration and must not be copied into project docs.

## Handoff Prompt

v0.6.2 is closed. Begin no implementation work until `v0.7 — Unified Overnight Brief` receives its own product/design task. Preserve the v0.6.2 shadow-only boundary: single-pass Flash, scoped `max_events=10`, GitHub Trending Python Daily exact exclusion only, and no production integration. Known Phase 4 recall/ranking limitations are documented experimental evidence, not a reason to resume prompt, source-filter, model, validator, or orchestration tuning. Blockers remain `暂无明确阻塞。`.
