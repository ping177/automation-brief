#!/usr/bin/env python3
"""Manually run the formal Generation 2 Morning Brief with delivery disabled."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Callable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from collector import FeedFetcher  # noqa: E402
from generation_2_runtime import (  # noqa: E402
    DEFAULT_FEEDS_PATH,
    DEEPSEEK_PROVIDER_ID,
    Generation2RuntimeConfigurationError,
    build_generation_2_runtime,
    resolve_morning_brief_report_slot,
    resolve_morning_brief_rolling_slot,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    slot_group = parser.add_mutually_exclusive_group()
    slot_group.add_argument(
        "--date",
        help="Morning Brief report date (YYYY-MM-DD); defaults to today",
    )
    slot_group.add_argument(
        "--as-of-now",
        action="store_true",
        help="Use a manual rolling window ending at the current Shanghai time",
    )
    parser.add_argument(
        "--real-provider",
        choices=(DEEPSEEK_PROVIDER_ID,),
        required=True,
        help="Explicitly opt in to the real Generation 2 provider",
    )
    parser.add_argument("--feeds", type=Path, default=DEFAULT_FEEDS_PATH)
    parser.add_argument("--data-root", type=Path, help="Override canonical runtime data root")
    parser.add_argument("--model-cache", type=Path, help="Override the local embedding model cache")
    parser.add_argument("--run-id", help="Optional explicit Generation 2 run identity")
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    *,
    runtime_builder=build_generation_2_runtime,
    collector_fetcher: FeedFetcher | None = None,
    clock: Callable[[], datetime] | None = None,
) -> int:
    args = parse_args(argv)
    try:
        slot_options = {} if clock is None else {"clock": clock}
        if args.as_of_now:
            slot = resolve_morning_brief_rolling_slot(**slot_options)
        else:
            slot = resolve_morning_brief_report_slot(args.date, **slot_options)
        runtime = runtime_builder(
            provider=args.real_provider,
            feeds_path=args.feeds,
            data_root=args.data_root,
            model_cache=args.model_cache,
        )
        run_options = {
            "run_id": args.run_id,
            "collector_fetcher": collector_fetcher,
        }
        if clock is not None:
            run_options["clock"] = clock
        result = runtime.run(slot, **run_options)
    except Generation2RuntimeConfigurationError as error:
        print(f"Generation 2 runtime configuration failed: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"Generation 2 runtime failed: {type(error).__name__}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "artifact_dir": None if result.run_dir is None else str(result.run_dir),
                "generation_outcome": result.generation_outcome,
                "report_date": slot.report_date.isoformat(),
                "run_id": result.run_id,
                "target_language": slot.target_language,
                "window_end": slot.window_end.isoformat(),
                "window_start": slot.window_start.isoformat(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result.generation_outcome in {"complete", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
