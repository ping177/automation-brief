# Backlog

本文记录 automation-brief 的后续任务和优先级。这里只描述未来方向，不替代 `docs/PROJECT_STATE.md` 的当前状态，也不记录 Git 快照。

## Numeric version route

新的正式 machine version token 统一使用 numeric 形式：

```text
v0.6.1 — Product Reset + Language Boundary
v0.6.2 — AI Curator Shadow Evaluation
v0.7 — Morning Brief
v0.7.1 — Morning Brief MVP（CLOSED）
v0.7.2 — Production Cutover（CLOSED）
v0.7.3 — Morning Brief Long-term Usage Validation（CLOSED）
v0.7.4 — Legacy Product Retirement & Capability Consolidation（SUPERSEDED / replaced by v1.0 plan）
v1.0 — Event-driven Morning Brief（Architecture + Core Data + Runtime / Failure Contract Freeze COMPLETE；v1.x roadmap FROZEN；next task v1.8 Shadow / Parallel Validation）
v1.1 — Canonical Domain & Runtime Foundation（COMPLETED / CLOSED）
v1.2 — Deterministic Ingest（COMPLETED / CLOSED）
v1.3 — Event Clustering（COMPLETED / CLOSED）
v1.4 — Event Selector（COMPLETED / CLOSED）
v1.5 — Event Classifier + Writer（COMPLETED / CLOSED）
v1.6 — Renderer + Artifacts + Orchestrator Integration（COMPLETED / CLOSED）
v1.7 — Offline / Snapshot Validation（COMPLETED / CLOSED）
v1.8 — Shadow / Parallel Validation（IN PROGRESS）
v1.9 — Production Cutover（PLANNED）
v1.10 — Legacy Retirement & v1.x Closeout（PLANNED）
```

历史条目中的既有 `-alpha` / `-beta` token 是 legacy 事实，保留原样，不回写历史。

## P0 / Next

当前无已知 P0 阻塞。

P0 只用于影响每日 08:00 自动生成、Obsidian iCloud 同步、Bark 推送或 Mac 自动唤醒链路的紧急问题。

### v0.7.2 Production Cutover acceptance — CLOSED

- 仓库实现与离线 routing smoke 已完成：无参数 `run_daily_digest.sh` 保持 `digest` rollback，`overnight_brief` 显式贯穿生成、Obsidian 和 Bark；plist example 已选择 Morning Brief。
- 用户已在真实 Terminal 完成项目 `.env` 配置并将权限设为 `0600`，reload 实际 LaunchAgent，并以 `run_daily_digest.sh overnight_brief` 成功完成受控 production smoke；不得在自动化测试中调用真实 DeepSeek、读取 secret、修改 pmset 或覆盖用户 plist。
- 已确认 `morning-brief-2026-08-15.md`、真实 provider succeeded artifact `overnight-20260815T143736.428601Z-f8958055f793`、Obsidian Morning 文件和 Bark Morning 通知均成功；artifact 仅记录非敏感验收字段：`succeeded / deepseek / deepseek-v4-flash / passed / empty failure_code / 20 events`。
- 真实链路失败时，移除实际 plist 的 `overnight_brief` 参数并 reload，即恢复历史无参数 Daily Digest；v0.7.3 七天真实使用验证现已完成并 CLOSED，不重新打开 Generation 1 新闻质量 tuning。

### v0.7.3 Morning Brief Long-term Usage Validation — CLOSED

- 七天真实使用观察和产品 review 已完成。
- Closeout 不是“Generation 1 完全达到长期产品目标”；真实使用暴露出重复 / 事件聚合不足、legacy fallback 中文边界、旧规则误分类、reader-facing UX、市场数据价值不足、持仓能力价值未证明等问题。
- 这些 evidence 支持停止继续 patch Generation 1 核心新闻架构，转入已经冻结的 `v1.0 — Event-driven Morning Brief` architecture rebuild。
- 当前 production 仍运行 Generation 1 pipeline；在 v1.8 shadow / parallel validation 和 v1.9 production cutover 前不删除或退役旧 production / legacy surface。
- READ-ONLY Dependency Audit、Core Data Contract Freeze 与 Runtime / Failure Contract Freeze 已完成；v1.x implementation roadmap 已冻结，下一步唯一任务是 `v1.1 — Canonical Domain & Runtime Foundation`。不重新实施 superseded 的 v0.7.4 路线。

### v1.0 Core Data Contract Freeze — COMPLETE

- READ-ONLY Dependency Audit 确认迁移路线为 preserve mature infrastructure + rewrite news core；当前没有删除 legacy tracked file，Generation 1 production 保持运行。
- canonical contract 已冻结 Article、EventCandidate、single immutable-lifecycle Event、deterministic Evidence projection、Brief 和最小 component-local StageResult；不复用 legacy CuratedEvent 作为 rename-only schema。
- Runtime / Failure Contract 已完成并与本合同交叉引用；尚未进入 implementation，不选择 embedding model，不安装 dependency。

### v1.0 Runtime / Failure Contract Freeze — COMPLETE

- canonical runtime contract 已冻结 run identity、StageResult invariant、合法 empty / partial / failed、逐 component failure isolation 与 continuation matrix。
- selector 保持独立 global logical operation；classifier / writer 在各自 stage 内支持 batch 与 event_id item-local validation，classification failure 不阻止 writing，禁止 cross-stage provider response coalescing。
- LLM physical request 最多两次 bounded attempts；delivery 与 Brief generation 分离；post-cutover 不存在 automatic Generation 1 semantic fallback。
- 下一步进入 `v1.1 — Canonical Domain & Runtime Foundation`，不在本 freeze 中实现 pipeline、retry、fallback、artifact 或 delivery behavior。
- actual LaunchAgent / pmset / runtime 现场状态留作后续 follow-up，不是当前 blocker。

### v1.1 Canonical Domain & Runtime Foundation — COMPLETE / CLOSED

- 新增独立 `canonical_domain.py`，实现冻结的 `Article`、`EventCandidate`、single immutable-lifecycle `Event`、classification / writing sections、`Brief`、`StageResult` 和 `ItemFailure`。
- 完成 stable identity、canonical URL、language / datetime normalization、UTC inclusive window validation、严格 enum/ID/text validation，以及带单一 `contract_version` envelope 的 deterministic JSON round-trip。
- `written-unclassified` 保持合法；未创建 `Run` entity，不接入 RSS/provider，不修改 Gen1、production routing、artifact/delivery、legacy 文件或三份 frozen v1.0 contract。
- 新增独立离线 smoke，覆盖 identity、四种 Event 状态、StageResult 三态、全部 category/failure code、naive datetime reject、ordering 和 serialization invariants。
- v1.2 已在 side-by-side 范围内完成；下一步唯一任务为 `v1.3 — Event Clustering`，不提前创建 selector/classifier/writer/orchestrator 或其它后续业务 stage。

### v1.2 Deterministic Ingest — COMPLETE / CLOSED

- 新增 `collector.py`、`normalizer.py` 和 `article_dedup.py`，形成 `Sources → source-scoped raw batches → canonical Article[] → exact dedup` 的最小 deterministic foundation。
- collector 复用 `feeds.json` 与 Gen1 bounded fetch/retry boundary，只保留 source name / URL / language；source-level failure isolation、合法 empty batch 和 `StageResult` 三态均由离线 fixture 覆盖。
- normalizer 通过 `Article.from_source` 唯一生成 canonical Article；naive/malformed timestamp fail closed，linked missing timestamp 合法，linkless missing timestamp item-local reject；language 和 collected_at 遵守 canonical UTC vocabulary。
- dedup 只使用 canonical URL / stable article_id，保留 first-valid 和 stable ingest order，不做 semantic title/event/source ranking。
- 未修改 `main.py`、feeds 配置、Gen1 production routing、三份 frozen canonical contract 或 dependency；未调用真实 RSS/API，未实现 v1.3+ stages，未删除 legacy。
- 下一步唯一任务为 `v1.3 — Event Clustering`。

### v1.3 Event Clustering — COMPLETED / CLOSED

- 已新增 side-by-side `event_cluster.py`，实现 canonical `Article[] → EventCandidate[]` 的 injectable embedder boundary、`article-title-summary-v1` projection、L2 normalization、pairwise cosine、threshold edges、deterministic union-find components、singleton retention 和 bounded non-canonical diagnostics。
- fake-embedder offline smoke 与七 case labeled fixture 保持独立；real-model evaluator 按 calibration / held-out split sweep threshold、计算 precision / recall / F0.5、overmerge / split、expected/actual memberships 和 deterministic repeat。
- canonical semantics 是同一约 24h Morning Brief report window 内的 reader-level story bundle，不是 persistent atomic occurrence identity。announcement / reaction / clarification / closely related follow-up 在读者视角下可以合并；共享关键词、国家、公司或主题不足以合并明显不同的新闻。
- accepted configuration 为 `intfloat/multilingual-e5-small` immutable revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`、`article-title-summary-v1`、summary cap 300、threshold `0.91`、`connected-components-v1`。四个 production-relevant cases 的 overmerge / split 为 `0 / 0`，production precision / recall / F0.5 为 `1.0 / 1.0 / 1.0`，expected reader memberships `8 / 8` exact。
- Treasury cross-language split 与 connected-components chaining 仅作 synthetic robustness evidence；temporal Iran early/later merge 是 outside-normal-window observation，不作为 production gate。v1.3 不使用 DeepSeek、任何 LLM、translation、keyword override、multiple thresholds、source/category weighting 或 Gen1 fallback。详见非权威 [`docs/V1.3_EVENT_CLUSTERING_SPEC.md`](V1.3_EVENT_CLUSTERING_SPEC.md)。
- direct runtime dependencies are `sentence-transformers==3.4.1`、`transformers==4.48.1`、`torch==2.5.1`。显式 evaluator 默认使用 writable `AUTOMATION_BRIEF_MODEL_CACHE`，未设置时落到 canonical data root 的 `runs/model-cache`；model/cache binaries 不进入 repository。后续 v1.4、v1.5、v1.6、v1.7 milestones 均已完成并关闭，当前下一步唯一任务为 v1.8 Shadow / Parallel Validation。

### v1.4 Event Selector — COMPLETED / CLOSED

- 新增 side-by-side `event_selector.py`、严格 `selected: [{event_candidate_id, order}]` response contract、最小 editorial prompt、quality fixture / runner 与 offline regression；不接入 `main.py`、Generation 1、production routing 或 v1.5 stages。
- Selector 保持完整 Event pool 的整体 editorial judgment，不使用固定评分、类别配额、来源权重或固定选取数量；deterministic projection、global outer failure 与 item-local salvage 均保持 frozen contract。
- real-provider quality validation 已通过：3/3 runs succeeded；4/4 must-include 在三次运行中全部入选；3/3 should-omit 在三次运行中全部排除；judgment-call 具备合理波动。v1.4 closeout 已完成；v1.5、v1.6 与 v1.7 均已完成并关闭，下一项工作为 v1.8 Shadow / Parallel Validation。

### v1.5 Event Classifier + Writer — COMPLETED / CLOSED

- Slice 1 新增 side-by-side `event_classifier.py` 与 `tests/offline_event_classifier_smoke.py`：只拥有 canonical `category`，使用 9-category vocabulary、batch-ready response shape（physical batch size 1）、strict exact-key validation 与 per-event failure isolation。
- Classifier 保留 Event membership、`selection_order`、writing 与其它 upstream-owned fields；Article lookup 缺失在 gateway 前 fail closed；成功输出只含 classified Events，失败以现有 `ItemFailure` taxonomy 表达。
- Slice 1 已通过全部 relevant offline smoke、Python compile/compileall、Project-State gate 与 `git diff --check`；不调用真实 DeepSeek，不接入 `main.py`、renderer、artifacts、orchestrator 或 production routing。
- Slice 2 新增 side-by-side `event_writer.py` 与 `tests/offline_event_writer_smoke.py`：只拥有三项 reader-facing zh-CN writing 字段，接受 classified/unclassified/mixed Events，完整投影 Article provenance，使用 strict response validation、最小 CJK gate 与 per-event failure isolation；不提供 raw/legacy/placeholder/backfill fallback。
- Slice 3 新增独立 `tests/offline_event_classifier_writer_continuation_smoke.py`：以 test-local composition 验证 classifier partial/all-failed 时所有 selected Events 继续进入 Writer，失败分类的 Event 可成为 `written-unclassified`，以及 Writer failure 保持 event-local；不新增 production orchestration helper。
- Slice 1 Classifier、Slice 2 Writer 与 Slice 3 Continuation Regression 均已通过 relevant offline smoke、Python compile/compileall、Project-State gate 与 `git diff --check`；v1.5 implementation complete。
- 首次 real-provider validation 为 classifier/writer 全部 succeeded、6/6 Events written、0 technical failures；Classifier 分类均合理且无 `other` 滥用，Event-level synthesis、Chinese readability 和 evidence grounding 均 PASS。首轮 `why_it_matters_zh` 读者建议问题已通过最小 prompt correction 解决，revalidation 未发现 release blocker。
- v1.5 现已 `COMPLETED / CLOSED`；v1.6 Renderer + Artifacts + Orchestrator Integration 与 v1.7 Offline / Snapshot Validation 也已 `COMPLETED / CLOSED`，保持 side-by-side，不改变 production routing，下一步为 v1.8 Shadow / Parallel Validation。报告不持久化 provider request，不输出 secrets，不新增评分或 benchmark。

### v1.7 Offline / Snapshot Validation — COMPLETED / CLOSED

- 完成小型 canonical fixture matrix：representative clean morning、合法 empty、partial degradation、hard-stop failure 与 malformed/provider protocol；不建设 benchmark、评分、LLM judge、RAG、数据库或 generic evaluation engine。
- 完整 Generation 2 offline pipeline 由 deterministic fake fetcher、fixed report slot、fixture-backed embeddings、fake selector/classifier/writer gateways 和 temporary artifact root 驱动；`cluster` metadata 只留在 test harness，不进入 RawFeedEntry 或 canonical Article，clustering 仍调用 production `event_cluster`。
- Snapshot / structural regression 锁定 event clustering membership、selector salvage/order、classifier vocabulary/invalid-category failure、writer lifecycle、continuation matrix、renderer Brief/Markdown、source dedup/provenance、checkpoint/artifact inventory、diagnostic durability、empty/partial/hard-stop outcome 与 no-backfill/no-legacy-fallback 边界。
- Human Reader-Facing Acceptance: PASS。最终布局为 H1 日期、H2 italic category、H3 bold + `var(--text-accent)` Event title、`摘要：` / `为什么重要：`、Obsidian-compatible HTML `<details>` source folding；无 `## 今日要闻`，category regroup/order 与 canonical global `Brief.event_ids` 保持不变。
- focused renderer/orchestrator smoke、全部 28 个 `tests/offline_*.py`、Python compile/compileall、shell syntax、Project-State Push Gate 16/16、fixture parsing 与 `git diff --check` 均通过；未调用真实 RSS/DeepSeek/provider，未修改 Generation 1 production routing。

### v1.8 Shadow / Parallel Validation — IN PROGRESS

- 第一小步实现 production-reusable `generation_2_runtime.py`：正式组装 active sources、canonical report slot、冻结 E5 local-only embedder、共享 DeepSeek JSON gateway adapter 与 canonical Generation 2 artifacts；不依赖 Gen1，不接 delivery 或 `reports/`。
- 新增薄 manual invocation `scripts/run_generation_2_shadow.py`；必须显式 `--real-provider deepseek`，默认 delivery disabled，真实 RSS/provider 运行仅由用户在 Terminal 执行。
- 首次真实 run 的 input population failure 已以 Gen2 source-snapshot freshness qualification 收敛：所有有效 entries 都无可解析 publication timestamp 的 source 不进入 Article/window/clustering pool，但不修改 nullable Article contract、Gen1 source config 或 production routing。
- 首次真实 run 的 clustering production hard negatives 已通过 versioned `semantic-title-anchor-v1` edge policy 做正式 corrective replacement；纯 threshold 方案因会拆分已确认真实 positives 而被否决。原 v1.3 `8/8` evidence 保持，新 5-case corrective acceptance 也为 `8/8 exact`。
- manual validation 现在支持与 `--date` 互斥的 `--as-of-now` rolling-24h mode；下一步 acceptance 是用户在 Terminal 执行至少一次有效真实 rolling-24h Gen2 run，并完成 reader-facing 人工验收。若发现明显问题，再按具体问题做针对性补测。

### v1.x Implementation Version Roadmap — FROZEN

完整路线与治理规则以 [`docs/DECISIONS.md`](DECISIONS.md) 的 `v1.x Implementation Version Roadmap（FROZEN）` 为 canonical source；这里保留执行索引：

```text
v1.0  governance baseline（COMPLETED / CLOSED）
v1.1  Canonical Domain & Runtime Foundation（COMPLETED / CLOSED）
v1.2  Deterministic Ingest（COMPLETED / CLOSED）
v1.3  Event Clustering
v1.4  Event Selector（COMPLETED / CLOSED）
v1.5  Event Classifier + Writer（COMPLETED / CLOSED）
v1.6  Renderer + Artifacts + Orchestrator Integration（COMPLETED / CLOSED）
v1.7  Offline / Snapshot Validation（COMPLETED / CLOSED）
v1.8  Shadow / Parallel Validation（IN PROGRESS）
v1.9  Production Cutover
v1.10 Legacy Retirement & v1.x Closeout
```

v1.3 已冻结 E5-small immutable revision、`article-title-summary-v1`、summary cap 300 与 threshold `0.91`；v1.6 仍不做 production cutover；v1.8 前 Generation 1 继续提供正式 reader-facing output；v1.9 禁止 automatic Generation 1 semantic fallback；v1.10 才执行 post-cutover consumer audit、legacy retirement 和 v1.x closeout。Market 不属于 v1.x core，Holdings 不进入 v1.x。

### v0.7.4 Legacy Product Retirement & Capability Consolidation（SUPERSEDED / replaced by v1.0 plan）

本条目保留 v0.7.4 的历史目标和 audit 结论，但其独立实施路线已被 `v1.0 — Event-driven Morning Brief` 取代。原目标是让 Morning Brief 成为唯一 reader-facing 晨报产品，同时把仍被 Morning 使用的能力收敛为独立、中性的 shared capabilities；这些历史结论不应被删除，也不再作为当前执行计划。

历史 read-only dependency audit 结论：

- Daily Digest product-only surface 包括 `digest` 默认/显式 dispatch、`main.py` 中的 `DigestSections` / `write_digest_markdown` reader-facing contract、无参数 `run_daily_digest.sh` 的 rollback 入口、`daily-news-*` canonical naming、publisher/Bark 的 Daily 分支、Daily 专属测试和运行说明。
- Market Brief product-only surface 包括 `market_brief` dispatch、`market_brief_writer.py` 的完整 Market Brief writer、`market-brief-*` canonical naming、`scripts/run_market_brief.sh`、Market Brief 专属 tests/docs。`market_data.py`、`market_news.py`、`holdings.py` 和 `market_analysis.py` 的能力仍被 Morning 使用，不能按旧产品 surface 直接删除。
- Morning Brief 当前仍依赖旧模块中的能力：`main.py` 的 `legacy_items_from_candidates()`、`build_digest_sections()`、`digest_item_summary()` 和 `format_digest_item_time()` 支撑 fallback/reader rendering；`overnight_brief_writer.py` 还导入 `market_brief_writer.py` 中的行情、持仓、safe rendering helpers。当前 `market_brief_writer.py` 同时承载 Market product writer 与这些公共 helper。
- 已可按语义视为 shared capability、但部分仍物理位于 `main.py` 的包括 RSS/feed collection、normalization、`CandidateArticle` / Curator request/provider/artifact boundary、market data、market news、holdings anomaly、project paths，以及最终 report publishing/delivery 的公共机制。它们的中性化方式不在本轮固定文件名。

原 v0.7.4 路线的边界（现由 v1.0 重新承接）：

- v0.7.3 只观察 08:00 production 稳定性、DeepSeek、Obsidian/Bark、明显漏报、重复、分类/事实和 20-event 长期阅读体验。
- v1.0 的 `READ-ONLY Dependency Audit` 已针对当前真实 tree 完成；后续仍须先迁移 Morning 需要的 shared capability，再在 cutover 后重新审计并删除确认无消费者的旧 product surface。
- v1.0 的 `Legacy Retirement` narrative gate 对应 v1.8 shadow / parallel validation、v1.9 production acceptance and cutover；旧 production pipeline 在此前保持可运行，v1.10 才开始 retirement。
- 删除旧产品后，Morning 必须继续覆盖 v1.0 已批准的核心 Event pipeline 及必要的 delivery capability；不得把 whole-layer legacy fallback 重新设计为下一代业务架构。
- v1.0 不预先规定 Python 文件重命名、package hierarchy、feature flag 或新的 orchestration；本轮已单独冻结 v1.1–v1.10 implementation milestone route，但不增加 v1.11 或其它未审议版本。

v1.0 的 canonical architecture contract 见 [`docs/EVENT_DRIVEN_MORNING_BRIEF_ARCHITECTURE.md`](EVENT_DRIVEN_MORNING_BRIEF_ARCHITECTURE.md)，canonical core data contract 见 [`docs/EVENT_DRIVEN_MORNING_BRIEF_DATA_CONTRACT.md`](EVENT_DRIVEN_MORNING_BRIEF_DATA_CONTRACT.md)，canonical runtime / failure contract 见 [`docs/EVENT_DRIVEN_MORNING_BRIEF_RUNTIME_CONTRACT.md`](EVENT_DRIVEN_MORNING_BRIEF_RUNTIME_CONTRACT.md)。

### Canonical runtime data migration follow-up

- canonical runtime data 已迁移到 `~/Projects/_project-data/automation-brief/`；`reports/`、`runs/`、`manual-inputs/` 和 metadata-only `migration-records/` 已完成离线校验。
- 迁移前的 `output/`、仓库根 `daily-news.log` 和 `config/holdings.json` 保留且不再是默认来源。不要在本任务之外删除、覆盖或暂存这些 legacy 文件。
- 单独观察一段时间后，评估 legacy 文件清理、下游引用确认和审计 worktree 清理；清理必须是另一个明确任务，并先完成可回滚性检查。

### v0.6.1 Product Reset + Language Boundary

- Phase 1（本轮已完成）落地 Morning Brief 产品合同、未来统一输出结构、多语言输入 / 简体中文 reader-facing 输出边界、AI Curator 职责边界和 legacy / candidate 隔离合同；不修改业务代码、feed 配置、测试或生产入口。
- Phase 2（本轮已完成）实现可选顶层 feed `language` metadata：正式语义为 `zh-CN`、`en`、`und`，缺失、空值或非法值归一化为 `und`；旧配置继续可加载。
- v0.6.1 已正式完成；下一阶段是 v0.6.2 AI Curator Shadow Evaluation，仍只做 real-provider shadow evaluation，不替换生产输出。
- candidate path 读取 `language` 并写入现有 `CandidateArticle.language`；`CuratorRequest.target_language` 固定为 `zh-CN`。语言不进入 `stable_article_id()`、canonical URL、dedup identity 或 legacy keyword gate。
- v0.6.1 当时 16 个 active feed 全部保持启用，不删除、不改变 `mode` / `role`、不新增 `priority`，也不实现 `candidate_only` 配置；英文来源不因语言被删除。2026-08-16 v0.7.3 仅因持续 malformed 的 36 氪 feed 做 broken-feed production hygiene 删除，当前剩余 15 个 active feed 的 `mode` / `role` 未变，也未增加 replacement。
- `keep`、`keep_but_lower_priority`、`candidate_only`、`needs_review` 仅作为未来 source policy 的设计建议，不是本版本 runtime config；当前没有真实 feed health / 重复率验证，因此不改变运行行为。
- v0.6.1 不接真实 AI provider、不切换 daily digest 或 `market_brief` 生产输出、不正式生成 Morning Brief 输出，不删除 legacy runtime data，也不修改 launchd / pmset / Bark / Obsidian 路径。

### v0.6.0-alpha AI Curator shadow foundation — retained constraints

- 使用 `scripts/run_ai_curator_shadow.py --candidate-fixture ... --fixture-response ...` 进行完全离线 shadow preview，不接 Bark / Obsidian / launchd / pmset；真实 RSS shadow 路径仍只能手动显式运行。
- 继续确认 `CuratorRequest` 只包含关键词前 RSS 候选池，不包含 holdings、matched keywords、legacy score、legacy category、行情或持仓涨跌。
- 用 candidate trace 区分 source miss、selection miss、classification miss 和 deduplication miss。
- 真实 provider 的 shadow evaluation 顺延至 v0.6.2，必须先复用现有 contract 和 trace，不替换普通 daily digest 或显式 `market_brief`。

### Legacy v0.5-beta market data verification（不属于 v0.6.1）

- 用显式 `market_brief` 样例验证轻量公开行情源是否稳定返回主要指数和 holdings 个股涨跌。
- 检查成交额字段口径是否稳定；在口径确认前必须显示“数据暂不可用”，不能硬凑。
- 检查 holdings 行业 / 板块只来自 canonical `manual-inputs/holdings.json` 的 `sector` 字段或仓库示例配置，不引入硬编码真实持仓。
- 检查周末或非交易日生成时，报告日期和行情交易日是否分开显示。
- 检查 v0.5-beta.5 后重要新闻的来源限额和融资类型限额是否仍保留足够的高相关政策、业绩与产业事件。
- 检查 v0.5-beta.5 后投资机构名册、榜单、名单等行业资料是否持续降权，政府部门立案 / 查处 / 整治 / 通报等统计是否持续优先归为政策监管。
- 检查 v0.5-beta.5 后 AI 应用新闻不会扩展为算力或数据中心电力，且直接基础设施证据仍能形成对应主题。
- 检查市场或持仓异常是否持续优先于单条创业融资新闻进入风险与今日继续观察，且不出现交易动作建议。
- 继续确认默认 `python3 main.py` 和 `scripts/run_daily_digest.sh` 仍生成普通 digest，不自动推送 market brief。

## P1

### 观察 v0.4.1.2 自动运行稳定性

- 连续观察真实早报运行时间，确认 `pmset` 唤醒、launchd 触发、`caffeinate` 持有防睡眠 assertion、RSS 抓取、Obsidian iCloud 同步和 Bark 推送都稳定。
- 若再次出现延迟，优先查看 launchd stdout/stderr、`daily-news.log`、`pmset -g log` 和输出文件时间。
- 不优先通过单纯提前 `pmset` 唤醒时间解决运行中睡眠问题。

### Legacy `market_brief` 能力（保留、不扩展）

- v0.5-alpha 已完成最小骨架：显式 `market_brief` report type、稳定 Markdown section、可配置 holdings 读取、离线 sample 数据和 smoke test。
- v0.5.1-alpha 已补齐 holdings 本地配置体验：初始化本地 `config/holdings.json`、字段校验、敏感字段 warning 和手动 market brief 生成入口。
- v0.5.2-alpha 已让显式 `market_brief` 复用 RSS 候选新闻，生成重要市场事件、产业催化、风险/反证、今日观察点和 holdings 相关新闻匹配。
- v0.5.3-alpha 已完成新闻质量调优：候选新闻相关度评分、新闻类型分类、弱相关过滤、AI / 算力 / 数据中心电力主题聚合、具体观察理由和高精度 holdings 匹配。
- v0.5.3-alpha quality fix 已继续修正真实样例问题：综合快讯合集降权，IPO/上市不误判宏观或政策，风险/反证和今日观察清单输出可观察变量，主题线索必须带代表新闻，holdings 泛行业词不能单独触发强相关新闻。
- v0.5-beta first stage 已接入轻量公开 A 股行情：显式 `market_brief` 尝试展示主要指数、成交额和 holdings 个股涨跌；行情失败只降级提示，不阻断报告生成。
- v0.5-beta.1 已完成小修：报告日期 / 行情交易日分离，成交额口径未确认时保守显示不可用，今日主线不输出空模板，风险变量去重，IPO / 融资展示限量并过滤弱映射海外 IPO，holdings 增加相对主要指数的轻量观察。
- v0.5-beta.2 已完成行情与新闻融合 polish：新闻主线增加置信度门槛，科创50显著强于其他指数时输出行情层面观察，持仓相对观察细分小幅 / 明显 / 逆势，持仓异常且 RSS 无解释时输出后续观察变量，财报 / 营收 / 利润类新闻归为公司经营 / 财报。
- v0.5-beta.3 已完成新闻事件排序和合并 polish：政策监管新闻优先级提高，同主题证监会再融资 / 定增政策合并展示，IPO / 融资分类更严格，holdings 相关新闻区分明确相关新闻 / 弱相关变量，风险与反证优先覆盖政策监管变量。
- v0.5-beta.3.1 已完成真实样例 hotfix：A 股再融资 / 定增制度变量继续提权，泛“监管”分类收紧，观察理由关键词去重，今日主线增加 `relevance >= 70` 渲染阈值，券商业绩预告排序提高，风险与反证明确覆盖再融资和定增储架发行变量。
- v0.5-beta.5 已完成重要新闻相关度和分类 polish：重要新闻增加同源与融资类型限额，融资/财报按标题主动作处理，投资机构名册 / 榜单降权，政府监管统计优先归政策监管，算力/数据中心电力需要直接证据，风险与今日继续观察优先使用市场和持仓异常。
- 以上 v0.5 系列条目是已完成的显式 `market_brief` 历史能力；它继续作为独立、手动或显式触发的旧入口保留，不代表 Morning Brief 的最终产品定位，也不在 v0.6.1 中继续优化。
- 保持规则输出克制，不把普通科技动态、泛访谈、benchmark 争议和活动宣传误升格为市场信号。
- 持仓观察必须来自 canonical `manual-inputs/holdings.json` 或仓库示例文件，不能把具体持仓硬编码进业务代码。

### Later: deeper market data validation

- 后续再评估更稳定的数据源、行业 / 板块行情、相对强弱和成交结构。
- 继续避免复杂策略、交易动作、真实持仓敏感字段和重依赖。

### RSS 覆盖质量复盘

- 继续观察 v0.4.1 新增的 `global_tech_business` 和 `ai_industry` RSS 源是否提升覆盖而不过度增加噪音。
- 对漏报和误升格使用 `docs/MISSED_CASES.md` 记录，再决定是否调整源、关键词、role 或规则。
- 避免一次性新增大量未经验证的 RSS 源。

## P2

### v0.6.2 AI Curator Shadow Evaluation

- v0.6.0-alpha 已完成 shadow foundation。后续真实 provider 必须实现 `CuratorProvider` 接口，并复用同一 `CuratorRequest` / `CuratorResponse` contract。
- Global Event Curator 只做全球重大事件选择，不接 holdings、行情、legacy score、legacy category 或 matched keywords。
- 真实 provider 不可直接替换 daily digest 或 `market_brief`；必须先输出 shadow preview 和 candidate trace，并保留 legacy fallback。
- AI 不做全网生成、不编造事实、不替代来源链接。
- Phase 4B 已冻结显式 `phase4_live` provider-facing projection：summary cap=`500`、candidate limit=`200`、provider body limit=`200000`；selected-only 真实 DeepSeek shadow 已完成输入/transport 验证，但 output validation 先因 duplicate rejected article ID、随后因 duplicate evidence ID 被拒绝。现在 live 模式采用 selected-only semantics：rejection enumeration 不再收集，provider boundary 将 rejection 字段 canonicalize 为 `[]`，并仅对同一 event 内完全相同的 evidence ID 做保序 exact-dedupe；selected events 的其他 contract 仍严格验证，后续 real shadow 仍需单独授权，不能自动切换生产路径。
- v0.6.2 Phase 4 已关闭：simple single-pass technical shadow boundary、GitHub-only cleanup 与 production isolation 已验证；same-snapshot 内容实验显示 major-event recall / ranking 仍不稳定。不要在 v0.6.2 继续 prompt、模型、source filter、validator 或多阶段实验；下一正式工作是 v0.7 Morning Brief 的独立产品设计，仍不得自动切换生产路径。

### missed coverage 闭环

- 将漏报、重复、误升格、误降级案例稳定记录到 `docs/MISSED_CASES.md`。
- 每次规则调整都尽量补一个离线 smoke 样本或 section 组装级样本。
- 定期复盘 missed case 是否指向 source gap、keyword gap、role gap、rule gap 或未来 AI rerank gap。

### Bark / Obsidian 体验优化

- 继续保持 Bark 只推送简短通知，不推送完整 Markdown。
- 优化失败诊断文案和手动补发说明。
- 观察 iCloud 同步延迟，必要时补充排查 checklist，而不是把本机绝对路径写进代码。

## P3

### weekly AI tools radar

- `ai_tools` 继续默认排除 daily digest。
- GitHub Trending 不适合直接进入每日重点内容，可作为低频 AI/tool 观察源。
- 后续如做 weekly AI tools radar，应单独设计输出结构和筛选规则。

### launchd / pmset 可观测性增强

- 如真实运行仍偶发异常，可考虑补充更明确的 launchd 日志说明或诊断命令。
- 不优先修改 plist；需要修改时应先说明原因和影响范围。

### 配置文档整理

- 后续可把 `feeds.json`、`keywords.json`、`config.json` 的字段说明从 README 拆到独立配置文档。
- README 保持入口和常用运行说明，避免继续膨胀。
