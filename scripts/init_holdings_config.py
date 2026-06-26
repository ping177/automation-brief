from __future__ import annotations

import argparse
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOLDINGS_PATH = PROJECT_ROOT / "config" / "holdings.json"
DEFAULT_EXAMPLE_PATH = PROJECT_ROOT / "config" / "holdings.example.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create local config/holdings.json from the safe example.")
    parser.add_argument("--holdings", type=Path, default=DEFAULT_HOLDINGS_PATH, help="Target holdings.json path")
    parser.add_argument("--example", type=Path, default=DEFAULT_EXAMPLE_PATH, help="Source example holdings path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    holdings_path = args.holdings
    example_path = args.example

    if holdings_path.exists():
        print(f"config already exists: {holdings_path}")
        print("No changes made. Existing holdings config was not overwritten.")
        print("config/holdings.json is ignored by Git and should stay local.")
        return 0

    if not example_path.exists():
        print(f"Example config not found: {example_path}")
        return 1

    holdings_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example_path, holdings_path)
    print(f"Created local holdings config: {holdings_path}")
    print("config/holdings.json is ignored by Git and should not be committed.")
    print("Allowed fields: code, name, market, sector, watch_tags, notes.")
    print("Do not save cost, position, shares, amount, market value, profit/loss, or account amount.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
