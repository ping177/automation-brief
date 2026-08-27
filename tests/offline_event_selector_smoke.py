"""Offline v1.4 Event Selector contract smoke tests.

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
    EventCandidate,
    FailureCode,
    StageName,
    StageStatus,
)
from llm_gateway import GatewayError, GatewayResponse  # noqa: E402
from event_selector import SUMMARY_CHAR_LIMIT, select_events  # noqa: E402


WINDOW_START = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc)
COLLECTED_AT = datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc)


class FakeGateway:
    def __init__(
        self,
        payload: object | None = None,
        error: BaseException | None = None,
    ) -> None:
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
        return GatewayResponse(
            payload=self.payload,  # type: ignore[arg-type]
            attempts=1,
            provider_id="fixture",
            model="fixture-model",
        )


def article(
    key: str,
    *,
    title: str | None = None,
    summary: str | None = "A source summary.",
    published_at: datetime | None = COLLECTED_AT,
) -> Article:
    return Article.from_source(
        source="Fixture Source",
        url=f"https://fixture.example/{key}",
        published_at=published_at,
        collected_at=COLLECTED_AT,
        language="en",
        title=title or f"Story {key}",
        summary=summary,
    )


def candidate(*items: Article) -> EventCandidate:
    return EventCandidate.from_article_ids(item.article_id for item in items)


def projection_from(gateway: FakeGateway) -> dict[str, Any]:
    assert len(gateway.calls) == 1
    messages, parameters = gateway.calls[0]
    assert parameters is None
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    content = messages[1]["content"]
    assert isinstance(content, str)
    return json.loads(content)


def assert_no_forbidden_projection_keys(value: object) -> None:
    forbidden = {
        "url",
        "canonical_url",
        "article_id",
        "collected_at",
        "language",
        "category",
        "importance",
        "score",
        "importance_score",
        "relevance_score",
        "hotness_score",
        "source_score",
        "confidence_score",
        "embedding",
        "similarity",
        "cluster_threshold",
        "keyword_match",
        "feed_role",
        "mode",
        "holdings",
        "market_data",
        "raw",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for child in value.values():
            assert_no_forbidden_projection_keys(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_forbidden_projection_keys(child)


def select(
    candidates: object,
    articles: object,
    gateway: FakeGateway,
    *,
    window_start: object = WINDOW_START,
    window_end: object = WINDOW_END,
):
    return select_events(candidates, articles, window_start, window_end, gateway)


def test_empty_pool_is_success_without_gateway_call() -> None:
    gateway = FakeGateway({"selected": [{"unexpected": "not-called"}]})

    result = select([], [], gateway)

    assert result.stage == StageName.EVENT_SELECTOR
    assert result.status == StageStatus.SUCCEEDED
    assert result.outputs == ()
    assert result.failures == ()
    assert gateway.calls == []


def test_duplicate_candidate_input_fails_before_gateway() -> None:
    item = article("duplicate-candidate")
    duplicate = candidate(item)
    gateway = FakeGateway({"selected": []})

    result = select([duplicate, duplicate], [item], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures[0].code == FailureCode.INVALID_INPUT
    assert gateway.calls == []


def test_non_canonical_candidate_input_fails_before_gateway() -> None:
    item = article("invalid-candidate")
    gateway = FakeGateway({"selected": []})

    result = select([object()], [item], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures[0].code == FailureCode.INVALID_INPUT
    assert gateway.calls == []


def test_unresolved_article_fails_before_gateway() -> None:
    item = article("unresolved")
    item_candidate = candidate(item)
    gateway = FakeGateway({"selected": []})

    result = select([item_candidate], [], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures[0].code == FailureCode.INVALID_INPUT
    assert gateway.calls == []


def test_invalid_report_window_fails_before_gateway() -> None:
    item = article("invalid-window")
    item_candidate = candidate(item)
    gateway = FakeGateway({"selected": []})

    for start, end in (
        (datetime(2026, 8, 26, 0, 0), WINDOW_END),
        (WINDOW_END, WINDOW_START),
    ):
        result = select(
            [item_candidate],
            [item],
            gateway,
            window_start=start,
            window_end=end,
        )
        assert result.status == StageStatus.FAILED
        assert result.outputs == ()
        assert result.failures[0].code == FailureCode.INVALID_INPUT
    assert gateway.calls == []


def test_projection_is_deterministic_across_caller_order() -> None:
    first = article("projection-first")
    second = article("projection-second")
    third = article("projection-third")
    first_candidate = candidate(first, second)
    second_candidate = candidate(third)

    first_gateway = FakeGateway({"selected": []})
    first_result = select(
        [second_candidate, first_candidate],
        [third, second, first],
        first_gateway,
    )
    second_gateway = FakeGateway({"selected": []})
    second_result = select(
        [first_candidate, second_candidate],
        [first, third, second],
        second_gateway,
    )

    assert first_result.status == StageStatus.SUCCEEDED
    assert second_result.status == StageStatus.SUCCEEDED
    first_messages = first_gateway.calls[0][0]
    second_messages = second_gateway.calls[0][0]
    assert first_messages == second_messages

    projection = projection_from(first_gateway)
    assert [item["event_candidate_id"] for item in projection["event_candidates"]] == sorted(
        (first_candidate.event_candidate_id, second_candidate.event_candidate_id)
    )
    first_projected = next(
        item
        for item in projection["event_candidates"]
        if item["event_candidate_id"] == first_candidate.event_candidate_id
    )
    articles_by_id = {item.article_id: item for item in (first, second)}
    assert [item["title"] for item in first_projected["articles"]] == [
        articles_by_id[article_id].title for article_id in first_candidate.article_ids
    ]


def test_projection_allowlist_caps_unicode_summary_and_preserves_null_time() -> None:
    item = article(
        "projection-boundary",
        summary="新闻🙂" * 300,
        published_at=None,
    )
    item_candidate = candidate(item)
    gateway = FakeGateway({"selected": []})

    result = select([item_candidate], [item], gateway)

    assert result.status == StageStatus.SUCCEEDED
    projection = projection_from(gateway)
    assert set(projection) == {"window_start", "window_end", "event_candidates"}
    assert projection["window_start"] == WINDOW_START.isoformat()
    assert projection["window_end"] == WINDOW_END.isoformat()
    projected_article = projection["event_candidates"][0]["articles"][0]
    assert set(projected_article) == {"title", "summary", "source", "published_at"}
    assert projected_article["summary"] == item.summary[:SUMMARY_CHAR_LIMIT]
    assert len(projected_article["summary"]) == SUMMARY_CHAR_LIMIT
    assert projected_article["published_at"] is None
    assert_no_forbidden_projection_keys(projection)


def test_all_valid_selection_uses_event_from_candidate_and_leaves_derived_sections_null() -> None:
    first = article("valid-first")
    second = article("valid-second")
    first_candidate = candidate(first)
    second_candidate = candidate(second)
    gateway = FakeGateway(
        {
            "selected": [
                {"event_candidate_id": first_candidate.event_candidate_id, "order": 1},
                {"event_candidate_id": second_candidate.event_candidate_id, "order": 2},
            ]
        }
    )

    result = select([first_candidate, second_candidate], [first, second], gateway)

    assert result.status == StageStatus.SUCCEEDED
    assert len(result.outputs) == 2
    assert result.outputs[0].event_id == first_candidate.event_candidate_id
    assert result.outputs[0].article_ids == first_candidate.article_ids
    assert result.outputs[0].selection_order == 1
    assert result.outputs[0].classification is None
    assert result.outputs[0].writing is None
    assert result.outputs[1].event_id == second_candidate.event_candidate_id
    assert result.outputs[1].selection_order == 2


def test_subset_and_zero_selection_are_valid_without_backfill() -> None:
    first = article("subset-first")
    second = article("subset-second")
    first_candidate = candidate(first)
    second_candidate = candidate(second)

    subset_gateway = FakeGateway(
        {
            "selected": [
                {"event_candidate_id": second_candidate.event_candidate_id, "order": 1}
            ]
        }
    )
    subset_result = select(
        [first_candidate, second_candidate],
        [first, second],
        subset_gateway,
    )
    assert subset_result.status == StageStatus.SUCCEEDED
    assert [event.event_id for event in subset_result.outputs] == [
        second_candidate.event_candidate_id
    ]

    empty_gateway = FakeGateway({"selected": []})
    empty_result = select(
        [first_candidate, second_candidate],
        [first, second],
        empty_gateway,
    )
    assert empty_result.status == StageStatus.SUCCEEDED
    assert empty_result.outputs == ()
    assert empty_result.failures == ()
    assert len(empty_gateway.calls) == 1


def test_explicit_order_beats_provider_array_order() -> None:
    first = article("order-first")
    second = article("order-second")
    first_candidate = candidate(first)
    second_candidate = candidate(second)
    gateway = FakeGateway(
        {
            "selected": [
                {"event_candidate_id": second_candidate.event_candidate_id, "order": 2},
                {"event_candidate_id": first_candidate.event_candidate_id, "order": 1},
            ]
        }
    )

    result = select([first_candidate, second_candidate], [first, second], gateway)

    assert result.status == StageStatus.SUCCEEDED
    assert [event.event_id for event in result.outputs] == [
        first_candidate.event_candidate_id,
        second_candidate.event_candidate_id,
    ]
    assert [event.selection_order for event in result.outputs] == [1, 2]


def test_non_contiguous_orders_are_reindexed_contiguously() -> None:
    first = article("non-contiguous-first")
    second = article("non-contiguous-second")
    first_candidate = candidate(first)
    second_candidate = candidate(second)
    gateway = FakeGateway(
        {
            "selected": [
                {"event_candidate_id": second_candidate.event_candidate_id, "order": 9},
                {"event_candidate_id": first_candidate.event_candidate_id, "order": 2},
            ]
        }
    )

    result = select([first_candidate, second_candidate], [first, second], gateway)

    assert result.status == StageStatus.SUCCEEDED
    assert [event.selection_order for event in result.outputs] == [1, 2]


def test_malformed_item_keeps_valid_sibling_and_is_partial() -> None:
    first = article("malformed-valid")
    second = article("malformed-item")
    first_candidate = candidate(first)
    second_candidate = candidate(second)
    gateway = FakeGateway(
        {
            "selected": [
                {"event_candidate_id": first_candidate.event_candidate_id, "order": 1},
                {"event_candidate_id": second_candidate.event_candidate_id},
            ]
        }
    )

    result = select([first_candidate, second_candidate], [first, second], gateway)

    assert result.status == StageStatus.PARTIAL
    assert [event.event_id for event in result.outputs] == [first_candidate.event_candidate_id]
    assert len(result.failures) == 1
    assert result.failures[0].item_id == second_candidate.event_candidate_id
    assert result.failures[0].code == FailureCode.ITEM_VALIDATION_FAILED


def test_unknown_reference_keeps_valid_sibling_and_is_partial() -> None:
    item = article("unknown-sibling")
    item_candidate = candidate(item)
    gateway = FakeGateway(
        {
            "selected": [
                {"event_candidate_id": item_candidate.event_candidate_id, "order": 1},
                {"event_candidate_id": "evt_unknown_from_fixture", "order": 2},
            ]
        }
    )

    result = select([item_candidate], [item], gateway)

    assert result.status == StageStatus.PARTIAL
    assert len(result.outputs) == 1
    assert result.failures[0].item_id == "evt_unknown_from_fixture"
    assert result.failures[0].code == FailureCode.UNKNOWN_REFERENCE


def test_all_malformed_items_fail_without_outputs() -> None:
    item = article("all-malformed")
    item_candidate = candidate(item)
    gateway = FakeGateway({"selected": [{"event_candidate_id": item_candidate.event_candidate_id}]})

    result = select([item_candidate], [item], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures[0].code == FailureCode.ITEM_VALIDATION_FAILED


def test_non_positive_or_non_integer_orders_are_item_validation_failures() -> None:
    item = article("invalid-order")
    item_candidate = candidate(item)
    for invalid_order in (0, -1, 1.0, 2.0, True, False, "1", None):
        gateway = FakeGateway(
            {
                "selected": [
                    {
                        "event_candidate_id": item_candidate.event_candidate_id,
                        "order": invalid_order,
                    }
                ]
            }
        )
        result = select([item_candidate], [item], gateway)
        assert result.status == StageStatus.FAILED
        assert result.outputs == ()
        assert result.failures[0].code == FailureCode.ITEM_VALIDATION_FAILED


def test_all_unknown_items_fail_without_creating_events() -> None:
    item = article("all-unknown")
    item_candidate = candidate(item)
    gateway = FakeGateway(
        {
            "selected": [
                {"event_candidate_id": "evt_unknown_only", "order": 1},
            ]
        }
    )

    result = select([item_candidate], [item], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures[0].code == FailureCode.UNKNOWN_REFERENCE


def test_duplicate_candidate_reference_excludes_all_occurrences() -> None:
    first = article("duplicate-output-first")
    second = article("duplicate-output-second")
    first_candidate = candidate(first)
    second_candidate = candidate(second)
    gateway = FakeGateway(
        {
            "selected": [
                {"event_candidate_id": first_candidate.event_candidate_id, "order": 1},
                {"event_candidate_id": first_candidate.event_candidate_id, "order": 3},
                {"event_candidate_id": second_candidate.event_candidate_id, "order": 2},
            ]
        }
    )

    result = select([first_candidate, second_candidate], [first, second], gateway)

    assert result.status == StageStatus.PARTIAL
    assert [event.event_id for event in result.outputs] == [second_candidate.event_candidate_id]
    assert [failure.item_id for failure in result.failures] == [
        first_candidate.event_candidate_id,
        first_candidate.event_candidate_id,
    ]
    assert all(failure.code == FailureCode.ITEM_VALIDATION_FAILED for failure in result.failures)


def test_duplicate_order_excludes_all_items_sharing_order() -> None:
    first = article("duplicate-order-first")
    second = article("duplicate-order-second")
    third = article("duplicate-order-third")
    first_candidate = candidate(first)
    second_candidate = candidate(second)
    third_candidate = candidate(third)
    gateway = FakeGateway(
        {
            "selected": [
                {"event_candidate_id": first_candidate.event_candidate_id, "order": 1},
                {"event_candidate_id": second_candidate.event_candidate_id, "order": 1},
                {"event_candidate_id": third_candidate.event_candidate_id, "order": 2},
            ]
        }
    )

    result = select(
        [first_candidate, second_candidate, third_candidate],
        [first, second, third],
        gateway,
    )

    assert result.status == StageStatus.PARTIAL
    assert [event.event_id for event in result.outputs] == [third_candidate.event_candidate_id]
    assert [event.selection_order for event in result.outputs] == [1]
    assert {failure.item_id for failure in result.failures} == {
        first_candidate.event_candidate_id,
        second_candidate.event_candidate_id,
    }
    assert all(failure.code == FailureCode.ITEM_VALIDATION_FAILED for failure in result.failures)


def test_outer_response_failures_are_global_and_not_salvaged() -> None:
    item = article("outer-failure")
    item_candidate = candidate(item)
    for payload in (
        {},
        {"selected": {}},
        {"selected": [], "unexpected": True},
        [
            {"selected": []},
        ],
    ):
        gateway = FakeGateway(payload)
        result = select([item_candidate], [item], gateway)
        assert result.status == StageStatus.FAILED
        assert result.outputs == ()
        assert result.failures[0].code == FailureCode.RESPONSE_PARSE_FAILED
        assert len(gateway.calls) == 1


def test_gateway_failures_map_without_selector_retry() -> None:
    item = article("gateway-failure")
    item_candidate = candidate(item)
    cases = (
        (GatewayError("invalid_input", 0), FailureCode.INVALID_INPUT),
        (GatewayError("timeout", 1), FailureCode.TIMEOUT),
        (GatewayError("transport_failed", 2), FailureCode.TRANSPORT_FAILED),
        (GatewayError("provider_failed", 2, status=503), FailureCode.PROVIDER_FAILED),
        (GatewayError("response_parse_failed", 1), FailureCode.RESPONSE_PARSE_FAILED),
    )
    for error, expected_code in cases:
        gateway = FakeGateway(error=error)
        result = select([item_candidate], [item], gateway)
        assert result.status == StageStatus.FAILED
        assert result.outputs == ()
        assert len(result.failures) == 1
        assert result.failures[0].item_id is None
        assert result.failures[0].code == expected_code
        assert len(gateway.calls) == 1


def test_unexpected_gateway_exception_maps_to_transport_failure() -> None:
    item = article("unexpected-gateway")
    item_candidate = candidate(item)
    gateway = FakeGateway(error=RuntimeError("fixture transport detail"))

    result = select([item_candidate], [item], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures[0].code == FailureCode.TRANSPORT_FAILED
    assert len(gateway.calls) == 1


def test_invalid_gateway_dependency_fails_before_call() -> None:
    item = article("invalid-gateway")
    item_candidate = candidate(item)

    result = select([item_candidate], [item], object())

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures[0].code == FailureCode.INVALID_INPUT


def test_projection_and_response_boundaries_exclude_semantic_side_channels() -> None:
    item = article("boundary")
    item_candidate = candidate(item)
    gateway = FakeGateway(
        {
            "selected": [
                {
                    "event_candidate_id": item_candidate.event_candidate_id,
                    "order": 1,
                    "score": 99,
                }
            ]
        }
    )

    result = select([item_candidate], [item], gateway)

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures[0].code == FailureCode.ITEM_VALIDATION_FAILED


def test_selector_has_no_generation_one_or_semantic_ranking_dependencies() -> None:
    source = (PROJECT_ROOT / "event_selector.py").read_text(encoding="utf-8")
    for forbidden_name in (
        "ai_curator",
        "ai_curator_provider",
        "event_cluster",
        "importance_score",
        "relevance_score",
        "hotness_score",
        "source_score",
        "confidence_score",
        "category",
        "embedding",
        "similarity",
        "legacy",
    ):
        assert forbidden_name not in source


def main() -> None:
    test_empty_pool_is_success_without_gateway_call()
    test_duplicate_candidate_input_fails_before_gateway()
    test_non_canonical_candidate_input_fails_before_gateway()
    test_unresolved_article_fails_before_gateway()
    test_invalid_report_window_fails_before_gateway()
    test_projection_is_deterministic_across_caller_order()
    test_projection_allowlist_caps_unicode_summary_and_preserves_null_time()
    test_all_valid_selection_uses_event_from_candidate_and_leaves_derived_sections_null()
    test_subset_and_zero_selection_are_valid_without_backfill()
    test_explicit_order_beats_provider_array_order()
    test_non_contiguous_orders_are_reindexed_contiguously()
    test_malformed_item_keeps_valid_sibling_and_is_partial()
    test_unknown_reference_keeps_valid_sibling_and_is_partial()
    test_all_malformed_items_fail_without_outputs()
    test_non_positive_or_non_integer_orders_are_item_validation_failures()
    test_all_unknown_items_fail_without_creating_events()
    test_duplicate_candidate_reference_excludes_all_occurrences()
    test_duplicate_order_excludes_all_items_sharing_order()
    test_outer_response_failures_are_global_and_not_salvaged()
    test_gateway_failures_map_without_selector_retry()
    test_unexpected_gateway_exception_maps_to_transport_failure()
    test_invalid_gateway_dependency_fails_before_call()
    test_projection_and_response_boundaries_exclude_semantic_side_channels()
    test_selector_has_no_generation_one_or_semantic_ranking_dependencies()
    print("offline event selector smoke passed")


if __name__ == "__main__":
    main()
