# v1.0 — Event-driven Morning Brief Runtime / Failure Contract

> Status: Runtime / Failure Contract Freeze COMPLETE（docs-only，2026-08-26）
>
> 本文件是 v1.0 news core 的唯一 canonical runtime / failure contract。产品与职责边界见 [`EVENT_DRIVEN_MORNING_BRIEF_ARCHITECTURE.md`](EVENT_DRIVEN_MORNING_BRIEF_ARCHITECTURE.md)，canonical objects、identity 与 ownership 见 [`EVENT_DRIVEN_MORNING_BRIEF_DATA_CONTRACT.md`](EVENT_DRIVEN_MORNING_BRIEF_DATA_CONTRACT.md)。本文件冻结 run、StageResult、failure isolation、retry、batch、artifact、delivery 与 cutover 后 fallback 语义，不实现 pipeline。

## 1. Scope 与证据边界

本合同保持既有主链：

```text
Sources
  → collector
  → normalizer
  → article_dedup
  → event_cluster
  → event_selector
  → event_classifier
  → event_writer
  → brief_renderer
  → delivery

shared infrastructure: orchestrator + llm_gateway
```

冻结原则：

- **Fail locally, not globally**：失败只扩大到 correctness 所要求的最小单元；已有 valid outputs 必须保留；
- logical component、provider batch 与 physical API call 是三个不同边界；
- 合法空结果、部分覆盖失败与 hard failure 必须可区分；
- 不使用 Generation 1 keyword ranking、legacy classification、whole-layer Curator 或 legacy writer 修补 v1.0 失败；
- 不使用 raw English、placeholder、自动改成 `other`、backfill、rerank、second-pass selection 或 LLM JSON repair 假装成功；
- canonical runtime behavior 只冻结影响 correctness、failure isolation、ownership 和 production semantics 的部分；模型、prompt、embedding threshold、batch size、具体 provider timeout 秒数和 artifact retention 天数属于 implementation/config tuning。

本次 read-only inventory 证明以下成熟基础可复用：

- per-source RSS fetch、bounded timeout/retry 与成功 source 保留；
- stable Article identity、canonical data root 与 path resolver；
- provider preflight、finite timeout、bounded retry、secret-safe transport error；
- strict response parsing / validation、known-ID provenance validation；
- UTC timestamp + random suffix run identity、atomic staging-to-final artifact publish、allowlisted diagnostics；
- canonical Markdown 先生成、Obsidian 与 Bark 独立尝试的 delivery boundary；
- launch script 的 process-env-first / project `.env.local` second 软件职责边界。

以下 Generation 1 semantics 不继承：单个 Curator response 统一承担 selection / clustering / classification / writing、whole-response validation failure 使整个 AI layer 作废、以及 whole-layer legacy writer fallback。

## 2. Run identity 与 lifecycle

一次 **run** 是 orchestrator 对一个已验证 report slot 发起的一次完整 v1.0 generation + delivery 尝试。report slot 由 Data Contract 已冻结的 `report_date`、inclusive `window_start`、inclusive `window_end` 与 `target_language` 定义。

- `run_id` 是 runtime metadata，不进入 Article、EventCandidate、Event 或 Brief；
- orchestrator 接受 run 时生成一次 `run_id`，格式采用可按 UTC 排序的 timestamp 加不可预测 random suffix；同一 run 内 immutable；
- 同一 report slot rerun 保持相同 `brief_id`，但获得新的 `run_id`；
- physical request retry 不创建新 run；它复用同一 run、stage invocation、batch identity 和 logical request body，只增加 `attempt`；
- stage / batch artifact 必须通过 `run_id + stage + invocation/batch identity` 可追溯；
- run 的 generation outcome 与 delivery outcome 分开记录。delivery failure 不回写 Brief，也不改变 `Brief.generation_status`。

run 只有在 canonical input slot 和 runtime manifest 成功建立后才能开始。canonical stage checkpoint 无法原子持久化时，不允许把该 stage 的内存结果继续传给 downstream；诊断性附属文件写入失败则不修改已验证 domain output，但必须尽可能留下安全 operational warning。

## 3. `StageResult` status invariants

Data Contract 的 `StageResult<T>` 继续是唯一 component-local result envelope。状态必须机械推导，不由实现自由选择。

| Status | Required invariant | Meaning |
|---|---|---|
| `succeeded` | `failures` empty；`outputs` 可 empty | stage 完整执行并满足其 contract；empty 必须由合法空输入或合法零选择产生 |
| `partial` | 至少一个 retained valid output；至少一个 failure | stage 保留了可继续消费的有效工作，同时存在明确 coverage/item/batch/channel failure |
| `failed` | `outputs` empty；至少一个 failure | 当前 stage 没有任何可供 downstream 信任的输出 |

补充 invariant：

- 一个 batch 全部失败、其它 batch 有 valid outputs 时，聚合后的 component stage 是 `partial`，不是 `failed`；
- `failed` 不表示整个 run 必然终止。classifier 可 `failed` 而 writer 继续消费 selected Events；delivery 可 `failed` 而 Brief generation 已成功；
- `partial` 只在 output unit 有 retained value 时成立。collector 的 output unit 是 source-scoped fetched batch，因此 successful source 即使含零条 raw record，也构成 retained output；这不是新的 canonical domain object；
- `succeeded + outputs=[]` 不能来自吞掉 exception。stage 必须能够说明是 empty input、全部 source 正常但无 raw record、或 selector 合法选择零项；
- ItemFailure 只记录本 stage ownership 内的 failure。后序 stage 不复制前序 failures，只由 orchestrator 汇总 run outcome；
- `diagnostic_ref` 只有在安全 artifact 已实际持久化后才可出现；它不影响 status invariant。

允许 `partial` 的 logical stages：collector、normalizer、article_dedup、event_cluster、event_selector、event_classifier、event_writer、delivery。`brief_renderer` 自身是 deterministic atomic projection，不通过静默跳过 invalid Event 形成 renderer-level partial。`llm_gateway` 不新增 StageResult stage enum；它记录单次 physical request 的 success/failure runtime metadata，多个 batches 由调用它的 logical component 聚合进 canonical StageResult。

## 4. Legal empty、partial coverage 与 hard failure

| Runtime case | Stage/run semantics | Brief rule |
|---|---|---|
| 所有 active sources 正常，窗口内没有 raw record / Article | collector source batches succeeded；normalizer 及后序 stages 合法 empty success | selector 不调用 provider并合法选择 0；可生成 `complete` empty Brief |
| selector 对非空 candidate pool 合法返回空集合 | selector `succeeded`、outputs empty、failures empty | 可生成 `complete` empty Brief，前提是其它 generation stage 无 failure |
| 部分 sources technical failure，其余 sources 成功（即使成功 source 为零条） | collector `partial`，保留成功 source batches | 若后续能产生 valid Brief，则 generation_status=`partial` |
| 所有 active sources technical failure | collector `failed` | 阻止 downstream generation；不得创建 Brief |
| selector outer response / provider total failure，无可信 selected output | selector `failed` | 不创建 Brief，不调用 legacy selection |
| selector 有 item failures 且仍有可确定顺序的 valid selections | selector `partial` | 继续；若至少一个 Event written 且 renderer 成功，Brief 为 `partial` |
| writer 对部分 selected Events 失败 | writer `partial` | 只引用 valid written Events，Brief 为 `partial` |
| writer 对所有 selected Events 失败 | writer `failed` | selector 非空时不创建 empty Brief；不得伪装成合法零选择 |

output 数量不是 correctness proxy。合法 empty 由无 failure 的 stage semantics 证明；coverage failure 即使最终 reader-facing events 看似完整，也不得标为 `complete`。

## 5. Component runtime matrix

| Component | Input / output unit | Ownership | Isolation / partial | Retry owner | Downstream / forbidden fallback |
|---|---|---|---|---|---|
| `collector` | one configured source → one source-scoped fetched batch（0..N raw records） | I/O + source boundary | per source；成功 batches 保留；all sources failed 才是 failed | source adapter；见 §11 | 成功 batches 给 normalizer；不得用 cached/legacy feed result 假装本次成功 |
| `normalizer` | one raw record → zero/one Article | deterministic validation/normalization | malformed raw item item-local；valid Articles 保留 | none | valid Articles 给 dedup；不做 content repair、translation 或 guessed fields |
| `article_dedup` | Article stream → exact-deduped Articles | deterministic identity/exact dedup | per Article/duplicate group；clean Articles 保留 | none | 给 clustering；不做 semantic dedup 或 semantic fallback |
| `event_cluster` | deduped Articles → EventCandidates | local semantic model + deterministic membership/identity | per Article / cluster operation where safe；model initialization failure is stage-level；valid candidates保留 | no orchestrator retry by default | 给 selector；不得调用 LLM/legacy cluster fallback |
| `event_selector` | whole report-window EventCandidate pool + referenced Articles → ordered selected Events | LLM editorial selection + deterministic validation | global request with item salvage rules in §7；partial legal | `llm_gateway` per physical selector request | only trustworthy selected Events continue；no keyword ranking/legacy Curator/backfill |
| `event_classifier` | one or batched selected Events + evidence → derived Events with classification | LLM category only + item validation | per event_id；partial legal；failed classification retains selected Event outside stage output | `llm_gateway` per classifier batch | writer may still receive selected Event with `classification=null`; no `other` coercion |
| `event_writer` | one or batched selected Events + evidence; classification optional context → derived Events with writing | LLM three zh-CN fields only + item validation | per event_id；partial legal；prior Event retained | `llm_gateway` per writer batch | only written Events reach renderer；no raw English/placeholder/legacy writer/backfill |
| `brief_renderer` | report slot + ordered valid written Events + Articles + upstream status summary → one Brief + deterministic render artifact | deterministic composition/rendering | atomic renderer result；accepts partial upstream; no item skip inside renderer | none | valid artifact to delivery；no ranking/dedup/classification/translation/fallback |
| `delivery` | one durably persisted canonical report artifact + active channel plan → per-target runtime metadata | filesystem / channel I/O | targets independent；partial legal | each adapter, bounded | no mutation of Brief; one target failure does not undo another |
| `llm_gateway` | one stage-scoped logical request batch → provider envelope or transport failure metadata | transport, timeout, retry, request/response envelope safety, attempt metadata | one physical request has no domain partial；logical component validates items and aggregates batches | owns LLM retry | no new StageResult stage；no selector/classifier/writer business rules or cross-stage repair |
| `orchestrator` | one report slot/run → ordered canonical component StageResults, artifacts and outcomes | sequencing, run identity, checkpoint, status derivation | never discards retained outputs；applies continuation matrix | does not duplicate component/gateway retry | no new StageResult stage；no semantic fallback, hidden ranking/writing or delivery state in Brief |

## 6. Collector、normalizer、dedup 与 cluster

### Collector

- active source 是 failure isolation unit；`ItemFailure.item_id` 使用非敏感 stable source identifier，不能安全定位时为 null；
- source fetch / parse 完整成功后输出 source-scoped batch，batch 可含零条 record；
- A/B/D success、C failure 时 collector 为 `partial`，A/B/D batches 必须保留；
- active sources 全部失败时 collector 为 `failed`；不得把零 raw records 当成正常无新闻；
- source disabled / 未进入本次 active plan 不算 failure；active source 缺配置或输入非法是 `invalid_input`。

### Normalizer

- raw item independently validated；malformed item 产生 `item_validation_failed`，并以 source-local record identity（若安全可得）关联；
- 不因一个 malformed item 丢弃同 source 的其它 records；
- no input 是合法 empty success；非空 input 全部 invalid 则 failed；
- 不生成缺失 source facts，不抓正文，不调用 LLM repair。

### Article dedup

- exact duplicate group 的 deterministic winner 不是 failure；它是正常 dedup output；
- 无法验证 identity / canonical URL 的单个异常 Article 是 item-local failure，clean Articles 继续；
- 不得将异常 Article 自动转成 singleton 或调用 semantic fallback。

### Event cluster

- local semantic model initialization / load failure 使 stage failed，因为没有可信 event membership；不调用 LLM cluster fallback；
- 单个 Article embedding / local validation failure 可 item-local 排除，successful EventCandidates 保留，stage partial；
- 非空 Articles 全部无法形成 valid candidate 时 failed；合法 empty Articles 输入时 succeeded empty；
- similarity threshold、embedding model、vector schema、batch size 和 hardware tuning 不在 canonical runtime contract。

## 7. Selector global semantics

Selector 是一个独立 logical operation，scope 是本次 report window 的完整 valid EventCandidate pool。它可以物理分批传输 only if implementation 能证明全局相对选择仍在一个 logical decision 中；初始 implementation 不应通过独立局部选择 batch 破坏 global comparison。

Provider output 必须先通过 outer envelope validation，再逐 selected item validation：

- outer payload 无法解析、顶层 shape 错误或无法识别 selected collection：整个 selector logical request failed，不能 salvage；
- provider 合法返回空 selected list：succeeded empty，不是 failure；
- unknown `event_candidate_id`、missing/invalid order、malformed item：仅该 item failure；
- duplicate selected ID：该 ID 的所有 occurrences 均 invalid，不猜测保留哪一个；
- duplicate order：共享该 order 的所有 items 均 invalid，不猜测 provider intended order；
- candidate 未出现在 selected list 中是正常未选择，不是 missing output；
- valid items 移除 failures 后按 provider 给出的 unique order 排序，并只做 deterministic contiguous reindex；不改变 relative order，不补入候选；
- 若 outer response 可解析且仍有 valid selections，selector partial；若所有 returned items invalid，selector failed；
- provider total failure或 retry exhausted：selector failed，没有可信 output，不创建 Brief。

Contiguous reindex 是对 surviving explicit order 的机械 canonicalization，不是 semantic repair。禁止从 list position 猜 missing order、从相似 ID 猜 unknown reference、重新 prompt 修 JSON，或调用 Generation 1 selection。

## 8. Classifier / writer item validation

Classifier 与 writer 的 physical response 无论是否 batch，都必须按 `event_id` 独立验证：

- whole envelope unparseable / wrong top-level shape：该 physical batch 的全部 expected event_ids 失败；其它 batches 不受影响；
- duplicate event_id：该 ID 的所有 returned occurrences 失败；
- unknown / extra event_id：extra item 失败且不产生 output；
- missing expected event output：每个 missing ID 各自产生 failure；
- malformed item、invalid category、invalid/non-zh-CN/empty writing field：只使对应 Event 失败；
- valid item 不因同 response 中其它 item 失败而丢弃；
- provider 不得修改 event membership、selection order、provenance 或其它 stage-owned fields；任何 mutation 是该 item validation failure。

Classifier failure **不阻止 writer**。Data Contract 中 classification 与 writing 是由不同 owner 写入的独立 optional derived sections；renderer 不需要 category 才能证明 writing 或 provenance valid。writer 接受 selected Event 与 evidence，classification 仅在存在且 valid 时作为 read-only context。分类失败的 Event 保持 `classification=null`，不得改成 `other`；writer 成功后可成为 written-unclassified Event，并在 renderer presentation 中进入“其他” section。这只是 deterministic display fallback，不创建 classification，也不回写 canonical `other`。该 run 的 Brief 为 `partial`。

Writer failure 保留该 Event 的最后一个 valid selected/classified value，但 failed Event 不进入 Brief。不得使用原文 title/summary 直接 reader-facing fallback，不得生成 placeholder，不调用 legacy writer，也不 backfill 未选择 Event。

## 9. Batch 与 provider request topology

- selector、classifier、writer 是三个独立 logical operations；
- classifier 可在其 stage 内 batch 多个 Events，writer 也可独立 batch；exact batch size 是 tuning；
- 一个 logical stage 可使用一个或多个 physical calls；一个 module 不等于一个 API call；
- v1.0 初始 canonical topology **不允许 cross-stage physical response coalescing**。classifier 与 writer 不共享一个 provider response，因为这会把 independent validation、retry ownership 和 failure artifact 再次耦合成 hidden giant Curator；
- 同 stage 多 batch 时，每个 batch 独立 retry、validation 和 artifact；Batch A exhausted 不删除 Batch B outputs；聚合 stage 有 outputs + failures 即 partial；
- batch retry 重放相同 logical batch/request，不改变 prompt、item membership、order 或 run identity；不把 batch transport failure拆成逐 item provider retry，因为原调用已经以 batch 为 transport unit。

Exact physical call count 不冻结：它受 provider limits、batch size 与 implementation tuning 影响，且不是 domain correctness。长期 contract 只冻结 logical separation、same-stage batching、independent batch recovery 和禁止 cross-stage coalescing。

## 10. LLM timeout / retry / backoff

`llm_gateway` 独占 LLM transport timeout、attempt count、backoff 和 provider status mapping；selector/classifier/writer 不包裹第二层 retry。

Canonical minimum：

- 每个 physical request 的 `maximum_attempts = 2`（一次 initial attempt + 最多一次 ordinary re-request）；
- 每次 attempt 必须有 finite positive timeout；具体秒数由 provider profile/config 冻结并进入 run metadata。Generation 1 的 DeepSeek 90 秒是当前 profile evidence，不作为 provider-independent v1.0 永久值；
- retry 前最多一个 finite configured delay；delay 必须有上限并记录，允许明确配置为 0。Generation 1 provider 当前是 immediate retry；v1.0 不凭空冻结新秒数。具体秒数与是否使用 bounded jitter 属 tuning；不得无限或递归 backoff；
- retryable：transport/network failure、timeout、HTTP 429、HTTP 5xx；
- non-retryable：missing/invalid config或credential、request preflight/size limit、其它 HTTP 4xx、outer response parse/finish failure、schema/item validation、unknown reference、content policy、local model、renderer 与 semantic failure；
- ordinary re-request 必须使用相同 serialized logical request、run/stage/batch identity，并增加 attempt metadata；它不是新 prompt、JSON repair、second LLM stage 或 semantic backfill；
- response 已到达且进入 parse/validation 后，不因 schema/item failure自动 re-request；valid sibling items仍按 §7/§8 salvage。

Collector source adapter 采用独立成熟边界：每 source `maximum_attempts = 2`、每 attempt finite timeout、attempt 间一个 bounded fixed delay；当前 implementation evidence 是 15 秒 timeout / 3 秒 delay。具体数值可在 implementation/config review 调整，但不得取消 finite / bounded invariant。只重试 transient transport/timeout/429/5xx；确定性 parse/schema 与其它 4xx 不进入 repair loop。

Delivery adapter 可对**确定未成功接收**的 transient failure 最多尝试 3 次，延迟 finite/bounded；当前 Bark evidence 是 15 秒 timeout、10/20 秒 delays。若 timeout 等结果无法确认 channel 是否已经接收，且 channel 不支持 idempotency key，则不得自动重复发送；记录 ambiguous failure，留给显式 operator retry。

## 11. Minimal stable failure taxonomy

Stable code 只表达会影响 ownership、retry、downstream 或 operator diagnosis 的类别。细节放在 allowlisted structured diagnostics，不把 human message 塞进 code。

| Code | Owner / typical use | Retry class |
|---|---|---|
| `invalid_input` | any stage；config、canonical input或request preflight invalid | non-retryable |
| `source_fetch_failed` | collector source transport/status/parse exhausted | transient cause 可由 source adapter retry |
| `timeout` | collector / llm_gateway / delivery attempt timeout | bounded retry subject to ambiguity rule |
| `transport_failed` | collector / llm_gateway / delivery network transport | bounded retry |
| `provider_failed` | llm_gateway 429/5xx exhausted或non-retryable provider status | 429/5xx bounded；其它 non-retryable |
| `response_parse_failed` | LLM outer envelope/content/finish reason无法可靠解析 | non-retryable |
| `item_validation_failed` | normalizer/dedup/selector/classifier/writer item schema/enum/field invalid或missing/duplicate output | non-retryable |
| `unknown_reference` | provider引用未知 candidate/event/article ID | non-retryable |
| `local_model_failed` | event_cluster local model init/inference failure | non-retryable in run |
| `render_failed` | brief_renderer deterministic composition/serialization failure | non-retryable in run |
| `persistence_failed` | canonical checkpoint/report atomic persist failure | non-retryable in run |
| `delivery_failed` | active downstream channel failure after adapter policy | adapter-specific bounded retry |

对于 source fetch，使用最具体 root-cause code：timeout 用 `timeout`，network transport 用 `transport_failed`；`source_fetch_failed` 只用于其它 source HTTP/parse failure exhausted。`duplicate_id`、`missing_output`、`invalid_category` 等属于 diagnostic reason/path，不升级为新的 stable code。Provider HTTP status、attempt、batch ID 和 safe stage path 属 runtime metadata。Authorization header、credential value、raw provider error body、unbounded exception text、raw prompt/response 不得进入 ItemFailure 或 diagnostics。

## 12. Orchestrator continuation matrix

| Stage outcome | Continuation |
|---|---|
| collector failed | stop generation；no Brief |
| normalizer / dedup / cluster partial with outputs | continue with retained outputs；run carries generation degradation |
| normalizer / dedup / cluster failed after non-empty upstream | stop generation；no Brief |
| legal empty reaches selector | short-circuit selector/classifier/writer as succeeded empty without provider call；render legal empty Brief |
| selector partial with valid outputs | continue selected outputs |
| selector failed | stop generation；no Brief |
| classifier partial/failed | continue all selected Events to writer；valid classifications attached where available |
| writer partial with valid written outputs | continue only written outputs to renderer |
| writer failed for non-empty selection | stop generation；no Brief |
| renderer failed | no publishable Brief artifact；do not call delivery |
| delivery partial/failed | generation remains complete/partial as already frozen；retain canonical report and successful target results |

Orchestrator 只执行该矩阵、run identity、checkpoint 与 outcome derivation；不拥有 semantic selection、category、writing、legacy fallback 或 retry loop。

## 13. Brief `generation_status`

Renderer deterministic 推导：

- `complete`：collector 到 event_writer 的所有 applicable StageResults 均无 failures，selector 给出合法 result（包括零选择），renderer 成功；
- `partial`：存在任何 retained generation-stage failure / source coverage degradation，但仍满足以下之一：
  - selector 合法选择至少一个 Event，至少一个 Event 已有 valid writing；或
  - selector 合法零选择，但 earlier stage 有 retained partial coverage且该零选择仍可信；
- feed failure 即使剩余 sources 产生了看似完整 Events，Brief 仍是 `partial`；
- classifier 单 item或全部失败而 writer 成功：Brief `partial`，Events 可 `classification=null`；
- writer 部分失败：只引用 successful written Events，Brief `partial`；
- selector succeeded empty 且全部 generation stages无 failure：`complete` empty Brief；
- selector failed无可信 output、non-empty selection 的 writer 全部失败、或 renderer failed：不创建 Brief；不存在 `generation_status=failed` 的 Brief object。

`complete` / `partial` 不由 event quota、选中数量或“每天必须有一份”决定。delivery outcome 不参与 generation_status。

## 14. Renderer semantics

Renderer minimum input：valid report slot、一个 trustworthy selector outcome、按 selection_order 排列的零个或多个 valid written Events、可完整 resolve 的 Articles/provenance，以及 upstream generation outcome summary。

- renderer 接受 upstream partial，并生成 structurally complete 的 partial Brief；
- canonical `Brief.event_ids` 严格保持全局 `selection_order`；Markdown 只在 presentation 层按 canonical category 分区，section 顺序由各 category 的最小 `selection_order` 决定，section 内保持 `selection_order`；
- classification 缺失时在 Markdown 中使用“其他”作为 deterministic display fallback，不创建 category、不写 canonical `other`；
- canonical Event 必须在进入 renderer 前通过 validation。若一个 Event 在 renderer 才暴露 invalid，说明 upstream boundary violation；renderer 不静默跳过该 Event；
- composition / serialization / atomic artifact failure 使 renderer StageResult failed，且不存在 publishable Brief artifact；
- renderer 不 ranking、semantic dedup、classification、translation、writing、legacy fallback 或 delivery。

## 15. Delivery 与 idempotency

Delivery 只在 Brief 与 canonical rendered report artifact 已 atomic durable persist 后执行；artifact persistence 是 renderer/orchestrator checkpoint，不是 delivery channel：

1. canonical report checkpoint失败属于`persistence_failed`，renderer/orchestrator不调用delivery；
2. Obsidian/mobile copy 与 Bark notification 是独立 active targets；一个失败不阻止另一个，也不删除 canonical report；
3. 未配置/disabled optional target 不属于 active plan，记录 `skipped` runtime metadata，不产生 ItemFailure；
4. delivery metadata（channel、destination opaque ref、attempt、status/time、safe response metadata）只进 run artifact，不进 Brief；
5. generation 已成功但 delivery failed 时，保留 Brief、canonical artifact 与成功 channel results；不重新生成、不切换 legacy product。

最小 idempotency key 为 `brief_id + rendered_artifact_digest + channel`；同一 run 的 retries 必须复用。支持 idempotency key 的 adapter 必须传递该 key；不支持时仅对明确未被接收的 failure自动 retry。ambiguous timeout 不自动 resend，防止重复通知。新的 rerun 若 rendered digest 相同，应由 delivery history 检出已成功 target并默认不重复发送；显式 operator resend 必须产生可审计的新 delivery attempt metadata。

本合同不修改当前 Markdown、Obsidian 或 Bark 实现，也不冻结具体 destination path。

## 16. Artifact / diagnostics

复用 canonical data root、path resolver 与现有 atomic artifact pattern，不引入数据库或 observability platform。

### Canonical artifact

- run manifest、StageResult、validated canonical objects与最终 Brief/render artifact按 `run_id` 关联；
- canonical checkpoint 使用 staging + atomic finalization；final artifact immutable，不原地覆盖；
- successful outputs必须在 later stage失败时仍保留；failed item 的 last valid prior-stage object 保留在 prior checkpoint；
- canonical object artifact只包含 Data Contract字段与单一 contract version envelope；runtime metadata不混入 domain schema；
- canonical checkpoint persistence failure产生 `persistence_failed` 并阻止该 output进入 downstream。

### Diagnostic artifact

- 保存 stable code、safe item/source/batch reference、attempt、timing、provider/model identifiers、request/response byte counts和 allowlisted validation path；
- provider request artifact只允许保存经过投影、allowlist 与 secret review 的实际 logical payload；Authorization、credential值和环境内容永不保存；
- provider response只保存通过 allowlist 的 parsed/validated items与 bounded failure diagnostics；failed raw HTTP body、raw exception、unvalidated arbitrary payload不保存；
- `diagnostic_ref` 是 opaque linkage；诊断写入失败不伪造 ref，也不把 secret写进日志补救；
- artifact manager/orchestrator拥有 retention/cleanup。active run中不清理；cleanup只能由独立maintenance policy执行，不由component或delivery顺手删除。具体 retention period属于后续配置治理。

## 17. Pre-cutover / post-cutover fallback

### Pre-cutover

- Generation 1 继续是 reader-facing production；
- v1.0 只以 offline/snapshot、随后 shadow/parallel运行；v1.0 failure 不改变 Generation 1 output、routing、Bark或Obsidian；
- current no-argument digest rollback与legacy surface继续保留，直到v1.0 cutover后另行retirement audit。

### Post-cutover

- valid `complete` 或 `partial` v1.0 Brief且canonical artifact已durable persist时可以发布；partial必须在artifact/observability明确记录degradation，不伪装complete；
- 没有valid Brief时不发布新的Morning Brief，不覆盖或删除历史report；记录generation failure并触发既有operational diagnosis/alert边界；
- delivery failure只重试eligible channel，不重新运行semantic stages，不改变Brief generation status；
- **不存在automatic legacy semantic fallback**：不调用Generation 1 keyword ranking、legacy category、whole-layer Curator、NewsItem writer或raw English rendering；
- rollback到Generation 1只能是cutover治理层的显式、人工、可审计routing decision，不是单个run内automatic fallback。

该边界防止Generation 1已知的semantic duplicate、misclassification与language leakage重新进入v1.0。

## 18. Frozen vs implementation tuning

### Canonical freeze

- run identity/lifecycle、StageResult invariant、legal empty与hard failure区别；
- per-component isolation/continuation、selector salvage boundary、classifier/writer item-local validation；
- classifier failure不阻止writer、no raw/legacy/category fallback；
- same-stage batching、independent batch retry、no cross-stage coalescing；
- finite timeout、bounded attempts/backoff、retryability classes；
- minimal failure taxonomy、Brief status derivation、renderer/delivery/artifact/fallback semantics。

### 留给 implementation/config tuning

- Python module/package layout、exact batch size与physical call count；
- selector/classifier/writer prompt、provider/model migration、token budget；
- embedding model/vector schema/similarity threshold；
- provider-specific timeout秒数、bounded delay秒数/jitter与delivery destination；
- artifact filenames、retention period、logging backend与dashboard；
- future optional Market capability。

## 19. Explicit exclusions 与 next action

本次未实现任何 v1.0 module、schema、retry、fallback或delivery behavior；未拆`main.py`，未修改CandidateArticle/CuratedEvent/prompt/provider/feed/shell/plist/routing，未安装embedding dependency，未调用RSS、DeepSeek、Bark、Obsidian或production pipeline，未写runtime data，未删除legacy/tests。

Architecture Freeze、READ-ONLY Dependency Audit、Core Data Contract Freeze与本Runtime / Failure Contract Freeze均已完成。v1.x implementation roadmap 已冻结；下一步唯一任务是：

```text
v1.1 — Canonical Domain & Runtime Foundation
```

该任务不重新打开本合同；本文件只提供 runtime / failure constraints，不实现 v1.1。
