"""Offline regression for classifier-to-writer continuation semantics.

The tests keep cross-stage composition local to the test.  They inject one fake
gateway per stage and never call a provider or open a network connection.
"""

from __future__ import annotations

from datetime import datetime, timezone
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
    FailureCode,
    ItemFailure,
    StageName,
    StageStatus,
)
from event_classifier import classify_events  # noqa: E402
from event_writer import write_events  # noqa: E402
from llm_gateway import GatewayError, GatewayResponse  # noqa: E402


COLLECTED_AT = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc)


class FakeGateway:
    """Typed offline gateway that returns queued payloads or raises errors."""

    def __init__(self, responses: Sequence[object]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[Sequence[Mapping[str, Any]], Mapping[str, Any] | None]] = []

    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> GatewayResponse:
        self.calls.append((messages, parameters))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return GatewayResponse(
            payload=response,  # type: ignore[arg-type]
            attempts=1,
            provider_id="fixture",
            model="fixture-model",
        )


def article(key: str) -> Article:
    return Article.from_source(
        source=f"Fixture Source {key}",
        url=f"https://fixture.example/{key}",
        published_at=COLLECTED_AT,
        collected_at=COLLECTED_AT,
        language="en",
        title=f"Story {key}",
        summary=f"Complete evidence for {key}.",
    )


def selected_event(item: Article, *, order: int) -> Event:
    candidate = EventCandidate.from_article_ids((item.article_id,))
    return Event.from_candidate(candidate, selection_order=order)


def writing_payload(event: Event, prefix: str) -> dict[str, str]:
    return {
        "event_id": event.event_id,
        "title_zh": f"{prefix}标题：最新进展",
        "summary_zh": f"{prefix}摘要说明已确认的事实和后续进展。",
        "why_it_matters_zh": f"普通读者今天需要知道{prefix}的具体影响。",
    }


def _writer_inputs_after_classifier(
    selected_events: Sequence[Event],
    classifier_outputs: Sequence[Event],
) -> tuple[Event, ...]:
    """Test-local expression of the frozen continuation rule."""

    classified_by_id = {event.event_id: event for event in classifier_outputs}
    return tuple(
        classified_by_id.get(event.event_id, event)
        for event in selected_events
    )


def test_classifier_partial_continues_all_selected_events_to_writer() -> None:
    first_article = article("partial-classified")
    second_article = article("partial-unclassified")
    selected = (
        selected_event(first_article, order=1),
        selected_event(second_article, order=2),
    )

    classifier_gateway = FakeGateway(
        [
            {
                "classifications": [
                    {
                        "event_id": selected[0].event_id,
                        "category": EventCategory.TECHNOLOGY_AI.value,
                    }
                ]
            },
            {
                "classifications": [
                    {
                        "event_id": selected[1].event_id,
                        "category": "not-a-canonical-category",
                    }
                ]
            },
        ]
    )

    classifier_result = classify_events(
        selected,
        [first_article, second_article],
        classifier_gateway,
    )

    assert classifier_result.stage == StageName.EVENT_CLASSIFIER
    assert classifier_result.status == StageStatus.PARTIAL
    assert [event.event_id for event in classifier_result.outputs] == [
        selected[0].event_id
    ]
    assert classifier_result.failures == (
        ItemFailure(
            item_id=selected[1].event_id,
            code=FailureCode.ITEM_VALIDATION_FAILED,
        ),
    )

    writer_inputs = _writer_inputs_after_classifier(selected, classifier_result.outputs)
    assert [event.event_id for event in writer_inputs] == [
        event.event_id for event in selected
    ]
    assert writer_inputs[0] is not selected[0]
    assert writer_inputs[1] is selected[1]
    assert writer_inputs[0].classification is not None
    assert writer_inputs[1].classification is None

    writer_gateway = FakeGateway(
        [
            {"writings": [writing_payload(writer_inputs[0], "分类事件")]},
            {"writings": [writing_payload(writer_inputs[1], "未分类事件")]},
        ]
    )
    writer_result = write_events(
        writer_inputs,
        [second_article, first_article],
        writer_gateway,
    )

    assert writer_result.stage == StageName.EVENT_WRITER
    assert writer_result.status == StageStatus.SUCCEEDED
    assert writer_result.failures == ()
    assert len(writer_gateway.calls) == 2
    assert [event.event_id for event in writer_result.outputs] == [
        event.event_id for event in selected
    ]

    for original, written in zip(selected, writer_result.outputs):
        assert written.event_id == original.event_id
        assert written.article_ids == original.article_ids
        assert written.selection_order == original.selection_order
        assert written.writing is not None
    assert writer_result.outputs[0].classification is not None
    assert writer_result.outputs[1].classification is None


def test_classifier_all_failed_does_not_determine_writer_status() -> None:
    first_article = article("all-failed-first")
    second_article = article("all-failed-second")
    selected = (
        selected_event(first_article, order=1),
        selected_event(second_article, order=2),
    )

    classifier_gateway = FakeGateway(
        [
            {"classifications": []},
            {
                "classifications": [
                    {
                        "event_id": selected[1].event_id,
                        "category": "not-a-canonical-category",
                    }
                ]
            },
        ]
    )
    classifier_result = classify_events(
        selected,
        [first_article, second_article],
        classifier_gateway,
    )

    assert classifier_result.stage == StageName.EVENT_CLASSIFIER
    assert classifier_result.status == StageStatus.FAILED
    assert classifier_result.outputs == ()
    assert {failure.item_id for failure in classifier_result.failures} == {
        event.event_id for event in selected
    }

    writer_inputs = _writer_inputs_after_classifier(selected, classifier_result.outputs)
    assert all(actual is expected for actual, expected in zip(writer_inputs, selected))
    writer_gateway = FakeGateway(
        [
            {"writings": [writing_payload(writer_inputs[0], "未分类一")]},
            {"writings": [writing_payload(writer_inputs[1], "未分类二")]},
        ]
    )
    writer_result = write_events(
        writer_inputs,
        [first_article, second_article],
        writer_gateway,
    )

    assert writer_result.stage == StageName.EVENT_WRITER
    assert writer_result.status == StageStatus.SUCCEEDED
    assert writer_result.failures == ()
    assert len(writer_result.outputs) == 2
    assert len(writer_gateway.calls) == 2
    assert all(event.classification is None for event in writer_result.outputs)
    assert all(event.writing is not None for event in writer_result.outputs)


def test_writer_failure_remains_local_after_classifier_partial_result() -> None:
    first_article = article("writer-success")
    second_article = article("writer-failure")
    selected = (
        selected_event(first_article, order=1),
        selected_event(second_article, order=2),
    )

    classifier_gateway = FakeGateway(
        [
            {
                "classifications": [
                    {
                        "event_id": selected[0].event_id,
                        "category": EventCategory.COMPANY_INDUSTRY.value,
                    }
                ]
            },
            {"classifications": []},
        ]
    )
    classifier_result = classify_events(
        selected,
        [first_article, second_article],
        classifier_gateway,
    )
    assert classifier_result.status == StageStatus.PARTIAL

    writer_inputs = _writer_inputs_after_classifier(selected, classifier_result.outputs)
    assert writer_inputs[0] is not selected[0]
    assert writer_inputs[1] is selected[1]
    writer_gateway = FakeGateway(
        [
            {"writings": [writing_payload(writer_inputs[0], "成功事件")]},
            GatewayError("transport_failed", 1),
        ]
    )
    writer_result = write_events(
        writer_inputs,
        [first_article, second_article],
        writer_gateway,
    )

    assert classifier_result.stage == StageName.EVENT_CLASSIFIER
    assert classifier_result.status == StageStatus.PARTIAL
    assert writer_result.stage == StageName.EVENT_WRITER
    assert writer_result.status == StageStatus.PARTIAL
    assert [event.event_id for event in writer_result.outputs] == [
        selected[0].event_id
    ]
    assert writer_result.failures == (
        ItemFailure(
            item_id=selected[1].event_id,
            code=FailureCode.TRANSPORT_FAILED,
        ),
    )
    assert writer_result.outputs[0].classification is not None
    assert writer_result.outputs[0].writing is not None
    assert writer_inputs[1].classification is None
    assert writer_inputs[1].writing is None
    assert selected[1].event_id not in {
        event.event_id for event in writer_result.outputs
    }


def main() -> None:
    test_classifier_partial_continues_all_selected_events_to_writer()
    test_classifier_all_failed_does_not_determine_writer_status()
    test_writer_failure_remains_local_after_classifier_partial_result()
    print("offline classifier writer continuation smoke passed")


if __name__ == "__main__":
    main()
