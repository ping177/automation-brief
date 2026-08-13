from __future__ import annotations

from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
import re
import sys
from typing import Mapping, Sequence

from ai_curator import CandidateArticle, CuratedEvent, normalize_article_link
from market_analysis import MarketBriefContext
from market_brief_writer import (
    DISCLAIMER,
    DIRECT_TRADING_ADVICE_TERMS,
    append_insights,
    append_market_temperature,
    average_index_pct_change,
    format_pct_change,
    format_quote_meta,
    has_clear_holding_news,
    holding_anomaly_text,
    market_led_observation,
    prioritized_watch_points,
    markdown_escape as base_markdown_escape,
)
from market_news import HOLDING_RELATION_CLEAR, NewsInsight


OVERNIGHT_BRIEF_SECTIONS = (
    "## 一、昨夜最重要的事",
    "## 二、隔夜市场",
    "## 三、今日值得关注",
    "## 四、持仓异常",
)
MAX_MARKET_ITEMS = 4
MAX_WATCH_ITEMS = 3
MAX_HOLDING_ALERTS = 3
CURATED_MARKET_CATEGORIES = frozenset({"financial_markets", "energy_commodities"})
CURATED_WATCH_CATEGORIES = frozenset(
    {
        "geopolitics",
        "macro_policy",
        "financial_markets",
        "energy_commodities",
        "china_policy",
    }
)
CURATED_READER_IMPORTANCE_VALUES = frozenset({"must_know", "important"})
OVERNIGHT_FORBIDDEN_TERMS = (*DIRECT_TRADING_ADVICE_TERMS, "目标价", "仓位", "成本", "盈亏")


def markdown_escape(value: str) -> str:
    cleaned = base_markdown_escape(value)
    for term in OVERNIGHT_FORBIDDEN_TERMS:
        cleaned = cleaned.replace(term, "具体交易信息")
    return cleaned


def _sanitize_rendered_line(value: str) -> str:
    cleaned = value
    for term in OVERNIGHT_FORBIDDEN_TERMS:
        cleaned = cleaned.replace(term, "具体交易信息")
    return cleaned


def _story_title(item: object) -> str:
    return str(getattr(item, "title", "") or "").strip()


def _story_link(item: object) -> str:
    return str(getattr(item, "link", "") or "").strip()


def _story_key(value: str) -> str:
    lowered = value.lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", lowered)


def _same_story(first: object, second: object) -> bool:
    first_link = _story_link(first)
    second_link = _story_link(second)
    if first_link and second_link and first_link == second_link:
        return True

    first_title = _story_key(_story_title(first))
    second_title = _story_key(_story_title(second))
    if not first_title or not second_title:
        return False
    if first_title == second_title:
        return True
    if min(len(first_title), len(second_title)) >= 4 and (
        first_title in second_title or second_title in first_title
    ):
        return True
    if min(len(first_title), len(second_title)) < 10:
        return False
    return SequenceMatcher(None, first_title, second_title).ratio() >= 0.88


def _append_digest_item(lines: list[str], index: int, item: object) -> None:
    """Reuse the digest's summary and timestamp helpers with safe escaping."""

    current_main = sys.modules.get("__main__")
    if current_main is not None and hasattr(current_main, "digest_item_summary"):
        digest_item_summary = current_main.digest_item_summary
        format_digest_item_time = current_main.format_digest_item_time
    else:
        from main import digest_item_summary, format_digest_item_time

    title = _story_title(item)
    source = str(getattr(item, "source", "") or "")
    link = _story_link(item)
    lines.extend(
        [
            f"### {markdown_escape(title)}",
            "",
            markdown_escape(digest_item_summary(item)),
            "",
            f"`{markdown_escape(source)} · {format_digest_item_time(item)}` · [原文]({link})",
            "",
        ]
    )


def _curated_event_partitions(
    events: Sequence[CuratedEvent],
) -> tuple[tuple[CuratedEvent, ...], tuple[CuratedEvent, ...]]:
    core: list[CuratedEvent] = []
    market: list[CuratedEvent] = []
    for event in events:
        if event.category in CURATED_MARKET_CATEGORIES:
            market.append(event)
        else:
            core.append(event)
    return tuple(core), tuple(market)


def _append_curated_event(
    lines: list[str],
    event: CuratedEvent,
    candidate_by_id: Mapping[str, CandidateArticle],
) -> None:
    lines.extend(
        [
            f"### {markdown_escape(event.canonical_title)}",
            "",
            markdown_escape(event.summary),
            "",
        ]
    )
    if event.why_important:
        lines.extend([f"为什么重要：{markdown_escape(event.why_important)}", ""])

    evidence_lines: list[str] = []
    for article_id in event.evidence_article_ids:
        article = candidate_by_id.get(article_id)
        if article is None:
            continue
        source = str(article.source or "").strip()
        link = str(article.link or article.normalized_link or "").strip()
        source_text = markdown_escape(source) or "未知来源"
        if link:
            evidence_lines.append(f"- 来源：{source_text} · [原文]({link})")
        else:
            evidence_lines.append(f"- 来源：{source_text}")
    if evidence_lines:
        lines.extend(["证据来源：", *evidence_lines, ""])


def _append_curated_events(
    lines: list[str],
    events: Sequence[CuratedEvent],
    candidate_by_id: Mapping[str, CandidateArticle],
    *,
    empty_text: str,
) -> None:
    if not events:
        lines.extend([empty_text, ""])
        return
    for event in events:
        _append_curated_event(lines, event, candidate_by_id)


def _curated_watch_points(context: MarketBriefContext, events: Sequence[CuratedEvent]) -> tuple[str, ...]:
    points: list[str] = []
    for event in events:
        if (
            event.importance not in CURATED_READER_IMPORTANCE_VALUES
            or event.category not in CURATED_WATCH_CATEGORIES
        ):
            continue
        points.extend(str(item or "").strip() for item in event.uncertainties)

    market_observation = market_led_observation(context)
    if market_observation:
        points.append(market_observation)

    points.extend(context.snapshot.watch_signals)
    points.extend(
        point
        for point in prioritized_watch_points(context)
        if point.startswith("持仓变量：")
    )

    selected: list[str] = []
    for point in points:
        cleaned = str(point or "").strip()
        if not cleaned or cleaned in selected:
            continue
        selected.append(cleaned)
        if len(selected) >= MAX_WATCH_ITEMS:
            break
    return tuple(selected)


def _curated_holding_events(
    context: MarketBriefContext,
    holding_title: str,
    events: Sequence[CuratedEvent],
    candidate_by_id: Mapping[str, CandidateArticle],
) -> tuple[CuratedEvent, ...]:
    related = next(
        (
            match
            for match in context.news_analysis.holding_related_news
            if match.holding_title == holding_title
        ),
        None,
    )
    if related is None:
        return ()
    clear_links = {
        normalize_article_link(item.link)
        for item in related.matches
        if item.holding_relation in ("", HOLDING_RELATION_CLEAR) and item.link
    }
    if not clear_links:
        return ()

    matches: list[CuratedEvent] = []
    for event in events:
        for article_id in event.evidence_article_ids:
            article = candidate_by_id.get(article_id)
            if article is None:
                continue
            article_link = normalize_article_link(article.link or article.normalized_link)
            if article_link and article_link in clear_links:
                matches.append(event)
                break
    return tuple(matches)


def _append_curated_holding_alerts(
    lines: list[str],
    context: MarketBriefContext,
    events: Sequence[CuratedEvent],
    candidate_by_id: Mapping[str, CandidateArticle],
) -> None:
    alerts: list[tuple[object, tuple[CuratedEvent, ...], str]] = []
    for observation in context.holding_observations:
        quote = observation.quote
        anomaly = holding_anomaly_text(context, quote.pct_change) if quote else ""
        related_events = _curated_holding_events(
            context,
            observation.title,
            events,
            candidate_by_id,
        )
        if not anomaly and not related_events:
            continue
        alerts.append((observation, related_events, anomaly))
        if len(alerts) >= MAX_HOLDING_ALERTS:
            break
    if not alerts:
        return

    lines.extend([OVERNIGHT_BRIEF_SECTIONS[3], ""])
    for observation, related_events, anomaly in alerts:
        lines.extend([f"### {markdown_escape(observation.title)}", ""])
        if observation.quote:
            quote = observation.quote
            lines.append(
                f"- 行情：{markdown_escape(_format_quote(quote.pct_change, quote.source, quote.as_of))}"
            )
        if related_events:
            lines.append("- 高精度匹配：相关中文事件已在前文展示，此处不重复展开。")
        elif anomaly:
            lines.append(f"- {markdown_escape(anomaly)}")
        lines.append("")


def _unique_market_insights(
    context: MarketBriefContext,
    reserved: Sequence[object],
) -> tuple[NewsInsight, ...]:
    candidates: list[NewsInsight] = list(context.news_analysis.market_events)
    candidates.extend(
        item
        for item in context.news_analysis.industry_catalysts
        if item.relevance_score >= 70
    )

    selected: list[NewsInsight] = []
    for candidate in candidates:
        if any(_same_story(candidate, existing) for existing in (*reserved, *selected)):
            continue
        selected.append(candidate)
        if len(selected) >= MAX_MARKET_ITEMS:
            break
    return tuple(selected)


def _unique_market_items(
    market_items: Sequence[object],
    reserved: Sequence[object],
    selected_insights: Sequence[NewsInsight],
) -> tuple[object, ...]:
    selected: list[object] = []
    for item in market_items:
        if any(_same_story(item, existing) for existing in (*reserved, *selected_insights, *selected)):
            continue
        selected.append(item)
        if len(selected) + len(selected_insights) >= MAX_MARKET_ITEMS:
            break
    return tuple(selected)


def _watch_points(context: MarketBriefContext, displayed: Sequence[object]) -> tuple[str, ...]:
    candidates: list[str] = list(context.news_analysis.watch_points)

    market_observation = market_led_observation(context)
    if market_observation:
        candidates.insert(0, market_observation)

    average_pct = average_index_pct_change(context)
    if average_pct is not None and average_pct <= -0.6:
        candidates.append("观察高弹性成长方向是否继续承压，以及前一交易日强势是否出现快速反转。")

    for observation in context.holding_observations:
        quote = observation.quote
        if quote and holding_anomaly_text(context, quote.pct_change) and not has_clear_holding_news(
            context, observation.title
        ):
            candidates.append("持仓变量：当前 RSS 尚未解释该异常波动，后续需核验公司公告和板块消息。")
            break

    selected: list[str] = []
    for point in candidates:
        cleaned = str(point or "").strip()
        if not cleaned:
            continue
        normalized_point = _story_key(cleaned)
        if any(
            _story_key(_story_title(item)) and _story_key(_story_title(item)) in normalized_point
            for item in displayed
        ):
            continue
        if cleaned in selected:
            continue
        selected.append(cleaned)
        if len(selected) >= MAX_WATCH_ITEMS:
            break
    return tuple(selected)


def _clear_holding_news(context: MarketBriefContext, title: str) -> tuple[NewsInsight, ...]:
    for match in context.news_analysis.holding_related_news:
        if match.holding_title != title:
            continue
        return tuple(
            item
            for item in match.matches
            if item.holding_relation in ("", HOLDING_RELATION_CLEAR)
        )
    return ()


def _holding_alerts(
    context: MarketBriefContext,
    displayed: Sequence[object],
) -> tuple[tuple[object, tuple[NewsInsight, ...], str], ...]:
    alerts: list[tuple[object, tuple[NewsInsight, ...], str]] = []
    for observation in context.holding_observations:
        quote = observation.quote
        anomaly = holding_anomaly_text(context, quote.pct_change) if quote else ""
        clear_news = _clear_holding_news(context, observation.title)
        if not anomaly and not clear_news:
            continue
        unseen_news = tuple(
            item for item in clear_news if not any(_same_story(item, existing) for existing in displayed)
        )
        alerts.append((observation, unseen_news, anomaly))
        if len(alerts) >= MAX_HOLDING_ALERTS:
            break
    return tuple(alerts)


def _append_holding_alerts(
    lines: list[str],
    context: MarketBriefContext,
    displayed: Sequence[object],
) -> None:
    alerts = _holding_alerts(context, displayed)
    if not alerts:
        return

    lines.extend([OVERNIGHT_BRIEF_SECTIONS[3], ""])
    for observation, unseen_news, anomaly in alerts:
        lines.extend([f"### {markdown_escape(observation.title)}", ""])
        if observation.quote:
            quote = observation.quote
            lines.append(
                f"- 行情：{markdown_escape(_format_quote(quote.pct_change, quote.source, quote.as_of))}"
            )
        if anomaly:
            lines.append(f"- {markdown_escape(anomaly)}")
        if unseen_news:
            lines.append("- 高精度匹配相关新闻：")
            for item in unseen_news:
                lines.append(f"  - {markdown_escape(item.title)}（{markdown_escape(item.source)}）")
                if item.reason:
                    lines.append(f"    - {markdown_escape(item.reason)}")
                if item.link:
                    lines.append(f"    - [原文]({item.link})")
        elif _clear_holding_news(context, observation.title):
            lines.append("- 高精度匹配：相关事件已在前文展示，此处不重复展开。")
        lines.append("")


def _format_quote(pct_change: float | None, source: str, as_of: str) -> str:
    return f"{format_pct_change(pct_change)}{format_quote_meta(source, as_of)}"


def _append_safe_market_temperature(lines: list[str], context: MarketBriefContext) -> None:
    rendered: list[str] = []
    append_market_temperature(rendered, context)
    lines.extend(_sanitize_rendered_line(line) for line in rendered)


def _append_safe_insights(lines: list[str], items: Sequence[NewsInsight]) -> None:
    rendered: list[str] = []
    append_insights(rendered, items, empty_text=None)
    lines.extend(_sanitize_rendered_line(line) for line in rendered)


def render_overnight_brief_markdown(
    core_items: Sequence[object],
    market_items: Sequence[object],
    context: MarketBriefContext,
    *,
    report_date: date | None = None,
    feed_failures: Sequence[tuple[str, str]] | None = None,
    generated_at: datetime | None = None,
    curated_events: Sequence[CuratedEvent] | None = None,
    candidate_by_id: Mapping[str, CandidateArticle] | None = None,
) -> str:
    resolved_report_date = report_date or context.snapshot.data_date
    generated_time = generated_at or datetime.now().astimezone()
    curator_active = curated_events is not None
    evidence_by_id = candidate_by_id or {}
    curated = tuple(
        event
        for event in (curated_events or ())
        if event.importance in CURATED_READER_IMPORTANCE_VALUES
    )
    curated_core, curated_market = _curated_event_partitions(curated)
    core = tuple(core_items)
    market_insights = () if curator_active else _unique_market_insights(context, core)
    market_fallback_items = (
        () if curator_active else _unique_market_items(market_items, core, market_insights)
    )
    displayed = (*core, *market_insights, *market_fallback_items)

    lines = [
        f"# 早间简报｜{resolved_report_date.isoformat()}",
        "",
        f"生成时间：{generated_time.isoformat(timespec='seconds')}",
        f"报告日期：{resolved_report_date.isoformat()}",
        "时间窗口：过去 24 小时",
        "Mode: overnight_brief",
        "",
        OVERNIGHT_BRIEF_SECTIONS[0],
        "",
    ]
    if curator_active:
        _append_curated_events(
            lines,
            curated_core,
            evidence_by_id,
            empty_text="过去时间窗口内暂无明确的重大事件。",
        )
    elif core:
        for index, item in enumerate(core, start=1):
            _append_digest_item(lines, index, item)
    else:
        lines.extend(["过去时间窗口内暂无明确的重大事件。", ""])

    lines.extend(
        [
            OVERNIGHT_BRIEF_SECTIONS[1],
            "",
            "- 结构化行情说明：当前主要为前一交易日 A 股指数数据，不代表完整全球隔夜行情。",
            "",
        ]
    )
    _append_safe_market_temperature(lines, context)
    if curator_active and curated_market:
        lines.append("### 市场新闻")
        lines.append("")
        _append_curated_events(
            lines,
            curated_market,
            evidence_by_id,
            empty_text="暂无明确的市场新闻。",
        )
    elif market_insights:
        lines.append("### 市场新闻")
        lines.append("")
        _append_safe_insights(lines, market_insights)
    if market_fallback_items:
        lines.append("### 市场信号")
        lines.append("")
        for index, item in enumerate(market_fallback_items, start=1):
            _append_digest_item(lines, index, item)
    if not curated_market and not market_insights and not market_fallback_items:
        lines.extend(["暂无明确的市场新闻或市场信号。", ""])

    lines.extend([OVERNIGHT_BRIEF_SECTIONS[2], ""])
    watch_points = (
        _curated_watch_points(context, curated)
        if curator_active
        else _watch_points(context, displayed)
    )
    if watch_points:
        for point in watch_points:
            lines.append(f"- {markdown_escape(point)}")
        lines.append("")
    else:
        lines.extend(["暂无明确的延续观察变量。", ""])

    if curator_active:
        _append_curated_holding_alerts(lines, context, curated, evidence_by_id)
    else:
        _append_holding_alerts(lines, context, displayed)

    failures = tuple(context.feed_failures if feed_failures is None else feed_failures)
    lines.extend(["", "---", "", f"- {DISCLAIMER}"])
    if failures:
        lines.append("- RSS 抓取失败源：")
        for source, reason in failures:
            lines.append(f"  - {markdown_escape(source)}：{markdown_escape(reason)}")
    lines.append("")
    return "\n".join(lines)


def write_overnight_brief_markdown(
    core_items: Sequence[object],
    market_items: Sequence[object],
    context: MarketBriefContext,
    output_dir: Path,
    *,
    report_date: date | None = None,
    feed_failures: Sequence[tuple[str, str]] | None = None,
    curated_events: Sequence[CuratedEvent] | None = None,
    candidate_by_id: Mapping[str, CandidateArticle] | None = None,
) -> Path:
    resolved_report_date = report_date or context.snapshot.data_date
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"morning-brief-{resolved_report_date.isoformat()}.md"
    output_file.write_text(
        render_overnight_brief_markdown(
            core_items,
            market_items,
            context,
            report_date=resolved_report_date,
            feed_failures=feed_failures,
            curated_events=curated_events,
            candidate_by_id=candidate_by_id,
        ),
        encoding="utf-8",
    )
    return output_file
