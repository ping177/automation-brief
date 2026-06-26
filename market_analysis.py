from __future__ import annotations

from dataclasses import dataclass

from holdings import HoldingsConfig
from market_data import MarketSnapshot
from market_news import MarketNewsAnalysis, analyze_market_news


@dataclass(frozen=True)
class HoldingObservation:
    title: str
    sector: str
    watch_tags: tuple[str, ...]
    notes: str
    observation: str


@dataclass(frozen=True)
class MarketBriefContext:
    snapshot: MarketSnapshot
    holdings_config: HoldingsConfig
    holding_observations: tuple[HoldingObservation, ...]
    news_analysis: MarketNewsAnalysis
    feed_failures: tuple[tuple[str, str], ...]


def build_market_brief_context(
    snapshot: MarketSnapshot,
    holdings_config: HoldingsConfig,
    news_records: list[object] | None = None,
    feed_failures: list[tuple[str, str]] | tuple[tuple[str, str], ...] | None = None,
) -> MarketBriefContext:
    news_analysis = analyze_market_news(news_records or [], holdings_config)
    observations = tuple(
        HoldingObservation(
            title=f"{holding.code} {holding.name}",
            sector=holding.sector,
            watch_tags=holding.watch_tags,
            notes=holding.notes,
            observation="已读取关注对象；当前不计算相对强弱，仅结合新闻线索观察。",
        )
        for holding in holdings_config.holdings
    )
    return MarketBriefContext(
        snapshot=snapshot,
        holdings_config=holdings_config,
        holding_observations=observations,
        news_analysis=news_analysis,
        feed_failures=tuple(feed_failures or ()),
    )
