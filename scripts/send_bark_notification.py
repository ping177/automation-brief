from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project_paths import get_project_paths  # noqa: E402


PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_DIR / ".env.local"
REPORT_SETTINGS = {
    "digest": ("daily-news", "每日早间回顾已生成"),
    "overnight_brief": ("morning-brief", "早间简报已生成"),
}
MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (10, 20)
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


def find_displayed_items(markdown_path: Path) -> str:
    pattern = re.compile(r"^Displayed items:\s*(.+)$")
    for line in markdown_path.read_text(encoding="utf-8").splitlines()[:20]:
        match = pattern.match(line.strip())
        if match:
            return match.group(1).strip()
    return ""


def build_obsidian_uri(vault_name: str, relative_dir: str, report_name: str) -> str:
    relative_path = f"{relative_dir.strip('/')}/{report_name}"
    query = urlencode({"vault": vault_name, "file": relative_path}, quote_via=quote)
    return f"obsidian://open?{query}"


def send_notification(bark_url: str, title: str, body: str, url: str = "") -> None:
    payload = {"title": title, "body": body}
    if url:
        payload["url"] = url

    request = Request(
        bark_url.rstrip("/"),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "daily-news-automation",
        },
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        response.read()


def format_notification_error(exc: BaseException) -> str:
    if isinstance(exc, HTTPError):
        return f"http_{exc.code}"
    if isinstance(exc, TimeoutError):
        return "ambiguous_timeout"
    if isinstance(exc, URLError):
        if isinstance(exc.reason, TimeoutError):
            return "ambiguous_timeout"
        return "transport_failed"
    if isinstance(exc, OSError):
        return "transport_failed"
    return "delivery_failed"


def is_retryable_notification_error(exc: BaseException) -> bool:
    """Keep only the existing explicit HTTP retry classes."""

    return isinstance(exc, HTTPError) and (exc.code == 429 or 500 <= exc.code <= 599)


def resolve_report_settings(report_type: str, report_date: date) -> tuple[str, str]:
    settings = REPORT_SETTINGS.get(report_type)
    if settings is None:
        raise ValueError(f"Unsupported report type: {report_type}")
    prefix, title = settings
    return f"{prefix}-{report_date.isoformat()}.md", title


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
        report_name, title = resolve_report_settings(report_type, resolve_report_date(report_date))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    paths = get_project_paths(repo_root=PROJECT_DIR, data_root=data_root)
    report_path = paths.reports_dir / report_name
    if report_date is not None and not report_path.exists():
        print(f"Report not found: {report_path}", file=sys.stderr)
        return 1

    resolved_env_file = Path(env_file) if env_file is not None else ENV_FILE
    bark_url = load_env_value(resolved_env_file, "BARK_URL")
    if not bark_url:
        print("BARK_URL is not set; skip Bark notification.")
        return 0

    if not report_path.exists():
        print(f"Report not found: {report_path}", file=sys.stderr)
        return 1

    relative_report_path = Path("reports") / report_path.name
    body_parts = [str(relative_report_path)]
    if report_type == "digest":
        displayed_items = find_displayed_items(report_path)
        if displayed_items:
            body_parts.append(f"Displayed items: {displayed_items}")

    obsidian_uri = ""
    vault_name = load_env_value(resolved_env_file, "OBSIDIAN_VAULT_NAME")
    mobile_digest_relative_path = load_env_value(resolved_env_file, "MOBILE_DIGEST_RELATIVE_PATH")
    if vault_name and mobile_digest_relative_path:
        obsidian_uri = build_obsidian_uri(vault_name, mobile_digest_relative_path, report_path.name)

    body = "\n".join(body_parts)
    explicit_report_date = report_date is not None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            send_notification(bark_url, title, body, obsidian_uri)
            break
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            error_message = format_notification_error(exc)
            if explicit_report_date and not is_retryable_notification_error(exc):
                if error_message == "ambiguous_timeout":
                    print(
                        "Bark notification ambiguous: failure_code=ambiguous_timeout; no retry",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"Bark notification failed: failure_code={error_message}; no retry",
                        file=sys.stderr,
                    )
                return 1
            if attempt >= MAX_ATTEMPTS:
                print(
                    f"Bark notification failed after {MAX_ATTEMPTS} attempts: "
                    f"failure_code={error_message}",
                    file=sys.stderr,
                )
                return 1

            delay = RETRY_DELAYS_SECONDS[attempt - 1]
            print(
                f"Bark notification attempt {attempt}/{MAX_ATTEMPTS} failed: "
                f"failure_code={error_message}; retrying in {delay}s",
                file=sys.stderr,
            )
            time.sleep(delay)
        except Exception:
            # Never expose an unexpected provider/client exception (which may
            # contain the configured Bark URL); unknown failures are not safe
            # retry classes and fail closed for both routes.
            print(
                "Bark notification failed: failure_code=delivery_failed; no retry",
                file=sys.stderr,
            )
            return 1

    if obsidian_uri:
        print("Bark notification sent with Obsidian URL.")
    else:
        print("Bark notification sent.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send the canonical daily report through Bark.")
    parser.add_argument("--data-root", type=Path, help="Override canonical runtime data root")
    parser.add_argument("--env-file", type=Path, help="Override local environment file")
    parser.add_argument(
        "--report-type",
        choices=tuple(REPORT_SETTINGS),
        default="digest",
        help="Select the canonical report to announce (default: digest)",
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
