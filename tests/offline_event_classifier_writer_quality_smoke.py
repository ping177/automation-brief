"""Offline smoke tests for the v1.5 Classifier + Writer quality harness."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from canonical_domain import EventCategory, FailureCode, StageStatus  # noqa: E402
from evaluate_event_classifier_writer_quality import (  # noqa: E402
    DEEPSEEK_MAX_TOKENS,
    DEEPSEEK_MODEL,
    FIXTURE_PATH,
    _DeepSeekQualityGateway,
    build_dry_run_report,
    load_quality_fixture,
    parse_args,
    render_quality_report,
    run_quality_validation,
)
from llm_gateway import GatewayError, GatewayResponse  # noqa: E402


class ScriptedGateway:
    """No-network gateway that returns responses by stage and event ID."""

    def __init__(
        self,
        fixture,
        *,
        classifier_fail_ids: Sequence[str] = (),
        writer_fail_ids: Sequence[str] = (),
    ) -> None:
        self.category_by_id = {
            event.event_id: category.value
            for event, category in zip(
                fixture.selected_events,
                (
                    EventCategory.GEOPOLITICS,
                    EventCategory.MACRO_POLICY,
                    EventCategory.TECHNOLOGY_AI,
                    EventCategory.PUBLIC_SAFETY,
                    EventCategory.ENERGY_COMMODITIES,
                    EventCategory.CHINA_POLICY,
                ),
            )
        }
        self.classifier_fail_ids = set(classifier_fail_ids)
        self.writer_fail_ids = set(writer_fail_ids)
        self.calls: list[tuple[str, str, Sequence[Mapping[str, Any]]]] = []

    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> GatewayResponse:
        assert parameters is None
        content = messages[-1]["content"]
        _, separator, encoded_projection = content.partition("\n")
        assert separator
        projection = json.loads(encoded_projection)
        event_id = projection["events"][0]["event_id"]
        stage = "writer" if "target_language" in projection else "classifier"
        self.calls.append((stage, event_id, messages))
        if stage == "classifier" and event_id in self.classifier_fail_ids:
            raise GatewayError("transport_failed", 1)
        if stage == "writer" and event_id in self.writer_fail_ids:
            payload = {
                "writings": [
                    {
                        "event_id": event_id,
                        "title_zh": "English only title",
                        "summary_zh": "English only summary",
                        "why_it_matters_zh": "English only reason",
                    }
                ]
            }
        elif stage == "classifier":
            payload = {
                "classifications": [
                    {"event_id": event_id, "category": self.category_by_id[event_id]}
                ]
            }
        else:
            payload = {
                "writings": [
                    {
                        "event_id": event_id,
                        "title_zh": "事件综合标题",
                        "summary_zh": "事件综合摘要保留事实和后续进展。",
                        "why_it_matters_zh": "普通读者今天需要知道这项事件的具体影响。",
                    }
                ]
            }
        return GatewayResponse(
            payload=payload,
            attempts=1,
            provider_id="fixture",
            model="fixture-model",
        )


class CapturingDelegate:
    def __init__(self) -> None:
        self.parameters: object = None

    def complete_json(self, messages, *, parameters=None):
        self.parameters = parameters
        return GatewayResponse(
            payload={"classifications": []},
            attempts=1,
            provider_id="fixture",
            model="fixture-model",
        )


def _projection(messages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    content = messages[-1]["content"]
    _, separator, encoded_projection = content.partition("\n")
    assert separator
    return json.loads(encoded_projection)


def _assert_no_forbidden_projection_keys(value: object) -> None:
    forbidden = {
        "expected_category_note",
        "selection_order",
        "importance",
        "score",
        "legacy_category",
        "embedding",
        "cluster_diagnostics",
        "provenance",
        "writing",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for child in value.values():
            _assert_no_forbidden_projection_keys(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_forbidden_projection_keys(child)


def test_fixture_builds_selected_canonical_events_and_manual_notes() -> None:
    fixture = load_quality_fixture(FIXTURE_PATH)

    assert fixture.fixture_id == "v1-5-classifier-writer-representative-events"
    assert fixture.provenance == "synthetic"
    assert len(fixture.selected_events) == 6
    assert [event.selection_order for event in fixture.selected_events] == list(range(1, 7))
    assert all(2 <= len(event.article_ids) <= 3 for event in fixture.selected_events)
    assert len({article.article_id for article in fixture.articles}) == len(fixture.articles)
    assert len(fixture.event_key_by_id) == len(fixture.selected_events)
    notes = " ".join(fixture.expected_category_note_by_id.values()).casefold()
    for expected_phrase in ("geopolitics", "macro", "technology", "public safety", "judgment call"):
        assert expected_phrase in notes
    assert max(len(article.summary or "") for article in fixture.articles) > 500


def test_dry_run_exercises_both_stages_without_network_or_quality_score() -> None:
    fixture = load_quality_fixture(FIXTURE_PATH)

    report = build_dry_run_report(fixture)

    assert report["mode"] == "dry-run"
    assert report["provider_id"] == "offline"
    assert report["classifier_stage_status"] == "succeeded"
    assert report["writer_stage_status"] == "succeeded"
    assert len(report["events"]) == len(fixture.selected_events)
    assert all(item["actual_category"] == "other" for item in report["events"])
    assert all(item["title_zh"] and item["summary_zh"] for item in report["events"])
    serialized = json.dumps(report, ensure_ascii=False).casefold()
    assert "api_key" not in serialized
    assert "authorization" not in serialized
    assert ".env.local" not in serialized
    assert "score" not in serialized


def test_runner_projection_preserves_complete_bundle_and_hides_fixture_metadata() -> None:
    fixture = load_quality_fixture(FIXTURE_PATH)
    gateway = ScriptedGateway(fixture)

    run = run_quality_validation(fixture, gateway)

    assert run.classifier_result.status == StageStatus.SUCCEEDED
    assert run.writer_result.status == StageStatus.SUCCEEDED
    assert len(gateway.calls) == 2 * len(fixture.selected_events)
    expected_event_ids = [event.event_id for event in fixture.selected_events]
    assert [event_id for stage, event_id, _ in gateway.calls if stage == "classifier"] == expected_event_ids
    assert [event_id for stage, event_id, _ in gateway.calls if stage == "writer"] == expected_event_ids
    assert [event.selection_order for event in run.continuation_events] == list(range(1, 7))
    article_by_id = {article.article_id: article for article in fixture.articles}
    for stage, event, messages in gateway.calls:
        projection = _projection(messages)
        if stage == "classifier":
            assert set(projection) == {"events"}
            projected_event = projection["events"][0]
            assert set(projected_event) == {"event_id", "articles"}
            assert [item["article_id"] for item in projected_event["articles"]] == list(
                next(item for item in fixture.selected_events if item.event_id == event).article_ids
            )
            assert all(set(item) == {"article_id", "title", "summary", "language"} for item in projected_event["articles"])
        else:
            assert set(projection) == {"target_language", "events"}
            assert projection["target_language"] == "zh-CN"
            projected_event = projection["events"][0]
            assert set(projected_event) == {"event_id", "category", "articles"}
            assert projected_event["category"] in {category.value for category in EventCategory}
            assert [item["article_id"] for item in projected_event["articles"]] == list(
                next(item for item in fixture.selected_events if item.event_id == event).article_ids
            )
            for projected_article in projected_event["articles"]:
                original = article_by_id[projected_article["article_id"]]
                assert set(projected_article) == {
                    "article_id",
                    "source",
                    "url",
                    "published_at",
                    "language",
                    "title",
                    "summary",
                }
                assert projected_article["summary"] == original.summary
                assert len(projected_article["summary"]) == len(original.summary or "")
        _assert_no_forbidden_projection_keys(projection)
        assert "expected_category_note" not in json.dumps(messages, ensure_ascii=False)


def test_classifier_failure_continues_with_original_event_and_report_is_safe() -> None:
    fixture = load_quality_fixture(FIXTURE_PATH)
    failed_event = fixture.selected_events[1]
    gateway = ScriptedGateway(fixture, classifier_fail_ids=(failed_event.event_id,))

    run = run_quality_validation(fixture, gateway)
    report = render_quality_report(
        fixture,
        run,
        mode="offline-test",
        provider_id="fixture",
        model="fixture-model",
    )

    assert run.classifier_result.status == StageStatus.PARTIAL
    assert run.writer_result.status == StageStatus.SUCCEEDED
    assert run.continuation_events[1] is failed_event
    assert run.continuation_events[0].classification is not None
    failed_report = report["events"][1]
    assert failed_report["actual_category"] is None
    assert failed_report["classifier_failure"] == [
        {"item_id": failed_event.event_id, "code": FailureCode.TRANSPORT_FAILED.value}
    ]
    assert failed_report["title_zh"] is not None
    assert failed_report["writer_failure"] == []
    assert report["writer_stage_status"] == "succeeded"


def test_writer_failure_remains_local_and_does_not_backfill() -> None:
    fixture = load_quality_fixture(FIXTURE_PATH)
    failed_event = fixture.selected_events[3]
    gateway = ScriptedGateway(fixture, writer_fail_ids=(failed_event.event_id,))

    run = run_quality_validation(fixture, gateway)
    report = render_quality_report(
        fixture,
        run,
        mode="offline-test",
        provider_id="fixture",
        model="fixture-model",
    )

    assert run.classifier_result.status == StageStatus.SUCCEEDED
    assert run.writer_result.status == StageStatus.PARTIAL
    assert len(run.writer_result.outputs) == len(fixture.selected_events) - 1
    failed_report = report["events"][3]
    assert failed_report["title_zh"] is None
    assert failed_report["summary_zh"] is None
    assert failed_report["why_it_matters_zh"] is None
    assert failed_report["writer_failure"]
    assert all(item["title_zh"] for item in report["events"] if item["event_id"] != failed_event.event_id)
    serialized = json.dumps(report, ensure_ascii=False).casefold()
    assert "raw article fallback" not in serialized
    assert "placeholder" not in serialized


def test_deepseek_adapter_reuses_frozen_gateway_parameters() -> None:
    delegate = CapturingDelegate()
    gateway = _DeepSeekQualityGateway(delegate)

    gateway.complete_json([{"role": "user", "content": "fixture"}])

    assert delegate.parameters == {
        "max_tokens": DEEPSEEK_MAX_TOKENS,
        "thinking": {"type": "disabled"},
    }
    assert DEEPSEEK_MODEL == "deepseek-v4-flash"


def test_cli_defaults_to_dry_run_and_does_not_import_production_routing() -> None:
    args = parse_args(["--fixture", str(FIXTURE_PATH)])

    assert args.real_provider is None
    source = (PROJECT_ROOT / "scripts" / "evaluate_event_classifier_writer_quality.py").read_text(
        encoding="utf-8"
    )
    for forbidden_dependency in ("from main", "import main", "event_selector", "ai_curator"):
        assert forbidden_dependency not in source


def main() -> None:
    test_fixture_builds_selected_canonical_events_and_manual_notes()
    test_dry_run_exercises_both_stages_without_network_or_quality_score()
    test_runner_projection_preserves_complete_bundle_and_hides_fixture_metadata()
    test_classifier_failure_continues_with_original_event_and_report_is_safe()
    test_writer_failure_remains_local_and_does_not_backfill()
    test_deepseek_adapter_reuses_frozen_gateway_parameters()
    test_cli_defaults_to_dry_run_and_does_not_import_production_routing()
    print("offline event classifier/writer quality smoke passed")


if __name__ == "__main__":
    main()
