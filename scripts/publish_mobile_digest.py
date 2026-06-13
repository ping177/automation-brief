from __future__ import annotations

import shutil
import sys
from datetime import date
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_DIR / ".env"
OUTPUT_DIR = PROJECT_DIR / "output"


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


def main() -> int:
    mobile_digest_dir = load_env_value(ENV_FILE, "MOBILE_DIGEST_DIR")
    if not mobile_digest_dir:
        print("MOBILE_DIGEST_DIR is not set; skip mobile digest sync.")
        return 0

    report_path = OUTPUT_DIR / f"daily-news-{date.today().isoformat()}.md"
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
    raise SystemExit(main())
