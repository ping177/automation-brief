from __future__ import annotations

from dataclasses import dataclass

from holdings import HoldingsConfig
from market_data import MarketSnapshot


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


def build_market_brief_context(snapshot: MarketSnapshot, holdings_config: HoldingsConfig) -> MarketBriefContext:
    observations = tuple(
        HoldingObservation(
            title=f"{holding.code} {holding.name}",
            sector=holding.sector,
            watch_tags=holding.watch_tags,
            notes=holding.notes,
            observation="已读取关注标的，但暂未计算相对强弱。",
        )
        for holding in holdings_config.holdings
    )
    return MarketBriefContext(
        snapshot=snapshot,
        holdings_config=holdings_config,
        holding_observations=observations,
    )
