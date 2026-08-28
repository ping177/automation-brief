# Project

自动化简报

## Repo path

`/Users/wp/Projects/自动化简报`

## Current version

v1.8 — Shadow / Parallel Validation（IN PROGRESS；v1.x implementation roadmap FROZEN）

## Current status

v1.8 已进入真实 manual validation。正式 Gen2 runtime 不依赖 Generation 1；首次真实 run 的 1521 条 timestamp-null pollution 已以 source-snapshot freshness qualification 收敛。3 个已确认 clustering overmerge 已以 `identity-guarded-connected-components-v2` / `semantic-title-anchor-v1` 完成正式 corrective replacement：保留 pinned model/revision、projection、`0.91` base floor 与 connected components，只对 `0.91–0.925` ambiguity band 增加 normalized-title 4-character identity support。原 v1.3 与新 corrective fixture 的 production memberships 均为 `8/8 exact`。Gen2 manual runner 现在支持与 `--date` 互斥的 rolling-24h `--as-of-now`，不改变未来 production 的固定 08:00 report slot。Gen1 production routing、schedule 与 delivery 保持不变；Gen2 不写 `reports/`、不接 Bark/Obsidian/publisher。

v1.6 已正式 `COMPLETED / CLOSED`：implementation acceptance: PASS；offline full-pipeline E2E: PASS。新增 side-by-side deterministic `brief_renderer.py`、Generation 2 专用 `v1_artifacts.py`、纯 composition `orchestrator.py` 与 direct-script smoke。Orchestrator 接受 explicit report slot/run identity，依 frozen stage order执行 report-window admission、checkpoint-before-downstream、classifier overlay、Writer continuation、Brief status推导与artifact finalization；`events-writer-input` 正式持久化，artifact persistence fail closed。实现不接入 `main.py` production routing，不调用真实 DeepSeek，不实现 delivery、semantic fallback 或 raw Article backfill。

v1.5 Slice 1 Event Classifier、Slice 2 Event Writer 与 Slice 3 Continuation Regression 已完成：side-by-side canonical classifier/writer、strict response validation、完整 Article provenance projection、最小 zh-CN writing gate、per-event failure isolation、classifier → writer continuation 与 `written-unclassified` lifecycle regression 均已落地；不改变 Generation 1 production routing。最终真实 DeepSeek validation 使用同一 6-Event representative synthetic fixture：classifier/writer stage 均 `succeeded`、event count `6`、classifier technical failures `0`、writer technical failures `0`。分类均合理且无 `other` 滥用；Event-level synthesis、Chinese readability 和 evidence grounding 均 PASS，首轮 `why_it_matters_zh` 读者建议问题已通过最小 prompt correction 解决，revalidation 未发现 release blocker。v1.5 标记为 `COMPLETED / CLOSED`。

v1.4 real-provider quality validation 为 3/3 runs succeeded；4/4 must-include 在三次运行中全部入选，3/3 should-omit 在三次运行中全部排除，judgment-call 具备合理波动。Selector、v1.5 Classifier 与 Writer 尚未接入 production；v1.5 已完成并关闭。

v0.7.3 七天真实使用验证已完成并 CLOSED。产品 review 的结论不是 Generation 1 完全达到长期产品目标；真实使用暴露出重复 / 事件聚合不足、legacy fallback 中文边界、旧规则误分类、reader-facing UX、市场数据价值不足、持仓能力价值未证明等问题。该 evidence 支持停止继续 patch Generation 1 核心新闻架构，转入已经冻结的 v1.0 Event-driven architecture rebuild。

当前 production 仍运行 Generation 1 pipeline；v1.2 至 v1.8 当前均仅以 side-by-side 组件、regression 或 manual-only runtime 落地，real-model/quality/offline runner 只用于显式 acceptance，在 v1.8 shadow / parallel validation 和 v1.9 production cutover 前，不删除或退役现有 production / legacy surface。无参数 `digest` 继续保留为 rollback。

READ-ONLY Dependency Audit 已完成，迁移路线确定为 preserve mature infrastructure + rewrite news core。Architecture、Core Data 与 Runtime / Failure Contract Freeze 均已完成，v1.0 governance baseline 与 v1.1–v1.7 implementation milestones 已 COMPLETED / CLOSED，v1.3 在修正后的 24h reader-level story-bundle semantics 下完成 real-model acceptance：`intfloat/multilingual-e5-small`（immutable revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`）、`article-title-summary-v1`、threshold `0.91`，production-critical overmerge / split 为 `0 / 0`，precision / recall / F0.5 为 `1.0 / 1.0 / 1.0`，expected memberships `8 / 8` exact。v1.8 第一小步保持 manual-only side-by-side，未接入 production routing；Generation 1 继续作为正式 baseline，直到 v1.9 production cutover。

## Latest completed

2026-08-28 完成 v1.8 第一步 runtime、input population 修复与 clustering corrective replacement，并新增 manual rolling-24h validation mode。source freshness qualification 使 5 个 legacy 新华网 snapshots 与 GitHub Trending Python Daily 的 1521 条 null pollution 无法进入 Article/window/clustering pool。clustering 保留 model/revision/projection/base floor/connected components，以 `semantic-title-anchor-v1` 拒绝 3 个真实 ambiguity-band hard negatives，同时保留国防部记者会与 CrowdStrike positives；原 v1.3 和新 corrective real-model acceptance 均 `8/8 exact`且 deterministic。rolling slot 以当前 Asia/Shanghai aware 时间结束并向前 24 小时，`--date` 与 `--as-of-now` 互斥；不修改 frozen contracts、Gen1 或 delivery。v1.8 尚未 close，下一步是至少一次有效真实 rolling-24h Gen2 run 与用户 reader-facing 人工验收，明显问题再针对性补测。

2026-08-28 完成并关闭 v1.7 Offline / Snapshot Validation：代表性 clean morning fixture 通过完整 Generation 2 pipeline，并以 empty、partial、hard-stop、malformed/provider protocol fixtures 覆盖 failure semantics、continuation、checkpoint-before-downstream、Brief/Markdown 与 provenance/artifacts。最终 reader-facing layout 已确认 PASS：无“今日要闻”，category 使用 H2 italic，Event title 使用 H3 + `var(--text-accent)` + bold，摘要使用 `摘要：`、保留 `为什么重要：`，来源使用 `<details>/<summary>/<ul>/<li>/<a>` 纯 HTML children；category regroup/order、global `Brief.event_ids`、dedup/provenance 与 written-unclassified fallback 保持不变。focused smoke、全部 28 个 offline scripts、compile/compileall、shell syntax、Project-State Push Gate 16/16、fixture parsing 与 `git diff --check` 均 PASS。未调用真实 RSS/DeepSeek/provider，未修改 Generation 1 production routing；下一步为 v1.8 Shadow / Parallel Validation。

2026-08-27 完成并关闭 v1.6：Slice 1–3 与 reader-facing acceptance polish 均已完成。`orchestrator.py` 以 explicit report slot、runtime-only `GenerationRunResult`、frozen stage APIs和Artifact Manager组成独立 Generation 2 runtime；新增 normalizer-owned inclusive report-window admission；Gen1 fetch retry仅保留 exception cause，Gen2 collector沿cause chain恢复 `timeout` / `transport_failed` typing。离线回归覆盖full order、checkpoint-before-downstream、classifier partial/all-failed overlay、`events-writer-input`、written-unclassified、writer partial/all-failed、selector/collector/renderer hard-stop、legal empty、partial empty、diagnostic durability与artifact fail-closed；代表性 3/1/4-source reader-layout fixture 已经完整 offline pipeline 生成并通过人工验收。implementation acceptance、offline full-pipeline E2E 与 human reader-facing layout acceptance 均 PASS；未联网、未调用真实 DeepSeek、未修改 frozen contracts、delivery或production routing。原计划 Slice 4 已由 Slice 3 orchestrator smoke 实质覆盖，不单独实现。

2026-08-27 完成 v1.6 Slice 2 Artifact/Checkpoint Manager：新增 side-by-side `v1_artifacts.py` 与 `tests/offline_v1_artifacts_smoke.py`，覆盖 caller-supplied run identity、staging manifest、canonical Article/Event/Brief/StageResult round-trip、non-empty object persistence、checkpoint-before-downstream capability、business-stage failure evidence、atomic write/finalization failure、immutable final/duplicate run id、safe diagnostics 与 diagnostic ref stripping、brief/Markdown 分离及不写 `reports/`；artifact、renderer、canonical/ingest/cluster/selector/classifier/writer/continuation/legacy artifact/path/production-routing regressions、Python compile 与 `git diff --check` 通过。未调用真实 DeepSeek，未修改 frozen contracts、Generation 1 production routing 或 delivery；下一步为 v1.6 Orchestrator Integration。

2026-08-27 正式完成并关闭 v1.5 Event Classifier + Writer：同一 6-Event representative synthetic fixture 的最终真实 DeepSeek validation 中，provider 为 `deepseek`、model 为 `deepseek-v4-flash`，classifier/writer stage 均 `succeeded`，event count `6`、classifier technical failures `0`、writer technical failures `0`。分类均合理且无 `other` 滥用；Event-level synthesis、Chinese readability 和 evidence grounding 均 PASS，首轮 `why_it_matters_zh` 读者建议问题已通过最小 prompt correction 解决，revalidation 未发现 release blocker。v1.5 仍保持 side-by-side，未修改 production routing；下一步为 v1.6 Renderer + Artifacts + Orchestrator Integration。

2026-08-27 完成 v1.5 Writer significance guidance 最小修正：根据首次真实 DeepSeek validation 的 6/6 成功输出，仅收紧 `why_it_matters_zh` prompt，要求只陈述 supplied Article evidence 直接支持的具体意义，并禁止直接称呼读者、个人投资/购买/行为建议、evidence 之外的推测和“关注/继续观察”类通用 meta-language。offline regression 只锁定 prompt intent，未增加确定性文本规则、score、language detector、第二 LLM 或 judge；未改 schema、Classifier 或 production routing。Writer smoke、全部 offline smoke、Project-State Push Gate 16/16、Python compile 与 `git diff --check` 全部通过。下一步使用同一 v1.5 runner 做 real-provider revalidation。

2026-08-27 准备 v1.5 Classifier + Writer real DeepSeek quality validation harness：新增 `scripts/evaluate_event_classifier_writer_quality.py`、`tests/fixtures/event_classifier_writer_quality_v1_5.json` 与 `tests/offline_event_classifier_writer_quality_smoke.py`。runner 默认使用 no-network fake gateway，只有显式 `--real-provider deepseek` 才复用 neutral OpenAI-compatible gateway；fixture 含 6 个完整 Article bundle 与人工 classification review note，报告只输出安全的 Event writing / stage failure 结果。离线 smoke、现有相关 smoke、compile 与 `git diff --check` 通过；本轮未读取 key、未调用真实 provider、未修改 production routing、frozen contracts 或 dependencies。下一步为用户在 Terminal 执行 real DeepSeek quality validation。

2026-08-27 完成 v1.5 Slice 3 Classifier → Writer Continuation Regression：新增独立 `tests/offline_event_classifier_writer_continuation_smoke.py`；以 test-local composition 覆盖 classifier partial、classifier all-failed 仍继续 Writer、`written-unclassified`、Writer event-local failure 与 StageResult independence。全部 relevant offline smoke、compile/compileall、Project-State gate 与 `git diff --check` 通过；未新增 production helper、未调用真实 DeepSeek、未修改 frozen contracts、既有业务路由或 dependencies。下一步为 v1.5 real DeepSeek Classifier + Writer quality validation。

2026-08-27 完成 v1.5 Slice 2 Event Writer：新增 `event_writer.py` 与 `tests/offline_event_writer_smoke.py`；覆盖 classified/unclassified/mixed Event lifecycle、完整 Article provenance 与 canonical member ordering、strict writing response、duplicate/unknown/malformed response、最小 zh-CN gate、gateway/parse/transport/Article lookup per-event isolation 和 succeeded/partial/failed 状态。全部 relevant offline smoke、compile/compileall、Project-State gate 与 `git diff --check` 通过；未调用真实 DeepSeek，未修改 frozen contracts、既有业务路由或 dependencies。下一步为 Slice 3 classifier → writer continuation regression。

2026-08-27 完成 v1.5 Slice 1 Event Classifier：新增 `event_classifier.py` 与 `tests/offline_event_classifier_smoke.py`；覆盖 9 个 category、严格 response shape、完整 membership projection、duplicate/unknown/malformed response、gateway/parse/transport per-event isolation 和 succeeded/partial/failed 状态。未调用真实 DeepSeek，未修改 frozen contracts、既有业务路由或 dependencies。

2026-08-27 完成并关闭 v1.4 Event Selector：real-provider quality validation 为 3/3 runs succeeded，4/4 must-include 三次全部入选，3/3 should-omit 三次全部排除，judgment-call 具备合理波动；Selector prompt/core/runner/tests 保持最小，未发现无 consumer 的 diagnostic residue。项目级 credential file 已从 `.env` 安全改名为 `.env.local`，3 个 active consumers、README 和当前 runtime contract 已更新，两个文件均被 Git ignore。

2026-08-27 完成 v1.3 Event Clustering closeout：在修正后的 24h Morning Brief story-bundle semantics 下，以固定 E5-small model/revision、`article-title-summary-v1` projection 和 threshold `0.91` 完成 real-model acceptance。4 个 production-relevant cases 的 overmerge / split 为 `0 / 0`，production precision / recall / F0.5 为 `1.0 / 1.0 / 1.0`，expected reader memberships `8 / 8` exact；offline v1.1/v1.2/v1.3、相关 Generation 1 regression、Project-State gate、Python compile 与 `pip check` 均通过。Treasury zh/en split 保留为 synthetic robustness limitation；temporal Iran early/later merge 保留为 outside-normal-window observation，不否决 closeout。直接依赖为 `sentence-transformers==3.4.1`、`transformers==4.48.1`、`torch==2.5.1`；evaluator 默认使用 `AUTOMATION_BRIEF_MODEL_CACHE` 或 canonical data root `runs/model-cache`，不改变 Generation 1 runtime。

2026-08-27 完成 v1.3 Event semantics canonical correction（docs-only）：Event / EventCandidate 明确为同一约 24h Morning Brief report window 内的 reader-level story bundle，而非 persistent atomic real-world occurrence identity；允许 announcement / immediate reaction / clarification / closely related follow-up 在读者视角下合并，同时保留对明显不同新闻的 false-merge guard。明确 v1.5 Event Writer 将读取完整 Article provenance 并综合不同事实/角度；v1.3 继续仅用 local embedding + semantic similarity + simple deterministic clustering，不使用 LLM。未修改 canonical fields、identity、StageResult、runtime failure semantics、clustering code 或 fixture 事实标签。

2026-08-26 开始 `v1.3 — Event Clustering` implementation：新增 side-by-side `event_cluster.py`、fake-embedder offline smoke、labeled fixture 与独立 real-model evaluator；完成 projection、确定性 connected-components、canonical EventCandidate 构造、failure semantics 和 bounded diagnostics。早期 Python 3.9.6 / macOS arm64 依赖解析曾遇到 `scikit-learn` wheel 限制；该历史问题随后通过已验证的直接依赖版本和项目 `.venv` 解决，真实模型 revision、threshold calibration 与 v1.3 closeout 已在本次完成。

2026-08-26 完成 `v1.2 — Deterministic Ingest`：新增 side-by-side `collector.py`、`normalizer.py`、`article_dedup.py`、离线 smoke 与非权威 implementation note，完成 source-scoped batch / StageResult isolation、canonical Article normalization、fail-closed timestamp、UTC collected time、language normalization 和 exact first-valid dedup。未修改 `main.py`、feeds 配置、Gen1 contract、生产路由、外部 API、依赖或 legacy 文件；下一步为 v1.3 Event Clustering。

2026-08-26 完成 `v1.1 — Canonical Domain & Runtime Foundation`：新增独立 `canonical_domain.py` 与离线 `tests/offline_canonical_domain_smoke.py`，实现冻结字段、stable identity、UTC/window validation、immutable Event lifecycle、`StageResult`/`ItemFailure` 和 deterministic serialization round-trip。未修改 Gen1 contract、生产路由、外部 API、依赖或 legacy 文件。

v0.7.2 production cutover closeout：真实运行 artifact 为 `overnight-20260815T143736.428601Z-f8958055f793`，canonical report 为 `morning-brief-2026-08-15.md`，Obsidian 与 Bark 均已确认成功。2026-08-16 的 broken-feed production hygiene 仅从 `feeds.json` 删除失效 36 氪 feed。

2026-08-26 完成 v0.7.3 closeout 和 `v1.0 — Event-driven Morning Brief` Architecture Freeze（docs-only）：v0.7.3 的真实使用 evidence 支持停止 Generation 1 核心新闻架构 patching；v1.0 冻结 Article → Event → Brief 主链、模块职责、deterministic / model 边界、provenance、局部失败原则、Holdings / Market 边界和 legacy retirement gate。未创建业务模块、未修改 production routing。原 `v0.7.4` 独立退役路线保留为历史记录并标记为 superseded / replaced by v1.0 plan。

2026-08-26 完成 v1.0 READ-ONLY Dependency Audit 与 Core Data Contract Freeze（docs-only）：确认保留成熟 collection/identity/path/provider transport/artifact/delivery 基础设施并重写 news core；冻结 Article、EventCandidate、single immutable-lifecycle Event、Evidence projection、Brief 和 component-local StageResult。未实现 pipeline、未删除 legacy、未改变 Generation 1 production。

2026-08-26 完成 v1.0 Runtime / Failure Contract Freeze（docs-only）：冻结 run identity、StageResult invariant、合法 empty / partial / failed、逐组件 failure isolation、selector global salvage boundary、classifier / writer item-local validation、bounded retry/batch、artifact、renderer、delivery/idempotency 与 post-cutover no automatic legacy semantic fallback。未实现上述行为，未改变 Generation 1 production。

2026-08-26 完成 `v1.x Implementation Version Roadmap` governance freeze（docs-only）：冻结 v1.0 governance baseline 以及 v1.1–v1.10 numeric implementation milestones。v1.1 已按冻结范围完成；不选择 embedding model、不改变三份 v1.0 canonical contracts、不改变 Generation 1 production 或 legacy retirement timing。

## Deployment

Status: local macOS production accepted
Public URL: none
Provider: DeepSeek `deepseek-v4-flash`; real production success accepted
Notes: 2026-08-15 用户已完成实际 `.env` 配置与 `0600` 权限、LaunchAgent reload 和受控 kickstart；Morning Brief、Obsidian 同步及 Bark 推送均成功。当前仓库运行时默认路径已迁移到 `.env.local`，本次只更新仓库 consumer，未修改用户实际 LaunchAgent / pmset 配置。2026-08-16 的 36 氪删除是仓库级 production hygiene，未做真实 RSS/DeepSeek acceptance。v0.7.3 七天真实使用验证现已 CLOSED；production 仍运行 Generation 1，v1.8 shadow 前后继续作为正式 baseline，直到 v1.9 production cutover；v1.10 才进行 legacy retirement。v1.1 仅新增 side-by-side domain foundation 与离线验证，未改变实际部署或自动化链路；actual LaunchAgent / pmset / runtime 现场状态仍不是本任务 blocker。

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
- v0.7 — Morning Brief
- v0.7.1 — Morning Brief MVP（CLOSED）
- v0.7.2 — Production Cutover（CLOSED）
- v0.7.3 — Morning Brief Long-term Usage Validation（CLOSED）
- v0.7.4 — Legacy Product Retirement & Capability Consolidation（SUPERSEDED / replaced by v1.0 plan）
- v1.0 — Event-driven Morning Brief（governance baseline COMPLETED / CLOSED；v1.x implementation roadmap FROZEN）
- v1.1 — Canonical Domain & Runtime Foundation（COMPLETED / CLOSED）
- v1.2 — Deterministic Ingest（COMPLETED / CLOSED）
- v1.3 — Event Clustering（COMPLETED / CLOSED）
- v1.4 — Event Selector（COMPLETED / CLOSED；implementation + real-provider quality validation complete）
- v1.5 — Event Classifier + Writer（COMPLETED / CLOSED）
- v1.6 — Renderer + Artifacts + Orchestrator Integration（COMPLETED / CLOSED）
- v1.7 — Offline / Snapshot Validation（COMPLETED / CLOSED）
- v1.8 — Shadow / Parallel Validation（IN PROGRESS）
- v1.9 — Production Cutover（PLANNED）
- v1.10 — Legacy Retirement & v1.x Closeout（PLANNED）

## Last verified

2026-08-28

## Next Action

继续 v1.8 real Shadow / Parallel Validation：由用户在本人 Terminal 执行至少一次有效 rolling-24h manual Gen2 run，并完成 reader-facing 人工验收；若发现明显问题再针对性补测。不接 delivery，不启动 v1.9 或 comparison/review layer。

## Blockers

暂无明确阻塞。

## Important Context

- Git branch、latest commit、working tree 由 project-command-center 实时 Git 扫描读取；PROJECT_STATE.md 不作为这些字段的权威来源。
- README states production daily digest / `market_brief` do not call DeepSeek、Tavily 或任何真实 AI provider / paid search API；Phase 4 provider remains explicit/manual, and only the explicit v0.7 Morning Brief (`overnight_brief`) path may consume its validated events。
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
- v0.7.1 adds explicit Morning Brief (`overnight_brief`) output at `reports/morning-brief-YYYY-MM-DD.md`; it reuses existing digest/market capabilities, labels structured quotes as prior-trading-day A-share data, and does not connect Obsidian, Bark, launchd or pmset. The explicit manual path may call the existing phase4_live single-pass AI Curator; Provider technical failure falls back to the whole legacy news layer.
- v0.7.2 production acceptance confirms one explicit report type now runs through the existing stable shell / Obsidian / Bark chain. No-argument shell execution remains `digest`; the checked-in and accepted LaunchAgent path selects `overnight_brief`; unknown report types fail closed. Curator credentials use process-env-first, project-root `.env` second without logging secret material, and missing `.env`/key preserves the existing legacy fallback.
- The historical v0.7.4 architecture freeze and read-only audit remain recorded, but its independent implementation route is superseded / replaced by v1.0. Legacy retirement now occurs only after the v1.8 shadow / parallel validation and v1.9 production cutover gates; no old product surface is deleted before those gates.
- The v1.0 canonical architecture is documented in `docs/EVENT_DRIVEN_MORNING_BRIEF_ARCHITECTURE.md`; it does not prescribe immediate Python filenames, package hierarchy, feature flags, or business implementation. `Article` is input, `Event` is the core object, and `Brief` is output; Article dedup and event clustering remain separate.
- The v1.0 canonical core data contract is documented in `docs/EVENT_DRIVEN_MORNING_BRIEF_DATA_CONTRACT.md`; it freezes Article/EventCandidate/Event/Brief identity and ownership, deterministic Evidence projection, immutable Event stage derivation, and the minimal component-local result envelope without implementing runtime behavior.
- The v1.0 canonical runtime / failure contract is documented in `docs/EVENT_DRIVEN_MORNING_BRIEF_RUNTIME_CONTRACT.md`; it freezes run identity, StageResult semantics, per-component isolation, LLM batch/retry boundaries, Brief status, artifact/delivery behavior and no automatic post-cutover legacy semantic fallback. The contract is docs-only and not implemented.
- The v1.x implementation version roadmap is frozen in `docs/DECISIONS.md` and indexed in `docs/BACKLOG.md`; v1.1 through v1.7 are complete and closed with offline verification, and v1.7 Human Reader-Facing Acceptance is PASS. Generation 2 remains side-by-side and does not cut over production; v1.8 runs side-by-side without reader-facing output, v1.9 forbids automatic Generation 1 semantic fallback, and v1.10 owns post-cutover legacy retirement and closeout.
- v1.3 side-by-side implementation is present in `event_cluster.py` with fake-embedder smoke, labeled fixtures, and a separate real-model evaluator. The accepted fixed configuration is E5-small revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`, `article-title-summary-v1`, summary cap 300, threshold `0.91`, and `connected-components-v1`; production-critical acceptance is exact `8 / 8` with zero overmerge and split.
- Canonical Event / EventCandidate semantics are reader-level story bundles inside one approximately 24-hour Morning Brief report window, not persistent atomic occurrence identity. Announcement, immediate reaction, clarification, closely related follow-up, and complementary perspectives may cluster when separate reader-facing items would be materially repetitive. v1.5 Event Writer must read complete Article provenance and preserve material facts and perspectives in `title_zh`, `summary_zh`, and `why_it_matters_zh`.
- v1.3 clustering remains local embedding + semantic similarity + simple deterministic clustering. DeepSeek, local LLM pair verification, LLM adjudication, translation, and second-pass AI clustering are prohibited in this stage.
- v0.7.3 closeout is a product-review decision to stop patching the Generation 1 core news architecture, not a claim that Generation 1 fully met the long-term product target. The evidence is retained as historical input to v1.0 and is not being re-designed in this closeout. v1.3 remains side-by-side and does not alter Generation 1 production routing.
- `tests/offline_overnight_brief_smoke.py` covers cross-section dedupe, 0–3 watch variables, conditional holdings, missing market data, no holdings, feed failures and explicit dispatch; all offline smoke tests passed on 2026-08-13.
- P1 foundation docs are now split by responsibility: README as entry, PROJECT_STATE as dashboard state, BACKLOG as future work, TESTING as verification checklist, DECISIONS as long-term decisions, and MISSED_CASES as quality tracking.
- Further quality improvements should use the AI Curator shadow path instead of continuing small rule tweaks in `_score_article` or digest classification.
- v0.6.1 产品与语言合同已完成：输入可为 `zh-CN` / `en` / `und`，最终 Curator 输出为 `zh-CN`；语言不进入 article identity，也不进入 legacy path。
- v0.6.1 已为 `feeds.json` / `feeds.example.json` 增加可选 language metadata；旧配置缺失、空或非法 language 时归一化为 `und`。当时 16 个 active feed 的 name / url / mode / role / 顺序保持不变；2026-08-16 v0.7.3 另移除持续 malformed 的 36 氪 feed，剩余 15 个 active feed 保持不变。
- 2026-08-16 v0.7.3 broken-feed production hygiene 仅删除 `feeds.json` 中失效的 36 氪配置；不增加 replacement，不改变 AI Curator、Prompt、`max_events`、ranking、dedupe、fallback、其它 feed 或 `feeds.example.json`，也不代表重新进入新闻质量调优。
- v0.6.2 Phase 3A 已完成配置与 preflight boundary；Phase 3B real-provider one-shot gate 已用 exactly 2-candidate fixture 成功完成，整体 shadow evaluation 尚未完成，也未进行 production 切换。
- Phase 3B 成功样例的 Phase 4 evaluation item：检查 `why_important` 的 fact / interpretation boundary、unsupported causal inference、unsupported market implication 和 uncertainty handling；当前不修改 validator、关键词或 content scoring。
- Phase 4 provider behavior remains unchanged and its limits are shared by the explicit manual `overnight_brief` path; Bark、Obsidian、launchd、pmset、daily digest 和 `market_brief` 生产行为不变，AI failure 不得影响 production. Phase 3B 的 `2 / 4096` fixture limits 不得直接复用为 live RSS / production limits。
- Phase 3B fixture one-shot gate 仅由显式 `--real-provider deepseek` path 使用：`max_candidate_count=2`、`max_provider_request_body_bytes=4096`、`max_attempts=2`、`max_tokens=8192`、`timeout=90s`；这些不是 live RSS / production limits，也不是通用 provider 默认值。
- Phase 4A snapshot contract correction 允许 linked `published_at:null` candidate fixture，正式 replay 的 live snapshot 有 `159` candidates；完整 current provider body=`492741` bytes，title-only=`97583`，summary 300/500/1000-char counterfactual=`132770`/`138482`/`152332`，transport calls=`0`。后续 candidate-pool audit 仅将 GitHub Trending Python Daily 定义为 Phase 4 daily-main-pool 的 exact source exclusion；Investing.com 中文财经 保留为普通新闻 source。这不是 collector、feed 或通用 source ranking policy。
- Phase 4A 未修改 `main.py` window semantics：digest cutoff 仍在逐 article processing 时动态调用 `datetime.now(timezone.utc)`；`CuratorRequest.window_start/end` 仍使用候选最早/最晚 non-null `published_at`。由于 shared collector 同时服务 legacy path，后续 window change 需单独 production-impact review。
- Phase 4B 已冻结 explicit `phase4_live` input mode、summary cap=`500`、candidate limit=`200` 和 provider body limit=`200000`；v0.7 same-snapshot sensitivity 后，phase4_live runner default capacity 改为 20，以降低 10-event cap 对重大事件 coverage 的挤压。projection 只作用于 Provider-facing copy，`request.json` 保存 projected request，原始 live snapshot 保持独立完整且不被修改；20 仍是 ceiling，不是补满目标。
- Phase 4B candidate/body overflow 必须在 API-key lookup 和 HTTP transport 前 fail closed；不自动截断 candidate、不迭代缩短 summary、不提高 limit。Phase 3B `2 / 4096` 仍是独立 fixture-only mode。
- 真实 Phase 4 shadow 的 input/transport 正常；selected-only live output 先因 `duplicate_rejected_article_id`、随后因 `duplicate_evidence_article_id` 在 response validation fail closed。Prompt Alignment 未修改 validator；当前仅增加 phase4_live evidence exact-dedupe，rejection list 仍不 dedupe、不选 reason、不保存 rejection bookkeeping。
- Phase 4 live product decision 已改为 selected-only Curator semantics：模型只选择/聚合重要 events 与 evidence；未被 evidence 使用的 candidate 由程序推导，rejection enumeration 不再收集。显式 phase4_live provider boundary 将 rejection 字段 canonicalize 为 `[]`，并将同一 event 内完全相同的 evidence ID 保序 canonicalize 后再进入现有 validator；unknown/empty/different IDs、event/schema/content/finish_reason 等 contract 继续严格 fail closed。default/full 与 Phase 3B rejection/evidence contract 保持原样。
- 2026-08-13 旧的 direct AI-backed `overnight_brief` 运行发生在 artifact persistence 接线之前，因此仅有报告和 feed log，不能做精确 candidate/provider-facing 计数或逐事件 B/C/D 审计；后续 direct run 使用 `overnight-` 前缀并写入同一 `runs/ai-curator-shadow/` artifact root。现有 2026-08-12 shadow artifacts 仍不能冒充旧的 2026-08-13 运行。
- cleaned-pool single-pass phase4_live dry-run 为 `159 / 140 / 19 / 6 / 134 / 108264 / 119868 / 0`（original / provider-facing / source-excluded / capped / unchanged / curator bytes / provider bytes / transport calls），request `max_events=10`；原始 snapshot 继续独立完整，SHA-256 未变化。
- two-pass real validation 的唯一明确收益是第二段未把一篇无关 Pass A evidence 写进最终 response；但 must-include 覆盖降至 3/8，且仍有错误 grouping / evidence contamination / 分类问题，因此该路径已移除。`phase4_live` 重新使用一个 200000-byte preflight 和一段最多两次 transient retry 的 provider call；成功 run 只写 `request.json`、`response.json`、`trace.json`、`review.md` 和 `run.json`。
- DeepSeek runtime 配置固定为 `deepseek-v4-flash`；一次性 Pro same-snapshot artifact 仅作为 v0.6.2 实验记录保留，不需要 runtime profile 才能读取。
- `.env.local` is used for local Bark / Obsidian configuration and must not be copied into project docs; `.env` remains ignored for backward safety but is no longer an active project-root consumer.

## Handoff Prompt

v1.8 is IN PROGRESS. The production-shaped Generation 2 runtime remains manual-only and delivery-disabled. Source freshness qualification now excludes wholly timestamp-null snapshots before formal normalization/window/clustering, and `semantic-title-anchor-v1` corrects the three confirmed clustering hard negatives while preserving both real positive counterexamples and the historical v1.3 acceptance. Manual validation supports an explicit rolling-24h `--as-of-now` slot in addition to the fixed 08:00 canonical slot; the two CLI modes are mutually exclusive. Generation 1 production routing, schedules, Bark/Obsidian delivery, and frozen contracts remain unchanged. Complete at least one valid rolling-24h run and user reader-facing review; target any follow-up testing to concrete issues, without adding delivery, starting v1.9, or starting the comparison/review layer.
