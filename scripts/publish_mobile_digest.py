from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project_paths import get_project_paths  # noqa: E402


PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_DIR / ".env"


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


def main(*, data_root: Path | None = None, env_file: Path | None = None) -> int:
    paths = get_project_paths(repo_root=PROJECT_DIR, data_root=data_root)
    resolved_env_file = Path(env_file) if env_file is not None else ENV_FILE
    mobile_digest_dir = load_env_value(resolved_env_file, "MOBILE_DIGEST_DIR")
    if not mobile_digest_dir:
        print("MOBILE_DIGEST_DIR is not set; skip mobile digest sync.")
        return 0

    report_path = paths.reports_dir / f"daily-news-{date.today().isoformat()}.md"
    if not report_path.exists():
        print(f"Daily report not found: {report_path}", file=sys.stderr)
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
    cli_args = parser.parse_args()
    raise SystemExit(main(data_root=cli_args.data_root, env_file=cli_args.env_file))
