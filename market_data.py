from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable

from holdings import Holding, HoldingsConfig


MARKET_DATA_SOURCE = "eastmoney-push2"
MARKET_DATA_TIMEOUT_SECONDS = 8
EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
EASTMONEY_FIELDS = "f12,f14,f2,f3,f4,f6,f124"
DEFAULT_INDEXES = (
    ("上证指数", "000001", "1.000001"),
    ("深成指", "399001", "0.399001"),
    ("创业板指", "399006", "0.399006"),
    ("科创50", "000688", "1.000688"),
)


UrlOpen = Callable[..., Any]


@dataclass(frozen=True)
class MarketQuote:
    name: str
    code: str
    pct_change: float | None
    amount: float | None
    source: str
    as_of: str
    industry: str = ""
    sector: str = ""


@dataclass(frozen=True)
class MarketDataFailure:
    scope: str
    message: str


@dataclass(frozen=True)
class MarketSnapshot:
    data_date: date
    environment_note: str
    indexes: tuple[MarketQuote, ...]
    holdings: tuple[MarketQuote, ...]
    failures: tuple[MarketDataFailure, ...]
    strong_1d: tuple[str, ...]
    strong_5d: tuple[str, ...]
    trend_20d: tuple[str, ...]
    catalysts: tuple[str, ...]
    watch_signals: tuple[str, ...]


def _to_float(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_as_of(timestamp: Any) -> str:
    if isinstance(timestamp, (int, float)) and timestamp > 0:
        return datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _eastmoney_url(secids: tuple[str, ...]) -> str:
    query = urllib.parse.urlencode(
        {
            "fltt": "2",
            "secids": ",".join(secids),
            "fields": EASTMONEY_FIELDS,
        }
    )
    return f"{EASTMONEY_QUOTE_URL}?{query}"


def _fetch_eastmoney_quotes(secids: tuple[str, ...], urlopen: UrlOpen | None = None) -> tuple[dict[str, Any], ...]:
    if not secids:
        return ()

    opener = urlopen or urllib.request.urlopen
    request = urllib.request.Request(
        _eastmoney_url(secids),
        headers={
            "User-Agent": "automation-brief/0.5",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with opener(request, timeout=MARKET_DATA_TIMEOUT_SECONDS) as response:
        payload = response.read()

    parsed = json.loads(payload.decode("utf-8"))
    diff = parsed.get("data", {}).get("diff", [])
    if not isinstance(diff, list):
        raise RuntimeError("行情数据源返回格式异常")
    return tuple(item for item in diff if isinstance(item, dict))


def _quote_from_payload(
    payload: dict[str, Any],
    fallback_name: str,
    fallback_code: str,
    sector: str = "",
) -> MarketQuote:
    return MarketQuote(
        name=str(payload.get("f14") or fallback_name).strip() or fallback_name,
        code=str(payload.get("f12") or fallback_code).strip() or fallback_code,
        pct_change=_to_float(payload.get("f3")),
        amount=_to_float(payload.get("f6")),
        source=MARKET_DATA_SOURCE,
        as_of=_format_as_of(payload.get("f124")),
        industry=sector,
        sector=sector,
    )


def _holding_secid(holding: Holding) -> str:
    code = holding.code.strip()
    market = holding.market.strip().lower()
    if market in {"sh", "上海", "上交所"}:
        return f"1.{code}"
    if market in {"sz", "深圳", "深交所"}:
        return f"0.{code}"
    if code.startswith(("5", "6", "9")):
        return f"1.{code}"
    return f"0.{code}"


def fetch_index_quotes(urlopen: UrlOpen | None = None) -> tuple[MarketQuote, ...]:
    payloads = _fetch_eastmoney_quotes(tuple(secid for _, _, secid in DEFAULT_INDEXES), urlopen=urlopen)
    payload_by_code = {str(item.get("f12") or ""): item for item in payloads}
    quotes: list[MarketQuote] = []
    for fallback_name, fallback_code, _secid in DEFAULT_INDEXES:
        payload = payload_by_code.get(fallback_code)
        if payload:
            quotes.append(_quote_from_payload(payload, fallback_name, fallback_code))
        else:
            quotes.append(
                MarketQuote(
                    name=fallback_name,
                    code=fallback_code,
                    pct_change=None,
                    amount=None,
                    source=MARKET_DATA_SOURCE,
                    as_of=datetime.now().astimezone().isoformat(timespec="seconds"),
                )
            )
    return tuple(quotes)


def fetch_holding_quotes(
    holdings: tuple[Holding, ...],
    urlopen: UrlOpen | None = None,
) -> tuple[MarketQuote, ...]:
    if not holdings:
        return ()

    payloads = _fetch_eastmoney_quotes(tuple(_holding_secid(holding) for holding in holdings), urlopen=urlopen)
    payload_by_code = {str(item.get("f12") or ""): item for item in payloads}
    quotes: list[MarketQuote] = []
    for holding in holdings:
        payload = payload_by_code.get(holding.code)
        if payload:
            quotes.append(_quote_from_payload(payload, holding.name, holding.code, sector=holding.sector))
        else:
            quotes.append(
                MarketQuote(
                    name=holding.name,
                    code=holding.code,
                    pct_change=None,
                    amount=None,
                    source=MARKET_DATA_SOURCE,
                    as_of=datetime.now().astimezone().isoformat(timespec="seconds"),
                    industry=holding.sector,
                    sector=holding.sector,
                )
            )
    return tuple(quotes)


def fetch_market_snapshot(
    report_date: date,
    holdings_config: HoldingsConfig,
    urlopen: UrlOpen | None = None,
) -> MarketSnapshot:
    if os.environ.get("AUTOMATION_BRIEF_OFFLINE_MARKET_DATA") == "1":
        return load_offline_market_snapshot(report_date)

    failures: list[MarketDataFailure] = []
    try:
        indexes = fetch_index_quotes(urlopen=urlopen)
    except Exception as exc:
        indexes = ()
        failures.append(MarketDataFailure(scope="indexes", message=str(exc) or "指数行情数据暂不可用"))

    try:
        holding_quotes = fetch_holding_quotes(holdings_config.holdings, urlopen=urlopen)
    except Exception as exc:
        holding_quotes = ()
        failures.append(MarketDataFailure(scope="holdings", message=str(exc) or "持仓行情数据暂不可用"))

    if indexes or holding_quotes:
        environment_note = "已尝试接入轻量公开行情数据；缺失字段不做推断。"
    else:
        environment_note = "行情数据源未返回可用数据，本次不做行情验证。"

    return MarketSnapshot(
        data_date=report_date,
        environment_note=environment_note,
        indexes=tuple(indexes),
        holdings=tuple(holding_quotes),
        failures=tuple(failures),
        strong_1d=(),
        strong_5d=(),
        trend_20d=(),
        catalysts=(),
        watch_signals=(
            "观察主要指数涨跌和成交额是否支持新闻主线。",
            "观察持仓所属板块是否跟随市场主线。",
            "观察外部风险偏好、汇率利率和政策变量是否变化。",
        ),
    )


def load_offline_market_snapshot(report_date: date) -> MarketSnapshot:
    return MarketSnapshot(
        data_date=report_date,
        environment_note="行情数据源未返回可用数据，本次不做行情验证。",
        indexes=(),
        holdings=(),
        failures=(MarketDataFailure(scope="market_data", message="数据暂不可用"),),
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
