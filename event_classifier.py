"""LLM-backed v1.5 classification of selected canonical Events.

The classifier owns only the descriptive ``category`` field.  It keeps the
provider boundary injectable for offline tests, sends one physical request per
Event in this slice, and returns only successfully classified Events.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Protocol, Sequence

from canonical_domain import (
    Article,
    CanonicalContractError,
    Event,
    EventCategory,
    EventClassification,
    FailureCode,
    ItemFailure,
    StageName,
    StageResult,
    StageStatus,
    validate_event_selection_order,
)
from llm_gateway import GatewayError, GatewayResponse


CLASSIFIER_BATCH_SIZE = 1

_CLASSIFIER_SYSTEM_INSTRUCTION = (
    "Choose one single category that best describes what this event is, based only on "
    "the complete Article bundle content. Category describes event type, not importance "
    "or ranking. Do not use source, selection order, score, importance, writing, "
    "provenance, legacy category, or clustering diagnostics. Use exactly one value from "
    "the frozen vocabulary: "
    + ", ".join(category.value for category in EventCategory)
    + '. Prefer the most specific named category supported by the Article bundle. '
    + 'Category boundary guidance: public_safety covers disasters, floods, earthquakes, '
    + 'accidents, major casualties, rescue, public-health emergencies, and emergency response; '
    + 'technology_ai covers events whose core is an AI company, AI model, training data, '
    + 'AI product, or AI copyright/intellectual-property dispute or lawsuit. Reserve "other" '
    + 'only when none of the named categories naturally fits; do not choose "other" merely '
    + 'because an event involves law, litigation, appointments, or personnel. For mixed events, '
    + 'choose the named category that best matches the dominant subject. If no specific category '
    + 'naturally fits the event, choose "other"; semantic '
    + 'uncertainty is not a failure. Return exactly one JSON object with only '
    + '"classifications". Each item must '
    'contain only "event_id" and "category". Do not add prose.'
)

_CLASSIFIER_USER_INSTRUCTION = "Classify this selected Event:\n"


class ClassifierGateway(Protocol):
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
        stage=StageName.EVENT_CLASSIFIER,
        status=status,
        outputs=ordered_outputs,
        failures=ordered_failures,
        diagnostic_ref=diagnostic_ref,
    )


def _invalid_input() -> StageResult[Event]:
    return _result((), (ItemFailure(code=FailureCode.INVALID_INPUT),))


def _normalize_events(value: Any) -> tuple[Event, ...]:
    if isinstance(value, (str, bytes)):
        raise CanonicalContractError("events must be an iterable")
    try:
        events = tuple(value)
    except (TypeError, ValueError) as exc:
        raise CanonicalContractError("events must be an iterable") from exc
    if any(not isinstance(event, Event) for event in events):
        raise CanonicalContractError("events must contain Event objects")
    event_ids = tuple(event.event_id for event in events)
    if len(set(event_ids)) != len(event_ids):
        raise CanonicalContractError("events must not contain duplicate IDs")
    if any(event.classification is not None or event.writing is not None for event in events):
        raise CanonicalContractError("classifier input must contain selected Events only")
    validate_event_selection_order(events)
    return events


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

    try:
        raw_values = tuple(value)
    except (TypeError, ValueError) as exc:
        raise CanonicalContractError("articles must be an iterable or mapping") from exc
    articles = {}
    for item in raw_values:
        if not isinstance(item, Article):
            raise CanonicalContractError("articles must contain Article objects")
        if item.article_id in articles:
            raise CanonicalContractError("articles must not contain duplicate IDs")
        articles[item.article_id] = item
    return articles


def _project_event(event: Event, articles: Mapping[str, Article]) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "articles": [
            {
                "article_id": article_id,
                "title": articles[article_id].title,
                "summary": articles[article_id].summary,
                "language": articles[article_id].language,
            }
            for article_id in event.article_ids
        ],
    }


def _messages(projection: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    return (
        {"role": "system", "content": _CLASSIFIER_SYSTEM_INSTRUCTION},
        {
            "role": "user",
            "content": (
                _CLASSIFIER_USER_INSTRUCTION
                + json.dumps(
                    {"events": [projection]},
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
        },
    )


def _gateway_failure(event_id: str, error: GatewayError) -> tuple[ItemFailure, str | None]:
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
        diagnostic_ref = f"llm_gateway:{error.parse_reason or 'unspecified'}"
    return ItemFailure(item_id=event_id, code=failure_code), diagnostic_ref


def _item_id(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _item_shape_is_exact(value: Any) -> bool:
    return isinstance(value, Mapping) and set(value) == {"event_id", "category"}


def _validate_response(
    payload: Any,
    event: Event,
) -> tuple[EventCategory | None, tuple[ItemFailure, ...]]:
    """Validate one physical response while preserving item-local salvage."""

    if not isinstance(payload, Mapping) or set(payload) != {"classifications"}:
        return None, (ItemFailure(item_id=event.event_id, code=FailureCode.RESPONSE_PARSE_FAILED),)
    raw_items = payload["classifications"]
    if not isinstance(raw_items, list):
        return None, (ItemFailure(item_id=event.event_id, code=FailureCode.RESPONSE_PARSE_FAILED),)

    expected_id = event.event_id
    expected_occurrences = 0
    expected_invalid = False
    valid_categories: list[EventCategory] = []
    failures: list[ItemFailure] = []

    for raw_item in raw_items:
        candidate_id = _item_id(raw_item.get("event_id")) if isinstance(raw_item, Mapping) else None
        if candidate_id == expected_id:
            expected_occurrences += 1
            if not _item_shape_is_exact(raw_item):
                expected_invalid = True
                continue
            raw_category = raw_item["category"]
            try:
                category = EventCategory(raw_category) if isinstance(raw_category, str) else None
            except ValueError:
                category = None
            if category is None or not raw_category.strip():
                expected_invalid = True
                continue
            valid_categories.append(category)
            continue

        if not _item_shape_is_exact(raw_item):
            failures.append(ItemFailure(item_id=candidate_id, code=FailureCode.ITEM_VALIDATION_FAILED))
            continue

        if candidate_id is None:
            failures.append(ItemFailure(code=FailureCode.ITEM_VALIDATION_FAILED))
        else:
            failures.append(ItemFailure(item_id=candidate_id, code=FailureCode.UNKNOWN_REFERENCE))

    if expected_occurrences != 1 or expected_invalid or len(valid_categories) != 1:
        failure_count = expected_occurrences or 1
        failures.extend(
            ItemFailure(item_id=expected_id, code=FailureCode.ITEM_VALIDATION_FAILED)
            for _ in range(failure_count)
        )
        return None, tuple(failures)
    return valid_categories[0], tuple(failures)


def classify_events(
    selected_events: Iterable[Event],
    articles: Mapping[str, Article] | Iterable[Article],
    gateway: ClassifierGateway,
) -> StageResult[Event]:
    """Classify selected Events without changing any upstream-owned fields."""

    try:
        events = _normalize_events(selected_events)
        article_lookup = _normalize_articles(articles)
        for event in events:
            if any(article_id not in article_lookup for article_id in event.article_ids):
                raise CanonicalContractError("Event references an unresolved Article")
    except Exception:
        return _invalid_input()

    if not events:
        return _result((), ())

    complete_json = getattr(gateway, "complete_json", None)
    if not callable(complete_json):
        return _invalid_input()

    outputs: list[Event] = []
    failures: list[ItemFailure] = []
    diagnostic_refs: list[str] = []
    for event in events:
        projection = _project_event(event, article_lookup)
        try:
            response = complete_json(_messages(projection))
        except GatewayError as error:
            failure, diagnostic_ref = _gateway_failure(event.event_id, error)
            failures.append(failure)
            if diagnostic_ref is not None:
                diagnostic_refs.append(diagnostic_ref)
            continue
        except Exception:
            failures.append(ItemFailure(item_id=event.event_id, code=FailureCode.TRANSPORT_FAILED))
            continue

        payload = response if isinstance(response, Mapping) else getattr(response, "payload", None)
        category, item_failures = _validate_response(payload, event)
        failures.extend(item_failures)
        if category is not None:
            outputs.append(event.with_classification(EventClassification(category)))

    return _result(outputs, failures, diagnostic_ref=diagnostic_refs[0] if diagnostic_refs else None)


__all__ = ["CLASSIFIER_BATCH_SIZE", "ClassifierGateway", "classify_events"]
