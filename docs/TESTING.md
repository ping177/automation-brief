# Testing

本文记录 automation-brief 的测试命令、smoke checklist 和验收习惯。根据改动类型选择最小必要检查，不为 docs-only 任务运行不必要的业务链路。

## Docs-only 验证

仅修改 Markdown 文档时，通常运行：

```bash
git diff --check
git status --short
```

`git diff --check` 用于检查尾随空格、空白错误和 patch 格式问题。docs-only 改动不需要跑 Python 编译、RSS 健康检查或真实日报生成，除非文档改动同时暴露出需要验证的运行假设。

## v1.0 Architecture Freeze docs-only checklist

v1.0 freeze 的验证只检查治理合同，不启动任何业务 pipeline：

- `v1.0 — Event-driven Morning Brief` 是唯一新的 numeric product-generation token；不得将 `v1.0-alpha`、`v1.0-beta` 或新的 Phase A/B/C 用作 version token。
- canonical architecture doc 覆盖 Article → EventCandidate → Event → Brief 生命周期、collector / normalizer / article dedup / event cluster / selector / classifier / writer / renderer / delivery / orchestrator / gateway 职责，以及 provenance、local failure、Holdings / Market 边界。
- v0.7.3 baseline 和现有 production routing 保持可运行；v0.7.4 历史记录保留并标记为 superseded / replaced by v1.0 plan。
- 本轮不运行 RSS、DeepSeek、Bark、Obsidian、launchd、pmset 或生产晨报。

## v1.0 Core Data Contract Freeze docs-only checklist

- canonical contract 只存在于 `EVENT_DRIVEN_MORNING_BRIEF_DATA_CONTRACT.md`；architecture/Decisions/Project State 只做摘要和链接，不复制竞争 schema。
- Article → EventCandidate → selected Event → classified and/or written Event → Brief 的 producer-consumer chain 闭合，所有 provenance ID 均可 deterministic 回取 Article。
- deterministic-owned Article identity/source/URL/time 与 LLM-owned selection/category/writing 无重叠 write authority。
- Event 使用一个 immutable derived lifecycle，不复制三套 Event schema；selector 不输出 score/importance tier，category 不影响 selection，writer 只输出三项简体中文文本。
- Core Data stage 只冻结 StageResult envelope；timeout、retry、batch、provider recovery、artifact 与 production fallback 后续由 Runtime / Failure Contract 冻结，不回写 domain schema。
- Holdings、Market data/context、watch point 和 speculative full content 不进入 v1.0 core；没有修改 Python、config、dependency、prompt、shell、plist 或 production routing。

## v1.0 Runtime / Failure Contract Freeze docs-only checklist

- 唯一 canonical runtime contract 是 `EVENT_DRIVEN_MORNING_BRIEF_RUNTIME_CONTRACT.md`；其它治理文档只做摘要和链接。
- StageResult 必须满足：succeeded = no failures；partial = retained output + failure；failed = no output + failure。合法 empty success 由无 failure 的 stage semantics 证明。
- collector per-source、normalizer/dedup/cluster item-local、selector global-with-safe-salvage、classifier/writer event-local、delivery per-target 的 failure boundary 不互相扩散。
- classifier failure 不阻止 writer；classification 保持 null，不自动改为 `other`。writer failure 不使用 raw English、placeholder、legacy writer 或 backfill。
- selector/classifier/writer logical boundary 与 physical API call 分离；只允许 same-stage batching，禁止 cross-stage response coalescing；一个 batch failed 不删除其它 batch outputs。
- LLM physical request 最多两次 bounded attempts；parse/schema/item failure 不进入 repair stage。具体 provider timeout秒数、batch size、prompt/model/embedding threshold仍是 implementation/config tuning。
- Brief complete/partial只从generation stages推导；renderer failure不创建failed Brief；delivery failure不污染generation_status。
- post-cutover没有automatic Generation 1 semantic fallback；pre-cutover Generation 1 production与legacy surface保持不变。
- 检查 Architecture ↔ Data ↔ Runtime producer/consumer、ownership与fallback一致性；检查没有Python/config/prompt/feed/shell/plist/runtime-data改动或真实外部调用。

## v1.x Implementation Version Roadmap Freeze docs-only checklist

- `v1.0` governance baseline、`v1.1 — Canonical Domain & Runtime Foundation`、`v1.2 — Deterministic Ingest`、`v1.3 — Event Clustering`、`v1.4 — Event Selector`、`v1.5 — Event Classifier + Writer`、`v1.6 — Renderer + Artifacts + Orchestrator Integration` 与 `v1.7 — Offline / Snapshot Validation` 均为 `COMPLETED / CLOSED`；v1.5 的三段实现、offline regression 与最终 real-provider acceptance 已完成，v1.6 implementation acceptance、v1.7 offline full-pipeline E2E 与最终 Human Reader-Facing Acceptance 均 PASS。
- `v1.0 → v1.1 → v1.2 → v1.3 → v1.4 → v1.5 → v1.6 → v1.7 → v1.8 → v1.9 → v1.10` 与 `docs/DECISIONS.md` canonical roadmap 一致；不新增 alpha/beta/Phase version token。
- `v1.9.1` 是 v1.9 之后的 numeric classifier corrective，已 COMPLETED / CLOSED；单独记录 implementation/validation 状态，不改变上述 v1.0→v1.10 milestone 顺序，也不表示 v1.10 已开始。
- v1.3 已冻结 E5-small immutable revision、`article-title-summary-v1`、summary cap 300、threshold `0.91`；v1.6/v1.7 不做 production cutover；v1.8 不发送 reader-facing v1.x output；v1.9 不启用 automatic Generation 1 semantic fallback；v1.10 才执行 post-cutover consumer audit 与 legacy retirement。
- Generation 1 在 v1.8 shadow 前后作为正式 baseline；v1.9 cutover 完成后仅保留为 explicit human-approved rollback route。Market 不属于 v1.x core，Holdings 不进入 v1.x。
- roadmap freeze 当时不修改三份 v1.0 canonical contract semantics、不创建 v1.1 Python module、不运行业务 pipeline 或真实外部 API；后续 v1.1 implementation verification 见下节。

## v1.1 Canonical Domain & Runtime Foundation verification

v1.1 的实现验证保持离线、side-by-side，不启动 collector、provider、delivery 或现有 production route：

```bash
PYTHONPYCACHEPREFIX=/private/tmp .venv/bin/python -m py_compile canonical_domain.py tests/offline_canonical_domain_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_canonical_domain_smoke.py
```

`offline_canonical_domain_smoke.py` 覆盖 Article URL/linkless identity、canonical URL、timezone-aware UTC、naive datetime reject、EventCandidate membership identity/duplicate policy、Event 四种 lifecycle（包括 `written-unclassified`）、全部 9 个 category、Brief report-slot identity 与 inclusive window、StageResult succeeded/partial/failed invariants、全部 12 个 `ItemFailure` code、optional sections 和 deterministic serialization round-trip。v1.1 不新增 Run entity；`run_id` 仍属于 runtime metadata。实现不读取 `.env` 或 holdings，不调用 RSS/DeepSeek/Bark/Obsidian，不修改 Gen1 production behavior、production routing、legacy artifacts 或 frozen contracts。

完成 canonical smoke 后，应继续运行既有 Gen1 regression / governance checks，确认 `CandidateArticle`、`CuratedEvent`、AI Curator、artifacts、Morning Brief routing 和 Project-State Push Gate 未受影响；这些测试仍使用临时 fixture，不读取真实 secrets 或 runtime holdings。

## v1.2 Deterministic Ingest verification

v1.2 保持 side-by-side、offline-only，不接管 `main.py` production routing，不调用真实 RSS/API，不创建正式 orchestrator。source-scoped batch 是 collector 的唯一 raw boundary；成功但 0 entries 的 source 仍保留为空 batch，以便 mixed source success/failure 表达合法 `StageResult.partial`。

```bash
PYTHONPYCACHEPREFIX=/private/tmp/automation-brief-pyc .venv/bin/python -m py_compile canonical_domain.py collector.py normalizer.py article_dedup.py tests/offline_deterministic_ingest_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_deterministic_ingest_smoke.py
```

离线 smoke 覆盖：active `feeds.json` 的 name / URL / language-only projection；source success/failure isolation、malformed feed、timeout、all-success empty batch、aware UTC `collected_at`；canonical URL/tracking normalization、linked/linkless Article、naive/malformed timestamp fail-closed、language/summary/text cleanup；以及只按 canonical URL / stable article ID 的 exact first-valid dedup、stable ingest order、相似标题/不同 URL 保留和完整 collector → normalizer → dedup 组合。

v1.2 implementation note `docs/V1.2_DETERMINISTIC_INGEST_SPEC.md` 不是第四份 canonical contract；Article、StageResult、identity、URL、datetime 和 runtime semantics 仍以三份 frozen v1.0 contract 与 `canonical_domain.py` 为准。collector production fetch path 只委托既有 `main.parse_feed_with_retry`，因此 bounded retry / timeout infrastructure 未复制、未改变；所有 acceptance fetcher 均为 fake/local fixture。

## v1.3 Event Clustering verification

v1.3 保持 side-by-side、offline-only，输入 canonical `Article[]`，输出
`EventCandidate[]`；不接管 `main.py`，不调用 RSS、DeepSeek、Bark 或
Obsidian。普通 regression 不导入或下载 Sentence Transformers：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/automation-brief-v13-pyc .venv/bin/python -m py_compile event_cluster.py scripts/evaluate_event_clustering.py tests/offline_event_cluster_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_event_cluster_smoke.py
```

Smoke 使用 deterministic fake embeddings，覆盖 empty / singleton、同一 story bundle
跨语言、相同关键词负例、broad-topic separation、connected-components
chaining risk、输入顺序与重复运行确定性、canonical fields、bounded
diagnostics，以及 item validation / model initialization / embedding /
global similarity failure semantics。

`tests/fixtures/event_clustering_v1_3.json` 的 labeled cases 分为
calibration / held-out，并显式标注 `production-relevant`、`robustness-only` 或
`outside-normal-window`。`scripts/evaluate_event_clustering.py` 只在显式本地
模型验证时运行，要求不可变 40 位 model commit SHA，报告相似度分布、
precision / recall / F0.5、overmerge / split、expected/actual memberships、
按 acceptance class 分组的 gate 和重复运行稳定性。真实模型路径不属于普通
offline regression。

v1.3 production acceptance 使用修正后的产品判断：在同一约 24h
Morning Brief report window 内，reader 是否应把这些 Articles 作为一条
story 阅读，而不是要求严格同一 atomic occurrence。A 类为
production-relevant cases（announcement/reaction/follow-up、gun/share/reverse-repo
negatives、same-window broad-topic distinct events）；B 类为 useful synthetic
robustness（Treasury cross-language、chaining）；C 类为 invalid / overly strict
event-identity assumption（正常 report window 不会共现的 temporal Iran sanctions
early/later pair 不作为 production critical hard-negative gate）。不修改 fixture
事实标签。v1.3 仍限定为 local embedding + semantic similarity + simple
deterministic clustering，不使用 LLM。最终接受配置为 E5-small immutable revision
`614241f622f53c4eeff9890bdc4f31cfecc418b3`、`article-title-summary-v1`、summary cap
300、threshold `0.91`；production-critical overmerge / split 为 `0 / 0`，
production precision / recall / F0.5 为 `1.0 / 1.0 / 1.0`，expected
memberships `8 / 8` exact。Treasury split 与 temporal Iran merge 分别保留为
robustness limitation 与 outside-window observation。

## v1.4 Event Selector verification — COMPLETED / CLOSED

v1.4 已完成并 CLOSED，保持 side-by-side、offline-capable，不接管 `main.py` 或 Generation 1
production routing。Selector 的 provider-facing projection 只包含允许的 Event/article
context；response contract 保持严格 `selected: [{event_candidate_id, order}]`，outer
contract failure 不做 salvage，item-level malformed / unknown / duplicate 仍做安全
item-local salvage。quality runner 默认 dry-run，不读取 credentials、不访问网络、不持久化
provider response；真实 provider validation 只能由用户显式运行。

```bash
for f in tests/offline_*.py; do
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$f" || exit 1
done
PYTHONPYCACHEPREFIX=/private/tmp/automation-brief-v14-pyc .venv/bin/python -m py_compile \
  event_selector.py llm_gateway.py scripts/evaluate_event_selector.py \
  tests/offline_event_selector_smoke.py tests/offline_event_selector_quality_smoke.py \
  tests/offline_llm_gateway_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/evaluate_event_selector.py
```

real-provider quality validation 的接受门槛为多次 runs 均 succeeded、must-include 全部
覆盖、should-omit 不被凑数选入，且 judgment-call 允许合理波动；3/3 runs、4/4
must-include、3/3 should-omit 已通过。Selector 不设固定评分、类别配额、来源权重或
固定选取数量。

## v1.5 Slice 1 Event Classifier verification — COMPLETED

Classifier 保持 side-by-side、offline-only，不接管 `main.py` 或 Generation 1 production
routing，不调用真实 DeepSeek。physical batch size 固定为 1；projection、strict
`classifications` response validation、9-category vocabulary 和 event-local failure
semantics 均由离线 fake gateway 验证。Writer、renderer、artifacts、orchestrator 和
production integration 不属于本 Slice。

Classifier semantic regression additionally verifies that an Event with no naturally
matching specific category can successfully return canonical `other`; semantic uncertainty
is not a failure, while an unknown provider category remains an item validation failure.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_event_classifier_smoke.py
PYTHONPYCACHEPREFIX=/private/tmp/automation-brief-v15-classifier-pyc .venv/bin/python -m py_compile \
  event_classifier.py tests/offline_event_classifier_smoke.py
PYTHONPYCACHEPREFIX=/private/tmp/automation-brief-v15-classifier-pyc .venv/bin/python -m compileall -q -f \
  canonical_domain.py event_selector.py llm_gateway.py event_classifier.py \
  tests/offline_event_classifier_smoke.py
```

本 Slice 还应运行全部 `tests/offline_*.py`、`tests.test_project_state_push_gate` 与
`git diff --check`；验证不得读取 secrets、写入 runtime data/cache、调用真实 provider
或修改 frozen contracts。

显式 real-model acceptance command（需要预先存在的可写本地 model cache）为：

```bash
AUTOMATION_BRIEF_MODEL_CACHE=/path/to/writable-cache \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.venv/bin/python scripts/evaluate_event_clustering.py \
  --cache-folder "$AUTOMATION_BRIEF_MODEL_CACHE" --local-files-only \
  --threshold-start 0.70 --threshold-stop 0.95 --threshold-step 0.01 \
  --accepted-threshold 0.91
```

未设置 `AUTOMATION_BRIEF_MODEL_CACHE` 时，evaluator 默认使用 canonical data root
下的 `runs/model-cache`；该路径只用于本地 runtime，模型文件和 cache 不提交。

## v1.5 Slice 2 Event Writer verification — COMPLETED

Writer 保持 side-by-side、offline-only，不接管 `main.py` 或 Generation 1 production
routing，不调用真实 DeepSeek。physical batch size 固定为 1；projection 包含完整 Article
provenance、canonical member order、可选 category（unclassified 为 `null`）和固定
`target_language=zh-CN`；strict `writings` response validation、最小 CJK gate、
classified/unclassified lifecycle 与 event-local failure semantics 均由离线 fake gateway
验证。不得使用 raw English、legacy writer、placeholder、backfill 或 whole-layer fallback。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_event_writer_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_event_classifier_smoke.py
PYTHONPYCACHEPREFIX=/private/tmp/automation-brief-v15-writer-pyc .venv/bin/python -m py_compile \
  event_writer.py tests/offline_event_writer_smoke.py
PYTHONPYCACHEPREFIX=/private/tmp/automation-brief-v15-writer-pyc .venv/bin/python -m compileall -q -f \
  canonical_domain.py event_selector.py llm_gateway.py event_classifier.py event_writer.py \
  tests/offline_event_writer_smoke.py
```

本 Slice 还应运行全部 `tests/offline_*.py`、`tests.test_project_state_push_gate` 与
`git diff --check`；验证不得读取 secrets、写入 runtime data/cache、调用真实 provider
或修改 frozen contracts。Slice 3 continuation regression 已在下一节完成。

## v1.5 Slice 3 Classifier → Writer Continuation Regression — COMPLETED

新增独立 `tests/offline_event_classifier_writer_continuation_smoke.py`，只在测试内按原
selected Event 顺序将 classifier 成功输出与未分类的原 Event 组合后传给 Writer；不新增
production orchestration helper。回归覆盖 classifier partial、classifier all-failed 仍继续
Writer、`written-unclassified`、Writer failure event-local，以及两个 StageResult 相互独立。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_event_classifier_writer_continuation_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_event_writer_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_event_classifier_smoke.py
PYTHONPYCACHEPREFIX=/private/tmp/automation-brief-v15-slice3-pyc .venv/bin/python -m py_compile \
  event_classifier.py event_writer.py tests/offline_event_classifier_writer_continuation_smoke.py
PYTHONPYCACHEPREFIX=/private/tmp/automation-brief-v15-slice3-pyc .venv/bin/python -m compileall -q -f \
  canonical_domain.py event_selector.py llm_gateway.py event_classifier.py event_writer.py \
  tests/offline_event_classifier_smoke.py tests/offline_event_writer_smoke.py \
  tests/offline_event_classifier_writer_continuation_smoke.py
```

本 Slice 还应运行全部 `tests/offline_*.py`、`tests.test_project_state_push_gate` 与
`git diff --check`；验证不得读取 secrets、写入 runtime data/cache、调用真实 provider
或修改 frozen contracts。v1.5 real-provider acceptance 记录见下一节；v1.6 closeout 已完成，下一步为 v1.7 Offline / Snapshot Validation。

## v1.5 real DeepSeek Classifier + Writer quality acceptance — COMPLETED / CLOSED

新增 validation-only `scripts/evaluate_event_classifier_writer_quality.py` 与
`tests/fixtures/event_classifier_writer_quality_v1_5.json`，fixture 包含 6 个已选中的
synthetic Event bundle（每个 2 篇 Article）和人工 classification review note。runner
按 `selected Events → event_classifier.classify_events() → test-local frozen continuation
→ event_writer.write_events()` 执行；classifier failure 使用 available classified output，
否则保留 original selected Event。输出只包含每个 Event 的安全 stage status、category、
三项 writing 字段和 canonical failure code，不持久化 request/response，不输出 API key 或
Authorization header。默认 dry-run 使用 no-network fake gateway；只有显式 real-provider
opt-in 才调用既有 OpenAI-compatible gateway，且仍不接入 production routing。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_event_classifier_writer_quality_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/evaluate_event_classifier_writer_quality.py
```

首次真实 DeepSeek validation 的 classifier/writer 均 succeeded，6/6 Events written，
0 technical failures；Classifier quality、Event synthesis 和整体中文质量 PASS。
`why_it_matters_zh` 的唯一真实问题是面向读者的建议与 evidence 之外的推测。
Writer prompt 已做最小修正：只允许 supplied Article evidence 直接支持的具体意义，
并禁止直接称呼读者、个人建议、超出 evidence 的推测与通用 meta-language。offline
regression 只检查 prompt intent，不对模型输出做 deterministic advice detection。

用户后续应在自己的 Terminal 环境准备 `AUTOMATION_BRIEF_CURATOR_API_KEY`（沿用项目
`.env.local` 的既有 process-env-first 使用方式）后，显式执行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/evaluate_event_classifier_writer_quality.py \
  --real-provider deepseek
```

本 harness 不做自动中文质量评分、LLM judge、rule-based writing score 或 benchmark；
真实结果由人工审阅 fixture note、category、三项中文写作和技术 failure。最终
revalidation 使用 `deepseek` / `deepseek-v4-flash`：classifier stage 与 writer stage 均为
`succeeded`，6 个 Event 全部写出，classifier 与 writer technical failures 均为 0；分类
结果合理且无 `other` 滥用，Event-level synthesis、中文可读性与 evidence grounding 均
通过。首次 `why_it_matters_zh` 的读者导向建议问题已通过最小 prompt correction 解决，
revalidation 未发现 release blocker。v1.5 标记为 `COMPLETED / CLOSED`；v1.6
`Renderer + Artifacts + Orchestrator Integration` 与 v1.7 `Offline / Snapshot Validation`
均已完成 implementation acceptance、offline full-pipeline E2E 与 Human Reader-Facing
Acceptance，并标记为 `COMPLETED / CLOSED`；下一步为 `v1.8 — Shadow / Parallel Validation`。

## v1.7 Offline / Snapshot Validation — COMPLETED / CLOSED

v1.7 的 gate 是 deterministic offline / snapshot regression，不是 benchmark、评分系统或真实 provider 自动测试。完整 Generation 2 pipeline 由 fixed report slot、fixture-backed embeddings、fake selector/classifier/writer gateways、fake feed fetcher 和 temporary artifact root 驱动；`cluster` metadata 仅供 test harness 建立 embedding lookup，不能进入 RawFeedEntry 或 canonical Article，clustering 仍调用 production `event_cluster`。

最小 fixture matrix 覆盖 representative clean morning、合法 empty、partial degradation、hard-stop failure 与 malformed/provider protocol。Snapshot / structural assertions 锁定 clustering membership、selector salvage/order、classifier category vocabulary 与 invalid-category failure、writer lifecycle、classifier → writer continuation、Brief/Markdown projection、source dedup/provenance、checkpoint/artifact inventory、diagnostic durability、empty/partial/hard-stop outcome 以及 no-backfill/no-legacy-fallback 边界；真实 LLM 自然语言和 judgment-call 不做 brittle exact snapshot。

最终 reader-facing contract 已人工 PASS：Markdown 无 `## 今日要闻`，category 使用 `## *Category*`，Event title 使用 `###` + bold + `var(--text-accent)`，正文使用 `摘要：` / `为什么重要：`，来源使用 Obsidian-compatible `<details>/<summary>/<ul>/<li>/<a>`。category regroup/order、canonical global `Brief.event_ids`、written-unclassified display fallback 与 surviving provenance 保持不变。

最终 v1.7 verification：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_brief_renderer_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_orchestrator_smoke.py
for f in tests/offline_*.py; do
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$f" || exit 1
done
PYTHONPYCACHEPREFIX=/private/tmp/automation-brief-v17-closeout-pyc .venv/bin/python -m py_compile \
  canonical_domain.py collector.py normalizer.py article_dedup.py event_cluster.py \
  event_selector.py event_classifier.py event_writer.py brief_renderer.py v1_artifacts.py \
  orchestrator.py llm_gateway.py tests/offline_brief_renderer_smoke.py \
  tests/offline_orchestrator_smoke.py
PYTHONPYCACHEPREFIX=/private/tmp/automation-brief-v17-closeout-pyc .venv/bin/python -m compileall -q -f \
  canonical_domain.py collector.py normalizer.py article_dedup.py event_cluster.py \
  event_selector.py event_classifier.py event_writer.py brief_renderer.py v1_artifacts.py \
  orchestrator.py llm_gateway.py tests
sh -n .githooks/pre-push
sh -n scripts/check-project-state-push.sh
sh -n scripts/install-git-hooks.sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_project_state_push_gate
git diff --check
```

本验证共运行 28 个 `tests/offline_*.py`；不联网、不调用 RSS/DeepSeek/其它真实 provider、不读取 secrets、不写入 canonical runtime data。v1.7 保持 side-by-side，Generation 1 继续作为 production baseline；下一步为 v1.8 Shadow / Parallel Validation。

## v1.8 Generation 2 manual runtime verification — COMPLETED / CLOSED

本轮自动验证只使用 fake fetcher/embedder/gateway 与 temporary data root；不得调用真实 RSS、DeepSeek、Bark、Obsidian 或 production delivery：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_generation_2_runtime_smoke.py
for f in tests/offline_*.py; do
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$f" || exit 1
done
PYTHONPYCACHEPREFIX=/private/tmp/automation-brief-v18-pyc .venv/bin/python -m py_compile \
  collector.py generation_2_runtime.py scripts/run_generation_2_shadow.py \
  scripts/evaluate_event_selector.py scripts/evaluate_event_classifier_writer_quality.py \
  tests/offline_generation_2_runtime_smoke.py
git diff --check
```

runtime smoke 必须证明固定 08:00 canonical report slot 与 manual rolling-24h slot 均 deterministic/invalid fail closed；rolling slot 以当前 Asia/Shanghai aware 时间为 `window_end`、精确向前 24 小时为 `window_start`，并与 `--date` 互斥，不改变未来 production 的固定 08:00 规则。RSS first-attempt success、timeout/HTTP 429/5xx retry、HTTP 404 和 deterministic bozo/parse failure 不 retry，且 failure taxonomy 与 allowlisted attempt/HTTP status/bounded timing diagnostics 正确。formal builder happy path 必须实际初始化 frozen model/revision 的 pinned local cache并复用 embedder；missing cache、wrong-but-nonempty cache 或 pinned snapshot 不可加载都必须在 external collection 前 fail closed，且始终使用 `local_files_only=True`。fake dependencies 可完整生成 artifact，不 import/call Gen1 semantic fallback 或 Bark/publisher/Obsidian delivery，不写 `reports/`，artifact 只落 `<temp-data-root>/runs/event-driven-morning-brief/<run_id>/`。真实 provider run 仅由用户在 Terminal 显式执行 `scripts/run_generation_2_shadow.py --real-provider deepseek --date YYYY-MM-DD` 或互斥的 `scripts/run_generation_2_shadow.py --real-provider deepseek --as-of-now`；API key 只读当前 process env。

v1.8 acceptance 的最小真实门槛是至少一次有效 rolling-24h Gen2 run，并由用户完成 reader-facing 人工验收；该门槛已满足，用户确认最终 reader-facing Brief 可接受。v1.8 不做自动胜负判断、benchmark、dashboard 或 comparison platform。

source freshness acceptance 必须覆盖：全 timestamp snapshot 正常通过；300 条全 timestamp-null snapshot 整个排除并留下 bounded diagnostic；被排除条目不进入 clustering；同一 run 的 timestamped sibling source 不受影响。该测试不将 `collected_at` 或 URL 当作 publication evidence，不调用 Gen1 semantic path 或 production delivery。

clustering corrective acceptance 必须以同一 pinned local model/cache 分别运行历史 `event_clustering_v1_3.json` 与独立 `event_clustering_v1_8_corrective.json`。原 production expected memberships 必须保持 `8/8 exact`；新 fixture 的 3 个 hard negatives 必须全部拆分、2 个 positive counterexamples 必须保持聚合，共 `8/8 exact`；两者 repeat deterministic。offline smoke 另锁定 NFKC、casefold、Unicode `str.isalnum()` 与 4-character contiguous span 边界。

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python \
  scripts/evaluate_event_clustering.py --local-files-only \
  --fixture tests/fixtures/event_clustering_v1_3.json \
  --thresholds 0.91 --accepted-threshold 0.91
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python \
  scripts/evaluate_event_clustering.py --local-files-only \
  --fixture tests/fixtures/event_clustering_v1_8_corrective.json \
  --thresholds 0.91 --accepted-threshold 0.91
```

v1.8 closeout 还保留以下产品边界：Event Clustering 不追求理论上的 100% 同事件识别；只有长期真实使用中反复出现明显 duplicate、overmerge 或不可接受 split 时才重新打开 clustering，不为低概率边缘 case 持续调 threshold、projection 或叠加规则。Gen1 production routing、schedule、Bark/Obsidian delivery 与三份 frozen Architecture/Data/Runtime contracts 不在本 milestone 内修改。

## v1.9 Slice 2 Explicit Production Routing — COMPLETED

本轮只验证 checked-in `generation_2` route，不执行真实 production activation，不修改或 reload installed LaunchAgent：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_production_routing_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_generation_2_production_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_generation_2_runtime_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_orchestrator_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_v1_artifacts_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_project_state_push_gate
sh -n scripts/run_daily_digest.sh
plutil -lint scripts/com.ping.automation-brief.daily.plist.example
git diff --check
```

routing smoke 必须证明：显式 `generation_2` 先调用 `run_generation_2_production.py`，仅在其成功后调用既有 `overnight_brief` publisher/Bark contract；adapter failure 立即返回非零且不调用 publisher、Bark、`main.py` 或 Gen1 fallback。`overnight_brief` legacy route、process-env-first / `.env.local` API-key inheritance 与 plist example 的 `generation_2` token 均保持可验证。测试只使用临时 repo/data root、fake Python 和 fixture，绝不读取或打印真实 secrets，也不联网。

## v1.9 Slice 3 Delivery Seam Compliance — COMPLETED

本轮只验证显式日期与 delivery failure policy，不执行真实 production activation，不修改或 reload installed LaunchAgent：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_production_routing_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_generation_2_production_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_generation_2_runtime_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_orchestrator_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_v1_artifacts_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_project_state_push_gate
sh -n scripts/run_daily_digest.sh
plutil -lint scripts/com.ping.automation-brief.daily.plist.example
git diff --check
```

focused routing smoke 必须证明：`generation_2` 只解析一次 Asia/Shanghai report date，并将相同日期传给 adapter、publisher 和 Bark；invalid/missing dated report fail closed；publisher/Bark 四种独立结果均被尝试并聚合为最终 exit；adapter failure 仍在 delivery 前短路；Bark explicit-date ambiguous timeout 与无法可靠确认送达的 transport failure 只尝试一次且返回明确 failure，HTTP 429/5xx 保留 bounded retry；日志不泄露 token、Authorization、API key 或 secret-bearing URL。legacy `overnight_brief` route 保持可用，测试只使用临时 data root、fake transport 和 fixture，不联网。

## v1.9 Slice 4 Full Offline Acceptance — PASS

本 Slice 是进入受控 activation 前的完整离线 release gate，不新增 production 功能，不修改或 reload installed LaunchAgent，也不调用真实 provider、RSS、Bark 或 Obsidian：

```bash
set -eu
for test_file in tests/offline_*.py; do
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$test_file"
done
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_project_state_push_gate
PYTHONPYCACHEPREFIX=/private/tmp/automation-brief-slice4-pyc .venv/bin/python -m py_compile *.py scripts/*.py tests/*.py
PYTHONPYCACHEPREFIX=/private/tmp/automation-brief-slice4-compileall .venv/bin/python -m compileall -q -- *.py scripts tests
sh -n scripts/run_daily_digest.sh
plutil -lint scripts/com.ping.automation-brief.daily.plist.example
git diff --check
```

Acceptance 必须覆盖完整 checked-in chain：`generation_2` → production adapter → finalized artifact → canonical report → mobile/Obsidian publisher → Bark；complete、partial、legal empty、hard failed outcome；manifest/run identity、finalized-only、digest/collision、atomic publication；Asia/Shanghai date handoff 与 invalid/missing dated report；四种 delivery exit matrix；Bark timeout/transport no-resend、HTTP 429/5xx bounded retry、unexpected failure safe diagnostics；process-env-first、missing-key fail closed、no-Gen1 fallback、legacy `overnight_brief` route 和 08:00 plist contract。全部测试使用临时 fixture/data root，不读取真实 secret、不联网、不写真实用户目录。

### Slice 5 Controlled Production Activation（activation 已应用；第一次 scheduled acceptance PASS WITH ACCEPTED DEGRADATION）

- [x] 将 installed LaunchAgent route 人工切换为 `generation_2`，确认 label、working directory、日志路径和 08:00 schedule 不变。
- [x] 确认 scheduled environment 可安全获得 `AUTOMATION_BRIEF_CURATOR_API_KEY`，不写入 plist、命令行或日志。
- [x] 确认冻结 embedding model cache 存在，并可由 LaunchAgent 用户读取；以 `local_files_only=True` 初始化，不重新下载模型。
- [x] 使用 `launchctl bootout` / `bootstrap` reload 并确认 loaded waiting state；`runs = 0`，未 kickstart、未手动生成、未提前创建当日报告。
- [x] 等待 08:00 scheduled run，确认 LaunchAgent 实际触发且 exit 状态可审计。
- [x] 确认实际调用 `generation_2` route，且无重复 semantic run。
- [x] 确认 finalized Gen2 artifact、manifest、run identity 和 `generation_outcome` 正常生成。
- [x] 确认 canonical `reports/morning-brief-YYYY-MM-DD.md` 存在且 digest 与 finalized artifact 一致。
- [x] 确认 Obsidian note 路径、文件名和内容正确。
- [x] 确认 Bark 通知正确到达，且失败/ambiguous timeout 不自动重复发送。
- [ ] 点击 Bark URI，确认打开正确的 Obsidian note（可选 follow-up；不作为本次 closeout gate，用户已确认 delivery 成功）。
- [x] 完成人工 reader-facing Morning Brief 验收；第一次 scheduled run 为 partial，但 banner、内容与 delivery 均可接受，complete/partial/legal empty 离线矩阵保持通过。
- [x] 检查日志确认没有 `main.py`、Gen1 Curator、Gen1 semantic fallback 或重复 semantic stages。
- [x] 保留 explicit、人工批准、可审计的 `overnight_brief` rollback seam；本轮不实际 rollback。

第一次 scheduled acceptance 的 canonical evidence 位置：launchd stdout/stderr 为 repo 根目录 `daily-digest.launchd.out.log` / `daily-digest.launchd.err.log`；Gen2 finalized run 为 `<data-root>/runs/event-driven-morning-brief/<run_id>/manifest.json` 与 `morning-brief.md`；正式报告为 `<data-root>/reports/morning-brief-YYYY-MM-DD.md`；Obsidian note 为 `.env.local` 中既有 `MOBILE_DIGEST_DIR` 下的同名 Morning Brief。实际验收 run_id 为 `gen2-20260829T000008.376254Z-728ecd201649`，`generation_outcome=partial`，原因是已接受的 Investing.com timezone-less timestamp variation；只核对这些位置与安全字段，不输出 `.env.local` 内容、API key 或 Bark URL。

## v1.9 Focused Reader-Facing Category Presentation Corrective — COMPLETED

Renderer 仅按固定顺序遍历非空 category bucket：`geopolitics → china_policy → macro_policy → financial_markets → energy_commodities → company_industry → technology_ai → public_safety → other`。grouping 仍使用 selector-owned `selection_order`，section 内 Event 顺序、`Brief.event_ids`、Event classification 与 canonical schema 均不变；`classification=None` 的 written-unclassified 继续只在 reader-facing 层映射到“其他”，且“其他”最后。该 corrective 不修改 Selector、Classifier、Writer、orchestrator semantic behavior、production routing、delivery 或 LaunchAgent。

新增/更新的 offline coverage 锁定完整九类顺序、空 section 跳过、section 内 selection order、canonical `Brief.event_ids` 不变、genuine `other` 与 written-unclassified 同桶，以及 renderer/orchestrator representative Markdown snapshot。该项不需要 canonical `.expected.json` 变化。

## v1.9 Final Closeout — COMPLETED / CLOSED

- [x] final review 确认 Slice 1–5、第一次 scheduled Gen2 production acceptance 与 category presentation corrective 均通过；Generation 2 继续作为 installed `generation_2` active route，08:00 schedule、delivery seam 与 explicit human-approved `overnight_brief` rollback 保持不变。
- [x] 第一次 scheduled run `gen2-20260829T000008.376254Z-728ecd201649` 记录为 PASS WITH ACCEPTED DEGRADATION；唯一 partial 为 Investing.com 10 条 timezone-less timestamp 的既有 `item_validation_failed` fail-closed variation，作为 accepted non-blocker 保留。
- [x] renderer/orchestrator focused smoke、representative Markdown snapshot、Project-State Push Gate 与 `git diff --check` 通过；此前 full offline/runtime/artifact/routing validation 仍有效。
- [x] 未修改或 reload installed LaunchAgent、未调用真实 RSS/DeepSeek/Bark/Obsidian、未开始 v1.10 legacy retirement；后续只在 post-cutover stability 确认后开始 v1.10 Legacy Retirement READ-ONLY dependency audit。

## v1.9.1 Classifier `other` Boundary Correction — COMPLETED / CLOSED

v1.9.1 只在现有 classifier prompt 增加 named-category boundary clarification，并以
`tests/fixtures/event_classifier_boundary_v1_9_1.json` 做 focused offline regression。
fixture 覆盖灾害/重大伤亡 → `public_safety`、AI 公司/版权诉讼 → `technology_ai`，以及
没有自然 named-category 的 `other` counterexample；不调用真实 provider，不改变
Event/Brief canonical data、Selector、Writer 或 production route。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_event_classifier_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_event_classifier_writer_continuation_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/evaluate_event_classifier_writer_quality.py \
  --classifier-only \
  --fixture tests/fixtures/event_classifier_boundary_v1_9_1.json
```

offline gate 仍需运行全部 `tests/offline_*.py`、`tests.test_project_state_push_gate`、
相关 compile 与 `git diff --check`。focused real-provider same-case validation 只能由用户
显式手动执行；runner 的 `--real-provider deepseek` 只走 classifier-only 分支并将安全 report
打印到 stdout，不写 production artifacts。真实运行前由用户在 Terminal 按现有 `.env.local`
process-env-first 方式提供 `AUTOMATION_BRIEF_CURATOR_API_KEY`；runner 不自动运行额外
provider calls、不读取或输出 API key，不调用真实 RSS/Bark/Obsidian。此次 closeout 未重新
调用 DeepSeek，用户的 3 次手动 real-provider 结果记录如下。

最终 real-provider acceptance：用户手动对同一 fixture 运行 3 次，均 exit 0、
`classifier_stage_status=succeeded`、`technical_failures=[]`，5/5 cases 每次
`classification_match=true`；灾害 cases → `public_safety`、AI legal-dispute cases →
`technology_ai`、intentional `other` counterexample → `other`。partial banner 未在
v1.9.1 中修改，后续可作为独立 presentation follow-up 评估。

## v1.2 regression checklist

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_canonical_domain_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_feed_normalization_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_digest_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_ai_curator_candidate_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_project_state_push_gate
```

上述 regression 继续验证 Gen1 feed normalization、CandidateArticle、现有 exact dedup、digest routing 与 Project-State Push Gate；不读取 `.env`、真实 holdings 或 secrets。

## Project State Push Gate 验证

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_project_state_push_gate
sh -n .githooks/pre-push
sh -n scripts/check-project-state-push.sh
sh -n scripts/install-git-hooks.sh
git diff --check
```

`tests.test_project_state_push_gate` 仅使用 Python 标准库、临时 Git 仓库、临时 bare remote 和临时 Git identity，覆盖 branch、tag、首次 push、多 ref、真实 pre-push 接线、路径空格/非 ASCII 与安装脚本。测试通过 `GIT_CONFIG_GLOBAL` 临时文件和 `GIT_CONFIG_NOSYSTEM=1` 隔离用户 global/system config；不访问网络，不运行 RSS、Bark、Obsidian、launchd、pmset、生产晨报或 AI provider。

## Project State Push Gate checklist

- [ ] push 前已复核 Current version、Current status、Next Action、Blockers、Version Index，以及受影响时的 Deployment。
- [ ] 无明确 blocker 时 Blockers 精确为 `暂无明确阻塞。`。
- [ ] 最终 branch commit 只有一个合法 `Project-State-Review` trailer，且与最终 tree diff 一致；tag 只检查其 commit 上的合法声明。
- [ ] 不以 `git push --no-verify` 作为常规绕过手段。
- [ ] 知道此 gate 可被本地绕过，且不会验证 PROJECT_STATE 内容真实性或自动执行 commit / push。

## Python 改动验证

修改 Python 运行逻辑时，建议至少运行：

```bash
PYTHONPYCACHEPREFIX=/private/tmp python3 -m py_compile main.py check_feeds.py
.venv/bin/python tests/offline_digest_smoke.py
```

For v0.5-alpha market brief changes, also compile the market brief modules and run:

```bash
PYTHONPYCACHEPREFIX=/private/tmp python3 -m py_compile holdings.py market_brief_writer.py market_data.py market_analysis.py market_news.py
.venv/bin/python tests/offline_market_data_smoke.py
.venv/bin/python tests/offline_market_news_smoke.py
.venv/bin/python tests/offline_market_brief_smoke.py
```

For v0.5.1-alpha holdings local config changes, also compile the holdings scripts and run:

```bash
PYTHONPYCACHEPREFIX=/private/tmp python3 -m py_compile project_paths.py scripts/init_holdings_config.py scripts/validate_holdings_config.py
.venv/bin/python tests/offline_holdings_config_smoke.py
```

For v0.6.0-alpha / v0.6.2 Phase 2–3B AI Curator shadow changes, compile the curator, provider, artifact, and explicit shadow modules, then run:

```bash
PYTHONPYCACHEPREFIX=/private/tmp python3 -m py_compile ai_curator.py ai_curator_provider.py ai_curator_artifacts.py project_paths.py scripts/run_ai_curator_shadow.py scripts/publish_mobile_digest.py scripts/send_bark_notification.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/offline_ai_curator_candidate_smoke.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/offline_ai_curator_contract_smoke.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/offline_ai_curator_cli_smoke.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/offline_ai_curator_provider_smoke.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/offline_ai_curator_artifacts_smoke.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/offline_ai_curator_quality_smoke.py
.venv/bin/python tests/offline_project_paths_smoke.py
```

`offline_ai_curator_quality_smoke.py` 加载紧凑的 Phase 4 snapshot gold reference，并验证无加权 evaluator 能识别 `must_include_at_10` 漏选、higher-priority candidate 未选时的 background 占位、人工指定的 forbidden evidence binding、需要 attribution 但标题或摘要未保留，以及预期不确定性却输出 `high + []`。它也锁住窄 attribution phrase boundary，避免普通“数据”或“名称”因单字 substring 被误判。该 evaluator 不读取 snapshot 正文，不做通用 semantic relevance、fact checking、embedding、NLP 或生产 validation；gold 只用于离线同 snapshot 比较。

这些测试必须保持离线：不接真实 AI provider，不调用真实 RSS，不调用 Bark，不写入 Obsidian，不运行 launchd / pmset；真实 holdings 只允许由 validator 做不打印值的校验，其他 smoke 一律使用临时 fixture。Provider smoke 使用 fake transport，覆盖冻结 DeepSeek 配置与 exact body allowlist（`max_tokens`、disabled thinking、JSON mode、无 stream/tools）、完整 CuratorResponse prompt skeleton（包括 `canonical_title` exact key、无 `title` / `headline` alias、target language `zh-CN`）、`choices[0].finish_reason == "stop"` 成功边界，以及 `length`、`content_filter`、`tool_calls`、`insufficient_system_resource`、unknown 和缺失值的 fail-closed / no-retry 行为；同时覆盖 API key 缺失、timeout、瞬态网络错误、429、5xx、不可重试 4xx、空 content、invalid JSON、schema/evidence validation、missing required field、duplicate/overlap、content policy、safe validation diagnostics、max attempts、真实 request-body byte measurement、preflight limit 0-call 和 secret 不泄露。Artifact smoke 使用临时目录，覆盖成功/失败 run、atomic publish、same-day 不覆盖、writer success-boundary revalidation、allowlist、bounded failure diagnostics、content rendering safety、Legacy label、fetch-failure trace、metadata、response.json 只在 validated success 存在和两个 byte measurement 字段语义。

## v0.7.1 Morning Brief smoke checklist

v0.7.1 只验证显式 `overnight_brief` 统一晨报，不切换默认 `digest`，不运行 Obsidian、Bark、launchd 或 pmset。离线 smoke 不调用 AI Curator；显式人工运行时才会按 `phase4_live` 调用既有 single-pass Provider。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_overnight_brief_smoke.py
```

离线 smoke 至少覆盖：

- 四个目标 section 的生成顺序，以及正常情况下不渲染“持仓异常”。
- Daily Digest 核心事件进入第一节；同一 link 或近似标题事件跨第一、二节只展示一次。
- “今日值得关注”最多三条，跳过已展示新闻且不为凑数补齐。
- phase4_live prompt 明确 `max_events=20` 是 ceiling 而非 quota；少于 20 个 event 可正常 validation/render，低价值 uncertainty 不自动占 watch slot。
- AI success reader projection 展示 `must_know` / `important`，不展示主新闻或市场新闻中的 `background`，且 background uncertainty 不进入 watch；artifact response 保持完整。
- phase4_live prompt 明确同一 underlying event 不因指标或标题角度不同而拆分，并要求 canonical title、summary、why-important 与 evidence 支持同一实体和事件。
- 明确持仓异常或高精度持仓新闻才触发第四节；弱/无 holdings 不崩溃。
- 前一交易日 A 股结构化行情说明、行情缺失降级和部分 RSS 失败提示。
- 显式 `main.py --report-type overnight_brief` dispatch 输出 `morning-brief-YYYY-MM-DD.md`，Markdown 标题为“早间简报”。
- AI success 时 CuratedEvent 的 category 互斥投影、evidence source/link 映射、中文 reader-facing 文本、legacy 新闻隔离和相似标题不二次去重。
- AI market events 非空时不显示市场空态；没有 AI market events 时正确显示市场空态。
- Provider 技术失败时整份新闻层回退为 v0.7.1 legacy 输出；行情与持仓异常仍保留。
- direct AI-backed `overnight_brief` success/failure 使用同一 `write_shadow_run` persistence，分别写入成功 `response.json` 或失败阶段的 `run.json`，不调用真实 Provider 的离线测试使用 fake transport / 缺失 key。
- direct run 的 `run.json` 锁住 `original_candidate_count`、provider-facing `candidate_count`、`phase4_live` projection metadata；`request.json`、`response.json`、`trace.json` 和 `review.md` 均存在于同一 canonical run directory。

同时运行普通日报和旧市场简报回归：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_digest_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_market_brief_smoke.py
```

v0.7.1 不要求默认自动链、Obsidian/Bark 发布、全球行情补齐、第二次 AI 调用、AI 质量阈值或 weekly AI/tools digest。真实 AI-backed 样例必须由用户在自己的 Terminal 环境显式运行，不作为离线测试前置条件。

## v0.7.2 Production Cutover offline checklist

本阶段只验证 production routing、`.env` credential boundary 和 rollback compatibility，不调用真实 DeepSeek、不读取用户真实 `.env`、不复制到真实 Obsidian、不发送真实 Bark，也不操作 launchd / pmset：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/offline_production_routing_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_holdings_config_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_project_paths_smoke.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/offline_overnight_brief_smoke.py
```

targeted production smoke 使用临时 repo、临时项目 `.env`、fake Python、临时 canonical data root / mobile directory 和 monkeypatched Bark sender，至少锁住：

- `run_daily_digest.sh` 无参数显式下传 `digest`，`overnight_brief` 同时下传给 `main.py`、Obsidian 和 Bark，未知 report type fail closed。
- digest 不读取 Curator `.env` key；Morning 已有环境变量时不覆盖，环境变量缺失时从项目 `.env` 读取，`.env` 缺失或无 key 时不泄露 fixture secret、任务继续并保留 legacy fallback。
- env 变量与 `.env` 中的不同 fixture key 用于锁定 precedence；所有 fixture secret 都不出现在 stdout/stderr。
- publisher 对 digest 读取 `daily-news-*`，对 Morning 读取 `morning-brief-*`；即使当天 Daily 文件存在，Morning 也不会误复制旧 Daily。
- Bark digest 保留原 title 和 `Displayed items`；Morning 使用“早间简报已生成”、不依赖 `Displayed items`，body / Obsidian URI 均引用实际 `morning-brief-*`。
- plist example 保留 label、08:00 schedule 和既有路径，只在 `ProgramArguments` 追加 `overnight_brief`，不包含 API key 或 credential loader。
- 现有 overnight missing-key artifact 仍记录 `failure_code=missing_api_key`，reader-facing 报告继续 whole-layer legacy fallback。

真实 macOS acceptance 只能由用户在 Terminal 显式执行；本次 acceptance 已由用户于 2026-08-15 完成，记录见下节。离线 checklist 本身仍不调用真实 DeepSeek、不读取用户真实 `.env`，也不替代用户环境验收。

### v0.7.2 real macOS acceptance record

- 项目 `.env` 已配置 `AUTOMATION_BRIEF_CURATOR_API_KEY`，权限为 `0600`；实际 LaunchAgent 已 reload，`ProgramArguments` 为 `run_daily_digest.sh overnight_brief`，受控 `launchctl kickstart` 成功。
- 真实 artifact `overnight-20260815T143736.428601Z-f8958055f793` 的非敏感字段为：`status=succeeded`、`provider_id=deepseek`、`model=deepseek-v4-flash`、`validation_status=passed`、`failure_code=""`、`ai_event_count=20`。
- 已生成 `morning-brief-2026-08-15.md`，并确认 Obsidian 同步与 Bark 通知成功；生产链路确认通过。记录不包含 API key、`.env` 内容或其他 secret。

## v0.7.3 / v1.0 boundary

v0.7.3 七天真实使用验证和产品 review 已完成并 CLOSED。它不是 Generation 1 完全达到长期产品目标的证明；重复 / 事件聚合不足、legacy fallback 中文边界、旧规则误分类、reader-facing UX、市场数据价值不足和持仓能力价值未证明等 evidence 支持停止继续 patch Generation 1 核心新闻架构。

原 v0.7.4 独立退役路线已 superseded / replaced by v1.0，但其历史 audit 结论保留。v1.0 的 `READ-ONLY Dependency Audit` 已针对当前真实 tree 完成；删除或改名任何旧 product surface 前，仍必须先完成真实消费者迁移、cutover 后复审和覆盖验证。测试迁移应跟随真实消费者迁移，不能先按文件名批量删除。

v1.0 的 legacy retirement 只有在 Event-driven pipeline 完成 offline / snapshot validation、shadow / parallel validation、production acceptance 和 production cutover 后才开始；v1.0 内部过程使用 narrative stages，不创建 alpha/beta 或 Phase version token。v1.1 等后续 numeric version 只有在 v1.0 正式 CLOSED 后、确有独立产品增量时才考虑。

Phase 3B fixture one-shot gate 的最终离线 dry-run 命令为：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_ai_curator_shadow.py \
  --candidate-fixture /private/tmp/ai-curator-candidates.json \
  --real-provider deepseek \
  --dry-run
```

它必须输出 `mode: dry_run`、`provider_id: deepseek`、`model: deepseek-v4-flash`、`candidate_count <= 2`、`provider_request_body_bytes <= 4096` 和 `transport_calls: 0`，并报告 `curator_request_bytes` / exact `provider_request_body_bytes`。当前 prompt-aligned baseline fixture measurement 为 `candidate_count=2`、`curator_request_bytes=1178`、`provider_request_body_bytes=3964`；CLI candidate fixture 的对应 body 为 `4093`。该路径不需要真实 key、不输出 API key/Authorization、不写 artifact。`--real-provider deepseek` 必须同时提供 `--candidate-fixture`，不能退回 feeds/RSS；默认不带 `--real-provider` 仍使用 fixture provider；未知 provider 必须 fail closed。Phase 3A 通用 provider 仍不启用默认 limit，只有 Phase 3B 显式 fixture gate 传入 `2 / 4096`；候选数或 body 超限必须在 HTTP 前失败且 0 calls，不自动截断候选或 payload。

Phase 3B 离线回归至少锁住：恰好 2 个候选通过；超过 2 个候选 fail closed；body `<=4096` 通过、`>4096` fail closed；不自动截断 candidates/payload；dry-run transport calls 为 0 且不依赖 key；actual real path 缺 key 在 transport 前失败；unknown provider、retry count、`finish_reason == "stop"`、secret、atomic artifact 和 production isolation 回归保持通过。冻结配置仍为 `max_attempts=2`、`max_tokens=8192`、`timeout=90s`；这些仅适用于本次 fixture gate，不是 live RSS / production limits。

## Phase 3B real-provider gate closeout

已成功完成一次 fixture-only DeepSeek shadow gate，artifact 位于 canonical runtime data root 的 run `20260812T075832.935190Z-ffb3a259aaa6`。安全验收 metadata 为：

- provider / model：`deepseek` / `deepseek-v4-flash`
- `attempts=1`、`candidate_count=2`
- `curator_request_bytes=1178`
- `provider_request_body_bytes=3944`，满足 `3944 <= 4096`
- `status=succeeded`、`validation_status=passed`
- `ai_event_count=1`、`rejected_article_count=1`
- Legacy comparison：`not evaluated`

成功 artifact 集合为 `run.json`、`request.json`、`response.json`、`trace.json` 和 `review.md`。本次是 candidate fixture gate，不使用真实 RSS，不接入 production；记录和 review 不应包含 API key、Authorization header、raw HTTP envelope 或 raw provider response。

人工 review 除了确认全链路、evidence mapping、reject 行为和交易建议边界通过，还要把 `why_important` 的 fact / interpretation boundary、unsupported causal inference、unsupported market implication 和 uncertainty handling 纳入 Phase 4 evaluation。该观察当前不触发 validator、关键词或 content scoring 修改。

## Phase 4 boundary checklist

Phase 4 — Live RSS Shadow Evaluation 仍必须显式、shadow-only 地运行：

- `phase4_live` 只能通过 `--input-mode phase4_live` 选择，不能根据 candidate 数量或其他条件自动推断。
- DeepSeek runtime model 固定为 `deepseek-v4-flash`；离线 regression 必须证明非 Flash model fail closed，Phase 4 dry-run `transport_calls=0` 且 body 不超过 `200000` bytes。
- 本轮已冻结并验证 Provider-facing limits：summary cap=`500` chars、`max_candidate_count=200`、`max_provider_request_body_bytes=200000`。
- 第一次真实 RSS candidate window + DeepSeek shadow 已执行并在 response validation 阶段 fail closed；后续 real shadow 仍需另行明确授权，本轮只做 offline replay / body construction。
- 保持 shadow-only；不切换 daily digest / `market_brief`，不接入 Bark、Obsidian、launchd 或 pmset，AI failure 不影响 production。
- 不把 Phase 3B 的 `max_candidate_count=2` 或 `max_provider_request_body_bytes=4096` 直接当作 live RSS / production limits。

## Phase 4A snapshot contract and payload audit

Phase 4A 的 snapshot replay 和 payload decomposition 必须保持完全离线：不读取 RSS、不读取 `.env` 或 API key、不访问 holdings、不调用 DeepSeek，且 provider transport calls 必须为 `0`。`load_candidate_fixture()` 应忠实接受 live collector 合法产生的 linked `published_at: null`，拒绝字段缺失、malformed timestamp 和 linkless `null`；null 不得被替换为当前时间或 report date。

本轮正式 loader replay 的验收是 `/private/tmp/automation-brief-live-candidates-20260812T081815290841Z.json` 加载为 exactly `159` candidates。测量使用当前正式 `deepseek-v4-flash` serializer，只在内存中生成 full/title-only/300/500/1000-character summary scenarios，以及 first-25/50/100/all count scenarios；这些不是生产 truncation 或 pruning policy。安全测量结果保存在 `/private/tmp/automation-brief-phase-4a-payload-measurement.json`，只含长度、字节、feed/source/title 等 metadata，不含完整 RSS 正文或 provider body。

Phase 4A 不修改 digest 的动态 lookback cutoff，也不修改 `CuratorRequest.window_start/end` 的 article timestamp 语义；任何 window change 必须单独评估其对 shared legacy `collect_news()` path 的影响。

## Phase 4B provider projection and hard-limit verification

Phase 4B 的正式离线 replay 命令为：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_ai_curator_shadow.py \
  --candidate-fixture /private/tmp/automation-brief-live-candidates-20260812T081815290841Z.json \
  --real-provider deepseek \
  --input-mode phase4_live \
  --dry-run
```

验收必须同时满足：

- formal loader 的 `original_candidate_count=159`；仅 `phase4_live` 在 Provider preparation 前按 exact source name 排除产品类型天然不匹配的 `GitHub Trending Python Daily`（19），故 `candidate_count=140`、`source_excluded_count=19`。`Investing.com 中文财经` 继续进入每日主选池。原始 CandidateArticle / snapshot 不变，gold 的 8 个 must-includes supporting article IDs 必须全部仍在 provider-facing pool。
- explicit `phase4_live` 未传 `--max-events` 时 request `max_events=20`；default/full、fixture 和 Phase 3B 仍为 5，validator 继续使用 request value。
- `summary_max_chars=500`；`summaries_capped_count=6`；`summaries_unchanged_count=134`。
- projected `curator_request_bytes=108264`；cleaned-pool simple single-pass phase4_live provider body `provider_request_body_bytes=119868`；二者均在相应 limits 内。
- `transport_calls=0`，不读取 API key，不创建 artifact，不访问 RSS / holdings，原始 snapshot 的 SHA-256 不变化。
- Phase 4 provider preparation 顺序为 exact source exclusion → provider-facing candidate count check → projection → exact body construction/serialization → body check → API-key lookup/transport；candidate/body overflow 都是 0-call fail-closed。default/full 与 Phase 3B 不应用该 source exclusion。
- `request.json`（仅未来真实 Phase 4 artifact）必须保存 projected request，而不是原始完整 summary；原始 snapshot 仍保持独立完整输入。
- phase4_live system instruction 必须明确 selected-only semantics、rejection enumeration disabled、`rejected_article_ids=[]`，并要求模型只选择/聚合重要 events 与 evidence；default/full 和 Phase 3B prompt 保持原 rejection contract。
- phase4_live provider boundary 在 generic validator 前将非权威 rejection 字段 canonicalize 为 `[]`，并仅按 event 对完全相同的 evidence ID 做保序 exact-dedupe；不 dedupe rejection、不选 reason、不保存 rejection bookkeeping。canonicalization 后 selected event 的 known evidence、非空 evidence、event ID、schema、enum、report date、content policy、finish_reason 和 JSON parsing 仍严格 fail closed。
- unknown evidence ID 不因 canonicalization 被删除或修正；不同 evidence ID 不合并，跨 event 复用仍合法；default/full 与 Phase 3B fixture 的 duplicate evidence contract 保持 fail closed。
- `response.json` 必须保存 canonical empty rejection list；`review.md` 必须写 `Rejection enumeration: not collected in phase4_live`，不能写成 AI 没有 reject。

Phase 4B 离线回归还必须锁住：`<500`、`==500`、`>500`、empty/null summary、原始 candidate immutable、identity fields、exact 200 allowed、201 rejected、body `<=200000` allowed、body `>200000` rejected、no candidate pruning、no iterative summary shrinking，以及既有 Phase 3B `2 / 4096` fixture contract。

## Canonical runtime data migration verification

路径迁移先运行全部离线 smoke，再复制真实数据。迁移记录只包含文件名、大小、SHA-256、UTF-8 和来源/目标元数据，不包含 holdings 内容、报告正文、secrets 或 provider payload。canonical 默认树为：

```text
~/Projects/_project-data/automation-brief/
├── reports/
├── runs/daily-news.log
├── runs/ai-curator-shadow/
├── manual-inputs/holdings.json
└── migration-records/<migration-id>/
```

迁移后可使用仓库 validator 检查 canonical holdings（输出不得出现具体值），并使用临时 env 文件、临时 mobile 目录和 monkeypatch 进行下游读取 smoke。不要运行真实 RSS、AI provider、Bark、Obsidian、launchd 或 pmset。

如改动涉及脚本调用链、RSS 抓取、Bark、Obsidian 同步或真实输出，再按需运行：

```bash
.venv/bin/python check_feeds.py
.venv/bin/python main.py
scripts/run_daily_digest.sh
```

不要在验证输出中打印 `.env`、Bark key、Obsidian 私有路径等敏感配置或其他 secrets。

## JSON 配置验证

修改 JSON 配置或示例配置时，建议运行：

```bash
python3 -m json.tool feeds.json
python3 -m json.tool feeds.example.json
python3 -m json.tool config.json
python3 -m json.tool config.example.json
python3 -m json.tool keywords.json
python3 -m json.tool keywords.example.json
python3 -m json.tool config/holdings.example.json
```

如果只改其中一部分文件，可只验证对应 JSON；发布前或较大改动时建议全量验证。

## 自动化链路 smoke checklist

当改动影响真实运行链路，或需要确认早报闭环时，按以下顺序检查：

- 生成每日简报：运行 `scripts/run_daily_digest.sh` 或 `.venv/bin/python main.py`，确认 `~/Projects/_project-data/automation-brief/reports/daily-news-YYYY-MM-DD.md` 生成。
- 输出到 Obsidian iCloud：确认 Obsidian iCloud 目标目录出现同名日报，且内容与 canonical `reports/` 中文件一致。
- Bark 推送：确认 iPhone 收到 Bark 通知；如配置了 Obsidian URI，点击后应打开当天日报。
- launchd 定时：使用 `launchctl print gui/$(id -u)/com.ping.automation-brief.daily` 检查任务状态、运行次数和退出码。
- Mac 自动唤醒链路：使用 `pmset -g sched` 检查计划，必要时结合 `pmset -g log` 判断 07:58 唤醒和 08:00 运行是否按预期发生。

自动化链路 smoke 涉及本机环境、iCloud、Bark 和网络，只有在运行逻辑或自动化链路相关改动后才需要执行。

## missed coverage 复盘流程

当真实早报出现漏报、误升格、误降级或重复展示时：

1. 在 `docs/MISSED_CASES.md` 新增案例，记录日期、标题、原始链接、期望 section、重要性、原因类型和采取动作。
2. 判断问题属于 source gap、keyword gap、role gap、rule gap、dedupe gap、content format gap 或未来 AI rerank gap。
3. 优先补离线 smoke 样本或 section 组装级样本，再做规则调整。
4. 调整后运行 `tests/offline_digest_smoke.py`，必要时再运行真实 `main.py` 或 `scripts/run_daily_digest.sh`。
5. 回填 `docs/MISSED_CASES.md` 的回归状态。

`docs/MISSED_CASES.md` 是漏报和质量追踪文档，应保留为长期复盘入口。

## AI Curator shadow checklist

v0.6.0-alpha adds the original shadow plumbing; v0.6.2 Phase 2 adds provider and run-artifact boundaries, Phase 3A adds an explicit DeepSeek opt-in and no-transport preflight, and Phase 3B adds an explicit fixture-only hard-limit gate without enabling production. When modifying the AI Curator path, confirm:

- Candidate pool is built before legacy keyword filtering.
- Fully offline shadow CLI validation can use `--candidate-fixture` plus `--fixture-response`; that path must not read real feeds or call RSS.
- Linkless RSS entries with title, source/feed metadata, and published time may enter the shadow candidate pool, while legacy digest output keeps its link requirement.
- Legacy daily digest and explicit `market_brief` behavior remain unchanged.
- `CuratorRequest.articles` does not include holdings, matched keywords, legacy score, legacy category, market data, or holdings price moves.
- Candidate trace may include legacy diagnostic fields, but must not include cost, position, market value, profit/loss, `.env`, API keys, or secrets.
- Fixture responses fail loudly on unknown evidence ids, duplicate evidence ids within one event, duplicate event ids, invalid enums, empty required text, overlap between selected and rejected ids, and max event violations.
- Shadow preview does not contain direct trading advice terms such as 买入、卖出、加仓、减仓、止损、止盈 or 目标价.
- The OpenAI-compatible adapter reads the API key only from the configured environment variable, treats candidate text as untrusted, sends no provider-specific strict-schema option, validates parsed JSON with `validate_curator_response()`, and retries only transient transport errors, 429, and 5xx once by default.
- Failed provider/parser/validator runs record safe `run.json` metadata plus available request/trace artifacts and never write `response.json`; validator/content-policy failures may record only bounded rule/path diagnostics (and a known candidate id when needed), never raw exception text or the full model response; successful `response.json` is an explicit allowlist of validated domain fields.
- Each run lives under `runs/ai-curator-shadow/<run_id>/`; repeated same-day runs do not overwrite prior runs. Artifacts contain no API key value, Authorization header, holdings, or raw provider envelope.
- `run.json` records `candidate_count`, `curator_request_bytes`, and `provider_request_body_bytes`; fixture provider body bytes are `null`, and the Phase 3B candidate/body hard limits apply only to the explicit DeepSeek fixture gate, not the generic provider or production paths.
- `scripts/run_daily_digest.sh` 无参数仍生成普通 digest；显式 `overnight_brief` 才进入 Morning production routing。`scripts/run_market_brief.sh` 不再硬编码仓库 `output/`，由 resolver 选择 canonical `reports/`。

## market_brief smoke checklist

v0.5-beta first stage 的显式 `market_brief` 会复用 RSS 候选新闻，并尝试用轻量公开接口抓取主要指数和 holdings 个股行情。修改持仓读取、行情数据、新闻筛选、市场简报结构或投资安全边界时，至少确认：

- `market_brief` 能生成 Markdown。
- 输出包含固定 section。
- 持仓标题来自 holdings fixture，fixture 改变后输出随之变化。
- 指数行情 mock 正常返回时，输出展示上证 / 深成指 / 创业板 / 科创 50 涨跌。
- holdings 行情 mock 正常返回时，输出展示持仓个股涨跌。
- 行情字段缺失或请求失败时，输出显示“数据暂不可用”，报告仍能生成。
- 未配置 holdings 时，report 不崩溃。
- holdings 相关新闻只来自 `code`、`name`、`sector`、`watch_tags` 动态匹配。
- 离线 `offline_market_news_smoke.py` 使用 fixture，不依赖真实 RSS 网络。
- 离线 `offline_market_data_smoke.py` 使用 fixture / mock，不依赖真实行情网络。
- 业务代码不硬编码示例持仓。
- 输出不包含直接交易建议词。
- 行情限制说明只出现在市场温度、行情验证或数据限制相关位置，避免多 section 重复空文案。
- `tests/offline_digest_smoke.py` 仍通过，确保普通 daily digest 不回退。
- `scripts/init_holdings_config.py` 不覆盖已有本地 holdings。
- `scripts/validate_holdings_config.py` 对合法配置通过、对 JSON/字段错误失败、对成本/仓位/市值/盈亏字段 warning 且不输出具体值。
- `python3 main.py --report-type market_brief` 或 `scripts/run_market_brief.sh` 能显式生成 canonical `reports/market-brief-YYYY-MM-DD.md`。
- `scripts/run_daily_digest.sh` 不增加 `--report-type market_brief`，默认每日普通 digest 链路不变。

当前不要求 AKShare、TuShare、AI rerank、Bark、Obsidian、launchd 或 pmset 级联 smoke。真实行情网络只在手动显式 market brief 样例中观察，不作为离线测试前置条件。
