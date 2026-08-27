"""Offline v1.6 pure Brief renderer smoke tests.

The tests exercise only canonical domain fixtures and a deterministic renderer.
They do not import a provider, production routing, delivery, or a legacy
Morning Brief surface.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from brief_renderer import project_sources, render_brief  # noqa: E402
from canonical_domain import (  # noqa: E402
    Article,
    Event,
    EventCandidate,
    EventWriting,
    FailureCode,
    GenerationStatus,
    ItemFailure,
    StageName,
    StageResult,
    StageStatus,
)


REPORT_DATE = date(2026, 8, 27)
WINDOW_START = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc)
COLLECTED_AT = datetime(2026, 8, 27, 1, 0, tzinfo=timezone.utc)


def article(
    key: str,
    *,
    source: str | None = None,
    title: str | None = None,
    summary: str | None = "Source summary.",
    url: str | None = None,
) -> Article:
    return Article.from_source(
        source=source or f"Fixture Source {key}",
        url=url or f"https://fixture.example/{key}",
        published_at=COLLECTED_AT,
        collected_at=COLLECTED_AT,
        language="en",
        title=title or f"Raw source title {key}",
        summary=summary,
    )


def selected_event(*items: Article, order: int) -> Event:
    candidate = EventCandidate.from_article_ids(item.article_id for item in items)
    return Event.from_candidate(candidate, selection_order=order)


def written_event(event: Event, prefix: str) -> Event:
    return event.with_writing(
        EventWriting(
            title_zh=f"{prefix}中文标题",
            summary_zh=f"{prefix}中文摘要，只使用已经写入的事件事实。",
            why_it_matters_zh=f"{prefix}影响说明保持具体且基于已提供证据。",
        )
    )


def succeeded(stage: StageName, outputs: tuple[object, ...] = ()) -> StageResult[object]:
    return StageResult(stage=stage, status=StageStatus.SUCCEEDED, outputs=outputs)


def partial(
    stage: StageName,
    outputs: tuple[object, ...],
    *,
    item_id: str | None = None,
) -> StageResult[object]:
    return StageResult(
        stage=stage,
        status=StageStatus.PARTIAL,
        outputs=outputs,
        failures=(ItemFailure(item_id=item_id, code=FailureCode.TIMEOUT),),
    )


def failed(stage: StageName, *, item_id: str | None = None) -> StageResult[object]:
    return StageResult(
        stage=stage,
        status=StageStatus.FAILED,
        failures=(ItemFailure(item_id=item_id, code=FailureCode.TIMEOUT),),
    )


def complete_upstream(
    selector: StageResult[object],
    writer: StageResult[object],
    *,
    classifier_outputs: tuple[object, ...] = (),
) -> tuple[StageResult[object], ...]:
    return (
        succeeded(StageName.COLLECTOR, ("source-batch",)),
        succeeded(StageName.NORMALIZER),
        succeeded(StageName.ARTICLE_DEDUP),
        succeeded(StageName.EVENT_CLUSTER),
        selector,
        succeeded(StageName.EVENT_CLASSIFIER, classifier_outputs),
        writer,
    )


def test_normal_complete_brief_renders_all_written_events() -> None:
    first = article("first", source="Reuters", title="Raw Reuters headline")
    second = article("second", source="AP", title="Raw AP headline")
    remaining = [article(f"event-{index}") for index in range(3, 6)]
    articles = (first, second, *remaining)
    selected = (
        selected_event(first, second, order=1),
        *(selected_event(item, order=index) for index, item in enumerate(remaining, start=2)),
    )
    written = tuple(written_event(event, f"事件{index}") for index, event in enumerate(selected, start=1))
    selector_result = succeeded(StageName.EVENT_SELECTOR, selected)
    writer_result = succeeded(StageName.EVENT_WRITER, written)

    rendered = render_brief(
        selector_result,
        writer_result,
        articles,
        REPORT_DATE,
        WINDOW_START,
        WINDOW_END,
        upstream_results=complete_upstream(selector_result, writer_result, classifier_outputs=selected),
    )

    assert rendered.stage_result.stage == StageName.BRIEF_RENDERER
    assert rendered.stage_result.status == StageStatus.SUCCEEDED
    assert rendered.stage == StageName.BRIEF_RENDERER
    assert rendered.status == StageStatus.SUCCEEDED
    assert rendered.stage_result.failures == ()
    brief = rendered.stage_result.outputs[0]
    assert brief.generation_status == GenerationStatus.COMPLETE
    assert brief.event_ids == tuple(event.event_id for event in written)
    assert brief.window_start == WINDOW_START
    assert brief.window_end == WINDOW_END
    assert rendered.markdown is not None
    markdown = rendered.markdown
    assert markdown.startswith("# 早间简报｜2026-08-27")
    assert "报告窗口：" not in markdown
    assert "生成状态：完整" not in markdown
    assert markdown.count("### ") == 4
    for event in written:
        assert event.writing is not None
        assert event.writing.title_zh in markdown
        assert event.writing.summary_zh in markdown
        assert event.writing.why_it_matters_zh in markdown
    assert "Raw Reuters headline" not in markdown
    assert "Raw AP headline" not in markdown
    assert "selection_order" not in markdown
    assert "canonical_url" not in markdown
    assert "diagnostic" not in markdown
    assert all(event.event_id not in markdown for event in written)
    assert all(item.article_id not in markdown for item in articles)


def test_partial_writer_preserves_relative_selection_order_without_ceiling() -> None:
    items = tuple(article(f"partial-{index}") for index in range(1, 6))
    selected = tuple(selected_event(item, order=index) for index, item in enumerate(items, start=1))
    surviving = tuple(written_event(selected[index - 1], f"保留{index}") for index in (1, 3, 5))
    selector_result = succeeded(StageName.EVENT_SELECTOR, selected)
    writer_result = partial(
        StageName.EVENT_WRITER,
        surviving,
        item_id=selected[1].event_id,
    )

    rendered = render_brief(
        selector_result,
        writer_result,
        items,
        REPORT_DATE,
        WINDOW_START,
        WINDOW_END,
        upstream_results=(
            succeeded(StageName.COLLECTOR, ("source-batch",)),
            succeeded(StageName.NORMALIZER),
            succeeded(StageName.ARTICLE_DEDUP),
            succeeded(StageName.EVENT_CLUSTER),
            selector_result,
            succeeded(StageName.EVENT_CLASSIFIER, selected),
            writer_result,
        ),
    )

    assert rendered.stage_result.status == StageStatus.SUCCEEDED
    brief = rendered.stage_result.outputs[0]
    assert brief.generation_status == GenerationStatus.PARTIAL
    assert brief.event_ids == tuple(event.event_id for event in surviving)
    assert rendered.markdown is not None
    markdown = rendered.markdown
    positions = [markdown.index(event.writing.title_zh) for event in surviving if event.writing is not None]
    assert positions == sorted(positions)
    assert "保留1中文标题" in markdown
    assert "保留3中文标题" in markdown
    assert "保留5中文标题" in markdown
    assert "保留2中文标题" not in markdown
    assert "保留4中文标题" not in markdown
    assert "Raw source title partial-2" not in markdown
    assert "Raw source title partial-4" not in markdown
    assert "> 本次简报部分生成，可能存在少量遗漏。" in markdown
    assert "报告窗口：" not in markdown
    assert "生成状态：" not in markdown
    assert markdown.count("### ") == 3


def test_classifier_failure_can_render_written_unclassified_event_as_partial() -> None:
    item = article("unclassified")
    selected = selected_event(item, order=1)
    written = written_event(selected, "未分类")
    selector_result = succeeded(StageName.EVENT_SELECTOR, (selected,))
    classifier_result = failed(StageName.EVENT_CLASSIFIER, item_id=selected.event_id)
    writer_result = succeeded(StageName.EVENT_WRITER, (written,))

    rendered = render_brief(
        selector_result,
        writer_result,
        (item,),
        REPORT_DATE,
        WINDOW_START,
        WINDOW_END,
        upstream_results=(classifier_result,),
    )

    assert rendered.stage_result.status == StageStatus.SUCCEEDED
    assert rendered.stage_result.outputs[0].generation_status == GenerationStatus.PARTIAL
    assert rendered.markdown is not None
    assert "未分类中文标题" in rendered.markdown
    assert "> 本次简报部分生成，可能存在少量遗漏。" in rendered.markdown
    assert "## technology_ai" not in rendered.markdown
    assert "## other" not in rendered.markdown


def test_empty_complete_brief_is_a_natural_empty_success() -> None:
    selector_result = succeeded(StageName.EVENT_SELECTOR)
    writer_result = succeeded(StageName.EVENT_WRITER)
    rendered = render_brief(
        selector_result,
        writer_result,
        (),
        REPORT_DATE,
        WINDOW_START,
        WINDOW_END,
        upstream_results=complete_upstream(selector_result, writer_result),
    )

    assert rendered.stage_result.status == StageStatus.SUCCEEDED
    brief = rendered.stage_result.outputs[0]
    assert brief.event_ids == ()
    assert brief.generation_status == GenerationStatus.COMPLETE
    assert rendered.markdown is not None
    assert "## 今日要闻\n\n本报告窗口内暂无入选事件。" in rendered.markdown
    assert "报告窗口：" not in rendered.markdown
    assert "生成状态：" not in rendered.markdown
    assert rendered.markdown.count("### ") == 0


def test_empty_partial_brief_keeps_empty_content_and_partial_status() -> None:
    selector_result = succeeded(StageName.EVENT_SELECTOR)
    writer_result = succeeded(StageName.EVENT_WRITER)
    rendered = render_brief(
        selector_result,
        writer_result,
        (),
        REPORT_DATE,
        WINDOW_START,
        WINDOW_END,
        upstream_results=(
            partial(StageName.COLLECTOR, ("retained-empty-source-batch",)),
            selector_result,
            writer_result,
        ),
    )

    assert rendered.stage_result.status == StageStatus.SUCCEEDED
    assert rendered.stage_result.outputs[0].generation_status == GenerationStatus.PARTIAL
    assert rendered.markdown is not None
    assert "> 本次简报部分生成，可能存在少量遗漏。\n\n## 今日要闻" in rendered.markdown
    assert "## 今日要闻\n\n本报告窗口内暂无入选事件。" in rendered.markdown
    assert "报告窗口：" not in rendered.markdown
    assert "生成状态：" not in rendered.markdown


def test_sources_are_collapsed_complete_and_exact_duplicate_urls_are_deduped() -> None:
    first = article("source-first", source="Reuters", url="https://fixture.example/story?utm_source=x")
    second = article("source-second", source="AP", url="https://fixture.example/second")
    projections = project_sources((first, first, second))
    assert len(projections) == 2
    assert [projection.source for projection in projections] == ["Reuters", "AP"]
    assert projections[0].url == "https://fixture.example/story"

    selected = selected_event(first, second, order=1)
    written = written_event(selected, "多来源")
    selector_result = succeeded(StageName.EVENT_SELECTOR, (selected,))
    writer_result = succeeded(StageName.EVENT_WRITER, (written,))
    rendered = render_brief(
        selector_result,
        writer_result,
        (first, second),
        REPORT_DATE,
        WINDOW_START,
        WINDOW_END,
        upstream_results=complete_upstream(selector_result, writer_result),
    )

    assert rendered.markdown is not None
    markdown = rendered.markdown
    assert "<details>" in markdown
    assert "<summary>来源（2）</summary>" in markdown
    assert markdown.count("[原文](<https://fixture.example/story>)") == 1
    assert markdown.count("[原文](<https://fixture.example/second>)") == 1
    assert markdown.index("<details>") < markdown.index("[原文](<https://fixture.example/story>)")
    assert markdown.index("[原文](<https://fixture.example/story>)") < markdown.index("</details>")
    assert markdown.count("<details>") == 1
    assert markdown.count("<summary>来源（2）</summary>") == 1


def test_source_projection_follows_event_article_id_order_not_lookup_order() -> None:
    first = article("order-first", source="Source First")
    second = article("order-second", source="Source Second")
    selected = selected_event(first, second, order=1)
    written = written_event(selected, "来源顺序")
    selector_result = succeeded(StageName.EVENT_SELECTOR, (selected,))
    writer_result = succeeded(StageName.EVENT_WRITER, (written,))
    lookup = {item.article_id: item for item in (first, second)}

    rendered = render_brief(
        selector_result,
        writer_result,
        tuple(reversed((first, second))),
        REPORT_DATE,
        WINDOW_START,
        WINDOW_END,
        upstream_results=complete_upstream(selector_result, writer_result),
    )

    assert rendered.markdown is not None
    source_lines = [line for line in rendered.markdown.splitlines() if line.startswith("- ")]
    expected_sources = [f"- {lookup[article_id].source}" for article_id in selected.article_ids]
    expected_lines = [
        f"{expected} · [原文](<{lookup[article_id].url}>)"
        for expected, article_id in zip(expected_sources, selected.article_ids)
    ]
    assert source_lines == expected_lines


def test_nonempty_selection_with_all_writer_failures_does_not_backfill_raw_articles() -> None:
    item = article("writer-failed", title="Do not render this raw title")
    selected = selected_event(item, order=1)
    selector_result = succeeded(StageName.EVENT_SELECTOR, (selected,))
    writer_result = failed(StageName.EVENT_WRITER, item_id=selected.event_id)
    rendered = render_brief(
        selector_result,
        writer_result,
        (item,),
        REPORT_DATE,
        WINDOW_START,
        WINDOW_END,
        upstream_results=(writer_result,),
    )

    assert rendered.stage_result.status == StageStatus.FAILED
    assert rendered.stage_result.outputs == ()
    assert rendered.markdown is None
    assert "Do not render this raw title" not in str(rendered.markdown)


def test_renderer_has_no_semantic_or_legacy_module_dependency() -> None:
    source = (PROJECT_ROOT / "brief_renderer.py").read_text(encoding="utf-8")
    for forbidden_module in (
        "event_selector",
        "event_classifier",
        "event_writer",
        "llm_gateway",
        "ai_curator",
        "overnight_brief_writer",
        "main",
    ):
        assert f"import {forbidden_module}" not in source
        assert f"from {forbidden_module}" not in source


def main() -> None:
    test_normal_complete_brief_renders_all_written_events()
    test_partial_writer_preserves_relative_selection_order_without_ceiling()
    test_classifier_failure_can_render_written_unclassified_event_as_partial()
    test_empty_complete_brief_is_a_natural_empty_success()
    test_empty_partial_brief_keeps_empty_content_and_partial_status()
    test_sources_are_collapsed_complete_and_exact_duplicate_urls_are_deduped()
    test_source_projection_follows_event_article_id_order_not_lookup_order()
    test_nonempty_selection_with_all_writer_failures_does_not_backfill_raw_articles()
    test_renderer_has_no_semantic_or_legacy_module_dependency()
    print("offline brief renderer smoke passed")


if __name__ == "__main__":
    main()
