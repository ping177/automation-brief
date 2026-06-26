from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from holdings import HoldingsConfig


@dataclass(frozen=True)
class NewsInsight:
    title: str
    source: str
    link: str
    reason: str


@dataclass(frozen=True)
class HoldingNewsMatch:
    holding_title: str
    matches: tuple[NewsInsight, ...]


@dataclass(frozen=True)
class MarketNewsAnalysis:
    market_events: tuple[NewsInsight, ...]
    industry_catalysts: tuple[NewsInsight, ...]
    environment_points: tuple[str, ...]
    theme_clues: tuple[str, ...]
    watch_points: tuple[str, ...]
    deep_dive_questions: tuple[str, ...]
    holding_related_news: tuple[HoldingNewsMatch, ...]


MARKET_EVENT_TERMS = (
    "A股",
    "港股",
    "美股",
    "债市",
    "汇率",
    "利率",
    "央行",
    "美联储",
    "财政部",
    "证监会",
    "交易所",
    "关税",
    "制裁",
    "财报",
    "业绩",
    "上市公司",
    "IPO",
    "并购",
    "重组",
    "回购",
    "估值",
    "融资",
)
INDUSTRY_CATALYST_TERMS = (
    "订单",
    "中标",
    "招标",
    "政策",
    "补贴",
    "出口管制",
    "商业化",
    "支付",
    "AI",
    "人工智能",
    "算力",
    "芯片",
    "半导体",
    "机器人",
    "新能源",
    "风电",
    "光伏",
    "储能",
    "电网",
    "特高压",
)
RISK_TERMS = (
    "风险",
    "下滑",
    "亏损",
    "处罚",
    "调查",
    "监管",
    "退市",
    "违约",
    "制裁",
    "关税",
    "出口管制",
)
WATCH_TERMS = (
    "今日",
    "明日",
    "今晚",
    "本周",
    "将公布",
    "将召开",
    "将披露",
    "将生效",
    "到期",
    "议息",
    "财报发布",
)
BROAD_HOLDING_WATCH_TAGS = (
    "出海",
    "央企",
    "国企",
    "新能源",
    "科技",
    "AI",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _article_text(article: Any) -> str:
    matched_keywords = getattr(article, "matched_keywords", {}) or {}
    keyword_text = ""
    if isinstance(matched_keywords, dict):
        keyword_text = " ".join(
            str(keyword)
            for keywords in matched_keywords.values()
            for keyword in (keywords if isinstance(keywords, list) else [])
        )
    return " ".join(
        (
            _clean(getattr(article, "title", "")),
            _clean(getattr(article, "summary", "")),
            _clean(getattr(article, "source", "")),
            _clean(getattr(article, "feed_role", "")),
            keyword_text,
        )
    )


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _insight(article: Any, reason: str) -> NewsInsight:
    return NewsInsight(
        title=_clean(getattr(article, "title", "Untitled")) or "Untitled",
        source=_clean(getattr(article, "source", "")) or _clean(getattr(article, "feed_name", "")) or "Unknown",
        link=_clean(getattr(article, "link", "")),
        reason=reason,
    )


def _dedupe_insights(items: list[NewsInsight], limit: int) -> tuple[NewsInsight, ...]:
    seen: set[tuple[str, str]] = set()
    deduped: list[NewsInsight] = []
    for item in items:
        key = (item.link, item.title)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return tuple(deduped)


def _holding_match_terms(holding: Any) -> tuple[str, ...]:
    terms = [
        _clean(getattr(holding, "code", "")),
        _clean(getattr(holding, "name", "")),
        _clean(getattr(holding, "sector", "")),
    ]
    terms.extend(
        tag
        for tag in (_clean(item) for item in getattr(holding, "watch_tags", ()) or ())
        if tag and tag not in BROAD_HOLDING_WATCH_TAGS
    )
    return tuple(term for term in terms if term)


def analyze_market_news(
    articles: list[Any],
    holdings_config: HoldingsConfig,
    max_items: int = 5,
) -> MarketNewsAnalysis:
    event_candidates: list[NewsInsight] = []
    catalyst_candidates: list[NewsInsight] = []
    risk_candidates: list[NewsInsight] = []
    watch_candidates: list[NewsInsight] = []
    theme_terms: list[str] = []

    for article in articles:
        text = _article_text(article)
        if _contains_any(text, MARKET_EVENT_TERMS):
            event_candidates.append(_insight(article, "涉及宏观、资本市场、监管或资产价格变量。"))
        if _contains_any(text, INDUSTRY_CATALYST_TERMS):
            catalyst_candidates.append(_insight(article, "可能影响产业预期、订单、政策或商业化节奏。"))
        if _contains_any(text, RISK_TERMS):
            risk_candidates.append(_insight(article, "需要作为风险或反证线索持续观察。"))
        if _contains_any(text, WATCH_TERMS):
            watch_candidates.append(_insight(article, "包含后续时间节点或待验证变量。"))

        for term in INDUSTRY_CATALYST_TERMS:
            if term.lower() in text.lower() and term not in theme_terms:
                theme_terms.append(term)
                break

    holding_matches: list[HoldingNewsMatch] = []
    for holding in holdings_config.holdings:
        terms = _holding_match_terms(holding)
        matches = [
            _insight(article, f"命中关注对象线索：{term}")
            for article in articles
            for term in terms
            if term.lower() in _article_text(article).lower()
        ]
        deduped_matches = _dedupe_insights(matches, max_items)
        if deduped_matches:
            holding_matches.append(
                HoldingNewsMatch(
                    holding_title=f"{holding.code} {holding.name}",
                    matches=deduped_matches,
                )
            )

    market_events = _dedupe_insights(event_candidates, max_items)
    industry_catalysts = _dedupe_insights(catalyst_candidates, max_items)
    risk_points = _dedupe_insights(risk_candidates, max_items)
    watch_points = _dedupe_insights(watch_candidates, max_items)

    environment_points = (f"RSS 候选新闻 {len(articles)} 条；以下只基于新闻线索做观察。",)
    if risk_points:
        environment_points += tuple(f"风险/反证：{item.title}" for item in risk_points[:2])

    theme_clues = tuple(f"新闻线索指向：{term}" for term in theme_terms[:max_items])
    deep_dive_questions = tuple(
        f"{item.title}：后续是否能被真实行情、成交结构或公司公告验证？"
        for item in (market_events + industry_catalysts)[:max_items]
    )

    return MarketNewsAnalysis(
        market_events=market_events,
        industry_catalysts=industry_catalysts,
        environment_points=environment_points,
        theme_clues=theme_clues,
        watch_points=tuple(f"{item.title}：{item.reason}" for item in watch_points),
        deep_dive_questions=deep_dive_questions,
        holding_related_news=tuple(holding_matches),
    )
