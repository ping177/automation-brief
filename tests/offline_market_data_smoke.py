from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from holdings import Holding, HoldingsConfig  # noqa: E402
from market_data import fetch_market_snapshot  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def holdings_config() -> HoldingsConfig:
    return HoldingsConfig(
        holdings=(
            Holding(
                code="601179",
                name="中国西电",
                market="A股",
                sector="电力设备",
                watch_tags=("特高压", "电网设备"),
                notes="观察是否跟随电网投资周期",
            ),
        ),
        source_path=None,
    )


def fake_urlopen(request, timeout: int = 0) -> FakeResponse:  # noqa: ANN001
    url = request.full_url
    if "1.000001" in url:
        return FakeResponse(
            {
                "data": {
                    "diff": [
                        {"f12": "000001", "f14": "上证指数", "f3": 0.52, "f6": 468000000000, "f124": 1782457200},
                        {"f12": "399001", "f14": "深成指", "f3": -0.21, "f6": 590000000000, "f124": 1782457200},
                        {"f12": "399006", "f14": "创业板指", "f3": 1.13, "f6": "-", "f124": 1782457200},
                        {"f12": "000688", "f14": "科创50", "f3": None, "f6": None, "f124": 1782457200},
                    ]
                }
            }
        )
    return FakeResponse(
        {
            "data": {
                "diff": [
                    {"f12": "601179", "f14": "中国西电", "f3": 2.34, "f6": 1234000000, "f124": 1782457200}
                ]
            }
        }
    )


def failing_urlopen(_request, timeout: int = 0) -> FakeResponse:  # noqa: ANN001
    raise OSError("offline fixture failure")


def main() -> None:
    report_date = date(2026, 6, 26)
    snapshot = fetch_market_snapshot(report_date, holdings_config(), urlopen=fake_urlopen)

    assert snapshot.data_date == report_date
    assert snapshot.market_data_date.isoformat() == "2026-06-26"
    assert len(snapshot.indexes) == 4
    assert len(snapshot.holdings) == 1
    assert len(snapshot.failures) == 1
    assert snapshot.indexes[0].name == "上证指数"
    assert snapshot.indexes[0].pct_change == 0.52
    assert snapshot.indexes[0].amount is None
    assert any(failure.scope == "amount" for failure in snapshot.failures)
    assert snapshot.indexes[2].amount is None
    assert snapshot.indexes[3].pct_change is None
    assert snapshot.holdings[0].code == "601179"
    assert snapshot.holdings[0].pct_change == 2.34
    assert snapshot.holdings[0].sector == "电力设备"

    failed_snapshot = fetch_market_snapshot(report_date, holdings_config(), urlopen=failing_urlopen)
    assert failed_snapshot.indexes == ()
    assert failed_snapshot.holdings == ()
    assert len(failed_snapshot.failures) == 2
    assert {failure.scope for failure in failed_snapshot.failures} == {"indexes", "holdings"}
    assert "行情数据源未返回可用数据" in failed_snapshot.environment_note

    empty_snapshot = fetch_market_snapshot(
        report_date,
        HoldingsConfig(holdings=(), source_path=None),
        urlopen=fake_urlopen,
    )
    assert len(empty_snapshot.indexes) == 4
    assert empty_snapshot.holdings == ()

    print("offline market data smoke passed")


if __name__ == "__main__":
    main()
