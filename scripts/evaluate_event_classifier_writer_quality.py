#!/usr/bin/env python3
"""Explicit v1.5 Classifier + Writer quality-validation runner.

The default dry-run exercises the complete fixture -> classifier -> continuation
-> writer path with a local fake gateway.  A real provider call requires the
explicit ``--real-provider deepseek`` opt-in.  Reports are printed to stdout,
are safe for manual review, and are never persisted automatically.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from canonical_domain import (  # noqa: E402
    Article,
    Event,
    EventCandidate,
    StageResult,
    StageStatus,
    datetime_in_report_window,
    normalize_canonical_datetime,
    validate_event_selection_order,
    validate_report_window,
)
from event_classifier import ClassifierGateway, classify_events  # noqa: E402
from event_writer import WriterGateway, write_events  # noqa: E402
from generation_2_runtime import (  # noqa: E402
    DEEPSEEK_API_KEY_ENV,
    DEEPSEEK_ENDPOINT,
    DEEPSEEK_MAX_ATTEMPTS,
    DEEPSEEK_MAX_TOKENS,
    DEEPSEEK_MODEL,
    DEEPSEEK_PROVIDER_ID,
    DEEPSEEK_TIMEOUT_SECONDS,
    DeepSeekGeneration2Gateway,
    build_deepseek_generation_2_gateway,
)
from llm_gateway import GatewayResponse  # noqa: E402


FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "event_classifier_writer_quality_v1_5.json"
)
_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class QualityFixture:
    """Synthetic selected Events and their manual review annotations."""

    fixture_id: str
    provenance: str
    window_start: datetime
    window_end: datetime
    selected_events: tuple[Event, ...]
    articles: tuple[Article, ...]
    event_key_by_id: Mapping[str, str]
    expected_category_note_by_id: Mapping[str, str]


@dataclass(frozen=True)
class QualityRun:
    """The two independent stage results and test-local continuation input."""

    classifier_result: StageResult[Event]
    continuation_events: tuple[Event, ...]
    writer_result: StageResult[Event]


class _OfflineQualityGateway:
    """Deterministic no-network gateway used by the default dry-run."""

    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> GatewayResponse:
        if parameters is not None:
            raise ValueError("offline gateway does not accept provider parameters")
        if not messages or not isinstance(messages[-1], Mapping):
            raise ValueError("offline gateway received an invalid message sequence")
        content = messages[-1].get("content")
        if not isinstance(content, str):
            raise ValueError("offline gateway received invalid message content")
        _, separator, encoded_projection = content.partition("\n")
        if not separator:
            raise ValueError("offline gateway received an unprojected message")
        projection = json.loads(encoded_projection)
        event_projection = projection["events"][0]
        event_id = event_projection["event_id"]
        if "target_language" in projection:
            payload = {
                "writings": [
                    {
                        "event_id": event_id,
                        "title_zh": "离线验证事件进展",
                        "summary_zh": "离线 fake gateway 返回用于验证链路的中文事件综合。",
                        "why_it_matters_zh": "普通读者今天需要知道这项事件的具体进展。",
                    }
                ]
            }
        else:
            payload = {
                "classifications": [
                    {"event_id": event_id, "category": "other"}
                ]
            }
        return GatewayResponse(
            payload=payload,
            attempts=1,
            provider_id="offline",
            model="fixture",
        )


_DeepSeekQualityGateway = DeepSeekGeneration2Gateway


def _require_exact_keys(
    value: Mapping[str, Any], expected: set[str], context: str
) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys are invalid")


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    return value


def _required_key(value: Any, field_name: str) -> str:
    key = _required_text(value, field_name)
    if not _KEY_PATTERN.fullmatch(key):
        raise ValueError(f"{field_name} must be a lowercase hyphenated key")
    return key


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be an ISO datetime")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO datetime") from error
    return normalize_canonical_datetime(parsed, field_name)


def load_quality_fixture(path: Path) -> QualityFixture:
    """Load fixture metadata and construct selected canonical Events."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("fixture must be an object")
    _require_exact_keys(
        payload,
        {"fixture_id", "provenance", "window_start", "window_end", "events"},
        "fixture",
    )
    fixture_id = _required_key(payload["fixture_id"], "fixture_id")
    if payload["provenance"] != "synthetic":
        raise ValueError("fixture provenance must be synthetic")
    window_start, window_end = validate_report_window(
        _parse_datetime(payload["window_start"], "window_start"),
        _parse_datetime(payload["window_end"], "window_end"),
    )
    raw_events = payload["events"]
    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError("fixture events must be a non-empty list")

    articles: list[Article] = []
    events: list[Event] = []
    event_key_by_id: dict[str, str] = {}
    expected_category_note_by_id: dict[str, str] = {}
    event_keys_seen: set[str] = set()
    article_ids_seen: set[str] = set()
    selection_orders: list[int] = []

    for raw_event in raw_events:
        if not isinstance(raw_event, Mapping):
            raise ValueError("fixture event must be an object")
        _require_exact_keys(
            raw_event,
            {"event_key", "expected_category_note", "selection_order", "articles"},
            "fixture event",
        )
        event_key = _required_key(raw_event["event_key"], "event_key")
        expected_note = _required_text(
            raw_event["expected_category_note"], "expected_category_note"
        )
        selection_order = raw_event["selection_order"]
        if (
            isinstance(selection_order, bool)
            or not isinstance(selection_order, int)
            or selection_order < 1
        ):
            raise ValueError("selection_order must be a positive integer")
        if event_key in event_keys_seen:
            raise ValueError("fixture event keys must be unique")
        raw_articles = raw_event["articles"]
        if not isinstance(raw_articles, list) or not 2 <= len(raw_articles) <= 3:
            raise ValueError("fixture event articles must contain two or three items")

        event_articles: list[Article] = []
        for raw_article in raw_articles:
            if not isinstance(raw_article, Mapping):
                raise ValueError("fixture article must be an object")
            _require_exact_keys(
                raw_article,
                {"source", "url", "published_at", "language", "title", "summary"},
                "fixture article",
            )
            published_at = _parse_datetime(raw_article["published_at"], "published_at")
            if not datetime_in_report_window(published_at, window_start, window_end):
                raise ValueError("fixture article must fall inside the report window")
            summary = raw_article["summary"]
            if summary is not None and not isinstance(summary, str):
                raise ValueError("fixture article summary must be text or null")
            article = Article.from_source(
                source=_required_text(raw_article["source"], "source"),
                url=_required_text(raw_article["url"], "url"),
                published_at=published_at,
                collected_at=window_end,
                language=_required_text(raw_article["language"], "language"),
                title=_required_text(raw_article["title"], "title"),
                summary=summary,
            )
            if article.article_id in article_ids_seen:
                raise ValueError("fixture Article IDs must be unique across Events")
            article_ids_seen.add(article.article_id)
            event_articles.append(article)
            articles.append(article)

        candidate = EventCandidate.from_article_ids(
            article.article_id for article in event_articles
        )
        event = Event.from_candidate(candidate, selection_order=selection_order)
        if event.event_id in event_key_by_id:
            raise ValueError("fixture Event IDs must be unique")
        event_key_by_id[event.event_id] = event_key
        expected_category_note_by_id[event.event_id] = expected_note
        event_keys_seen.add(event_key)
        selection_orders.append(selection_order)
        events.append(event)

    if selection_orders != list(range(1, len(events) + 1)):
        raise ValueError("fixture selection_order values must be contiguous and ordered")
    validate_event_selection_order(events)
    return QualityFixture(
        fixture_id=fixture_id,
        provenance="synthetic",
        window_start=window_start,
        window_end=window_end,
        selected_events=tuple(events),
        articles=tuple(articles),
        event_key_by_id=event_key_by_id,
        expected_category_note_by_id=expected_category_note_by_id,
    )


def _continue_after_classifier(
    selected_events: Sequence[Event],
    classifier_result: StageResult[Event],
) -> tuple[Event, ...]:
    """Apply frozen continuation locally; this is not a production helper."""

    classified_by_id = {event.event_id: event for event in classifier_result.outputs}
    return tuple(
        classified_by_id.get(event.event_id, event) for event in selected_events
    )


def run_quality_validation(
    fixture: QualityFixture,
    gateway: ClassifierGateway | WriterGateway,
) -> QualityRun:
    """Run the real v1.5 stage chain against selected fixture Events."""

    classifier_result = classify_events(fixture.selected_events, fixture.articles, gateway)
    continuation_events = _continue_after_classifier(
        fixture.selected_events, classifier_result
    )
    writer_result = write_events(continuation_events, fixture.articles, gateway)
    return QualityRun(
        classifier_result=classifier_result,
        continuation_events=continuation_events,
        writer_result=writer_result,
    )


def _failure_dicts(result: StageResult[Event], event_id: str) -> list[dict[str, Any]]:
    return [
        failure.to_dict()
        for failure in result.failures
        if failure.item_id == event_id
    ]


def _technical_failure_dicts(run: QualityRun) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for stage_name, result in (
        ("classifier", run.classifier_result),
        ("writer", run.writer_result),
    ):
        for failure in result.failures:
            failures.append({"stage": stage_name, **failure.to_dict()})
    return failures


def render_quality_report(
    fixture: QualityFixture,
    run: QualityRun,
    *,
    mode: str,
    provider_id: str,
    model: str,
) -> dict[str, Any]:
    """Render only non-secret stage outcomes and reader-facing writing fields."""

    classified_by_id = {event.event_id: event for event in run.classifier_result.outputs}
    written_by_id = {event.event_id: event for event in run.writer_result.outputs}
    event_reports: list[dict[str, Any]] = []
    for event in fixture.selected_events:
        classified = classified_by_id.get(event.event_id)
        written = written_by_id.get(event.event_id)
        writing = None if written is None else written.writing
        event_reports.append(
            {
                "event_id": event.event_id,
                "expected_category_note": fixture.expected_category_note_by_id[
                    event.event_id
                ],
                "actual_category": (
                    None
                    if classified is None or classified.classification is None
                    else classified.classification.category.value
                ),
                "classifier_failure": _failure_dicts(
                    run.classifier_result, event.event_id
                ),
                "title_zh": None if writing is None else writing.title_zh,
                "summary_zh": None if writing is None else writing.summary_zh,
                "why_it_matters_zh": (
                    None if writing is None else writing.why_it_matters_zh
                ),
                "writer_failure": _failure_dicts(run.writer_result, event.event_id),
            }
        )

    diagnostic_refs: list[dict[str, str]] = []
    for stage_name, result in (
        ("classifier", run.classifier_result),
        ("writer", run.writer_result),
    ):
        if result.diagnostic_ref is not None:
            diagnostic_refs.append(
                {"stage": stage_name, "diagnostic_ref": result.diagnostic_ref}
            )
    return {
        "mode": mode,
        "provider_id": provider_id,
        "model": model,
        "fixture_id": fixture.fixture_id,
        "provenance": fixture.provenance,
        "event_count": len(fixture.selected_events),
        "classifier_stage_status": run.classifier_result.status.value,
        "writer_stage_status": run.writer_result.status.value,
        "technical_failures": _technical_failure_dicts(run),
        "diagnostic_refs": diagnostic_refs,
        "events": event_reports,
    }


def build_dry_run_report(fixture: QualityFixture) -> dict[str, Any]:
    run = run_quality_validation(fixture, _OfflineQualityGateway())
    return render_quality_report(
        fixture,
        run,
        mode="dry-run",
        provider_id="offline",
        model="fixture",
    )


def _deepseek_gateway() -> _DeepSeekQualityGateway:
    return build_deepseek_generation_2_gateway()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--real-provider", choices=(DEEPSEEK_PROVIDER_ID,))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        fixture = load_quality_fixture(args.fixture)
        if args.real_provider is None:
            run = run_quality_validation(fixture, _OfflineQualityGateway())
            mode = "dry-run"
            provider_id = "offline"
            model = "fixture"
        else:
            run = run_quality_validation(fixture, _deepseek_gateway())
            mode = "real-provider"
            provider_id = DEEPSEEK_PROVIDER_ID
            model = DEEPSEEK_MODEL
        report = render_quality_report(
            fixture,
            run,
            mode=mode,
            provider_id=provider_id,
            model=model,
        )
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        if args.real_provider is not None and (
            run.classifier_result.status is not StageStatus.SUCCEEDED
            or run.writer_result.status is not StageStatus.SUCCEEDED
        ):
            raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as error:
        raise SystemExit(
            f"event classifier/writer quality evaluation failed: {type(error).__name__}"
        ) from error


__all__ = [
    "DEEPSEEK_API_KEY_ENV",
    "DEEPSEEK_ENDPOINT",
    "DEEPSEEK_MAX_ATTEMPTS",
    "DEEPSEEK_MAX_TOKENS",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_PROVIDER_ID",
    "DEEPSEEK_TIMEOUT_SECONDS",
    "FIXTURE_PATH",
    "QualityFixture",
    "QualityRun",
    "_DeepSeekQualityGateway",
    "build_dry_run_report",
    "load_quality_fixture",
    "parse_args",
    "render_quality_report",
    "run_quality_validation",
]


if __name__ == "__main__":
    main()
