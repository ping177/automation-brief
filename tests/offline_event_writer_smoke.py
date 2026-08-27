"""Offline v1.5 Event Writer contract smoke tests.

The suite injects a typed fake gateway and never calls a provider or opens a
network connection. Each test is invoked directly from ``main`` to match the
repository's existing offline smoke style.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from canonical_domain import (  # noqa: E402
    Article,
    Event,
    EventCandidate,
    EventCategory,
    EventClassification,
    EventWriting,
    FailureCode,
    ItemFailure,
    StageName,
    StageStatus,
)
from event_writer import WRITER_BATCH_SIZE, write_events  # noqa: E402
from llm_gateway import GatewayError, GatewayResponse  # noqa: E402


COLLECTED_AT = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc)


class FakeGateway:
    def __init__(
        self,
        responses: Sequence[object] = (),
        *,
        payload: object | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.responses = list(responses)
        self.payload = payload
        self.error = error
        self.calls: list[tuple[Sequence[Mapping[str, Any]], Mapping[str, Any] | None]] = []

    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> GatewayResponse:
        self.calls.append((messages, parameters))
        if self.error is not None:
            raise self.error
        response = self.responses.pop(0) if self.responses else self.payload
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, GatewayResponse):
            return response
        return GatewayResponse(
            payload=response,  # type: ignore[arg-type]
            attempts=1,
            provider_id="fixture",
            model="fixture-model",
        )


def article(
    key: str,
    *,
    title: str | None = None,
    summary: str | None = "A complete source summary.",
    language: str = "en",
    url: str | None = None,
    published_at: datetime | None = COLLECTED_AT,
) -> Article:
    return Article.from_source(
        source=f"Fixture Source {key}",
        url=url or f"https://fixture.example/{key}",
        published_at=published_at,
        collected_at=COLLECTED_AT,
        language=language,
        title=title or f"Story {key}",
        summary=summary,
    )


def selected_event(*items: Article, order: int = 1) -> Event:
    candidate = EventCandidate.from_article_ids(item.article_id for item in items)
    return Event.from_candidate(candidate, selection_order=order)


def classified_event(*items: Article, order: int = 1) -> Event:
    return selected_event(*items, order=order).with_classification(
        EventClassification(EventCategory.TECHNOLOGY_AI)
    )


def writing_payload(event: Event, *, prefix: str = "事件") -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "title_zh": f"{prefix}标题：重要进展",
        "summary_zh": f"{prefix}摘要说明了事实、回应和后续进展。",
        "why_it_matters_zh": f"普通读者今天需要知道{prefix}的具体影响。",
    }


def write(events: object, articles: object, gateway: FakeGateway):
    return write_events(events, articles, gateway)


def projection_from(gateway: FakeGateway, call_index: int = 0) -> dict[str, Any]:
    messages, parameters = gateway.calls[call_index]
    assert parameters is None
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    content = messages[1]["content"]
    assert isinstance(content, str)
    _, separator, projection_json = content.partition("\n")
    return json.loads(projection_json if separator else content)


def assert_no_forbidden_projection_keys(value: object) -> None:
    forbidden = {
        "canonical_url",
        "collected_at",
        "article_ids",
        "selection_order",
        "importance",
        "score",
        "importance_score",
        "relevance_score",
        "hotness_score",
        "source_score",
        "legacy_category",
        "embedding",
        "similarity",
        "cluster_threshold",
        "keyword_match",
        "feed_role",
        "mode",
        "holdings",
        "market",
        "market_data",
        "raw",
        "writing",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for child in value.values():
            assert_no_forbidden_projection_keys(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_forbidden_projection_keys(child)


def test_batch_size_and_empty_input_are_safe() -> None:
    assert WRITER_BATCH_SIZE == 1
    gateway = FakeGateway(payload={"writings": [{"unexpected": "not-called"}]})

    result = write([], [], gateway)

    assert result.stage == StageName.EVENT_WRITER
    assert result.status == StageStatus.SUCCEEDED
    assert result.outputs == ()
    assert result.failures == ()
    assert gateway.calls == []


def test_classified_event_writes_immutably_and_preserves_owned_fields() -> None:
    first = article("classified-first")
    second = article("classified-second", language="zh-CN")
    event = classified_event(first, second)
    gateway = FakeGateway(payload={"writings": [writing_payload(event)]})

    result = write([event], [second, first], gateway)

    assert result.status == StageStatus.SUCCEEDED
    assert result.failures == ()
    assert len(result.outputs) == 1
    written = result.outputs[0]
    assert written is not event
    assert written.event_id == event.event_id
    assert written.article_ids == event.article_ids
    assert written.selection_order == event.selection_order
    assert written.classification == event.classification
    assert event.writing is None
    assert written.writing == EventWriting(
        "事件标题：重要进展",
        "事件摘要说明了事实、回应和后续进展。",
        "普通读者今天需要知道事件的具体影响。",
    )


def test_unclassified_event_becomes_written_unclassified() -> None:
    item = article("unclassified")
    event = selected_event(item)
    gateway = FakeGateway(payload={"writings": [writing_payload(event, prefix="未分类事件")]})

    result = write([event], [item], gateway)

    assert result.status == StageStatus.SUCCEEDED
    assert result.failures == ()
    assert len(result.outputs) == 1
    written = result.outputs[0]
    assert written.classification is None
    assert written.writing is not None
    assert written.writing.title_zh.startswith("未分类事件")


def test_mixed_classified_and_unclassified_events_are_supported() -> None:
    first = article("mixed-classified")
    second = article("mixed-unclassified")
    events = (classified_event(first, order=1), selected_event(second, order=2))
    gateway = FakeGateway(
        responses=[
            {"writings": [writing_payload(events[0], prefix="分类事件")]},
            {"writings": [writing_payload(events[1], prefix="未分类事件")]},
        ]
    )

    result = write(events, [first, second], gateway)

    assert result.status == StageStatus.SUCCEEDED
    assert result.failures == ()
    assert [event.event_id for event in result.outputs] == [event.event_id for event in events]
    assert result.outputs[0].classification == events[0].classification
    assert result.outputs[1].classification is None
    assert all(event.writing is not None for event in result.outputs)
    assert len(gateway.calls) == 2


def test_projection_contains_complete_membership_and_all_article_provenance() -> None:
    first = article(
        "projection-first",
        title="First source title",
        summary="First source full summary.",
        url="https://fixture.example/first?utm_source=fixture",
        published_at=datetime(2026, 8, 26, 23, 59, tzinfo=timezone.utc),
    )
    second = article(
        "projection-second",
        title="第二个来源标题",
        summary=None,
        language="zh-CN",
        url="https://fixture.example/second",
        published_at=None,
    )
    event = classified_event(second, first)
    gateway = FakeGateway(payload={"writings": [writing_payload(event)]})

    result = write([event], [first, second], gateway)

    assert result.status == StageStatus.SUCCEEDED
    projection = projection_from(gateway)
    assert set(projection) == {"target_language", "events"}
    assert projection["target_language"] == "zh-CN"
    assert len(projection["events"]) == 1
    projected_event = projection["events"][0]
    assert set(projected_event) == {"event_id", "category", "articles"}
    assert projected_event["event_id"] == event.event_id
    assert projected_event["category"] == EventCategory.TECHNOLOGY_AI.value
    assert [item["article_id"] for item in projected_event["articles"]] == list(event.article_ids)
    articles_by_id = {item.article_id: item for item in (first, second)}
    for projected in projected_event["articles"]:
        original = articles_by_id[projected["article_id"]]
        assert set(projected) == {
            "article_id",
            "source",
            "url",
            "published_at",
            "language",
            "title",
            "summary",
        }
        assert projected["source"] == original.source
        assert projected["url"] == original.url
        assert projected["published_at"] == (
            None if original.published_at is None else original.published_at.isoformat()
        )
        assert projected["language"] == original.language
        assert projected["title"] == original.title
        assert projected["summary"] == original.summary
    assert_no_forbidden_projection_keys(projection)


def test_unclassified_projection_uses_null_category_and_preserves_long_summary() -> None:
    long_summary = "完整事实" * 400
    item = article("long-summary", summary=long_summary)
    event = selected_event(item)
    gateway = FakeGateway(payload={"writings": [writing_payload(event)]})

    result = write([event], [item], gateway)

    assert result.status == StageStatus.SUCCEEDED
    projection = projection_from(gateway)
    projected_event = projection["events"][0]
    assert projected_event["category"] is None
    assert projected_event["articles"][0]["summary"] == long_summary
    assert len(projected_event["articles"][0]["summary"]) == len(long_summary)


def test_prompt_states_evidence_based_simplified_chinese_synthesis() -> None:
    item = article("prompt")
    event = selected_event(item)
    gateway = FakeGateway(payload={"writings": [writing_payload(event)]})

    result = write([event], [item], gateway)

    assert result.status == StageStatus.SUCCEEDED
    system_prompt = gateway.calls[0][0][0]["content"]
    assert isinstance(system_prompt, str)
    normalized = " ".join(system_prompt.casefold().split())
    for required_text in (
        "complete article bundle",
        "morning brief",
        "simplified chinese",
        "important facts",
        "responses",
        "clarifications",
        "closely related developments",
        "do not translate or summarize articles one by one",
        "same fact",
        "different perspectives",
        "supplied article evidence",
        "outside knowledge",
        "provenance",
        "why_it_matters_zh",
        "state the concrete significance of the event",
        "implications directly supported by the supplied article evidence",
        "do not directly address the reader",
        "personal investment, purchase, or behavioral advice",
        "do not speculate beyond the supplied evidence",
        "generic meta-language",
        "pay attention",
        "keep watching",
    ):
        assert required_text in normalized


def test_response_shape_and_field_validation_are_strict() -> None:
    item = article("strict-validation")
    event = selected_event(item)
    valid = writing_payload(event)
    invalid_payloads = (
        {"writings": [{"event_id": event.event_id, "title_zh": "标题", "summary_zh": "摘要"}]},
        {"writings": [{"event_id": event.event_id, "title_zh": "", "summary_zh": "摘要", "why_it_matters_zh": "原因"}]},
        {"writings": [{"event_id": event.event_id, "title_zh": "标题", "summary_zh": 1, "why_it_matters_zh": "原因"}]},
        {"writings": [{"event_id": event.event_id, "title_zh": "标题", "summary_zh": "摘要", "why_it_matters_zh": None}]},
        {"writings": [{**valid, "extra": "拒绝"}]},
        {"unexpected": []},
        {"writings": {}},
        [],
        {"writings": [valid], "extra": "拒绝"},
    )
    for payload in invalid_payloads:
        gateway = FakeGateway(payload=payload)
        result = write([event], [item], gateway)
        assert result.status == StageStatus.FAILED
        assert result.outputs == ()
        assert result.failures
        assert result.failures[0].item_id == event.event_id
        assert result.failures[0].code in {
            FailureCode.ITEM_VALIDATION_FAILED,
            FailureCode.RESPONSE_PARSE_FAILED,
        }


def test_unknown_event_reference_is_rejected_without_guessing() -> None:
    item = article("unknown-reference")
    event = selected_event(item)
    unknown_id = "evt_" + "f" * 24
    gateway = FakeGateway(
        payload={"writings": [{**writing_payload(event), "event_id": unknown_id}]}
    )

    result = write([event], [item], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert ItemFailure(item_id=unknown_id, code=FailureCode.UNKNOWN_REFERENCE) in result.failures
    assert ItemFailure(item_id=event.event_id, code=FailureCode.ITEM_VALIDATION_FAILED) in result.failures


def test_duplicate_event_id_rejects_all_occurrences() -> None:
    item = article("duplicate-response")
    event = selected_event(item)
    gateway = FakeGateway(
        payload={
            "writings": [
                writing_payload(event, prefix="第一次"),
                writing_payload(event, prefix="第二次"),
            ]
        }
    )

    result = write([event], [item], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert [failure.item_id for failure in result.failures] == [event.event_id, event.event_id]
    assert all(failure.code == FailureCode.ITEM_VALIDATION_FAILED for failure in result.failures)


def test_missing_article_is_local_and_does_not_block_sibling() -> None:
    first = article("missing-member")
    second = article("available-member")
    events = (selected_event(first, order=1), selected_event(second, order=2))
    gateway = FakeGateway(
        payload={"writings": [writing_payload(events[1], prefix="可用事件")]}
    )

    result = write(events, [second], gateway)

    assert result.status == StageStatus.PARTIAL
    assert [event.event_id for event in result.outputs] == [events[1].event_id]
    assert result.failures == (
        ItemFailure(item_id=events[0].event_id, code=FailureCode.INVALID_INPUT),
    )
    assert len(gateway.calls) == 1


def test_single_gateway_or_parse_failure_is_local() -> None:
    first = article("gateway-success")
    second = article("gateway-failure")
    events = (selected_event(first, order=1), selected_event(second, order=2))
    gateway = FakeGateway(
        responses=[
            {"writings": [writing_payload(events[0], prefix="成功事件")]},
            GatewayError("response_parse_failed", 2, parse_reason="invalid_choices"),
        ]
    )

    result = write(events, [first, second], gateway)

    assert result.status == StageStatus.PARTIAL
    assert [event.event_id for event in result.outputs] == [events[0].event_id]
    assert result.failures == (
        ItemFailure(item_id=events[1].event_id, code=FailureCode.RESPONSE_PARSE_FAILED),
    )
    assert len(gateway.calls) == 2


def test_all_success_and_all_failure_statuses() -> None:
    first = article("all-success-first")
    second = article("all-success-second")
    events = (selected_event(first, order=1), selected_event(second, order=2))
    success_gateway = FakeGateway(
        responses=[
            {"writings": [writing_payload(event, prefix="成功")]}
            for event in events
        ]
    )
    success = write(events, [first, second], success_gateway)
    assert success.status == StageStatus.SUCCEEDED
    assert len(success.outputs) == 2
    assert success.failures == ()

    failure_gateway = FakeGateway(
        responses=[
            GatewayError("provider_failed", 2, status=503),
            GatewayError("timeout", 2),
        ]
    )
    failure = write(events, [first, second], failure_gateway)
    assert failure.status == StageStatus.FAILED
    assert failure.outputs == ()
    assert {item_failure.item_id for item_failure in failure.failures} == {
        event.event_id for event in events
    }


def test_pure_english_writing_field_fails_minimal_zh_gate() -> None:
    item = article("english-field")
    event = selected_event(item)
    valid = writing_payload(event)
    for field_name in ("title_zh", "summary_zh", "why_it_matters_zh"):
        payload = dict(valid)
        payload[field_name] = "English only"
        gateway = FakeGateway(payload={"writings": [payload]})

        result = write([event], [item], gateway)

        assert result.status == StageStatus.FAILED
        assert result.outputs == ()
        assert result.failures == (
            ItemFailure(item_id=event.event_id, code=FailureCode.ITEM_VALIDATION_FAILED),
        )


def test_chinese_with_english_proper_nouns_passes_minimal_zh_gate() -> None:
    item = article("mixed-language-writing")
    event = selected_event(item)
    gateway = FakeGateway(
        payload={
            "writings": [
                {
                    "event_id": event.event_id,
                    "title_zh": "OpenAI 发布新模型",
                    "summary_zh": "AI 与 GPU 产业出现新的进展。",
                    "why_it_matters_zh": "普通读者今天需要了解 GDP 与市场预期的变化。",
                }
            ]
        }
    )

    result = write([event], [item], gateway)

    assert result.status == StageStatus.SUCCEEDED
    assert result.failures == ()
    assert result.outputs[0].writing is not None
    assert result.outputs[0].writing.title_zh == "OpenAI 发布新模型"


def test_existing_writing_is_rejected_without_overwrite() -> None:
    item = article("already-written")
    event = selected_event(item)
    written = event.with_writing(EventWriting("已有标题", "已有摘要", "已有原因"))
    gateway = FakeGateway(payload={"writings": [writing_payload(event)]})

    result = write([written], [item], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures == (
        ItemFailure(item_id=written.event_id, code=FailureCode.INVALID_INPUT),
    )
    assert gateway.calls == []


def test_invalid_input_and_no_fallback_surface() -> None:
    item = article("invalid-input")
    event = selected_event(item)
    gateway = FakeGateway(payload={"writings": [writing_payload(event)]})

    result = write([event], [object()], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures == (ItemFailure(code=FailureCode.INVALID_INPUT),)
    assert gateway.calls == []

    source = (PROJECT_ROOT / "event_writer.py").read_text(encoding="utf-8")
    for forbidden_name in (
        "ai_curator",
        "event_selector",
        "event_cluster",
        "market_brief_writer",
        "overnight_brief_writer",
        "importance",
        "legacy_category",
        "placeholder",
        "backfill",
    ):
        assert forbidden_name not in source


def main() -> None:
    test_batch_size_and_empty_input_are_safe()
    test_classified_event_writes_immutably_and_preserves_owned_fields()
    test_unclassified_event_becomes_written_unclassified()
    test_mixed_classified_and_unclassified_events_are_supported()
    test_projection_contains_complete_membership_and_all_article_provenance()
    test_unclassified_projection_uses_null_category_and_preserves_long_summary()
    test_prompt_states_evidence_based_simplified_chinese_synthesis()
    test_response_shape_and_field_validation_are_strict()
    test_unknown_event_reference_is_rejected_without_guessing()
    test_duplicate_event_id_rejects_all_occurrences()
    test_missing_article_is_local_and_does_not_block_sibling()
    test_single_gateway_or_parse_failure_is_local()
    test_all_success_and_all_failure_statuses()
    test_pure_english_writing_field_fails_minimal_zh_gate()
    test_chinese_with_english_proper_nouns_passes_minimal_zh_gate()
    test_existing_writing_is_rejected_without_overwrite()
    test_invalid_input_and_no_fallback_surface()
    print("offline event writer smoke passed")


if __name__ == "__main__":
    main()
