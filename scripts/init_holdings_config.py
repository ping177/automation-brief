from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from project_paths import get_project_paths  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create canonical local holdings.json from the safe example.")
    parser.add_argument("--holdings", type=Path, help="Target holdings.json path")
    parser.add_argument("--example", type=Path, help="Source example holdings path")
    parser.add_argument("--data-root", type=Path, help="Override canonical runtime data root")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = get_project_paths(repo_root=PROJECT_ROOT, data_root=args.data_root)
    holdings_path = args.holdings or paths.holdings_file
    example_path = args.example or paths.example_holdings_file

    if holdings_path.exists():
        print(f"config already exists: {holdings_path}")
        print("No changes made. Existing holdings config was not overwritten.")
        print("Canonical holdings.json is local data and should stay outside the repository.")
        return 0

    if not example_path.exists():
        print(f"Example config not found: {example_path}")
        return 1

    holdings_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example_path, holdings_path)
    print(f"Created local holdings config: {holdings_path}")
    print("Canonical holdings.json is local data and should not be committed.")
    print("Allowed fields: code, name, market, sector, watch_tags, notes.")
    print("Do not save cost, position, shares, amount, market value, profit/loss, or account amount.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
