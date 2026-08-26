# v1.0 — Event-driven Morning Brief Architecture

> Status: Architecture Freeze（docs-only，2026-08-26）
>
> 这是 v1.0 下一代 Morning Brief 的 canonical architecture contract。它冻结产品边界、职责边界和迁移时机，不创建业务代码，也不替代后续的 Core Data Contract 或 Runtime / Failure Contract。

## 1. 产品定位

下一代产品继续叫 **Morning Brief**，架构名称为 **Event-driven Morning Brief**。

核心原则是：

> **Article 是输入，Event 是核心业务对象，Brief 是输出。**

v1.0 不是 AI 投研助手、股票推荐工具、新闻到股票机会映射器或每日投资观点生成器。它的 reader-facing 输出仍然是适合早晨快速阅读的简体中文 Morning Brief。

`v0.7.3` 保留为 Generation 1 Morning Brief 的七天真实使用验证 baseline。v1.0 是下一代完整架构重建里程碑；在当前 freeze 之后，v1.0 仍未开始业务实现或 production cutover。

## 2. Version governance 与 narrative stages

正式产品世代只使用一个 numeric token：

```text
v1.0 — Event-driven Morning Brief
```

不得为内部过程创建 `v1.0-alpha`、`v1.0-beta`、`Phase A/B/C` 或其它阶段型版本名。内部过程只使用 narrative stage：

```text
Architecture Freeze
        → READ-ONLY Dependency Audit
        → Core Data Contract Freeze
        → Runtime / Failure Contract Freeze
        → Implementation
        → Offline / Snapshot Validation
        → Shadow / Parallel Validation
        → Production Cutover
        → Legacy Retirement
        → v1.0 CLOSED
```

旧的 `v0.7.4 — Legacy Product Retirement & Capability Consolidation` 历史记录保留，但其独立实施路线被 v1.0 取代。旧产品只有在 v1.0 完成 shadow / parallel validation 和 production cutover 后才进入 retirement；不得在 v0.7.3 baseline 期间提前删除 legacy surface。

## 3. 冻结的核心主链

```text
Sources
  ↓
collector.py
  ↓
normalizer.py
  ↓
article_dedup.py
  ↓
event_cluster.py
  ↓
event_selector.py
  ↓
event_classifier.py
  ↓
event_writer.py
  ↓
brief_renderer.py
  ↓
delivery.py
```

基础设施横切主链，但不拥有新闻业务判断：

```text
orchestrator.py
llm_gateway.py
```

以上名称是架构职责建议，不是本轮要求创建、重命名或拆分成对应 Python 文件。正式实现前必须先完成 dependency audit、Core Data Contract Freeze 和 Runtime / Failure Contract Freeze。

## 4. Domain object lifecycle

```text
Article
  → EventCandidate
  → selected Event
  → classified and written Event
  → Brief
```

### Article

Article 是来源输入的 canonical representation，至少需要能够稳定表达：

- `title`
- `url`
- `source`
- `published_at`
- `language`
- `summary` / `content`
- stable identity metadata

字段名称、必填性、时间语义和 schema version 留到 Core Data Contract Freeze 正式确定。Article 不携带由后续模块推断出的 importance、category 或 reader-facing interpretation。

### EventCandidate

EventCandidate 是 event clustering 的输出。它表示一组可能属于同一现实世界事件的 Articles，并必须保留：

- `article_ids`
- source references
- 可由原始 Article 回取的 provenance

EventCandidate 还没有经过当天相对选择，也不应被当作最终 reader-facing Event。

### Event

Event 是 v1.0 的核心业务对象。它由 EventCandidate 经过 selection、classification 和 writing 逐步补齐：

- selector 决定是否进入 Brief 以及相对顺序；
- classifier 在 selection 之后提供语义 category；
- writer 生成 reader-facing 简体中文文本；
- provenance 始终由 Article deterministic 回查，不由 LLM 生成。

`must_know`、`important` 等 importance enum、category enum、confidence、uncertainty 和其它字段是否保留，统一留到 Data Contract Freeze 决定。本轮不凭空新增 enum，也不把 `watch_point` 设为必选核心字段。

### Brief

Brief 是 Event 和其它已批准 shared capability 的 deterministic reader-facing composition。它负责把已选、已分类、已写作的 Events 组织成 Morning Brief，不重新判断事件重要性。

## 5. 模块职责冻结

### `collector.py`

负责从 RSS 及未来其它信息源获取原始新闻，并报告 source-level fetch result。

只负责“抓回来”，不负责重要性、分类、keyword relevance 或 semantic filtering。

### `normalizer.py`

负责把不同 source 的原始记录统一为 canonical Article，包括字段清洗、时间和语言 metadata、stable identity 所需信息。

不做新闻语义判断，不给 Article 赋 importance、category 或 event interpretation。

### `article_dedup.py`

负责 Article-level deterministic deduplication，回答：

> “这是不是同一篇文章的重复副本？”

允许使用 canonical URL、去除 tracking 参数后的 URL、source article id，以及其它可以确定性证明重复的 identity。

它不回答“不同文章是不是同一个现实事件”；不得把 event-level semantic clustering 混回 Article dedup。

### `event_cluster.py`

负责把不同 Articles 聚合为 EventCandidate，回答：

> “这些不同报道是不是属于同一个现实世界事件？”

初始实现方向优先使用 local embedding / semantic similarity；不默认调用 DeepSeek，不用大量人工 keyword 规则理解事件。它负责 event grouping 和 provenance linking，不负责当天重要性 selection、category classification 或最终中文写作。

### `event_selector.py`

从过去约 24 小时已完成 clustering 的 EventCandidate pool 中选择今天最不应错过的事件，并返回 selected event ids 与 relative order。

Selector 使用 LLM 做当天 pool 内的相对选择，但不使用 numeric score、complex ranking formula、source score、hotness score 或 fixed category quota。category 不给 importance 加分；宁缺毋滥，任何由后续 contract 定义的数量上限也不是填满目标。

Selector 不负责 clustering、classification、final Chinese writing 或 source/evidence 生成。

### `event_classifier.py`

只对已经由 selector 选中的 Event 做语义分类。分类发生在 selection 之后。

Classifier 使用 LLM；category 与 importance 完全解耦，不得重新引入“financial news +20”一类规则。具体 category enum 留到 Data Contract Freeze。

### `event_writer.py`

只负责把已入选、已分类的 Event 生成为 reader-facing 简体中文内容，核心方向为：

- `title_zh`
- `summary_zh`
- `why_it_matters_zh`

它不负责 selection、classification、clustering 或 evidence creation。`watch_point` 当前不是必选核心字段，是否保留另行决定。

### `brief_renderer.py`

负责 deterministic Morning Brief composition，包括 section organization、Markdown、event ordering、source rendering、reader-facing layout 和数量 ceiling。

Renderer 不重新 ranking、classification、semantic dedup 或新闻理解。

### `delivery.py`

负责最终报告保存与推送，包括 Markdown、Bark 和未来 delivery channel。

Delivery 不参与内容判断，不改变 Event 顺序或文字。

### `orchestrator.py`

只负责编排整个 pipeline、传递明确的 contract、收集局部结果和驱动阶段顺序。

它不负责新闻判断、分类、selection、writing 或 dedup。

### `llm_gateway.py`

负责共享 LLM provider infrastructure，包括 provider call、batching、transport retry、request/response handling 和 provider-level observability。

它不得承载 selector、classifier、writer 的 business rules。模块职责拆分与物理 API call 次数是两个概念：未来可以在 gateway / orchestration 层合理 batch，但不能为了减少 API call 又形成一个承担 clustering、selection、classification、writing 的“大 Curator”。

## 6. Deterministic work 与 model work

下一代的工作分配冻结为：

```text
代码负责：collection、normalization、Article dedup、schema validation、
          provenance、rendering、delivery、orchestration

local semantic model 初期负责：event clustering

LLM 主要负责：event selection、event classification、event writing
```

任何未来 batch 都必须保持上述 logical responsibility boundary。API call 合并不能改变模块合同，也不能把一个不可审计的全能 Curator 重新引入主链。

## 7. Failure model

冻结原则：

> **Fail locally, not globally.**

单个 Event 或 batch 的 LLM output failure 只能影响最小合理单元。一个非法 category、单个事件的写作失败或一个局部 batch 的 validation failure，不得自动使整个 AI news layer 作废，也不得触发 whole-layer legacy fallback 作为 v1.0 architecture 的默认设计。

retry policy、batch failure、partial success、validation failure handling、artifact semantics 和 runtime error taxonomy 留到 Runtime / Failure Contract Freeze 正式设计。本轮只冻结故障隔离方向。

v0.x 现有 rollback / fallback 是当前生产安全边界，v1.0 开发期间继续保留并可运行；它不构成 v1.0 的新业务架构。

## 8. Evidence 与 provenance

Evidence 不是独立 AI 模块。Event 必须保存 Article provenance：

```text
article_ids
source refs
```

source、URL、published_at 和其它 article metadata 必须从原始 Article deterministic 回取。LLM 不生成、猜测或重写 source URL；reader-facing Brief 可以只展示少量主要来源，但完整 provenance 必须保留在 artifact / data contract 中。

## 9. Holdings 与 Market 边界

### Holdings

Holdings **REMOVE / NOT CARRIED FORWARD**。旧版本已经存在 holdings，不代表它自动进入 v1.0 Event-driven Morning Brief 正式 capability。

### Market

Market / 隔夜市场不是 v1.0 核心 Event pipeline，当前只作为未来 optional capability。不要在本次 freeze 设计 Market v2；未来若数据源能够提供真正有价值的 market context，必须先做独立 READ-ONLY capability audit，再决定是否接入。

## 10. Legacy coexistence 与 retirement gate

v1.0 实现期间，旧 production pipeline 必须保持可运行：

- 不提前删除 Daily / Market legacy code；
- 不在本轮修改 production routing；
- 不把未完成的新 pipeline 接到当前自动化入口；
- 新架构应先以 offline / snapshot、再以 shadow / parallel 方式验证。

Legacy retirement 不是 Architecture Freeze 的动作。只有新架构完成真实 shadow / parallel validation、production acceptance 和 production cutover 后，才进入 legacy retirement；删除前仍需对当时 tree 做 read-only consumer audit，并按真实消费者迁移 shared capabilities。

## 11. v1.0 stage gates

以下是过程 gate，不是新的 version token：

1. Architecture Freeze：冻结本文件的产品、主链、模块职责和非目标。
2. READ-ONLY Dependency Audit：核对真实消费者、当前模块耦合和可迁移边界。
3. Core Data Contract Freeze：正式确定 Article、EventCandidate、Event、Brief schema、enum、identity 和 provenance contract。
4. Runtime / Failure Contract Freeze：正式确定 retry、partial success、validation、artifact、observability 和局部失败行为。
5. Implementation：在旧 production 可运行的前提下实现 v1.0 pipeline。
6. Offline / Snapshot Validation：用 deterministic fixtures / snapshots 验证模块合同和跨阶段 provenance。
7. Shadow / Parallel Validation：与 Generation 1 结果做真实 shadow / parallel comparison。
8. Production Cutover：经过 acceptance 后切换 production routing，并保留可回滚路径。
9. Legacy Retirement：重新审计消费者、迁移 shared capabilities 后，才删除旧产品容器。
10. v1.0 CLOSED：确认 Morning Brief production 稳定且旧产品 retirement 完成。

## 12. 本轮明确不做

本次 Architecture Freeze 只修改治理与架构文档，不做以下事项：

- 不创建 `collector.py` 等业务模块；
- 不实现 Article / Event / Brief 数据 schema；
- 不调用 RSS、DeepSeek 或其它 provider；
- 不安装依赖；
- 不修改 production routing、LaunchAgent、Bark 或 Obsidian；
- 不删除或重命名 legacy code；
- 不设计 Market v2、holdings migration、RAG、多模型或多阶段 ranking；
- 不把 v1.0 内部 stage 写成 alpha/beta/Phase 版本名。

## 13. 文档治理

本文件是 v1.0 Event-driven Morning Brief 的详细 architecture contract。长期决策在 `docs/DECISIONS.md` 记录，当前 dashboard 状态在 `docs/PROJECT_STATE.md` 记录，后续任务在 `docs/BACKLOG.md` 记录，过程和验证在 `docs/DEVLOG.md` 与 `docs/TESTING.md` 记录。其它文档不得创建一套相互竞争的 v1.0 架构或版本治理。
