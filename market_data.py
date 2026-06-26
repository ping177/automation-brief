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
        environment_note="暂无真实行情数据，等待 v0.5-beta 接入。",
        strong_1d=("暂无真实行情数据，暂不计算 1 日强势方向。",),
        strong_5d=("暂无真实行情数据，暂不计算 5 日持续强势方向。",),
        trend_20d=("暂无真实行情数据，暂不计算 20 日趋势主线。",),
        catalysts=("暂无实时产业催化数据，当前仅保留观察框架。",),
        watch_signals=(
            "观察主要指数、成交量和行业轮动是否出现连续性。",
            "观察持仓所属板块是否跟随市场主线。",
            "观察外部风险偏好、汇率利率和政策变量是否变化。",
        ),
    )
