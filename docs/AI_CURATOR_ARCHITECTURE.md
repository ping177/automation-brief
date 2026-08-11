# AI Curator Architecture

This document describes the v0.6.0-alpha shadow foundation and the v0.6.1 product/language contract. It is not a production AI integration.

## Scope

v0.6.0-alpha adds the data boundary, validation contract, fixture provider, candidate trace, and explicit preview renderer for a future Global Event Curator. v0.6.1 freezes the Overnight Brief product boundary, source-language metadata, Simplified Chinese reader output, and legacy/candidate isolation, then wires feed language into the candidate contract without changing production output behavior.

It does not:

- call a real AI provider
- replace the ordinary daily digest
- replace `market_brief`
- modify Bark, Obsidian, launchd, or pmset automation
- send holdings, positions, costs, profit/loss, or market quotes to the curator

## Product Reset

The product is a personal overnight global news brief (Overnight Brief), not an AI investment assistant, stock-opportunity finder, stock recommendation tool, news-to-stock mapper, or daily investment-opinion generator.

The future unified reader-facing structure is:

```text
一、隔夜全球要闻
二、隔夜市场
三、今日观察
四、我的持仓（仅异常时出现）
```

The global-news section should favor roughly 10–18 high-value events, factual summaries, cross-source consolidation, and evidence traceability. “今日观察” is limited to at most three variables to keep watching, not a market forecast. “我的持仓” is conditional and must not expose cost, position size, profit/loss, or trading advice. v0.6.1 defines this contract and the minimal feed/candidate wiring; it does not generate `overnight_brief.md`, delete daily or market brief outputs, or switch production behavior.

## Language Boundary

The input pool may contain multiple languages, while all reader-facing Curator text is Simplified Chinese.

- A feed may declare an optional top-level `language` value: `zh-CN`, `en`, or `und`.
- Missing, blank, or unsupported feed language normalizes to `und`; no automatic language-detection dependency or entry-level language framework is introduced.
- `CandidateArticle.language` is the source-language snapshot copied from the feed metadata.
- `CuratorRequest.target_language` is the requested reader-facing language and is fixed by the product contract to `zh-CN`.
- Source language is metadata only: it does not enter `stable_article_id()`, canonical URL, deduplication identity, or the legacy keyword gate.

Phase 1 documents this contract. Phase 2 implements feed normalization and candidate propagation while remaining backward compatible with configurations that omit `language`.

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
- rejection of low-value candidates

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

`CuratorResponse` includes curated events, rejected article ids, and warnings. Events use controlled enums for importance, novelty, confidence, and category.

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

## Trace

Candidate trace records every full-window candidate and may include legacy diagnostic fields:

- `legacy_keyword_matched`
- `legacy_matched_keywords`
- `legacy_selected`
- `legacy_score`
- `legacy_category`
- `legacy_reject_reason`

These fields are for offline comparison only. They are not included in `CuratorRequest.articles`.

## Explicit Shadow Entry

The manual entry is:

```bash
python3 scripts/run_ai_curator_shadow.py --fixture-response path/to/response.json
```

It writes preview, request, and trace files under the canonical `runs/ai-curator-shadow/` data directory by default. Those generated files are local artifacts and should not be committed.

For fully offline validation, provide a local candidate fixture:

```bash
python3 scripts/run_ai_curator_shadow.py \
  --candidate-fixture /private/tmp/ai-curator-candidates.json \
  --fixture-response /private/tmp/ai-curator-response.json \
  --output-dir /private/tmp/ai-curator-shadow-output
```

When `--candidate-fixture` is present, the shadow CLI loads candidates from that file and does not load `feeds.json` or call RSS collection.

## Version Route and Next Step

The formal route is:

```text
v0.6.1 — Product Reset + Language Boundary
v0.6.2 — AI Curator Shadow Evaluation
v0.7 — Unified Overnight Brief
```

v0.6.1 Phase 1 documentation and Phase 2 feed-language normalization / candidate contract wiring are complete. Real-provider shadow evaluation belongs to v0.6.2, must use the same `CuratorProvider` / `CuratorRequest` / `CuratorResponse` contracts, and must not replace daily digest, `market_brief`, or production automation.
