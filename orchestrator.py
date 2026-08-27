"""Generation 2 runtime composition for the frozen Morning Brief stages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
import uuid

from article_dedup import deduplicate_articles
from brief_renderer import render_brief
from canonical_domain import (
    Article,
    Brief,
    CanonicalContractError,
    Event,
    StageName,
    StageResult,
    StageStatus,
    TARGET_LANGUAGE,
)
from collector import FeedFetcher, SourceBatch, SourceConfig, collect_sources
from event_classifier import ClassifierGateway, classify_events
from event_cluster import EmbeddingBackend, cluster_articles
from event_selector import SelectorGateway, select_events
from event_writer import WriterGateway, write_events
from normalizer import admit_articles_to_report_window, normalize_source_batches
from v1_artifacts import ArtifactRun, V1ArtifactManager


@dataclass(frozen=True)
class GenerationRunResult:
    """Runtime-only result for one Generation 2 orchestration attempt."""

    run_id: str
    stage_results: tuple[StageResult[Any], ...]
    brief: Brief | None
    rendered_markdown: str | None
    run_dir: Path | None
    generation_outcome: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_run_id() -> str:
    return f"gen2-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}-{uuid.uuid4().hex[:12]}"


def _source_batch_payload(batch: SourceBatch) -> dict[str, Any]:
    return {
        "source": {
            "name": batch.source.name,
            "url": batch.source.url,
            "language": batch.source.language,
        },
        "collected_at": batch.collected_at.isoformat(),
        "entries": [
            {
                "ordinal": entry.ordinal,
                "entry_id": entry.entry_id,
                "title": entry.title,
                "link": entry.link,
                "summary": entry.summary,
                "description": entry.description,
                "published": entry.published,
                "updated": entry.updated,
            }
            for entry in batch.entries
        ],
    }


def _diagnostic_record(result: StageResult[Any]) -> dict[str, str] | None:
    if result.diagnostic_ref is None:
        return None
    record = {
        "status": result.status.value,
        "reason": result.diagnostic_ref,
    }
    if result.failures:
        record["failure_code"] = result.failures[0].code.value
    return record


def _checkpoint(
    run: ArtifactRun,
    result: StageResult[Any],
    *,
    object_name: str | None = None,
    output_serializer: Callable[[Any], Any] | None = None,
) -> None:
    run.persist_stage_result(
        result,
        output_serializer=output_serializer,
        diagnostic_record=_diagnostic_record(result),
    )
    if object_name is not None:
        run.persist_objects(object_name, result.outputs)


def _failed_run(
    run: ArtifactRun,
    stage_results: list[StageResult[Any]],
) -> GenerationRunResult:
    paths = run.finalize(
        run_status="failed",
        metadata={"generation_outcome": "failed"},
    )
    return GenerationRunResult(
        run_id=run.run_id,
        stage_results=tuple(stage_results),
        brief=None,
        rendered_markdown=None,
        run_dir=paths.run_dir,
        generation_outcome="failed",
    )


def _overlay_classifier_results(
    selected_events: tuple[Event, ...],
    classifier_result: StageResult[Event],
) -> tuple[Event, ...]:
    classified_by_id: dict[str, Event] = {}
    selected_by_id = {event.event_id: event for event in selected_events}
    for classified in classifier_result.outputs:
        if not isinstance(classified, Event) or classified.event_id in classified_by_id:
            raise CanonicalContractError("classifier outputs must contain unique Events")
        selected = selected_by_id.get(classified.event_id)
        if selected is None:
            raise CanonicalContractError("classifier output references an unselected Event")
        if (
            classified.article_ids != selected.article_ids
            or classified.selection_order != selected.selection_order
            or classified.writing is not None
            or classified.classification is None
        ):
            raise CanonicalContractError("classifier output changed selector-owned Event fields")
        classified_by_id[classified.event_id] = classified

    writer_inputs = tuple(
        classified_by_id.get(selected.event_id, selected) for selected in selected_events
    )
    if len(writer_inputs) != len(selected_events):
        raise CanonicalContractError("writer input count changed after classifier overlay")
    if tuple(event.event_id for event in writer_inputs) != tuple(
        event.event_id for event in selected_events
    ):
        raise CanonicalContractError("writer input sequence changed after classifier overlay")
    for writer_input, selected in zip(writer_inputs, selected_events):
        if (
            writer_input.article_ids != selected.article_ids
            or writer_input.selection_order != selected.selection_order
        ):
            raise CanonicalContractError("writer input changed selector-owned Event fields")
    return writer_inputs


def run_generation_2(
    *,
    report_date: date | str,
    window_start: datetime,
    window_end: datetime,
    target_language: str,
    sources: Iterable[SourceConfig],
    selector_gateway: SelectorGateway,
    classifier_gateway: ClassifierGateway,
    writer_gateway: WriterGateway,
    embedder_factory: Callable[[], EmbeddingBackend] | None,
    artifact_manager: V1ArtifactManager,
    run_id: str | None = None,
    collector_fetcher: FeedFetcher | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> GenerationRunResult:
    """Execute the frozen Generation 2 continuation matrix without fallback."""

    report_slot = Brief.from_report_slot(
        report_date=report_date,
        window_start=window_start,
        window_end=window_end,
        target_language=target_language,
    )
    if target_language != TARGET_LANGUAGE:
        raise CanonicalContractError(f"target_language must be {TARGET_LANGUAGE}")
    if isinstance(sources, (str, bytes)):
        raise ValueError("sources must be an iterable")
    source_values = tuple(sources)
    if any(not isinstance(source, SourceConfig) for source in source_values):
        raise ValueError("sources must contain SourceConfig objects")
    if not isinstance(artifact_manager, V1ArtifactManager):
        raise ValueError("artifact_manager must be V1ArtifactManager")

    resolved_run_id = run_id or _new_run_id()
    run = artifact_manager.start_run(
        resolved_run_id,
        metadata={
            "report_date": report_slot.report_date.isoformat(),
            "window_start": report_slot.window_start.isoformat(),
            "window_end": report_slot.window_end.isoformat(),
            "target_language": report_slot.target_language,
        },
    )
    stage_results: list[StageResult[Any]] = []

    collector_result = collect_sources(
        source_values,
        fetcher=collector_fetcher,
        clock=clock,
    )
    stage_results.append(collector_result)
    _checkpoint(run, collector_result, output_serializer=_source_batch_payload)
    if collector_result.status is StageStatus.FAILED:
        return _failed_run(run, stage_results)

    normalizer_result = normalize_source_batches(collector_result.outputs)
    stage_results.append(normalizer_result)
    _checkpoint(run, normalizer_result, object_name="articles-normalized")
    if normalizer_result.status is StageStatus.FAILED:
        return _failed_run(run, stage_results)

    admitted_articles = admit_articles_to_report_window(
        normalizer_result.outputs,
        report_slot.window_start,
        report_slot.window_end,
    )
    excluded_count = len(normalizer_result.outputs) - len(admitted_articles)
    run.persist_diagnostic(
        {
            "status": "succeeded",
            "reason": "report_window_admission",
            "excluded_count": excluded_count,
        },
        diagnostic_ref="normalizer:report-window-admission",
    )
    run.persist_objects("articles-admitted", admitted_articles)

    dedup_result = deduplicate_articles(admitted_articles)
    stage_results.append(dedup_result)
    _checkpoint(run, dedup_result, object_name="articles")
    if dedup_result.status is StageStatus.FAILED:
        return _failed_run(run, stage_results)

    article_lookup: Mapping[str, Article] = {
        article.article_id: article for article in dedup_result.outputs
    }
    cluster_result = cluster_articles(
        dedup_result.outputs,
        embedder_factory=embedder_factory,
    )
    stage_results.append(cluster_result)
    _checkpoint(run, cluster_result, object_name="event-candidates")
    if cluster_result.status is StageStatus.FAILED:
        return _failed_run(run, stage_results)

    selector_result = select_events(
        cluster_result.outputs,
        article_lookup,
        report_slot.window_start,
        report_slot.window_end,
        selector_gateway,
    )
    stage_results.append(selector_result)
    _checkpoint(run, selector_result, object_name="events-selected")
    if selector_result.status is StageStatus.FAILED:
        return _failed_run(run, stage_results)

    selected_events = tuple(selector_result.outputs)
    classifier_result = classify_events(
        selected_events,
        article_lookup,
        classifier_gateway,
    )
    stage_results.append(classifier_result)
    _checkpoint(run, classifier_result, object_name="events-classified")

    writer_inputs = _overlay_classifier_results(selected_events, classifier_result)
    run.persist_objects("events-writer-input", writer_inputs)

    writer_result = write_events(writer_inputs, article_lookup, writer_gateway)
    stage_results.append(writer_result)
    _checkpoint(run, writer_result, object_name="events-written")
    if selected_events and writer_result.status is StageStatus.FAILED:
        return _failed_run(run, stage_results)

    render_result = render_brief(
        selector_result=selector_result,
        writer_result=writer_result,
        articles=article_lookup,
        report_date=report_slot.report_date,
        window_start=report_slot.window_start,
        window_end=report_slot.window_end,
        upstream_results=(
            collector_result,
            normalizer_result,
            dedup_result,
            cluster_result,
            classifier_result,
        ),
    )
    stage_results.append(render_result.stage_result)
    _checkpoint(run, render_result.stage_result)
    if render_result.stage_result.status is StageStatus.FAILED:
        return _failed_run(run, stage_results)

    brief = render_result.brief
    markdown = render_result.markdown
    if brief is None or markdown is None:
        raise CanonicalContractError("successful renderer must provide Brief and Markdown")
    run.persist_brief(brief, markdown)
    outcome = brief.generation_status.value
    paths = run.finalize(
        run_status=outcome,
        metadata={"generation_outcome": outcome},
    )
    return GenerationRunResult(
        run_id=run.run_id,
        stage_results=tuple(stage_results),
        brief=brief,
        rendered_markdown=markdown,
        run_dir=paths.run_dir,
        generation_outcome=outcome,
    )


__all__ = ["GenerationRunResult", "run_generation_2"]
