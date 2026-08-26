# v1.0 — Event-driven Morning Brief Core Data Contract

> Status: Core Data Contract Freeze（docs-only，2026-08-26）
>
> 本文件是 v1.0 news core 的 canonical data contract。它补充而不替代 [`EVENT_DRIVEN_MORNING_BRIEF_ARCHITECTURE.md`](EVENT_DRIVEN_MORNING_BRIEF_ARCHITECTURE.md)：architecture contract 冻结产品与职责边界，本文件冻结跨组件数据、identity、ownership、derivation 和最小局部失败边界。Runtime / Failure semantics 由已冻结的 [`EVENT_DRIVEN_MORNING_BRIEF_RUNTIME_CONTRACT.md`](EVENT_DRIVEN_MORNING_BRIEF_RUNTIME_CONTRACT.md) 定义；实现方式和 production routing 不在本文件中冻结。

## 1. Scope 与冻结原则

v1.0 core lifecycle 保持：

```text
Article
  → EventCandidate
  → selected Event
  → classified and/or written Event
  → Brief
```

冻结原则：

- `Article` 是输入，`Event` 是核心业务对象，`Brief` 是输出；
- canonical object 使用最小、显式、可独立 validation 的字段；
- stage 通过 immutable derived value 补齐同一个 `Event`，不复制三套字段高度重叠的 Event schema，也不原样改名复用旧 `CuratedEvent`；
- Article identity、URL、source、时间和 provenance 只由 deterministic code 拥有；LLM 不得生成、猜测或修改；
- selector 只做相对选择，不输出 numeric importance score、权重、source score、hotness score、category quota 或 importance tier；
- classifier 发生在 selection 后；category 只描述事件类型，不影响选择或顺序；
- writer 只生成 `title_zh`、`summary_zh`、`why_it_matters_zh`，reader-facing language 固定为简体中文；
- `Evidence` 是 Article 的 deterministic projection，不是独立 AI object 或独立 authority；
- Holdings 不进入 v1.0；Market data / market context 不进入 v1.0 core contract；
- `watch_point`、confidence、uncertainty、novelty 和 legacy importance enum 不进入本次 canonical core；
- 所有 stage 支持保留成功输出和 item-local failure；不得用一个失败使 whole news layer 作废。

## 2. Shared serialization rules

本文件冻结 logical payload，不冻结 Python class、module/package layout、artifact 文件名或物理 API request。

- canonical serialization 使用 UTF-8 JSON-compatible values；object field 使用本文名称，不接受 legacy alias 自动修复；
- contract artifact 必须在 payload 边界携带 `contract_version = "v1.0-core-data-contract"`；版本只在 serialization envelope 记录一次，不复制进每个 domain object；
- date 使用 `YYYY-MM-DD`；datetime 使用带时区的 ISO 8601，并在 canonical serialization 中归一为 UTC；
- ID、enum 和 required text 必须是 non-empty strings；未知 enum fail closed，不由 LLM 或 loader 自动猜测；
- tuple/list 的顺序属于 contract 时必须保留；set-like 字段在 serialization 前按本文规则 canonicalize；
- raw RSS/provider payload、prompt、provider envelope、embedding vector 和 secret 都不属于 canonical domain payload；
- 完整 run artifact 的文件布局、retention、atomic publish 和 observability metadata 留给 Runtime / Failure Contract Freeze。

## 3. `Article`

### Purpose、producer 与 consumers

`Article` 是 source record 经 normalizer 处理后的 canonical source representation，也是所有 provenance 的唯一 authority。

- producer：`normalizer`；
- consumers：`article_dedup`、`event_cluster`，以及通过 ID deterministic lookup 的 selector、classifier、writer、renderer 和 artifact layer；
- mutability：创建后 immutable。article dedup 可以保留一个 Article、丢弃 duplicate copy，但不得改写保留 Article 的 identity/provenance 字段。

### Canonical fields

| Field | Required | Type | Owner | Semantics |
|---|---:|---|---|---|
| `article_id` | yes | string | deterministic code | stable Article identity，格式 `art_<24 lowercase hex>` |
| `source` | yes | string | collector/normalizer | source/publisher 的 canonical display name；也是 linkless fallback identity 的一部分 |
| `url` | no | string or null | collector/normalizer | source record 提供的原始 article URL；必须是 absolute HTTP(S) URL |
| `canonical_url` | no | string or null | deterministic code | `url` 去 fragment、tracking query 并规范 scheme/host/trailing slash 后的值 |
| `published_at` | no | datetime or null | collector/normalizer | source 声明的发布时间；未知时为 null，不用 report date 或 current time 猜测 |
| `collected_at` | yes | datetime | collector/normalizer | source record 被本次 collector 接受的时间，不参与 URL-based identity |
| `language` | yes | enum | deterministic code | `zh-CN`、`en`、`und`；缺失或不支持的输入归一为 `und` |
| `title` | yes | string | collector/normalizer | 清洗后的 source-language 标题；不是 reader-facing 中文标题 |
| `summary` | no | string or null | collector/normalizer | source 提供的摘要/description 清洗结果；缺失时为 null，不由 normalizer 生成 |

### Identity 与 exact duplicate semantics

沿用并收紧现有 stable identity：

1. 有 `canonical_url` 时，`article_id` 的 hash basis 为 `link:<canonical_url>`；
2. 没有 URL 时，basis 为 `fallback:<normalized source>:<normalized title>:<published_at UTC>`；
3. 使用 SHA-256，并取前 24 个 lowercase hex，加 `art_` 前缀；
4. linkless Article 必须有 non-null `published_at`，否则不足以形成安全 stable identity，应由 normalizer 作为 item-local validation failure 返回；
5. 相同 non-null `canonical_url` 代表 deterministic exact duplicate；没有 URL 时，相同 `article_id` 代表 exact duplicate；
6. Article dedup 不得使用 semantic title similarity 来合并不同报道。不同 canonical URL 的多篇报道即使描述同一事件，也保留为不同 Articles，交给 `event_cluster`。

`language`、`collected_at`、summary 内容和 source feed 顺序不进入 identity。identity algorithm 的任何变化都属于 contract revision，不得静默重算历史 ID。

Article 本身没有 semantic order。一个 serialized Article collection 在没有更具体 stage ordering 时必须按 `article_id` lexicographic order canonicalize；collector/feed 到达顺序不得被下游当作 importance。

### Content、language 与 forbidden responsibilities

- v1.0 当前真实 collector 证据只支持 title 与 RSS summary/description；因此本次不添加 speculative `content` / full-body 字段。未来若引入正文采集，必须先修订本合同；raw source payload 不属于 Article。
- `title`、`summary` 保持 source language；只有 writer-owned 三个字段固定为简体中文。
- Article 不包含 legacy `feed_role`、`mode`、keyword match、category、importance、score、report date、holdings、market quote、reader-facing interpretation 或 provider projection metadata。
- `source`、`url`、`canonical_url`、`published_at`、`article_id` 是 deterministic-owned authority；任何 LLM output 出现这些字段都必须被忽略或拒绝，不能覆盖 Article。

## 4. `EventCandidate`

### Purpose、producer 与 consumers

`EventCandidate` 是 `event_cluster` 的正式输出，表示一组可能属于同一现实世界事件的不同 Articles。

- producer：`event_cluster`；
- consumers：`event_selector`、artifact/diagnostic layer；
- mutability：immutable；重新 clustering 产生新的 candidate set，不在原对象上改 membership。

### Canonical fields

| Field | Required | Type | Owner | Semantics |
|---|---:|---|---|---|
| `event_candidate_id` | yes | string | deterministic code | cluster membership identity，格式 `evt_<24 lowercase hex>` |
| `article_ids` | yes | ordered list[string] | event cluster + deterministic canonicalization | non-empty、unique、按 `article_id` lexicographic order；每个 ID 必须 resolve 到本次 Article pool |

`event_candidate_id` 的 hash basis 是按上述顺序 canonicalize 后、以换行连接的完整 `article_ids`；使用 SHA-256 前 24 个 lowercase hex 加 `evt_`。相同 membership 产生相同 ID；membership 改变必须产生不同 ID。不同 run 之间的语义事件连续性不由本合同推断。

EventCandidate pool 在进入 selector 前按 `event_candidate_id` lexicographic order canonicalize；该顺序只保证 replay/serialization 稳定，不表达 importance。唯一有业务意义的 Event order 由 selector 后续写入 `selection_order`。

### Allowed metadata 与 forbidden responsibilities

- clustering 可以内部使用 local embedding、similarity、model/version 和 threshold，但 embedding vector、pairwise similarity、centroid、threshold、cluster confidence 都不是 canonical EventCandidate 字段；如需保留，只能进入 diagnostics/artifact metadata，不能成为 downstream semantic authority。
- source refs 不复制进 EventCandidate；`article_ids` 是完整 provenance refs，source/URL/published_at 必须从 Article 回取。
- EventCandidate 没有 selection order、importance、category、中文标题/摘要、why-it-matters、watch point 或 reader-facing status。
- `event_cluster` 不得为了数量或 category 目标执行 selection，也不得提前 writing。

## 5. `Event` lifecycle 与 stage contracts

### Final choice：single Event with immutable derived stage sections

v1.0 使用一个 canonical `Event`，由每个 stage 返回新的 immutable derived value。这样可以：

- 让 `event_id` 与 provenance 在整个生命周期保持同一 authority；
- 让 validator 根据 stage 明确检查哪些 section 必须为空或已填；
- 在 classifier/writer item-local failure 时保留上一阶段成功 Event；
- 避免 `SelectedEvent`、`ClassifiedEvent`、`WrittenEvent` 三套重复 identity/provenance schema；
- 防止后序 LLM 改写前序 stage 拥有的字段。

### Canonical fields

| Field | Required | Type | Owner | Semantics |
|---|---:|---|---|---|
| `event_id` | yes | string | deterministic code | 等于被提升的 `event_candidate_id`；selection 不重新生成 identity |
| `article_ids` | yes | ordered list[string] | copied deterministically from EventCandidate | immutable full provenance；必须与 source EventCandidate 完全相同 |
| `selection_order` | yes | positive integer | event selector | 当天 selected pool 的 1-based contiguous relative order；只是 ordinal，不是 score |
| `classification` | no | object or null | event classifier | 成功时只包含 canonical `category` |
| `writing` | no | object or null | event writer | 成功时只包含三个 reader-facing 简体中文字段 |

`classification` shape：

| Field | Required | Type | Semantics |
|---|---:|---|---|
| `category` | yes | enum | 事件类型，不表达 importance |

本次沿用现有、已有 validator/tests 证据的 descriptive vocabulary：

```text
geopolitics
macro_policy
financial_markets
energy_commodities
china_policy
company_industry
technology_ai
public_safety
other
```

`financial_markets` / `energy_commodities` 只描述新闻事件类型，不引入 market quote、market analysis 或 Market capability。category 不得改变 `selection_order`，classifier 也不得重新选择或丢弃 Event。

`writing` shape：

| Field | Required | Type | Semantics |
|---|---:|---|---|
| `title_zh` | yes | string | 简体中文 reader-facing event title |
| `summary_zh` | yes | string | 由 Event Articles 支持的简体中文事实摘要 |
| `why_it_matters_zh` | yes | string | 克制说明事件为何值得读者关注，不输出交易建议或无 evidence 推断 |

三个 writing 字段必须 non-empty，并由 `article_ids` resolve 的 Article evidence 支持。writer 不得返回 source/URL/published_at/article ID/category/selection order，也不得修改这些字段。

### Stage input/output

| Component | Input | Successful output | Forbidden output ownership |
|---|---|---|---|
| `event_selector` | EventCandidates + referenced Articles + report window | ordered Events；`event_id/article_ids` deterministic copy，`selection_order=1..N`，classification/writing 为 null | score、importance tier、category、中文文案、provenance mutation |
| `event_classifier` | selected Events + referenced Articles | same Events with classification filled | selection/order change、writing、provenance mutation |
| `event_writer` | selected Events + referenced Articles；valid classification 可作为 optional read-only context | same Events with writing filled；classification 可为 null | selection/order/category change、Evidence creation、provenance mutation |

Selector 可以合法返回零个 Event；数量 ceiling 不是 quota。本合同不保留 `must_know` / `important` / `background`，因为 relative selection 已表达进入 Brief 与顺序，现有证据不足以证明另一个 importance tier 是必要 authority。

### Validation、ordering 与 partial derivation

- 同一 selected result 中 `event_id` 必须 unique，`selection_order` 必须 unique 且从 1 contiguous；序列化顺序必须与 `selection_order` 相同；
- `article_ids` 必须 non-empty、unique、可 resolve，且与 source EventCandidate 完全相同；
- selected state 要求 classification/writing 均为 null；classified-only state 要求 classification non-null、writing null；written-unclassified state 允许 classification null、writing non-null；classified-and-written state 两者均 non-null；`written` 的充分必要条件是 writing non-null；
- classifier 或 writer 对一个 Event 失败时，失败 Event 的上一阶段 value 保留在该 stage result/artifact 中；其它成功 Events 继续进入下一 stage；
- classifier failure 不阻止同一 selected Event 进入 writer；classification 保持 null，不得自动改成 `other`；
- Brief 只引用已达到 written state 的 Events。未完成 Event 不伪造占位文案，不触发 whole-layer legacy fallback。

## 6. `Evidence` / provenance

Evidence 选择 **deterministic projection**，不是可独立修改或由 AI 生成的 canonical entity。

`Evidence(article_id)` 从 canonical Article 投影：

| Projected field | Authority |
|---|---|
| `article_id` | Article |
| `source` | Article |
| `url` / `canonical_url` | Article |
| `published_at` | Article |
| `title` | Article |

Provenance linkage 固定为：

```text
Article.article_id
  ← EventCandidate.article_ids
  ← Event.article_ids
  ← Brief.event_ids → Event.article_ids
```

- EventCandidate 与 Event 保存完整 `article_ids`；Brief 通过 `event_ids` 回取完整 Event provenance；canonical artifacts 不得只保存 reader-facing source subset。
- renderer 可以按 Event `article_ids` 的 deterministic order 选取有限 primary sources 展示；reader-facing ceiling 属于 renderer policy，不是 Article/Event 字段，也不得截断 artifact 中的完整 provenance。本次不在缺少产品证据时猜测具体 ceiling 数值。
- Article 是 URL、source、published_at 的唯一 authority。LLM 只可引用已知 IDs；unknown ID、空 Evidence 或不可 resolve ID 必须成为当前 item/stage 的 validation failure。

## 7. `Brief`

### Purpose、producer 与 consumers

`Brief` 是已写作 Events 的 deterministic composition contract，不是 Markdown 文件本身。

- producer：`brief_renderer` 的 deterministic composition step；
- consumers：Markdown renderer、artifact layer、delivery adapter；
- mutability：immutable；内容变化产生新的 serialization/run artifact，不原地改写已发布 Brief。

### Canonical fields

| Field | Required | Type | Owner | Semantics |
|---|---:|---|---|---|
| `brief_id` | yes | string | deterministic code | report slot identity，格式 `brief_<24 lowercase hex>` |
| `report_date` | yes | date | orchestrator input, validated by renderer | reader-facing report date |
| `window_start` | yes | datetime | orchestrator/collection boundary | source window inclusive start |
| `window_end` | yes | datetime | orchestrator/collection boundary | source window inclusive end；必须晚于 start |
| `target_language` | yes | enum | product contract | 固定 `zh-CN` |
| `event_ids` | yes | ordered list[string] | deterministic renderer | 只引用 written Events，顺序严格等于 `selection_order` |
| `generation_status` | yes | enum | deterministic renderer | `complete` 或 `partial` |

`brief_id` basis 为 `report_date|window_start UTC|window_end UTC|target_language` 的 SHA-256 前 24 个 lowercase hex 加 `brief_`。同一 report slot 的 rerun 保持同一 Brief identity；run/attempt identity 属于 Runtime / Failure Contract。

`complete` 包括 selector 合法选择零个 Event 且没有 generation-stage failure 的 empty Brief。`partial` 表示存在 retained upstream coverage / item failure，但仍可由可信 selector outcome 与 valid written Events 产生 Brief；classification failure 不必使 writer 失败，classification 为 null 的 valid written Event 可以进入 Brief。若 renderer 无法产生 valid Brief，则不存在 Brief object，由外层 failed `StageResult` 表达；不创建结构不完整的“failed Brief”。完整推导见 Runtime / Failure Contract。

Renderer 必须从 referenced Event 和 Article deterministic 生成 section、Markdown、source display 和 layout；Brief 不包含或执行 ranking、classification、semantic dedup、writing、market composition、holdings、fallback 或 delivery 决策。

Delivery metadata（channel、destination、file path、notification ID、delivery status/time）由 delivery adapter/runtime artifact 管理，不属于 Brief，也不得回写 Brief。

## 8. Component-local `StageResult` / failure envelope

本轮只冻结支持 `Fail locally, not globally` 的最小 logical envelope：

### `StageResult<T>`

| Field | Required | Type | Semantics |
|---|---:|---|---|
| `stage` | yes | string enum | logical component name：collector、normalizer、article_dedup、event_cluster、event_selector、event_classifier、event_writer、brief_renderer、delivery |
| `status` | yes | enum | `succeeded`、`partial`、`failed` |
| `outputs` | yes | ordered list[T] | 所有已通过当前 stage validation 的成功输出；partial 时仍必须保留 |
| `failures` | yes | ordered list[`ItemFailure`] | 当前 stage 的结构化局部失败；不得包含 secret 或 raw provider payload |
| `diagnostic_ref` | no | string or null | 指向独立安全诊断/artifact 的 opaque ref；不是文件布局或 provider metadata 合同 |

### `ItemFailure`

| Field | Required | Type | Semantics |
|---|---:|---|---|
| `item_id` | no | string or null | 可定位时使用输入 item ID；source/batch-level failure 无安全 item ID 时为 null |
| `code` | yes | string | stable、machine-readable、stage-scoped failure code；具体 taxonomy 下阶段冻结 |

Invariants：

- `succeeded`：failures empty；outputs 可为空，例如 selector 合法选择零个 Event；
- `partial`：outputs non-empty 且 failures non-empty；
- `failed`：outputs empty 且 failures non-empty；
- `failed item IDs` 从 `failures[*].item_id` deterministic 派生，不再复制一个可能漂移的独立字段；
- 后序 stage 只消费前序成功 outputs。失败 item 的最后一个 valid prior-stage value 由 orchestrator/artifact 保留，不由失败 stage 覆盖；
- 一个 Event 的 failure 不得删除其它 outputs，不得把已有成功 Event 替换为 Generation 1 output，也不得触发 whole-layer fallback。

本 envelope 的 timeout、retry、batching、backoff、provider recovery、fallback routing、artifact 与 error taxonomy 约束见 [`EVENT_DRIVEN_MORNING_BRIEF_RUNTIME_CONTRACT.md`](EVENT_DRIVEN_MORNING_BRIEF_RUNTIME_CONTRACT.md)。

## 9. Producer-consumer closure 与 authority matrix

```text
normalizer → Article
  → article_dedup → Articles
  → event_cluster → EventCandidates
  → event_selector → selected Events
  → event_classifier → classified Events where valid
  → event_writer → written Events（classification optional）
  → brief_renderer → Brief
  → delivery
```

| Data | Sole owner | Read-only downstream users |
|---|---|---|
| Article identity/source/URL/time/language/source text | deterministic collector/normalizer | all downstream by Article lookup |
| exact duplicate decision | article_dedup | event_cluster/orchestrator |
| Event membership | event_cluster | selector/classifier/writer/renderer |
| selected membership and relative order | event_selector | classifier/writer/renderer |
| category | event_classifier | writer（optional read-only context）/renderer |
| `title_zh` / `summary_zh` / `why_it_matters_zh` | event_writer | renderer/delivery |
| Brief composition/status | deterministic brief_renderer | artifact/delivery |

No field has overlapping write authority. Same-stage batching does not change ownership；v1.0 Runtime / Failure Contract 禁止 cross-stage physical response coalescing，避免 classification / writing validation 与 retry ownership 重新耦合。

## 10. Explicit exclusions and next contract

本次没有：

- 实现或创建 v1.0 Python modules；
- 修改 `CandidateArticle`、`CuratedEvent`、prompt、provider 或 Generation 1 runtime；
- 选择 local embedding model、安装 dependency 或冻结 embedding vector schema；
- 引入 Holdings、Market data/context、watch point、importance tier、confidence、uncertainty、novelty 或 speculative full content；
- 实现已冻结的 timeout、retry、batch、provider recovery、production fallback、artifact 或 failure taxonomy；
- 改变 production、delivery、LaunchAgent、pmset 或 legacy retirement timing。

Runtime / Failure Contract Freeze 已完成。下一项唯一任务是：

```text
v1.0 Implementation Planning / first implementation slice
```
