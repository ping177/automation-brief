"""LLM-backed v1.4 selection from canonical EventCandidates to Events.

The selector owns one report-window decision: deterministic input projection,
strict provider response validation, and item-local salvage. It never changes
the immutable membership produced by the upstream clustering stage and never
falls back to the Generation 1 pipeline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping, Protocol, Sequence

from canonical_domain import (
    Article,
    CanonicalContractError,
    Event,
    EventCandidate,
    FailureCode,
    ItemFailure,
    StageName,
    StageResult,
    StageStatus,
    validate_event_selection_order,
    validate_report_window,
)
from llm_gateway import GatewayError, GatewayResponse


SUMMARY_CHAR_LIMIT = 500

_SELECTOR_SYSTEM_INSTRUCTION = (
    "From the complete event pool of events that actually occurred in roughly the past "
    "24 hours, select and order only the major events that a reader with about 10 minutes "
    "this morning most should not miss. Judge the pool as a whole by major real-world "
    "impact. Major national or societal changes and major natural disasters are examples, "
    "not categories or rules. Do not use fixed scores, category quotas or weighting, "
    "source weighting, or a target number of events. Do not select minor events to fill "
    "space; selecting none is valid. Keep every bundle's membership unchanged. Return "
    "exactly one JSON object with only selected. Each selected item must contain only "
    "event_candidate_id and a positive integer order. Order is relative editorial "
    "priority, not a score. The only valid JSON shape is:\n"
    "{\n"
    '  "selected": [\n'
    "    {\n"
    '      "event_candidate_id": "example_event_id",\n'
    '      "order": 1\n'
    "    }\n"
    "]\n"
    "}\n"
    'The selected array may be empty: {"selected":[]}. Do not add prose.'
)

_SELECTOR_USER_INSTRUCTION = (
    "Apply this editorial principle to the complete report-window event pool:\n"
)


class SelectorGateway(Protocol):
    """Minimal injectable boundary for the shared JSON gateway."""

    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> GatewayResponse | Mapping[str, Any]:
        ...


def _failure_sort_key(failure: ItemFailure) -> tuple[int, str, str]:
    return (
        1 if failure.item_id is None else 0,
        failure.item_id or "",
        failure.code.value,
    )


def _result(
    outputs: Sequence[Event],
    failures: Sequence[ItemFailure],
    diagnostic_ref: str | None = None,
) -> StageResult[Event]:
    ordered_outputs = tuple(outputs)
    ordered_failures = tuple(sorted(failures, key=_failure_sort_key))
    if ordered_outputs and ordered_failures:
        status = StageStatus.PARTIAL
    elif ordered_failures:
        status = StageStatus.FAILED
    else:
        status = StageStatus.SUCCEEDED
    return StageResult(
        stage=StageName.EVENT_SELECTOR,
        status=status,
        outputs=ordered_outputs,
        failures=ordered_failures,
        diagnostic_ref=diagnostic_ref,
    )


def _invalid_input() -> StageResult[Event]:
    return _result((), (ItemFailure(code=FailureCode.INVALID_INPUT),))


def _response_parse_failure(reason: str) -> StageResult[Event]:
    return _result(
        (),
        (ItemFailure(code=FailureCode.RESPONSE_PARSE_FAILED),),
        diagnostic_ref=f"event_selector:{reason}",
    )


def _gateway_failure(error: GatewayError) -> StageResult[Event]:
    code_by_kind = {
        "invalid_input": FailureCode.INVALID_INPUT,
        "timeout": FailureCode.TIMEOUT,
        "transport_failed": FailureCode.TRANSPORT_FAILED,
        "provider_failed": FailureCode.PROVIDER_FAILED,
        "response_parse_failed": FailureCode.RESPONSE_PARSE_FAILED,
    }
    failure_code = code_by_kind.get(error.kind, FailureCode.TRANSPORT_FAILED)
    diagnostic_ref = None
    if error.kind == "response_parse_failed":
        parse_reason = error.parse_reason or "unspecified"
        diagnostic_ref = f"llm_gateway:{parse_reason}"
    return _result(
        (),
        (ItemFailure(code=failure_code),),
        diagnostic_ref=diagnostic_ref,
    )


@dataclass(frozen=True)
class _SelectionItem:
    candidate_id: str | None
    order: int | None
    structurally_valid: bool


def _item_failure(item: _SelectionItem, code: FailureCode) -> ItemFailure:
    return ItemFailure(item_id=item.candidate_id, code=code)


def _parse_selection_item(raw_item: Any) -> _SelectionItem:
    if not isinstance(raw_item, Mapping) or set(raw_item) != {
        "event_candidate_id",
        "order",
    }:
        candidate_id = (
            raw_item.get("event_candidate_id")
            if isinstance(raw_item, Mapping)
            and isinstance(raw_item.get("event_candidate_id"), str)
            and raw_item.get("event_candidate_id").strip()
            else None
        )
        return _SelectionItem(candidate_id=candidate_id, order=None, structurally_valid=False)

    raw_candidate_id = raw_item["event_candidate_id"]
    candidate_id = (
        raw_candidate_id
        if isinstance(raw_candidate_id, str) and raw_candidate_id.strip()
        else None
    )
    raw_order = raw_item["order"]
    order = raw_order if type(raw_order) is int and raw_order >= 1 else None
    return _SelectionItem(
        candidate_id=candidate_id,
        order=order,
        structurally_valid=candidate_id is not None and order is not None,
    )


def _json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list):
        return "array"
    return "other"


def _validate_selection_payload(
    payload: Mapping[str, Any],
    candidates: Mapping[str, EventCandidate],
) -> StageResult[Event]:
    if "selected" not in payload:
        reason = "selected_missing_empty_payload" if not payload else "selected_missing"
        return _response_parse_failure(reason)
    if set(payload) != {"selected"}:
        return _response_parse_failure("unexpected_top_level_keys")
    if not isinstance(payload["selected"], list):
        selected_type = _json_type_name(payload["selected"])
        return _response_parse_failure(f"selected_wrong_type_{selected_type}")
    raw_items = payload["selected"]
    if not raw_items:
        return _result((), ())

    parsed_items = tuple(_parse_selection_item(raw_item) for raw_item in raw_items)
    candidate_counts: dict[str, int] = {}
    order_counts: dict[int, int] = {}
    for item in parsed_items:
        if item.candidate_id is not None:
            candidate_counts[item.candidate_id] = candidate_counts.get(item.candidate_id, 0) + 1
        if item.order is not None:
            order_counts[item.order] = order_counts.get(item.order, 0) + 1

    valid_items: list[tuple[int, EventCandidate]] = []
    failures: list[ItemFailure] = []
    for item in parsed_items:
        if not item.structurally_valid:
            failures.append(_item_failure(item, FailureCode.ITEM_VALIDATION_FAILED))
            continue
        if candidate_counts[item.candidate_id] > 1 or order_counts[item.order] > 1:
            failures.append(_item_failure(item, FailureCode.ITEM_VALIDATION_FAILED))
            continue
        if item.candidate_id not in candidates:
            failures.append(_item_failure(item, FailureCode.UNKNOWN_REFERENCE))
            continue
        valid_items.append((item.order, candidates[item.candidate_id]))

    valid_items.sort(key=lambda value: value[0])
    events: list[Event] = []
    try:
        for selection_order, (_, item_candidate) in enumerate(valid_items, start=1):
            events.append(Event.from_candidate(item_candidate, selection_order))
        validate_event_selection_order(events)
    except CanonicalContractError:
        return _result((), (ItemFailure(code=FailureCode.ITEM_VALIDATION_FAILED),))
    return _result(events, failures)


def _normalize_candidates(value: Any) -> tuple[EventCandidate, ...]:
    if isinstance(value, (str, bytes)):
        raise CanonicalContractError("event_candidates must be an iterable")
    raw_values = tuple(value.values()) if isinstance(value, Mapping) else tuple(value)
    candidates: list[EventCandidate] = []
    seen_ids: set[str] = set()
    for item in raw_values:
        if not isinstance(item, EventCandidate):
            raise CanonicalContractError("event_candidates must contain EventCandidate objects")
        if item.event_candidate_id in seen_ids:
            raise CanonicalContractError("event_candidates must not contain duplicate IDs")
        seen_ids.add(item.event_candidate_id)
        if not item.article_ids:
            raise CanonicalContractError("event candidates must retain article membership")
        candidates.append(item)
    return tuple(sorted(candidates, key=lambda item: item.event_candidate_id))


def _normalize_articles(value: Any) -> dict[str, Article]:
    if isinstance(value, (str, bytes)):
        raise CanonicalContractError("articles must be an iterable or mapping")
    if isinstance(value, Mapping):
        raw_values = tuple(value.items())
        articles: dict[str, Article] = {}
        for key, item in raw_values:
            if not isinstance(key, str) or not isinstance(item, Article) or key != item.article_id:
                raise CanonicalContractError("article lookup keys must match canonical Article IDs")
            if key in articles:
                raise CanonicalContractError("articles must not contain duplicate IDs")
            articles[key] = item
        return articles

    raw_values = tuple(value)
    articles = {}
    for item in raw_values:
        if not isinstance(item, Article):
            raise CanonicalContractError("articles must contain Article objects")
        if item.article_id in articles:
            raise CanonicalContractError("articles must not contain duplicate IDs")
        articles[item.article_id] = item
    return articles


def _project_inputs(
    candidates: Sequence[EventCandidate],
    articles: Mapping[str, Article],
    window_start: datetime,
    window_end: datetime,
) -> dict[str, Any]:
    return {
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "event_candidates": [
            {
                "event_candidate_id": candidate.event_candidate_id,
                "articles": [
                    {
                        "title": articles[article_id].title,
                        "summary": (
                            None
                            if articles[article_id].summary is None
                            else articles[article_id].summary[:SUMMARY_CHAR_LIMIT]
                        ),
                        "source": articles[article_id].source,
                        "published_at": (
                            None
                            if articles[article_id].published_at is None
                            else articles[article_id].published_at.isoformat()
                        ),
                    }
                    for article_id in candidate.article_ids
                ],
            }
            for candidate in candidates
        ],
    }


def _messages(projection: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    return (
        {"role": "system", "content": _SELECTOR_SYSTEM_INSTRUCTION},
        {
            "role": "user",
            "content": (
                _SELECTOR_USER_INSTRUCTION
                + json.dumps(
                    projection,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
        },
    )


def select_events(
    event_candidates: Iterable[EventCandidate],
    articles: Mapping[str, Article] | Iterable[Article],
    window_start: datetime,
    window_end: datetime,
    gateway: SelectorGateway,
) -> StageResult[Event]:
    """Select and canonically order Events for one report window."""

    try:
        candidates = _normalize_candidates(event_candidates)
        article_lookup = _normalize_articles(articles)
        normalized_start, normalized_end = validate_report_window(window_start, window_end)
        for item in candidates:
            if any(article_id not in article_lookup for article_id in item.article_ids):
                raise CanonicalContractError("event candidate references an unresolved Article")
    except Exception:
        return _invalid_input()

    if not candidates:
        return _result((), ())
    complete_json = getattr(gateway, "complete_json", None)
    if not callable(complete_json):
        return _invalid_input()

    projection = _project_inputs(candidates, article_lookup, normalized_start, normalized_end)
    try:
        response = complete_json(_messages(projection))
    except GatewayError as error:
        return _gateway_failure(error)
    except Exception:
        return _result((), (ItemFailure(code=FailureCode.TRANSPORT_FAILED),))

    payload = response if isinstance(response, Mapping) else getattr(response, "payload", None)
    if not isinstance(payload, Mapping):
        return _response_parse_failure("invalid_gateway_payload")
    return _validate_selection_payload(
        payload,
        {candidate.event_candidate_id: candidate for candidate in candidates},
    )


__all__ = ["SUMMARY_CHAR_LIMIT", "SelectorGateway", "select_events"]
