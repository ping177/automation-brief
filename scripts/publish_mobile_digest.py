from __future__ import annotations

import argparse
from datetime import date, datetime
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project_paths import get_project_paths  # noqa: E402


PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_DIR / ".env.local"
REPORT_PREFIXES = {
    "digest": "daily-news",
    "overnight_brief": "morning-brief",
}
_REPORT_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_env_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        name, value = line.split("=", 1)
        if name.strip() != key:
            continue

        cleaned = value.strip()
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
            cleaned = cleaned[1:-1]
        return cleaned

    return ""


def resolve_report_name(report_type: str, report_date: date) -> str:
    prefix = REPORT_PREFIXES.get(report_type)
    if prefix is None:
        raise ValueError(f"Unsupported report type: {report_type}")
    return f"{prefix}-{report_date.isoformat()}.md"


def resolve_report_date(report_date: date | str | None) -> date:
    """Resolve an optional explicit calendar date without timezone guessing."""

    if report_date is None:
        return date.today()
    if isinstance(report_date, datetime) or isinstance(report_date, date):
        if isinstance(report_date, datetime):
            raise ValueError("report_date must be a YYYY-MM-DD calendar date")
        return report_date
    if not isinstance(report_date, str) or not _REPORT_DATE_PATTERN.fullmatch(report_date):
        raise ValueError("report_date must be a valid YYYY-MM-DD calendar date")
    try:
        return date.fromisoformat(report_date)
    except ValueError:
        raise ValueError("report_date must be a valid YYYY-MM-DD calendar date") from None


def main(
    *,
    data_root: Path | None = None,
    env_file: Path | None = None,
    report_type: str = "digest",
    report_date: date | str | None = None,
) -> int:
    try:
        report_name = resolve_report_name(report_type, resolve_report_date(report_date))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    paths = get_project_paths(repo_root=PROJECT_DIR, data_root=data_root)
    report_path = paths.reports_dir / report_name
    if report_date is not None and not report_path.exists():
        print(f"Report not found: {report_path}", file=sys.stderr)
        return 1

    resolved_env_file = Path(env_file) if env_file is not None else ENV_FILE
    mobile_digest_dir = load_env_value(resolved_env_file, "MOBILE_DIGEST_DIR")
    if not mobile_digest_dir:
        print("MOBILE_DIGEST_DIR is not set; skip mobile digest sync.")
        return 0

    if not report_path.exists():
        print(f"Report not found: {report_path}", file=sys.stderr)
        return 1

    target_dir = Path(mobile_digest_dir).expanduser()
    target_path = target_dir / report_path.name

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(report_path, target_path)
    except OSError as exc:
        print(f"Mobile digest sync failed: {exc}", file=sys.stderr)
        return 1

    print(f"Mobile digest synced: {target_path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync the canonical daily report to a mobile directory.")
    parser.add_argument("--data-root", type=Path, help="Override canonical runtime data root")
    parser.add_argument("--env-file", type=Path, help="Override local environment file")
    parser.add_argument(
        "--report-type",
        choices=tuple(REPORT_PREFIXES),
        default="digest",
        help="Select the canonical report to sync (default: digest)",
    )
    parser.add_argument(
        "--report-date",
        help="Explicit report date (YYYY-MM-DD); omitted for legacy routes defaults to today",
    )
    cli_args = parser.parse_args()
    raise SystemExit(
        main(
            data_root=cli_args.data_root,
            env_file=cli_args.env_file,
            report_type=cli_args.report_type,
            report_date=cli_args.report_date,
        )
    )
