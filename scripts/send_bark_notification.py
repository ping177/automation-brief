from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen


PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_DIR / ".env"
OUTPUT_DIR = PROJECT_DIR / "output"
TITLE = "每日早间回顾已生成"


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


def main() -> int:
    bark_url = load_env_value(ENV_FILE, "BARK_URL")
    if not bark_url:
        print("BARK_URL is not set; skip Bark notification.")
        return 0

    report_path = OUTPUT_DIR / f"daily-news-{date.today().isoformat()}.md"
    if not report_path.exists():
        print(f"Daily report not found: {report_path}", file=sys.stderr)
        return 1

    relative_report_path = report_path.relative_to(PROJECT_DIR)
    body_parts = [str(relative_report_path)]
    displayed_items = find_displayed_items(report_path)
    if displayed_items:
        body_parts.append(f"Displayed items: {displayed_items}")

    obsidian_uri = ""
    vault_name = load_env_value(ENV_FILE, "OBSIDIAN_VAULT_NAME")
    mobile_digest_relative_path = load_env_value(ENV_FILE, "MOBILE_DIGEST_RELATIVE_PATH")
    if vault_name and mobile_digest_relative_path:
        obsidian_uri = build_obsidian_uri(vault_name, mobile_digest_relative_path, report_path.name)

    try:
        send_notification(bark_url, TITLE, "\n".join(body_parts), obsidian_uri)
    except HTTPError as exc:
        print(f"Bark notification failed: HTTP {exc.code} {exc.reason}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Bark notification failed: {exc.reason}", file=sys.stderr)
        return 1
    except TimeoutError:
        print("Bark notification failed: request timed out", file=sys.stderr)
        return 1

    if obsidian_uri:
        print("Bark notification sent with Obsidian URL.")
    else:
        print("Bark notification sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
