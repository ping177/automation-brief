# AI Curator Architecture

This document describes the v0.6.0-alpha shadow foundation. It is not a production AI integration.

## Scope

v0.6.0-alpha adds the data boundary, validation contract, fixture provider, candidate trace, and explicit preview renderer for a future Global Event Curator.

It does not:

- call a real AI provider
- replace the ordinary daily digest
- replace `market_brief`
- modify Bark, Obsidian, launchd, or pmset automation
- send holdings, positions, costs, profit/loss, or market quotes to the curator

## Pipeline Boundary

The curator candidate boundary sits before the legacy keyword gate:

```text
RSS entry
-> field extraction and normalization
-> time window filtering
-> exact candidate deduplication
-> CandidateArticle pool
   -> legacy pipeline: keyword matching -> NewsItem -> existing digest / market_brief
   -> shadow pipeline: CandidateArticle -> CuratorRequest -> fixture CuratorResponse
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

## Data Contract

`CandidateArticle` includes stable article metadata such as `article_id`, title, summary, source, feed role, timestamps, link, normalized link, report date, and collection time.

`CuratorRequest` includes schema version, report date, window start/end, target language, selection goal, max events, and articles.

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

It writes preview, request, and trace files under `output/ai-curator-shadow/` by default. Those generated files are local artifacts and should not be committed.

For fully offline validation, provide a local candidate fixture:

```bash
python3 scripts/run_ai_curator_shadow.py \
  --candidate-fixture /private/tmp/ai-curator-candidates.json \
  --fixture-response /private/tmp/ai-curator-response.json \
  --output-dir /private/tmp/ai-curator-shadow-output
```

When `--candidate-fixture` is present, the shadow CLI loads candidates from that file and does not load `feeds.json` or call RSS collection.

## Next Step

The next v0.6 step is a real provider behind the `CuratorProvider` interface, run in shadow mode against the same request schema and compared against legacy trace output before any production behavior changes.
