"""Deterministic Generation 2 projection from written Events to Markdown."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from html import escape as html_escape
from typing import Any, Iterable, Mapping

from canonical_domain import (
    Article,
    Brief,
    CanonicalContractError,
    Event,
    FailureCode,
    GenerationStatus,
    ItemFailure,
    StageName,
    StageResult,
    StageStatus,
    TARGET_LANGUAGE,
    validate_event_selection_order,
)


_GENERATION_STAGES = frozenset(
    {
        StageName.COLLECTOR,
        StageName.NORMALIZER,
        StageName.ARTICLE_DEDUP,
        StageName.EVENT_CLUSTER,
        StageName.EVENT_SELECTOR,
        StageName.EVENT_CLASSIFIER,
        StageName.EVENT_WRITER,
    }
)
_EARLIER_COVERAGE_STAGES = frozenset(
    {
        StageName.COLLECTOR,
        StageName.NORMALIZER,
        StageName.ARTICLE_DEDUP,
        StageName.EVENT_CLUSTER,
    }
)


@dataclass(frozen=True)
class SourceProjection:
    """The limited source data allowed in reader-facing Markdown."""

    source: str
    url: str | None


@dataclass(frozen=True)
class BriefRenderResult:
    """The renderer StageResult together with its deterministic Markdown artifact."""

    stage_result: StageResult[Brief]
    markdown: str | None

    @property
    def result(self) -> StageResult[Brief]:
        """Compatibility alias for callers that name the envelope ``result``."""

        return self.stage_result

    @property
    def stage(self) -> StageName:
        return self.stage_result.stage

    @property
    def status(self) -> StageStatus:
        return self.stage_result.status

    @property
    def outputs(self) -> tuple[Brief, ...]:
        return self.stage_result.outputs

    @property
    def failures(self) -> tuple[ItemFailure, ...]:
        return self.stage_result.failures

    @property
    def diagnostic_ref(self) -> str | None:
        return self.stage_result.diagnostic_ref

    @property
    def brief(self) -> Brief | None:
        if not self.stage_result.outputs:
            return None
        return self.stage_result.outputs[0]


def _failed(code: FailureCode, *, item_id: str | None = None) -> BriefRenderResult:
    return BriefRenderResult(
        stage_result=StageResult(
            stage=StageName.BRIEF_RENDERER,
            status=StageStatus.FAILED,
            failures=(ItemFailure(item_id=item_id, code=code),),
        ),
        markdown=None,
    )


def _normalize_articles(value: Any) -> dict[str, Article]:
    if isinstance(value, (str, bytes)):
        raise CanonicalContractError("articles must be an iterable or mapping")
    if isinstance(value, Mapping):
        articles: dict[str, Article] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not isinstance(item, Article) or key != item.article_id:
                raise CanonicalContractError("article lookup keys must match canonical Article IDs")
            if key in articles:
                raise CanonicalContractError("articles must not contain duplicate IDs")
            articles[key] = item
        return articles

    try:
        values = tuple(value)
    except (TypeError, ValueError) as exc:
        raise CanonicalContractError("articles must be an iterable or mapping") from exc
    articles = {}
    for item in values:
        if not isinstance(item, Article):
            raise CanonicalContractError("articles must contain Article objects")
        if item.article_id in articles:
            raise CanonicalContractError("articles must not contain duplicate IDs")
        articles[item.article_id] = item
    return articles


def _normalize_upstream_results(value: Any) -> tuple[StageResult[Any], ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        raise CanonicalContractError("upstream_results must be an iterable")
    try:
        results = tuple(value.values()) if isinstance(value, Mapping) else tuple(value)
    except (TypeError, ValueError) as exc:
        raise CanonicalContractError("upstream_results must be an iterable") from exc
    if any(not isinstance(result, StageResult) for result in results):
        raise CanonicalContractError("upstream_results must contain StageResult objects")
    return results


def project_sources(articles: Iterable[Article]) -> tuple[SourceProjection, ...]:
    """Project source name and canonical link, preserving input order.

    Only exact canonical URL duplicates are removed.  Linkless Articles remain
    separate entries because they have no URL on which to perform exact dedup.
    """

    if isinstance(articles, (str, bytes)):
        raise CanonicalContractError("source articles must be an iterable")
    try:
        values = tuple(articles)
    except (TypeError, ValueError) as exc:
        raise CanonicalContractError("source articles must be an iterable") from exc

    projected: list[SourceProjection] = []
    seen_urls: set[str] = set()
    for article in values:
        if not isinstance(article, Article):
            raise CanonicalContractError("source articles must contain Article objects")
        url = article.canonical_url or article.url
        if url is not None:
            if url in seen_urls:
                continue
            seen_urls.add(url)
        projected.append(SourceProjection(source=article.source, url=url))
    return tuple(projected)


def _reader_text(value: str) -> str:
    """Keep writer-owned text on one safe reader-facing Markdown line."""

    normalized = value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    normalized = html_escape(normalized, quote=False)
    for character, escaped in (
        ("\\", "\\\\"),
        ("`", "\\`"),
        ("*", "\\*"),
        ("_", "\\_"),
        ("[", "\\["),
        ("]", "\\]"),
        ("|", "\\|"),
    ):
        normalized = normalized.replace(character, escaped)
    return normalized


def _validate_selected_events(
    selector_result: StageResult[Any],
    article_lookup: Mapping[str, Article],
) -> tuple[Event, ...]:
    if not isinstance(selector_result, StageResult) or selector_result.stage is not StageName.EVENT_SELECTOR:
        raise CanonicalContractError("selector_result must be a selection StageResult")
    if selector_result.status is StageStatus.FAILED:
        raise RuntimeError("selector result is not trustworthy")
    events = tuple(selector_result.outputs)
    if any(not isinstance(event, Event) for event in events):
        raise CanonicalContractError("selector outputs must contain Event objects")
    try:
        validate_event_selection_order(events)
    except CanonicalContractError as exc:
        raise CanonicalContractError("selector outputs have invalid selection order") from exc
    for event in events:
        if any(article_id not in article_lookup for article_id in event.article_ids):
            raise CanonicalContractError("selector Event references an unresolved Article")
    return events


def _validate_written_events(
    writer_result: StageResult[Any],
    selected_events: tuple[Event, ...],
    article_lookup: Mapping[str, Article],
) -> tuple[Event, ...]:
    if not isinstance(writer_result, StageResult) or writer_result.stage is not StageName.EVENT_WRITER:
        raise CanonicalContractError("writer_result must be a writing StageResult")
    if writer_result.status is StageStatus.FAILED:
        raise RuntimeError("writer result has no usable outputs")

    selected_by_id = {event.event_id: event for event in selected_events}
    written = tuple(writer_result.outputs)
    if any(not isinstance(event, Event) for event in written):
        raise CanonicalContractError("writer outputs must contain Event objects")
    if len({event.event_id for event in written}) != len(written):
        raise CanonicalContractError("writer outputs must not contain duplicate Event IDs")

    for event in written:
        selected = selected_by_id.get(event.event_id)
        if selected is None:
            raise CanonicalContractError("writer output references an unselected Event")
        if event.article_ids != selected.article_ids or event.selection_order != selected.selection_order:
            raise CanonicalContractError("writer output changed selector-owned Event fields")
        if event.writing is None:
            raise CanonicalContractError("writer output must contain EventWriting")
        if any(article_id not in article_lookup for article_id in event.article_ids):
            raise CanonicalContractError("writer Event references an unresolved Article")

    if selected_events and not written:
        raise RuntimeError("non-empty selection has no written output")
    if writer_result.status is StageStatus.SUCCEEDED and {
        event.event_id for event in written
    } != set(selected_by_id):
        raise CanonicalContractError("succeeded writer result did not retain every selected Event")

    return tuple(sorted(written, key=lambda event: event.selection_order))


def _derive_generation_status(
    selector_result: StageResult[Any],
    writer_result: StageResult[Any],
    upstream_results: tuple[StageResult[Any], ...],
    selected_events: tuple[Event, ...],
    written_events: tuple[Event, ...],
) -> GenerationStatus:
    results = (selector_result, writer_result, *upstream_results)
    hard_failed = any(
        result.status is StageStatus.FAILED
        and result.stage not in {StageName.EVENT_CLASSIFIER, StageName.DELIVERY}
        for result in results
        if result.stage in _GENERATION_STAGES or result.stage is StageName.DELIVERY
    )
    if hard_failed:
        raise RuntimeError("a generation stage has no trustworthy output")

    degraded = any(
        result.stage in _GENERATION_STAGES and result.failures
        for result in results
    )
    earlier_partial = any(
        result.stage in _EARLIER_COVERAGE_STAGES and result.status is StageStatus.PARTIAL
        for result in results
    )
    if not degraded:
        return GenerationStatus.COMPLETE
    if written_events or (not selected_events and earlier_partial):
        return GenerationStatus.PARTIAL
    raise RuntimeError("generation degradation cannot produce a valid Brief")


def _render_markdown(
    brief: Brief,
    written_events: tuple[Event, ...],
    article_lookup: Mapping[str, Article],
) -> str:
    lines = [
        f"# 早间简报｜{brief.report_date.isoformat()}",
        "",
    ]
    if brief.generation_status is GenerationStatus.PARTIAL:
        lines.extend(["> 本次简报部分生成，可能存在少量遗漏。", ""])
    lines.extend(["## 今日要闻", ""])

    if not written_events:
        lines.append("本报告窗口内暂无入选事件。")
        return "\n".join(lines).rstrip() + "\n"

    for event in written_events:
        writing = event.writing
        if writing is None:
            raise CanonicalContractError("written Event must contain EventWriting")
        lines.extend(
            [
                f"### {_reader_text(writing.title_zh)}",
                "",
                _reader_text(writing.summary_zh),
                "",
                f"为什么重要：{_reader_text(writing.why_it_matters_zh)}",
                "",
            ]
        )
        sources = project_sources(article_lookup[article_id] for article_id in event.article_ids)
        lines.extend(
            [
                "<details>",
                f"<summary>来源（{len(sources)}）</summary>",
                "",
            ]
        )
        for source in sources:
            source_name = _reader_text(source.source)
            if source.url is None:
                lines.append(f"- {source_name} · 原文链接不可用")
            else:
                lines.append(f"- {source_name} · [原文](<{source.url}>)")
        lines.extend(["", "</details>", ""])

    return "\n".join(lines).rstrip() + "\n"


def render_brief(
    selector_result: StageResult[Event],
    writer_result: StageResult[Event],
    articles: Mapping[str, Article] | Iterable[Article],
    report_date: date | str,
    window_start: datetime,
    window_end: datetime,
    upstream_results: Iterable[StageResult[Any]] = (),
) -> BriefRenderResult:
    """Compose one canonical Brief and its reader-facing Markdown artifact.

    ``selector_result`` remains the authority for selection order and
    ``writer_result`` contributes only successful written Events.  No event is
    re-numbered or removed for layout reasons.
    """

    try:
        article_lookup = _normalize_articles(articles)
        normalized_upstream = _normalize_upstream_results(upstream_results)
        selected_events = _validate_selected_events(selector_result, article_lookup)
        written_events = _validate_written_events(writer_result, selected_events, article_lookup)
        generation_status = _derive_generation_status(
            selector_result,
            writer_result,
            normalized_upstream,
            selected_events,
            written_events,
        )
        brief = Brief.from_report_slot(
            report_date=report_date,
            window_start=window_start,
            window_end=window_end,
            event_ids=(event.event_id for event in written_events),
            generation_status=generation_status,
            target_language=TARGET_LANGUAGE,
        )
    except RuntimeError:
        return _failed(FailureCode.RENDER_FAILED)
    except (CanonicalContractError, TypeError, ValueError):
        return _failed(FailureCode.INVALID_INPUT)

    try:
        markdown = _render_markdown(brief, written_events, article_lookup)
    except Exception:
        return _failed(FailureCode.RENDER_FAILED)
    return BriefRenderResult(
        stage_result=StageResult(
            stage=StageName.BRIEF_RENDERER,
            status=StageStatus.SUCCEEDED,
            outputs=(brief,),
        ),
        markdown=markdown,
    )


__all__ = ["BriefRenderResult", "SourceProjection", "project_sources", "render_brief"]
