"""Offline v1.5 Event Classifier contract smoke tests.

The suite injects a typed fake gateway and never calls a provider or opens a
network connection.  Each test is invoked directly from ``main`` to match the
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
    EventCategory,
    EventCandidate,
    EventWriting,
    FailureCode,
    ItemFailure,
    StageName,
    StageStatus,
)
from event_classifier import classify_events  # noqa: E402
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
) -> Article:
    return Article.from_source(
        source="Fixture Source",
        url=f"https://fixture.example/{key}",
        published_at=COLLECTED_AT,
        collected_at=COLLECTED_AT,
        language=language,
        title=title or f"Story {key}",
        summary=summary,
    )


def selected_event(*items: Article, order: int = 1) -> Event:
    candidate = EventCandidate.from_article_ids(item.article_id for item in items)
    return Event.from_candidate(candidate, selection_order=order)


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
        "category",
        "classification",
        "selection_order",
        "importance",
        "score",
        "importance_score",
        "relevance_score",
        "hotness_score",
        "source_score",
        "writing",
        "title_zh",
        "summary_zh",
        "why_it_matters_zh",
        "legacy_category",
        "embedding",
        "similarity",
        "cluster_threshold",
        "keyword_match",
        "feed_role",
        "mode",
        "raw",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for child in value.values():
            assert_no_forbidden_projection_keys(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_forbidden_projection_keys(child)


def classify(events: object, articles: object, gateway: FakeGateway):
    return classify_events(events, articles, gateway)


def test_empty_input_is_success_without_gateway_call() -> None:
    gateway = FakeGateway(payload={"classifications": [{"unexpected": "not-called"}]})

    result = classify([], [], gateway)

    assert result.stage == StageName.EVENT_CLASSIFIER
    assert result.status == StageStatus.SUCCEEDED
    assert result.outputs == ()
    assert result.failures == ()
    assert gateway.calls == []


def test_all_nine_categories_are_accepted_and_update_event_immutably() -> None:
    articles = [article(f"category-resolved-{index}") for index in range(9)]
    events = tuple(selected_event(item, order=index + 1) for index, item in enumerate(articles))
    gateway = FakeGateway(
        responses=[
            {"classifications": [{"event_id": event.event_id, "category": category.value}]}
            for event, category in zip(events, EventCategory)
        ]
    )

    result = classify(events, articles, gateway)

    assert result.status == StageStatus.SUCCEEDED
    assert [event.classification.category for event in result.outputs] == list(EventCategory)
    for original, classified in zip(events, result.outputs):
        assert classified is not original
        assert classified.event_id == original.event_id
        assert classified.article_ids == original.article_ids
        assert classified.selection_order == original.selection_order
        assert classified.writing is None
        assert original.classification is None


def test_projection_contains_complete_membership_in_canonical_order_and_no_side_channels() -> None:
    first = article("projection-first", title="First article", summary=None)
    second = article("projection-second", title="Second article", language="zh-CN")
    event = selected_event(second, first)
    gateway = FakeGateway(payload={"classifications": [{"event_id": event.event_id, "category": "other"}]})

    result = classify([event], [first, second], gateway)

    assert result.status == StageStatus.SUCCEEDED
    projection = projection_from(gateway)
    assert set(projection) == {"events"}
    assert len(projection["events"]) == 1
    projected_event = projection["events"][0]
    assert set(projected_event) == {"event_id", "articles"}
    assert projected_event["event_id"] == event.event_id
    assert [item["article_id"] for item in projected_event["articles"]] == list(event.article_ids)
    article_by_id = {item.article_id: item for item in (first, second)}
    assert [item["title"] for item in projected_event["articles"]] == [
        article_by_id[article_id].title for article_id in event.article_ids
    ]
    projected_first = next(item for item in projected_event["articles"] if item["article_id"] == first.article_id)
    assert projected_first["summary"] is None
    assert set(projected_first) == {"article_id", "title", "summary", "language"}
    assert_no_forbidden_projection_keys(projection)
    system_prompt = gateway.calls[0][0][0]["content"]
    assert isinstance(system_prompt, str)
    normalized_prompt = " ".join(system_prompt.casefold().split())
    for required_text in (
        "single category",
        "what this event is",
        "importance",
        "selection order",
        "frozen vocabulary",
        "classifications",
    ):
        assert required_text in normalized_prompt


def test_projection_is_deterministic_for_article_lookup_order() -> None:
    first = article("deterministic-first")
    second = article("deterministic-second")
    event = selected_event(first, second)
    first_gateway = FakeGateway(payload={"classifications": [{"event_id": event.event_id, "category": "other"}]})
    second_gateway = FakeGateway(payload={"classifications": [{"event_id": event.event_id, "category": "other"}]})

    first_result = classify([event], [second, first], first_gateway)
    second_result = classify([event], [first, second], second_gateway)

    assert first_result.status == StageStatus.SUCCEEDED
    assert second_result.status == StageStatus.SUCCEEDED
    assert first_gateway.calls[0][0] == second_gateway.calls[0][0]


def test_response_shape_and_category_validation_are_item_local() -> None:
    first = article("validation-first")
    second = article("validation-second")
    events = (selected_event(first, order=1), selected_event(second, order=2))
    invalid_payloads = (
        {"classifications": [{"event_id": events[0].event_id, "category": "not-a-category"}]},
        {"classifications": [{"event_id": events[0].event_id}]},
        {"classifications": [{"event_id": events[0].event_id, "category": ""}]},
        {"classifications": [{"category": "other"}]},
        {"classifications": [{"event_id": "", "category": "other"}]},
        {"classifications": [{"event_id": events[0].event_id, "category": "other", "score": 1}]},
        {"unexpected": []},
        {"classifications": {}},
        [],
    )
    for payload in invalid_payloads:
        gateway = FakeGateway(payload=payload)
        result = classify([events[0]], [first], gateway)
        assert result.status == StageStatus.FAILED
        assert result.outputs == ()
        assert result.failures[0].item_id == events[0].event_id
        assert result.failures[0].code in {
            FailureCode.ITEM_VALIDATION_FAILED,
            FailureCode.RESPONSE_PARSE_FAILED,
        }


def test_unknown_event_reference_is_rejected_without_guessing() -> None:
    item = article("unknown-reference")
    event = selected_event(item)
    gateway = FakeGateway(
        payload={"classifications": [{"event_id": "evt_" + "f" * 24, "category": "other"}]}
    )

    result = classify([event], [item], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert any(
        failure.item_id == "evt_" + "f" * 24 and failure.code == FailureCode.UNKNOWN_REFERENCE
        for failure in result.failures
    )
    assert any(
        failure.item_id == event.event_id and failure.code == FailureCode.ITEM_VALIDATION_FAILED
        for failure in result.failures
    )


def test_duplicate_event_id_rejects_all_occurrences() -> None:
    item = article("duplicate-response")
    event = selected_event(item)
    gateway = FakeGateway(
        payload={
            "classifications": [
                {"event_id": event.event_id, "category": "other"},
                {"event_id": event.event_id, "category": "geopolitics"},
            ]
        }
    )

    result = classify([event], [item], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert [failure.item_id for failure in result.failures] == [event.event_id, event.event_id]
    assert all(failure.code == FailureCode.ITEM_VALIDATION_FAILED for failure in result.failures)


def test_valid_item_is_retained_when_response_contains_unknown_sibling() -> None:
    item = article("valid-with-unknown")
    event = selected_event(item)
    unknown_id = "evt_" + "e" * 24
    gateway = FakeGateway(
        payload={
            "classifications": [
                {"event_id": event.event_id, "category": "other"},
                {"event_id": unknown_id, "category": "geopolitics"},
            ]
        }
    )

    result = classify([event], [item], gateway)

    assert result.status == StageStatus.PARTIAL
    assert [output.event_id for output in result.outputs] == [event.event_id]
    assert result.outputs[0].classification.category == EventCategory.OTHER
    assert result.failures == (ItemFailure(item_id=unknown_id, code=FailureCode.UNKNOWN_REFERENCE),)


def test_valid_item_is_retained_when_response_contains_malformed_sibling() -> None:
    item = article("valid-with-malformed")
    event = selected_event(item)
    gateway = FakeGateway(
        payload={
            "classifications": [
                {"event_id": event.event_id, "category": "other"},
                {"unexpected": "malformed"},
            ]
        }
    )

    result = classify([event], [item], gateway)

    assert result.status == StageStatus.PARTIAL
    assert [output.event_id for output in result.outputs] == [event.event_id]
    assert result.failures == (ItemFailure(code=FailureCode.ITEM_VALIDATION_FAILED),)


def test_missing_article_lookup_fails_before_gateway() -> None:
    item = article("missing-lookup")
    event = selected_event(item)
    gateway = FakeGateway(payload={"classifications": []})

    result = classify([event], [], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures[0].code == FailureCode.INVALID_INPUT
    assert gateway.calls == []


def test_single_event_gateway_failures_do_not_affect_siblings() -> None:
    first = article("gateway-success")
    second = article("gateway-failure")
    events = (selected_event(first, order=1), selected_event(second, order=2))
    gateway = FakeGateway(
        responses=[
            {"classifications": [{"event_id": events[0].event_id, "category": "other"}]},
            GatewayError("transport_failed", 2),
        ]
    )

    result = classify(events, [first, second], gateway)

    assert result.status == StageStatus.PARTIAL
    assert [event.event_id for event in result.outputs] == [events[0].event_id]
    assert result.outputs[0].classification.category == EventCategory.OTHER
    assert len(result.failures) == 1
    assert result.failures[0].item_id == events[1].event_id
    assert result.failures[0].code == FailureCode.TRANSPORT_FAILED
    assert len(gateway.calls) == 2


def test_parse_and_unexpected_transport_failures_are_event_local() -> None:
    first = article("parse-failure")
    second = article("unexpected-failure")
    events = (selected_event(first, order=1), selected_event(second, order=2))
    gateway = FakeGateway(
        responses=[
            GatewayError("response_parse_failed", 1, parse_reason="assistant_content_invalid_json"),
            RuntimeError("fixture transport detail"),
        ]
    )

    result = classify(events, [first, second], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert {failure.item_id for failure in result.failures} == {event.event_id for event in events}
    assert {failure.code for failure in result.failures} == {
        FailureCode.RESPONSE_PARSE_FAILED,
        FailureCode.TRANSPORT_FAILED,
    }


def test_parse_failure_does_not_affect_successful_sibling() -> None:
    first = article("parse-success-sibling")
    second = article("parse-local-failure")
    events = (selected_event(first, order=1), selected_event(second, order=2))
    gateway = FakeGateway(
        responses=[
            {"classifications": [{"event_id": events[0].event_id, "category": "other"}]},
            GatewayError("response_parse_failed", 2, parse_reason="invalid_choices"),
        ]
    )

    result = classify(events, [first, second], gateway)

    assert result.status == StageStatus.PARTIAL
    assert [output.event_id for output in result.outputs] == [events[0].event_id]
    assert result.failures == (ItemFailure(item_id=events[1].event_id, code=FailureCode.RESPONSE_PARSE_FAILED),)


def test_all_success_and_all_failure_statuses() -> None:
    first = article("all-success-first")
    second = article("all-success-second")
    events = (selected_event(first, order=1), selected_event(second, order=2))
    success_gateway = FakeGateway(
        responses=[
            {"classifications": [{"event_id": event.event_id, "category": "other"}]}
            for event in events
        ]
    )
    success = classify(events, [first, second], success_gateway)
    assert success.status == StageStatus.SUCCEEDED
    assert len(success.outputs) == 2
    assert success.failures == ()

    failure_gateway = FakeGateway(
        responses=[GatewayError("provider_failed", 2, status=503), GatewayError("timeout", 2)]
    )
    failure = classify(events, [first, second], failure_gateway)
    assert failure.status == StageStatus.FAILED
    assert failure.outputs == ()
    assert {failure.item_id for failure in failure.failures} == {event.event_id for event in events}


def test_classification_does_not_change_existing_writing_or_membership() -> None:
    item = article("existing-writing")
    event = selected_event(item)
    writing = EventWriting("标题", "摘要", "原因")
    written = event.with_writing(writing)
    gateway = FakeGateway(payload={"classifications": [{"event_id": event.event_id, "category": "other"}]})

    result = classify([written], [item], gateway)

    assert result.status == StageStatus.FAILED
    assert result.failures[0].code == FailureCode.INVALID_INPUT
    assert gateway.calls == []


def test_classifier_has_no_generation_one_or_semantic_ranking_dependencies() -> None:
    source = (PROJECT_ROOT / "event_classifier.py").read_text(encoding="utf-8")
    for forbidden_name in (
        "ai_curator",
        "ai_curator_provider",
        "event_selector",
        "event_cluster",
        "importance_score",
        "hotness_score",
        "legacy writer",
    ):
        assert forbidden_name not in source


def main() -> None:
    test_empty_input_is_success_without_gateway_call()
    test_all_nine_categories_are_accepted_and_update_event_immutably()
    test_projection_contains_complete_membership_in_canonical_order_and_no_side_channels()
    test_projection_is_deterministic_for_article_lookup_order()
    test_response_shape_and_category_validation_are_item_local()
    test_unknown_event_reference_is_rejected_without_guessing()
    test_duplicate_event_id_rejects_all_occurrences()
    test_valid_item_is_retained_when_response_contains_unknown_sibling()
    test_valid_item_is_retained_when_response_contains_malformed_sibling()
    test_missing_article_lookup_fails_before_gateway()
    test_single_event_gateway_failures_do_not_affect_siblings()
    test_parse_and_unexpected_transport_failures_are_event_local()
    test_parse_failure_does_not_affect_successful_sibling()
    test_all_success_and_all_failure_statuses()
    test_classification_does_not_change_existing_writing_or_membership()
    test_classifier_has_no_generation_one_or_semantic_ranking_dependencies()
    print("offline event classifier smoke passed")


if __name__ == "__main__":
    main()
