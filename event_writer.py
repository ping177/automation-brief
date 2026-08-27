"""LLM-backed v1.5 writing of selected canonical Events.

The writer owns only the three reader-facing zh-CN writing fields.  Its
provider boundary is injectable for offline tests, and this slice keeps one
physical request per Event while preserving a batch-ready request shape.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping, Protocol, Sequence

from canonical_domain import (
    Article,
    CanonicalContractError,
    Event,
    EventWriting,
    FailureCode,
    ItemFailure,
    StageName,
    StageResult,
    StageStatus,
    TARGET_LANGUAGE,
    validate_event_selection_order,
)
from llm_gateway import GatewayError, GatewayResponse


WRITER_BATCH_SIZE = 1

_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002FA1F]")

_WRITER_SYSTEM_INSTRUCTION = (
    "Read the complete Article bundle for this Event and synthesize one natural, direct, "
    "information-dense Morning Brief event in simplified Chinese (zh-CN). Combine "
    "important facts, responses, clarifications, and closely related developments across "
    "all Articles; do not translate or summarize articles one by one. Avoid repeating the "
    "same fact across sources while preserving material different perspectives and "
    "follow-up developments. Use only the supplied Article evidence; do not add outside "
    "knowledge or guess provenance such as source, URL, or time. The title_zh, summary_zh, "
    "and why_it_matters_zh fields should be concise and concrete. why_it_matters_zh must "
    "state the concrete significance of the Event using only implications directly "
    "supported by the supplied Article evidence. Do not directly address the reader; "
    "do not give personal investment, purchase, or behavioral advice; do not speculate "
    "beyond the supplied evidence; and do not use generic meta-language telling readers "
    "to 'pay attention' "
    "or 'keep watching', such as '这一事件值得持续关注。' or "
    "'该事件可能产生深远影响。'. Do not select, "
    "rank, classify, or change the Event bundle. Return exactly one JSON object with only "
    '"writings". Each item must contain only "event_id", "title_zh", "summary_zh", and '
    '"why_it_matters_zh". Do not add prose.'
)

_WRITER_USER_INSTRUCTION = "Write this selected Event:\n"


class WriterGateway(Protocol):
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
        stage=StageName.EVENT_WRITER,
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
        "category": (
            None
            if event.classification is None
            else event.classification.category.value
        ),
        "articles": [
            {
                "article_id": article_id,
                "source": articles[article_id].source,
                "url": articles[article_id].url,
                "published_at": (
                    None
                    if articles[article_id].published_at is None
                    else articles[article_id].published_at.isoformat()
                ),
                "language": articles[article_id].language,
                "title": articles[article_id].title,
                "summary": articles[article_id].summary,
            }
            for article_id in event.article_ids
        ],
    }


def _messages(projection: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    return (
        {"role": "system", "content": _WRITER_SYSTEM_INSTRUCTION},
        {
            "role": "user",
            "content": (
                _WRITER_USER_INSTRUCTION
                + json.dumps(
                    {
                        "target_language": TARGET_LANGUAGE,
                        "events": [projection],
                    },
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
    return isinstance(value, Mapping) and set(value) == {
        "event_id",
        "title_zh",
        "summary_zh",
        "why_it_matters_zh",
    }


def _writing_fields_are_valid(value: Mapping[str, Any]) -> bool:
    for field_name in ("title_zh", "summary_zh", "why_it_matters_zh"):
        field_value = value[field_name]
        if not isinstance(field_value, str) or not field_value.strip():
            return False
        if not _CJK_PATTERN.search(field_value):
            return False
    return True


def _validate_response(
    payload: Any,
    event: Event,
) -> tuple[EventWriting | None, tuple[ItemFailure, ...]]:
    """Validate one physical response while preserving item-local salvage."""

    if not isinstance(payload, Mapping) or set(payload) != {"writings"}:
        return None, (ItemFailure(item_id=event.event_id, code=FailureCode.RESPONSE_PARSE_FAILED),)
    raw_items = payload["writings"]
    if not isinstance(raw_items, list):
        return None, (ItemFailure(item_id=event.event_id, code=FailureCode.RESPONSE_PARSE_FAILED),)

    expected_id = event.event_id
    expected_occurrences = 0
    expected_invalid = False
    valid_writings: list[EventWriting] = []
    failures: list[ItemFailure] = []

    for raw_item in raw_items:
        candidate_id = _item_id(raw_item.get("event_id")) if isinstance(raw_item, Mapping) else None
        if candidate_id == expected_id:
            expected_occurrences += 1
            if not _item_shape_is_exact(raw_item) or not _writing_fields_are_valid(raw_item):
                expected_invalid = True
                continue
            try:
                valid_writings.append(
                    EventWriting(
                        title_zh=raw_item["title_zh"],
                        summary_zh=raw_item["summary_zh"],
                        why_it_matters_zh=raw_item["why_it_matters_zh"],
                    )
                )
            except CanonicalContractError:
                expected_invalid = True
            continue

        if not _item_shape_is_exact(raw_item):
            failures.append(ItemFailure(item_id=candidate_id, code=FailureCode.ITEM_VALIDATION_FAILED))
            continue

        if candidate_id is None:
            failures.append(ItemFailure(code=FailureCode.ITEM_VALIDATION_FAILED))
        else:
            failures.append(ItemFailure(item_id=candidate_id, code=FailureCode.UNKNOWN_REFERENCE))

    if expected_occurrences != 1 or expected_invalid or len(valid_writings) != 1:
        failure_count = expected_occurrences or 1
        failures.extend(
            ItemFailure(item_id=expected_id, code=FailureCode.ITEM_VALIDATION_FAILED)
            for _ in range(failure_count)
        )
        return None, tuple(failures)
    return valid_writings[0], tuple(failures)


def write_events(
    selected_events: Iterable[Event],
    articles: Mapping[str, Article] | Iterable[Article],
    gateway: WriterGateway,
) -> StageResult[Event]:
    """Write selected Events without changing upstream-owned fields."""

    try:
        events = _normalize_events(selected_events)
    except Exception:
        return _invalid_input()

    if not events:
        return _result((), ())

    try:
        article_lookup = _normalize_articles(articles)
    except Exception:
        return _invalid_input()

    complete_json = getattr(gateway, "complete_json", None)
    if not callable(complete_json):
        return _invalid_input()

    outputs: list[Event] = []
    failures: list[ItemFailure] = []
    diagnostic_refs: list[str] = []
    for event in events:
        if event.writing is not None:
            failures.append(ItemFailure(item_id=event.event_id, code=FailureCode.INVALID_INPUT))
            continue
        if any(article_id not in article_lookup for article_id in event.article_ids):
            failures.append(ItemFailure(item_id=event.event_id, code=FailureCode.INVALID_INPUT))
            continue

        try:
            projection = _project_event(event, article_lookup)
        except Exception:
            failures.append(ItemFailure(item_id=event.event_id, code=FailureCode.INVALID_INPUT))
            continue

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
        writing, item_failures = _validate_response(payload, event)
        failures.extend(item_failures)
        if writing is not None:
            outputs.append(event.with_writing(writing))

    return _result(outputs, failures, diagnostic_ref=diagnostic_refs[0] if diagnostic_refs else None)


__all__ = ["WRITER_BATCH_SIZE", "WriterGateway", "write_events"]
