from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_HOLDINGS_FILE = BASE_DIR / "config" / "holdings.json"
DEFAULT_HOLDINGS_EXAMPLE_FILE = BASE_DIR / "config" / "holdings.example.json"
ALLOWED_HOLDING_FIELDS = frozenset(
    {
        "code",
        "name",
        "market",
        "sector",
        "watch_tags",
        "notes",
    }
)
SENSITIVE_HOLDING_FIELDS = frozenset(
    {
        "cost",
        "position",
        "shares",
        "amount",
        "market_value",
        "profit",
        "loss",
        "盈亏",
        "成本",
        "仓位",
        "持股数量",
        "账户金额",
    }
)


@dataclass(frozen=True)
class Holding:
    code: str
    name: str
    market: str
    sector: str
    watch_tags: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class HoldingsConfig:
    holdings: tuple[Holding, ...]
    source_path: Path | None
    used_example: bool = False


@dataclass(frozen=True)
class HoldingsValidationResult:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def _clean_string(value: Any) -> str:
    return str(value or "").strip()


def _clean_string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("holding.watch_tags must be a list")
    return tuple(_clean_string(item) for item in value if _clean_string(item))


def _load_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _normalize_holding(raw_holding: Any, index: int) -> Holding:
    if not isinstance(raw_holding, dict):
        raise ValueError(f"holdings[{index}] must be an object")

    code = _clean_string(raw_holding.get("code"))
    name = _clean_string(raw_holding.get("name"))
    market = _clean_string(raw_holding.get("market"))
    sector = _clean_string(raw_holding.get("sector"))
    notes = _clean_string(raw_holding.get("notes"))
    watch_tags = _clean_string_tuple(raw_holding.get("watch_tags"))

    missing = [
        field
        for field, value in (
            ("code", code),
            ("name", name),
            ("market", market),
            ("sector", sector),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"holdings[{index}] missing required fields: {', '.join(missing)}")

    return Holding(
        code=code,
        name=name,
        market=market,
        sector=sector,
        watch_tags=watch_tags,
        notes=notes,
    )


def normalize_holdings(payload: dict[str, Any], source_path: Path | None, used_example: bool) -> HoldingsConfig:
    raw_holdings = payload.get("holdings", [])
    if not isinstance(raw_holdings, list):
        raise ValueError("holdings must be a list")
    holdings = tuple(_normalize_holding(item, index) for index, item in enumerate(raw_holdings))
    return HoldingsConfig(holdings=holdings, source_path=source_path, used_example=used_example)


def find_sensitive_holding_fields(raw_holding: dict[str, Any]) -> tuple[str, ...]:
    return tuple(field for field in raw_holding if field in SENSITIVE_HOLDING_FIELDS)


def validate_holdings_payload(payload: Any) -> HoldingsValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(payload, dict):
        return HoldingsValidationResult(
            errors=("holdings.json must contain a JSON object",),
            warnings=(),
        )

    raw_holdings = payload.get("holdings")
    if not isinstance(raw_holdings, list):
        return HoldingsValidationResult(
            errors=("holdings must be a list",),
            warnings=(),
        )

    for index, raw_holding in enumerate(raw_holdings):
        item_label = f"holdings[{index}]"
        if not isinstance(raw_holding, dict):
            errors.append(f"{item_label} must be an object")
            continue

        sensitive_fields = find_sensitive_holding_fields(raw_holding)
        if sensitive_fields:
            warnings.append(
                f"{item_label} contains sensitive position/cost fields: {', '.join(sorted(sensitive_fields))}"
            )

        unsupported_fields = sorted(
            field
            for field in raw_holding
            if field not in ALLOWED_HOLDING_FIELDS and field not in SENSITIVE_HOLDING_FIELDS
        )
        if unsupported_fields:
            errors.append(f"{item_label} contains unsupported fields: {', '.join(unsupported_fields)}")

        missing_fields = sorted(field for field in ALLOWED_HOLDING_FIELDS if field not in raw_holding)
        if missing_fields:
            errors.append(f"{item_label} missing required fields: {', '.join(missing_fields)}")

        for field_name in ("code", "name", "market", "sector"):
            if field_name in raw_holding and not _clean_string(raw_holding.get(field_name)):
                errors.append(f"{item_label}.{field_name} must be a non-empty string")

        if "watch_tags" in raw_holding and not isinstance(raw_holding.get("watch_tags"), list):
            errors.append(f"{item_label}.watch_tags must be a list")

        if "notes" in raw_holding and not isinstance(raw_holding.get("notes"), str):
            errors.append(f"{item_label}.notes must be a string")

    return HoldingsValidationResult(errors=tuple(errors), warnings=tuple(warnings))


def load_holdings(
    path: Path = DEFAULT_HOLDINGS_FILE,
    example_path: Path = DEFAULT_HOLDINGS_EXAMPLE_FILE,
) -> HoldingsConfig:
    if path.exists():
        return normalize_holdings(_load_json_object(path), path, used_example=False)
    if example_path.exists():
        return normalize_holdings(_load_json_object(example_path), example_path, used_example=True)
    return HoldingsConfig(holdings=(), source_path=None, used_example=False)
