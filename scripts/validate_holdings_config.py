from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from holdings import DEFAULT_HOLDINGS_FILE, validate_holdings_payload  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate local config/holdings.json without printing holdings values.")
    parser.add_argument("--holdings", type=Path, default=DEFAULT_HOLDINGS_FILE, help="Path to holdings.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    holdings_path = args.holdings

    if not holdings_path.exists():
        print(f"Holdings config not found: {holdings_path}")
        print("Run: python3 scripts/init_holdings_config.py")
        return 1

    try:
        with holdings_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in holdings config: line {exc.lineno}, column {exc.colno}")
        return 1

    result = validate_holdings_payload(payload)
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    if result.warnings:
        print("检测到可能涉及真实仓位/成本的字段。当前版本建议不要在 holdings.json 中保存这些信息。")

    if result.errors:
        print("Holdings config is invalid:")
        for error in result.errors:
            print(f"- {error}")
        print("Allowed fields: code, name, market, sector, watch_tags, notes.")
        return 1

    print("Holdings config is valid.")
    print("Allowed fields: code, name, market, sector, watch_tags, notes.")
    print("Do not save cost, position, shares, amount, market value, profit/loss, or account amount.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
