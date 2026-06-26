from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MarketSnapshot:
    data_date: date
    environment_note: str
    strong_1d: tuple[str, ...]
    strong_5d: tuple[str, ...]
    trend_20d: tuple[str, ...]
    catalysts: tuple[str, ...]
    watch_signals: tuple[str, ...]


def load_offline_market_snapshot(report_date: date) -> MarketSnapshot:
    return MarketSnapshot(
        data_date=report_date,
        environment_note="当前未接真实行情，本节只作为新闻驱动观察的边界说明。",
        strong_1d=(),
        strong_5d=(),
        trend_20d=(),
        catalysts=(),
        watch_signals=(
            "观察主要指数、成交量和行业轮动是否出现连续性。",
            "观察持仓所属板块是否跟随市场主线。",
            "观察外部风险偏好、汇率利率和政策变量是否变化。",
        ),
    )
