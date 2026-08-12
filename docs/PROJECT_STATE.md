# Project

自动化简报

## Repo path

`/Users/wp/Projects/自动化简报`

## Current version

v0.6.2 — AI Curator Shadow Evaluation（Phase 4B live policy frozen）

## Current status

v0.6.2 Phase 3A/3B、Phase 4A 和 Phase 4B input boundary 均已完成：DeepSeek provider boundary、fixture-only `2 / 4096` gate、linked `published_at:null` snapshot contract、159-candidate payload decomposition，以及显式 `phase4_live` provider-facing projection / hard limits 均已通过离线验证。此前真实 RSS + DeepSeek shadow 的输入、projection、body limit 和 transport 均正常，但 real output 因 `duplicate_rejected_article_id` 被本地 validator fail closed；selected-only simplification 后的第二次 selected-only live shadow 再因 `duplicate_evidence_article_id` 被 validator fail closed。本轮完成仅限 phase4_live 的 evidence-ID canonicalization 与离线回归。Phase 4B limits 为 summary cap=`500`、max candidate count=`200`、max provider body=`200000`；selected event contract 仍严格验证，未修改 domain validator、schema、window semantics、production entry 或 daily digest / `market_brief` 行为。整体 shadow evaluation 尚未完成，下一次真实 shadow 仍需单独明确授权。

## Latest completed

v0.6.2 Phase 4 live selected-only simplification 已完成；第二次 selected-only live shadow 因 `duplicate_evidence_article_id` 被 validator 拒绝后，已完成仅限 phase4_live 的 evidence-ID canonicalization：同一 event 内完全相同的 evidence ID 保留首次出现并去重，unknown/empty/其他 selected-event contract 仍严格 fail closed。正式 loader replay 为 `original_candidate_count=159`；25 条 summary capped、134 条 unchanged；projected `curator_request_bytes=127574`、phase4_live exact provider body=`138433`、`transport_calls=0`。`phase4_live` 只能经显式 `--input-mode phase4_live` 选择；provider 超过 200 candidates 或 200000 body bytes 时 fail closed，不 pruning、不二次 shrinking。Provider boundary 在现有 validator 前将非权威 `rejected_article_ids` canonicalize 为 `[]`，Phase 3B `2 / 4096` fixture contract 保持独立通过，provider smoke two-candidate body=`3964`、CLI candidate fixture body=`4093`。

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
- v0.6.2 — AI Curator Shadow Evaluation（进行中；Phase 4B live policy frozen）

## Last verified

2026-08-12

## Next Action

如需继续，使用同一 live snapshot 另行明确授权一次真实 DeepSeek shadow：必须使用正式 live candidate window 和显式 `--input-mode phase4_live`，保持 shadow-only，并在 HTTP 前保留 candidate/body hard-limit fail-closed。不要切换 daily digest / `market_brief`，不要复用 Phase 3B `2 / 4096` limits。

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
- Phase 4A snapshot contract correction 允许 linked `published_at:null` candidate fixture，正式 replay 的 live snapshot 有 `159` candidates；完整 current provider body=`492741` bytes，title-only=`97583`，summary 300/500/1000-char counterfactual=`132770`/`138482`/`152332`，transport calls=`0`。GitHub Trending Python Daily 占 candidate serialized article bytes 的 `62.7564%`，VentureBeat AI 占 `16.1705%`；这些不是 source policy 或正式 limit。
- Phase 4A 未修改 `main.py` window semantics：digest cutoff 仍在逐 article processing 时动态调用 `datetime.now(timezone.utc)`；`CuratorRequest.window_start/end` 仍使用候选最早/最晚 non-null `published_at`。由于 shared collector 同时服务 legacy path，后续 window change 需单独 production-impact review。
- Phase 4B 已冻结 explicit `phase4_live` input mode、summary cap=`500`、candidate limit=`200` 和 provider body limit=`200000`；projection 只作用于 Provider-facing copy，`request.json` 保存 projected request，原始 live snapshot 保持独立完整且不被修改。最新正式 replay 为 159 candidates、25 capped、134 unchanged、projected request=`127574`、phase4_live provider body=`138433`、transport calls=`0`。
- Phase 4B candidate/body overflow 必须在 API-key lookup 和 HTTP transport 前 fail closed；不自动截断 candidate、不迭代缩短 summary、不提高 limit。Phase 3B `2 / 4096` 仍是独立 fixture-only mode。
- 真实 Phase 4 shadow 的 input/transport 正常；selected-only live output 先因 `duplicate_rejected_article_id`、随后因 `duplicate_evidence_article_id` 在 response validation fail closed。Prompt Alignment 未修改 validator；当前仅增加 phase4_live evidence exact-dedupe，rejection list 仍不 dedupe、不选 reason、不保存 rejection bookkeeping。
- Phase 4 live product decision 已改为 selected-only Curator semantics：模型只选择/聚合重要 events 与 evidence；未被 evidence 使用的 candidate 由程序推导，rejection enumeration 不再收集。显式 phase4_live provider boundary 将 rejection 字段 canonicalize 为 `[]`，并将同一 event 内完全相同的 evidence ID 保序 canonicalize 后再进入现有 validator；unknown/empty/different IDs、event/schema/content/finish_reason 等 contract 继续严格 fail closed。default/full 与 Phase 3B rejection/evidence contract 保持原样。
- 最新 phase4_live replay 为 `159 / 25 / 134 / 127574 / 138433 / 0`（candidate / capped / unchanged / curator bytes / provider bytes / transport calls）；原始 snapshot 继续独立完整，SHA-256 未变化。
- `.env` is used for local Bark / Obsidian configuration and must not be copied into project docs.

## Handoff Prompt

Continue automation-brief from v0.6.2 Phase 4 live selected-only simplification. Preserve normal daily digest automation and explicit/manual `market_brief` behavior. `phase4_live` must always be selected with explicit `--input-mode phase4_live`; its 500-char summary cap applies only to an immutable Provider-facing copy, while the original 159-candidate live snapshot remains complete and independent. Selected-only live outputs passed input/transport but failed closed at local response validation with `duplicate_rejected_article_id`, then `duplicate_evidence_article_id`; phase4_live now asks only for selected events/evidence, canonicalizes `rejected_article_ids` to `[]`, and removes only exact duplicate evidence IDs within each event before strict validation. Unknown/empty evidence and all other selected-event contract failures remain fail closed; default/Phase 3B rejection/evidence behavior is unchanged. Latest offline replay is `curator_request_bytes=127574`, `provider_request_body_bytes=138433`, `transport_calls=0`; limits remain 200 candidates / 200000 provider bytes. The next action, only with separate authorization, is a repeat real DeepSeek shadow using the same snapshot and explicit mode. Do not modify domain validator/schema, window semantics, do not reuse Phase 3B `2 / 4096`, and do not switch daily digest / `market_brief`, Bark, Obsidian, launchd, or pmset. Keep secrets and real holdings out of Git and docs. Blockers remain `暂无明确阻塞。`.
