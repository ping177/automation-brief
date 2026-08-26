from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from canonical_domain import (  # noqa: E402
    Article,
    CanonicalContractError,
    Event,
    EventCandidate,
    EventCategory,
    EventClassification,
    EventWriting,
    Brief,
    GenerationStatus,
    ItemFailure,
    FailureCode,
    StageName,
    StageResult,
    StageStatus,
    deserialize_article,
    deserialize_brief,
    deserialize_domain,
    deserialize_event,
    deserialize_event_candidate,
    deserialize_event_classification,
    deserialize_event_writing,
    deserialize_item_failure,
    deserialize_stage_result,
    datetime_in_report_window,
    serialize_article,
    serialize_brief,
    serialize_domain,
    serialize_event,
    serialize_event_candidate,
    serialize_event_classification,
    serialize_event_writing,
    serialize_item_failure,
    serialize_stage_result,
    stable_article_id,
    stable_brief_id,
    stable_event_candidate_id,
    validate_event_selection_order,
    validate_report_window,
)


REPORT_DATE = date(2026, 8, 26)
UTC_PLUS_EIGHT = timezone(timedelta(hours=8))
PUBLISHED_AT = datetime(2026, 8, 25, 20, 0, tzinfo=UTC_PLUS_EIGHT)
COLLECTED_AT = datetime(2026, 8, 26, 8, 0, tzinfo=UTC_PLUS_EIGHT)


def expect_contract_error(callback) -> None:  # noqa: ANN001
    try:
        callback()
    except CanonicalContractError:
        return
    raise AssertionError("Expected CanonicalContractError")


def article(
    *,
    url: str | None,
    title: str = "A canonical article",
    published_at: datetime | None = PUBLISHED_AT,
    language: str = "en",
) -> Article:
    return Article.from_source(
        source="Fixture Source",
        url=url,
        published_at=published_at,
        collected_at=COLLECTED_AT,
        language=language,
        title=title,
        summary="A source summary.",
    )


def test_article_identity_and_time_validation() -> None:
    first = article(url="https://EXAMPLE.com/story/?utm_source=rss#fragment")
    equivalent = article(url="https://example.com/story")
    changed = article(url="https://example.com/other-story")
    same_url_different_fields = article(
        url="https://example.com/story",
        title="A different source title",
        published_at=None,
        language="zh-CN",
    )
    assert first.canonical_url == "https://example.com/story"
    assert first.article_id == equivalent.article_id
    assert first.article_id == same_url_different_fields.article_id
    assert first.article_id != changed.article_id
    assert first.published_at == PUBLISHED_AT.astimezone(timezone.utc)
    assert first.collected_at == COLLECTED_AT.astimezone(timezone.utc)
    assert article(url="https://example.com/language", language="unsupported").language == "und"

    linkless = article(url=None, title="  Linkless   article  ")
    same_linkless = article(url=None, title="Linkless article", published_at=PUBLISHED_AT.astimezone(timezone.utc))
    assert linkless.article_id == same_linkless.article_id
    assert linkless.canonical_url is None
    assert linkless.url is None

    expect_contract_error(lambda: article(url=None, published_at=None))
    expect_contract_error(
        lambda: article(url="https://example.com/naive", published_at=datetime(2026, 8, 25, 12, 0))
    )
    expect_contract_error(lambda: article(url="ftp://example.com/story"))
    assert stable_article_id(first.canonical_url, first.source, first.title, first.published_at) == first.article_id


def test_event_candidate_identity_and_duplicate_policy() -> None:
    article_ids = (article(url="https://example.com/a").article_id, article(url="https://example.com/b").article_id)
    candidate_a = EventCandidate.from_article_ids(article_ids)
    candidate_b = EventCandidate.from_article_ids(reversed(article_ids))
    changed = EventCandidate.from_article_ids((*article_ids, article(url="https://example.com/c").article_id))
    assert candidate_a.event_candidate_id == candidate_b.event_candidate_id
    assert candidate_a.article_ids == tuple(sorted(article_ids))
    assert candidate_a.event_candidate_id != changed.event_candidate_id
    assert stable_event_candidate_id(article_ids) == candidate_a.event_candidate_id
    expect_contract_error(lambda: EventCandidate.from_article_ids((*article_ids, article_ids[0])))


def test_event_lifecycle_is_immutable_and_allows_written_unclassified() -> None:
    candidate = EventCandidate.from_article_ids((article(url="https://example.com/a").article_id,))
    selected = Event.from_candidate(candidate, selection_order=1)
    classification = EventClassification(EventCategory.TECHNOLOGY_AI)
    writing = EventWriting(
        title_zh="事件标题",
        summary_zh="事实摘要",
        why_it_matters_zh="说明关注原因",
    )
    classified = selected.with_classification(classification)
    written_unclassified = selected.with_writing(writing)
    classified_written = classified.with_writing(writing)
    assert selected.classification is None and selected.writing is None
    assert classified.classification == classification and classified.writing is None
    assert written_unclassified.classification is None and written_unclassified.writing == writing
    assert classified_written.classification == classification and classified_written.writing == writing
    assert selected.event_id == classified_written.event_id
    assert selected.article_ids == classified_written.article_ids
    assert selected.selection_order == classified_written.selection_order
    assert {EventClassification(category).category for category in EventCategory} == set(EventCategory)
    validate_event_selection_order((selected,))
    expect_contract_error(lambda: validate_event_selection_order((selected, selected)))
    expect_contract_error(lambda: Event.from_candidate(candidate, selection_order=0))
    expect_contract_error(lambda: EventClassification("not-a-category"))
    expect_contract_error(
        lambda: EventWriting(title_zh="", summary_zh="事实摘要", why_it_matters_zh="说明关注原因")
    )


def test_brief_report_slot_identity_and_window_semantics() -> None:
    window_start = datetime(2026, 8, 25, 16, 0, tzinfo=UTC_PLUS_EIGHT)
    window_end = datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc)
    first = Brief.from_report_slot(
        report_date=REPORT_DATE,
        window_start=window_start,
        window_end=window_end,
        event_ids=("evt_" + "a" * 24,),
        generation_status=GenerationStatus.PARTIAL,
    )
    rerun = Brief.from_report_slot(
        report_date=REPORT_DATE,
        window_start=window_start.astimezone(timezone.utc),
        window_end=window_end,
        event_ids=first.event_ids,
        generation_status=GenerationStatus.PARTIAL,
    )
    different_slot = Brief.from_report_slot(
        report_date=REPORT_DATE,
        window_start=window_start,
        window_end=datetime(2026, 8, 26, 9, 0, tzinfo=timezone.utc),
        event_ids=first.event_ids,
    )
    assert first.target_language == "zh-CN"
    assert first.brief_id == rerun.brief_id == stable_brief_id(REPORT_DATE, window_start, window_end)
    assert first.brief_id != different_slot.brief_id
    assert first.event_ids == ("evt_" + "a" * 24,)
    assert first.report_date == REPORT_DATE
    assert datetime_in_report_window(window_start, window_start, window_end)
    assert datetime_in_report_window(window_end, window_start, window_end)
    empty = Brief.from_report_slot(REPORT_DATE, window_start, window_end)
    assert empty.generation_status == GenerationStatus.COMPLETE and empty.event_ids == ()
    expect_contract_error(lambda: validate_report_window(window_end, window_start))
    expect_contract_error(lambda: validate_report_window(window_start, window_start))
    expect_contract_error(
        lambda: Brief.from_report_slot(
            REPORT_DATE,
            window_start,
            window_end,
            target_language="en",
        )
    )
    expect_contract_error(
        lambda: Brief.from_report_slot(
            report_date=REPORT_DATE,
            window_start=datetime(2026, 8, 25, 16, 0),
            window_end=window_end,
        )
    )


def test_stage_result_and_failure_invariants() -> None:
    success = StageResult(stage=StageName.EVENT_SELECTOR, status=StageStatus.SUCCEEDED, outputs=())
    success_with_output = StageResult(stage="event_selector", status="succeeded", outputs=("event",))
    partial = StageResult(
        stage="event_writer",
        status="partial",
        outputs=("written-event",),
        failures=(ItemFailure(item_id="evt_" + "a" * 24, code=FailureCode.TIMEOUT),),
    )
    failed = StageResult(
        stage="event_classifier",
        status="failed",
        outputs=(),
        failures=(ItemFailure(code="provider_failed"),),
    )
    assert success.outputs == ()
    assert success_with_output.outputs == ("event",)
    assert partial.status == StageStatus.PARTIAL and len(partial.failures) == 1
    assert failed.status == StageStatus.FAILED and failed.outputs == ()
    assert {failure.code for failure in (ItemFailure(code=code) for code in FailureCode)} == set(FailureCode)
    expect_contract_error(
        lambda: StageResult(stage="event_selector", status="succeeded", failures=(ItemFailure(code="timeout"),))
    )
    expect_contract_error(lambda: StageResult(stage="event_writer", status="partial", outputs=()))
    expect_contract_error(
        lambda: StageResult(stage="event_writer", status="partial", outputs=("x",), failures=())
    )
    expect_contract_error(
        lambda: StageResult(
            stage="event_writer",
            status="failed",
            outputs=("x",),
            failures=(ItemFailure(code="timeout"),),
        )
    )
    expect_contract_error(lambda: ItemFailure(code="unknown_code"))


def test_serialization_is_deterministic_and_round_trips() -> None:
    canonical_article = article(url="https://example.com/serialize")
    candidate = EventCandidate.from_article_ids((canonical_article.article_id,))
    event = Event.from_candidate(candidate, selection_order=1).with_writing(
        EventWriting("序列化标题", "序列化摘要", "序列化原因")
    )
    brief = Brief.from_report_slot(
        REPORT_DATE,
        datetime(2026, 8, 25, 16, 0, tzinfo=UTC_PLUS_EIGHT),
        datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc),
        event_ids=(event.event_id,),
    )
    stage = StageResult(
        stage="event_writer",
        status="partial",
        outputs=(event,),
        failures=(ItemFailure(code="timeout"),),
        diagnostic_ref="diag-1",
    )
    for value, serializer, deserializer in (
        (canonical_article, serialize_article, deserialize_article),
        (candidate, serialize_event_candidate, deserialize_event_candidate),
        (
            EventClassification(EventCategory.TECHNOLOGY_AI),
            serialize_event_classification,
            deserialize_event_classification,
        ),
        (EventWriting("标题", "摘要", "原因"), serialize_event_writing, deserialize_event_writing),
        (
            ItemFailure(item_id=canonical_article.article_id, code=FailureCode.TIMEOUT),
            serialize_item_failure,
            deserialize_item_failure,
        ),
        (event, serialize_event, deserialize_event),
        (brief, serialize_brief, deserialize_brief),
    ):
        encoded = serializer(value)
        assert encoded == serializer(value)
        assert deserializer(encoded) == value
        assert json.loads(encoded)["contract_version"] == "v1.0-core-data-contract"

    encoded_stage = serialize_stage_result(stage, output_serializer=lambda output: output.to_dict())
    decoded_stage = deserialize_stage_result(encoded_stage, output_loader=Event.from_dict)
    assert decoded_stage == stage
    assert deserialize_domain(serialize_domain(event)) == event


def main() -> None:
    test_article_identity_and_time_validation()
    test_event_candidate_identity_and_duplicate_policy()
    test_event_lifecycle_is_immutable_and_allows_written_unclassified()
    test_brief_report_slot_identity_and_window_semantics()
    test_stage_result_and_failure_invariants()
    test_serialization_is_deterministic_and_round_trips()
    print("offline canonical domain smoke passed")


if __name__ == "__main__":
    main()
