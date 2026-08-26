# AI Curator Architecture

This document describes the v0.6.0-alpha shadow foundation, the v0.6.1 product/language contract, the v0.6.2 Phase 2 provider/artifact foundation, the v0.6.2 Phase 3A DeepSeek preflight boundary, the successful Phase 3B fixture-only real-provider gate, and the Phase 4B live selected-only provider boundary. v0.7.2 now uses the existing `phase4_live` provider boundary in the accepted Morning Brief production path. The historical v0.7.4 section below is retained for traceability but its independent retirement route is superseded / replaced by the v1.0 Event-driven Morning Brief architecture documented in [`EVENT_DRIVEN_MORNING_BRIEF_ARCHITECTURE.md`](EVENT_DRIVEN_MORNING_BRIEF_ARCHITECTURE.md).

## Scope

v0.6.0-alpha adds the data boundary, validation contract, fixture provider, candidate trace, and explicit preview renderer for a future Global Event Curator. v0.6.1 freezes the Morning Brief product boundary, source-language metadata, Simplified Chinese reader output, and legacy/candidate isolation, then wires feed language into the candidate contract without changing production output behavior. v0.6.2 Phase 2 adds an explicit OpenAI-compatible adapter boundary and filesystem artifacts for offline shadow evaluation. v0.6.2 Phase 3A freezes one DeepSeek one-shot request profile and adds explicit real-provider opt-in plus a no-transport preflight. Phase 3B adds a fixture-only hard-limit gate shared by the explicit dry-run and real-provider paths; the offline preparation path itself remains non-networking, and the successful real-provider run remains an explicit fixture-only shadow gate.

The v0.7.1 correction adds one explicit manual consumer: `main.py --report-type overnight_brief` may invoke the existing `phase4_live` single-pass Provider and use its validated events for that one report. This is still an opt-in/manual path, not the default production automation or a replacement for the v0.6.2 shadow CLI/artifacts.

It does not:

- replace the ordinary daily digest
- replace `market_brief`
- modify Bark, Obsidian, launchd, or pmset automation
- send holdings, positions, costs, profit/loss, or market quotes to the curator

The explicit manual `overnight_brief` call uses the existing provider boundary only; Provider technical failure falls back to the whole legacy reader-facing news layer. It does not add a second pass, new schema, translation pipeline, ranking system, or quality threshold.

## Historical v0.7.4 Post-validation Architecture Freeze（superseded by v1.0）

This section is a historical governance target, not an active implementation plan. Its product-boundary and consumer-audit conclusions remain useful context, but the current canonical architecture and retirement timing are defined by v1.0. After stable real-morning validation, the historical intended product boundary was:

```text
RSS / feeds
-> CandidateArticle collection and normalization
-> single-pass AI Curator
-> validated CuratedEvent
-> Morning Brief reader projection
   + shared market data
   + shared holdings anomaly
   + shared provider technical fallback
-> canonical Morning report
-> Obsidian / Bark delivery
```

Morning Brief is the only reader-facing product in the historical target architecture. Daily Digest and Market Brief would have been retired as product containers; their still-useful capabilities would become neutral shared capabilities selected by Morning Brief. The current audit found that Morning still reaches legacy fallback and generic rendering helpers located in `main.py` and `market_brief_writer.py`; under that historical route, those consumers would have required migration before deleting old product-only surfaces. The active v1.0 route keeps this audit as input but moves retirement behind the new pipeline's shadow / parallel validation and production cutover gates.

The freeze intentionally does not choose replacement filenames, Python module names, package hierarchy, feature flags, or a new orchestration model. It also does not remove the v0.7.3 rollback path or predefine v0.8 content.

## Product Reset

The product is a personal Morning Brief, not an AI investment assistant, stock-opportunity finder, stock recommendation tool, news-to-stock mapper, or daily investment-opinion generator.

The future unified reader-facing structure is:

```text
一、昨夜最重要的事
二、隔夜市场
三、今日值得关注
四、持仓异常（仅异常时出现）
```

The global-news section should favor high-value events, factual summaries, cross-source consolidation, and evidence traceability. “今日值得关注” is limited to at most three variables to keep watching, not a market forecast. “持仓异常” is conditional and must not expose cost, position size, profit/loss, or trading advice. v0.6.1 defines this contract and the minimal feed/candidate wiring; it does not generate Morning Brief output, delete daily or market brief outputs, or switch production behavior.

## Language Boundary

The input pool may contain multiple languages, while all reader-facing Curator text is Simplified Chinese.

- A feed may declare an optional top-level `language` value: `zh-CN`, `en`, or `und`.
- Missing, blank, or unsupported feed language normalizes to `und`; no automatic language-detection dependency or entry-level language framework is introduced.
- `CandidateArticle.language` is the source-language snapshot copied from the feed metadata.
- `CuratorRequest.target_language` is the requested reader-facing language and is fixed by the product contract to `zh-CN`.
- Source language is metadata only: it does not enter `stable_article_id()`, canonical URL, deduplication identity, or the legacy keyword gate.

Phase 1 documents this contract. The Phase 2 implementation keeps the same domain contract while adding provider and artifact boundaries; configurations that omit `language` remain backward compatible.

## Pipeline Boundary

The curator candidate boundary sits before the legacy keyword gate:

```text
RSS entry
-> field extraction and normalization, including optional feed language
-> time window filtering
-> exact candidate deduplication
-> CandidateArticle pool
   -> legacy pipeline: keyword matching -> NewsItem -> existing digest / market_brief
   -> shadow pipeline: CandidateArticle.language -> CuratorRequest.target_language -> fixture CuratorResponse
```

This keeps the legacy rule output stable while allowing the future curator to see major RSS items that do not match current keywords.

RSS entries without links may enter the shadow `CandidateArticle` pool when they have enough basic metadata, including a non-empty title, feed/source metadata, and a parseable published timestamp. Their `article_id` uses the stable fallback hash based on source, normalized title, and normalized published time. The legacy `NewsItem` pipeline keeps its existing link requirement, so ordinary daily digest output does not start rendering linkless articles.

## Global Event Curator Separation

The Global Event Curator only selects globally important events from RSS candidates. It does not receive:

- holdings
- holding names
- holding sectors or watch tags
- index or holding price moves
- legacy relevance scores
- legacy categories
- legacy theme, risk, or watch output
- matched keywords

Market explanation and holdings interpretation belong to a later Market Impact Interpreter stage.

## Curator Responsibility Boundary

The Curator is an editorial layer for the candidate news pool. It is responsible for:

- candidate news selection
- duplicate-event aggregation
- importance ordering
- multilingual understanding
- Simplified Chinese titles and summaries
- source traceability
- rejection of low-value candidates in default/full and Phase 3B modes; selected-only event/evidence output in `phase4_live`

It is not responsible for:

- fetching or calculating market data
- calculating holding returns
- investment advice or target prices
- predicting market direction
- inferring missing facts
- procedural time or numeric calculations

Reader-facing Curator text must be grounded in candidate evidence, use Simplified Chinese, avoid trading advice, and preserve evidence article ids.

## Data Contract

`CandidateArticle` includes stable article metadata such as `article_id`, title, summary, source, feed role, source-language snapshot in `language`, timestamps, link, normalized link, report date, and collection time. The language snapshot is not part of article identity.

`CuratorRequest` includes schema version, report date, window start/end, `target_language` fixed to `zh-CN`, selection goal, max events, and articles.

`CuratorResponse` includes curated events, rejected article ids, and warnings. Events use controlled enums for importance, novelty, confidence, and category. In explicit `phase4_live`, the provider boundary uses selected-only semantics and canonicalizes `rejected_article_ids` to `[]`; the historical field remains in the domain schema and default/Phase 3B behavior is unchanged. Provider metadata, attempts, failure state, and evaluation measurements remain artifact metadata and are not added to these domain objects.

## Validation

`validate_curator_response()` rejects invalid fixture responses when:

- schema version or report date does not match
- evidence ids are missing or unknown
- events have no evidence
- event evidence ids repeat within the same event
- event ids repeat
- article ids repeat
- enum values are invalid
- selected and rejected article ids overlap
- title, summary, or why-important fields are blank
- the response exceeds max events

Unknown response fields are ignored by the v0.6.0-alpha parser; required known fields remain strict.

Candidate fixture articles reject sensitive or legacy-only fields such as holdings, matched keywords, legacy score/category, cost, position, market value, profit/loss, and API keys. Other unknown non-sensitive fields are ignored.

## Provider Adapter Boundary

`ai_curator_provider.py` contains one explicitly named `OpenAICompatibleCuratorProvider`. It uses Python standard-library HTTP and accepts `provider_id`, `model`, an absolute HTTPS `endpoint`, `api_key_env`, `timeout`, and `max_attempts` through `OpenAICompatibleProviderConfig`. The API key is read only at call time from the configured environment variable; it is never returned in an exception, printed, or passed to the artifact serializer.

The Phase 2 generic request remains a normal JSON body with `model` and system/user messages. The Phase 3A DeepSeek boundary uses the frozen configuration below and an explicit allowlist for the final HTTP body:

```text
provider_id: deepseek
model: deepseek-v4-flash
endpoint: https://api.deepseek.com/chat/completions
api_key_env: AUTOMATION_BRIEF_CURATOR_API_KEY
timeout: 90 seconds
max_attempts: 2
stream: false (not emitted as an enabled streaming field)
max_tokens: 8192
thinking: {"type": "disabled"}
response_format: {"type": "json_object"}
```

The exact DeepSeek body contains only `model`, `messages`, `max_tokens`, `thinking`, and `response_format`; it does not add tools, temperature, top_p, or arbitrary extra-body passthrough. The default/full and Phase 3B system instruction preserves the existing rejection contract. Explicit `phase4_live` uses one selected-only CuratorResponse instruction with `rejected_article_ids=[]`; it treats candidate fields as untrusted data, prohibits browsing or outside knowledge, and fixes reader-facing text to `zh-CN`. The selected-event validator remains strict and unchanged.

The Phase 4 editorial policy remains general rather than snapshot-specific. One Curator call owns event grouping, ranking, direct/minimal evidence, attribution preservation, and confidence/uncertainty calibration. A concrete underlying news peg remains the event boundary: articles about the same entity, time period, and core market/policy/geopolitical change must aggregate even when their metrics or headline angles differ. Each event's canonical title, summary, why-important text, and evidence IDs must describe and support the same entity and event. Routine or narrow events cannot gain priority from an authoritative source or prominent category, and low-value events need not fill the capacity. Before that one call, `phase4_live` alone excludes the exact product-mismatched source `GitHub Trending Python Daily` from the daily main pool. This narrow Provider-facing boundary does not alter the raw candidate pool, roles, feeds, source scoring, default/full, Phase 3B, or production paths; ordinary news sources such as `Investing.com 中文财经` remain eligible for Curator selection.

The quality gate uses a compact repo fixture bound to the audited snapshot SHA-256. It stores reference event IDs, `must_include_at_10` / `strong_candidate` tiers, article IDs, known forbidden bindings, attribution/uncertainty expectations, and representative omit IDs without news bodies or fixed generated prose. A small offline evaluator reports explicit findings only; it does not compute a weighted score or attempt general semantic validation, and it is not called by the provider, domain validator, artifact writer, daily digest, or `market_brief`.

The CLI resolves event capacity by explicit evaluation mode. Default/full, fixture operation, Phase 3B, and the domain `CuratorRequest` default remain 5. Only an explicit `phase4_live` run with no `--max-events` override uses 20. The v0.7 Morning Brief decision is based on same-snapshot sensitivity: the 10-event cap visibly squeezed major-event coverage, 15 did not provide a stable compromise, and two independent Flash runs at 20 improved coverage. Twenty is a ceiling, not a fill target; the model may return fewer events. The phase4_live prompt explicitly forbids quota filling with low-value events. The complete validated response remains in the canonical artifact, while Morning Brief reader projection displays only `must_know` and `important`; `background` does not enter any reader-facing event section or watch slot. Flash ordering of marginal events can still vary; this does not justify adding a new rule system, schema, or ranking stage.

The adapter accepts the provider envelope only long enough to extract the first message content. For this one-shot Curator, `choices[0].finish_reason` must be exactly `stop`; missing, unknown, `length`, `content_filter`, `tool_calls`, and `insufficient_system_resource` values fail closed without retry. In explicit `phase4_live`, the provider boundary projects the non-authoritative rejection field to `[]` and removes only exact duplicate evidence IDs within each event, preserving first-seen order, before the existing validator. Selected event fields still go through `validate_curator_response()` after that narrow canonicalization: unknown evidence IDs, empty evidence, duplicate event IDs, schema failures, and other contract violations fail closed. Default/full and Phase 3B payloads go directly to the generic validator, including strict rejection and duplicate-evidence validation. Invalid JSON, invalid response envelopes, invalid finish reasons, and selected-event evidence failures fail closed without retry. The default is at most two attempts: transient transport errors, HTTP 429, and HTTP 5xx may retry once; other 4xx responses do not retry.

## Real Provider Opt-In and Preflight

The fixture provider remains the safe default. Without `--real-provider deepseek`, the shadow CLI uses the local fixture response path and does not enter the AI HTTP provider path, even when `AUTOMATION_BRIEF_CURATOR_API_KEY` happens to exist in the environment. The real provider is selected only by the explicit flag:

```bash
python3 scripts/run_ai_curator_shadow.py \
  --candidate-fixture /private/tmp/ai-curator-candidates.json \
  --real-provider deepseek
```

Only `deepseek` is accepted, and the shadow CLI real-provider path requires `--candidate-fixture`; it cannot fall back to `feeds.json` or RSS collection. The shadow CLI does not infer provider mode from an API key and does not wire its artifact path into `main.py`, the daily or market brief scripts, launchd, Bark, Obsidian, or pmset. The explicit v0.7 manual `overnight_brief` path uses the same Provider boundary directly, without importing or invoking the shadow CLI. The key is read only by the provider call boundary from `AUTOMATION_BRIEF_CURATOR_API_KEY`; no key value, Authorization header, or raw transport object is persisted.

Phase 3A/3B preflight is explicit and safe to run with no key and no fixture response:

```bash
python3 scripts/run_ai_curator_shadow.py \
  --candidate-fixture /private/tmp/ai-curator-candidates.json \
  --real-provider deepseek \
  --dry-run
```

It builds the same `CuratorRequest` and exact DeepSeek body bytes used by the provider path, applies the Phase 3B fixture gate before API-key lookup, then prints a safe JSON summary containing provider/model/endpoint, candidate count and limits, both byte measurements and limits, timeout/retry/token settings, thinking/JSON modes, target language, and `transport_calls: 0`. It writes no shadow run artifact and never calls `urllib` or reads the API key.

## Payload Limits

Phase 3A does not enable a candidate-count or provider-body-byte default. The explicit `validate_provider_request_limits()` seam accepts only injected limits and runs after exact body serialization but before API-key lookup, `urllib.request.Request`, or any transport call. A violation fails closed with zero HTTP calls; it never truncates or silently drops candidates.

### Phase 3B Fixture One-shot Gate (Explicit CLI Path Only)

The explicit `--real-provider deepseek` CLI path now applies these frozen fixture-only limits to both `--dry-run` and the actual provider boundary:

```text
max_candidate_count: 2
max_provider_request_body_bytes: 4096
max_attempts: 2
max_tokens: 8192
```

The candidate and body checks run after exact serialization but before API-key lookup, `urllib.request.Request`, or any transport call. A violation fails closed with zero HTTP calls and zero attempts. Candidates and payloads are never truncated, deleted, or silently replaced. These limits are not live RSS limits, production limits, or Phase 3A generic provider defaults. The generic provider keeps its existing retry contract: at most two attempts, with retry only for transient transport errors, HTTP 429, and HTTP 5xx.

## Shadow Run Artifacts

The fixture shadow CLI writes each run below the configured shadow root, defaulting to the canonical runtime resolver path:

```text
runs/ai-curator-shadow/<run_id>/
├── run.json
├── request.json
├── response.json       # successful validated runs only
├── trace.json
└── review.md
```

`run_id` is a sortable UTC timestamp plus a collision-resistant suffix, so repeated runs on the same report date do not overwrite one another. The explicit AI-backed `overnight_brief` caller uses the same writer and canonical root, with an `overnight-` run-id prefix to distinguish its caller without adding a new metadata schema. The writer stages all files in a sibling temporary directory, validates the staged set, and atomically renames it to the final run id; I/O failure therefore cannot publish a formal partial run. `run.json` records status, report date, candidate/legacy/AI counts, provider metadata, attempts, validation status, `curator_request_bytes`, and `provider_request_body_bytes`. The first is the serialized provider-facing `CuratorRequest` JSON; the second is the complete HTTP JSON body actually passed to the provider transport, and is `null` for fixture runs. Failed runs additionally record classified `failure_stage` and `failure_code`; validator/content-policy failures may add a bounded `failure_diagnostic` containing only an allowlisted rule code, field path, and a known candidate article id when needed. They may retain safe request and trace artifacts but never write a fake `response.json`.

`request.json` and `response.json` use explicit allowlists. Before a successful run is persisted, the writer re-runs `validate_curator_response()` and the minimal Curator content policy against the response and checks request/response report dates. Raw provider envelopes are discarded. No artifact contains API key values, Authorization headers, holdings, raw HTTP transport dumps, raw validator exception text, or the full model-generated payload. In `phase4_live`, `response.json` therefore contains canonical `"rejected_article_ids": []`, and `review.md` says `Rejection enumeration: not collected in phase4_live` rather than implying that the AI rejected nothing. AI free text is rendered as escaped plain text in `review.md`; direct reader-facing trading actions are rejected, while factual reporting such as an institution assigning a “买入评级” is allowed. `review.md` is a human-review surface with candidate count/window, AI events, evidence/source context, explicit Legacy evaluation semantics, failure classification and safe validation diagnostics when applicable, and a review checklist. For direct `overnight_brief`, `trace.json` retains the full collected candidate identity/legacy comparison snapshot while `request.json` retains the exact provider-facing projection; this makes source exclusion and projection auditable without changing the Curator contract.

## Trace

Candidate trace records every full-window candidate and may include legacy diagnostic fields:

- `legacy_keyword_matched`
- `legacy_matched_keywords`
- `legacy_selected`
- `legacy_score`
- `legacy_category`
- `legacy_reject_reason`

These fields are for offline comparison only. They are not included in `CuratorRequest.articles`. Trace records are typed: candidate records and fetch-failure records use separate allowlists; fetch-failure text is reduced to a safe failure code and never stores raw exception text.

## Explicit Shadow Entry

The manual entry remains fixture-only by default; Phase 3A adds an explicit DeepSeek opt-in and dry-run:

```bash
python3 scripts/run_ai_curator_shadow.py --fixture-response path/to/response.json
```

It writes one run directory containing `run.json`, `request.json`, `response.json`, `trace.json`, and `review.md` under the canonical `runs/ai-curator-shadow/` data directory by default. Fixture runs mark Legacy comparison as `not evaluated` and provider request-body bytes as `null`; the live candidate path is only a `keyword-gate approximation`, explicitly not final production digest selection. Those generated files are local artifacts and should not be committed. The HTTP adapter is wired into this CLI only under the explicit `--real-provider deepseek` opt-in, so the documented fixture command cannot call a real provider.

The runtime DeepSeek configuration is fixed to `deepseek-v4-flash`. The historical Pro comparison remains readable from its artifact `model` field, but no longer requires a runtime profile or CLI switch.

The explicit `overnight_brief` command uses the same `phase4_live` limits and writes its run beside shadow artifacts:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python main.py --report-type overnight_brief
```

Find the newest direct run with `find /Users/wp/Projects/_project-data/automation-brief/runs/ai-curator-shadow -maxdepth 1 -type d -name 'overnight-*' -print | sort | tail -1`. A provider failure still writes a failed run artifact and leaves the Morning Brief's existing whole-news legacy fallback unchanged.

For fully offline validation, provide a local candidate fixture:

```bash
python3 scripts/run_ai_curator_shadow.py \
  --candidate-fixture /private/tmp/ai-curator-candidates.json \
  --fixture-response /private/tmp/ai-curator-response.json \
  --output-dir /private/tmp/ai-curator-shadow-output
```

When `--candidate-fixture` is present, the shadow CLI loads candidates from that file and does not load `feeds.json` or call RSS collection.

## Phase 3B Real-provider Shadow Result

The fixture-only DeepSeek one-shot gate completed successfully in run `20260812T075832.935190Z-ffb3a259aaa6`. It used provider `deepseek`, model `deepseek-v4-flash`, exactly two candidates, one attempt, and passed the local `CuratorResponse` validation and content policy. Safe measurements were `curator_request_bytes=1178` and `provider_request_body_bytes=3944`, so the provider body remained within the Phase 3B `4096`-byte fixture limit. The run produced the normal successful artifact set: `run.json`, `request.json`, `response.json`, `trace.json`, and `review.md`; Legacy comparison was `not evaluated`.

The run was fixture-only: it did not use the RSS collection path and did not connect Curator output to the daily digest, `market_brief`, Bark, Obsidian, launchd, or pmset. The Phase 3B `2 / 4096` limits remain one-shot fixture-gate limits and must be re-measured before any live RSS evaluation.

Human review found the technical chain and evidence mapping acceptable, with no trading advice. It also identified a Phase 4 evaluation item: `why_important` may add stronger interpretation than the evidence supports. Phase 4 review must distinguish fact from interpretation and check unsupported causal inference, unsupported market implication, and uncertainty handling. This observation does not change the validator, domain schema, provider contract, or content policy in Phase 3B.

## Phase 4A Snapshot Contract and Payload Measurement

The live candidate collector already treats `CandidateArticle.published_at` as optional: a candidate with a non-empty link may be retained when the feed has no usable publication timestamp, while a candidate with neither a link nor a publication timestamp is discarded. The fixture loader now mirrors that boundary. `published_at: null` is accepted only when `link` is non-empty; the field must still be present, malformed or empty timestamp strings fail closed, and linkless `null` candidates fail closed. A `null` timestamp is never replaced with the current time or `report_date`, and link-based article identity remains unchanged because `stable_article_id()` is still derived from the normalized link when one exists.

The saved live snapshot `/private/tmp/automation-brief-live-candidates-20260812T081815290841Z.json` was replayed through the formal fixture loader as exactly 159 candidates. The snapshot contains no secret, holdings, authorization header, or transport dump. The targeted contract regression covers linked `published_at: null`, a valid timestamp, malformed timestamps, and linkless `null`; all existing Curator contract checks remain in the same offline smoke.

Phase 4A measured the exact current DeepSeek serializer without transport and without applying the Phase 3B `2 / 4096` fixture gate:

| Scenario | Candidates | CuratorRequest bytes | Provider body bytes |
| --- | ---: | ---: | ---: |
| Full current summaries | 159 | 478,169 | 492,741 |
| Title only | 159 | 86,687 | 97,583 |
| Summary capped at 300 characters (counterfactual) | 159 | 121,866 | 132,770 |
| Summary capped at 500 characters (counterfactual) | 159 | 127,574 | 138,482 |
| Summary capped at 1,000 characters (counterfactual) | 159 | 141,392 | 152,332 |

Current summary lengths are strongly skewed: 159 candidates, 11 missing summaries, p50 95 characters, p90 6,524, p95 13,889, and maximum 54,536. GitHub Trending Python Daily contributes 299,828 serialized article bytes, 62.7564% of candidate article bytes, while VentureBeat AI contributes 77,257 bytes, 16.1705%. The largest individual serialized articles are dominated by long GitHub or VentureBeat summaries. This is evidence that a small number of unusually long summaries, not title length, dominate the full payload; it is not a source-priority or pruning decision.

Using the unmodified current summaries in original snapshot order, the exact provider body sizes were 23,451 bytes for the first 25 candidates, 44,273 for the first 50, 85,883 for the first 100, and 492,741 for all 159. These first-N figures are measurement scenarios only and are not candidate selection policy.

The window semantics were deliberately not changed in Phase 4A. `main.py` calls `within_lookback_hours()` from `candidate_from_entry()` for each article, and that helper computes `datetime.now(timezone.utc)` on each call; there is no frozen collection reference time. `CuratorRequest.window_start` and `window_end` are instead derived from the minimum and maximum non-null candidate `published_at` values in `build_curator_request()`. Changing either behavior would touch the shared `fetch_feed_candidates()` path used by both `collect_candidate_articles()` and the legacy `collect_news()` path, so it requires a separate production-impact review.

The measurements were offline-only (`transport_calls=0`). They establish that a future Phase 4 hard-limit decision must consider summary-size control and candidate-count control together; they do not select a cap, modify feeds, or authorize a real provider call.

## Phase 4B Provider-facing Projection and Hard Limits

Phase 4B freezes a small provider-facing input policy for the live shadow evaluation. It is selected only by the explicit CLI flag `--input-mode phase4_live`; the runtime never infers this mode from candidate count, summary size, provider choice, or any other condition. The existing Phase 3B fixture path remains a separate explicit `phase3b_fixture` mode with its `2 / 4096` limits.

The Phase 4B projection is a deterministic immutable copy:

```text
summary_max_chars: 500
max_candidate_count: 200
max_provider_request_body_bytes: 200000
```

Only the formal `CandidateArticle.summary` is capped. A summary longer than 500 characters is sliced once to exactly 500 characters; shorter, boundary-length, empty, and existing null values keep their legal semantics. Article identity, title, source/feed metadata, link, normalized identity, language, publication time, report date, collected time, and request window are copied unchanged. The raw RSS snapshot remains an independent complete input and is never rewritten by projection.

The provider preparation order is fixed:

1. Build the complete candidate list.
2. Check candidate count against the selected mode limit.
3. Create the provider-facing projected request.
4. Build the exact provider request body.
5. Serialize the exact body.
6. Check provider body bytes against the selected mode limit.
7. Only then look up the API key or construct/execute HTTP transport.

Both overflows fail closed with zero transport calls. The implementation never drops candidates, repeatedly shortens summaries, or raises a limit to fit the body. For a Phase 4 real-provider artifact, `request.json` is the projected request actually supplied to the provider serializer; the original live snapshot is not replaced. Allowlisted run metadata records `input_mode`, summary cap, original candidate count, projection counts, and both hard limits without storing raw HTTP envelopes, Authorization, API keys, holdings, or full provider responses.

The formal offline replay of `/private/tmp/automation-brief-live-candidates-20260812T081815290841Z.json` has 159 candidates, 25 capped summaries, and 134 unchanged summaries. With the simple single-pass quality-tuned phase4_live instruction, `max_events=10`, and the exact current DeepSeek serializer, the projected request measures `127575` bytes and the provider body measures `140129` bytes; `transport_calls=0`.

The real RSS + DeepSeek shadows using this same explicit `phase4_live` input passed the input/body/transport boundary but failed closed during local response validation: the selected-only run first exposed duplicate rejection bookkeeping, and the subsequent selected-only run exposed duplicate evidence IDs. The product decision remains selected-only for `phase4_live`: unselected candidates are derived by the program, so rejection enumeration is not collected. The provider boundary copies the parsed payload, sets `rejected_article_ids` to `[]`, and removes only exact duplicate evidence IDs within each event before the existing validator; it does not select reasons, merge different evidence IDs, alter article IDs, or relax strict event/evidence validation. Default/full and Phase 3B rejection/evidence behavior, schema, limits, retry, and finish-reason behavior remain unchanged.

## Version Route and Next Step

The formal route is:

```text
v0.6.1 — Product Reset + Language Boundary
v0.6.2 — AI Curator Shadow Evaluation
v0.7 — Morning Brief
v0.7.1 — Morning Brief MVP（CLOSED）
v0.7.2 — Production Cutover（CLOSED）
v0.7.3 — Morning Brief Long-term Usage Validation（CLOSED）
v0.7.4 — Legacy Product Retirement & Capability Consolidation（SUPERSEDED / replaced by v1.0 plan）
v1.0 — Event-driven Morning Brief（Architecture + Core Data Contract Freeze COMPLETE；next stage Runtime / Failure Contract Freeze）
```

v0.6.1 Phase 1 documentation and feed-language normalization / candidate contract wiring are complete. v0.6.2 Phase 2 provides the adapter and artifact foundation, Phase 3A freezes the DeepSeek request/preflight boundary, Phase 3B completes the offline fixture safety preparation and successful fixture-only real-provider gate, and Phase 4 closes with live projection, hard limits, selected-only rejection simplification, a single Flash provider call, and GitHub-only daily-main-pool exclusion. Large-pool real shadow technical boundaries succeeded, but same-snapshot content evaluation found recall/ranking limitations; the Curator shadow CLI remains separate, while v0.7.2 uses the existing `phase4_live` boundary only through the accepted `overnight_brief` production path. v0.7.3 is now CLOSED after the seven-day real-use review; the historical v0.7.4 plan is superseded. v1.0 Architecture Freeze, READ-ONLY Dependency Audit, and Core Data Contract Freeze are complete; the active next stage is Runtime / Failure Contract Freeze before implementation or retirement work.
