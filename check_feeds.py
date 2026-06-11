from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import feedparser


BASE_DIR = Path(__file__).resolve().parent
FEEDS_FILE = BASE_DIR / "feeds.json"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize_feeds(raw_feeds: Any) -> list[dict[str, str]]:
    if not isinstance(raw_feeds, list):
        raise ValueError("feeds.json must be a list of feed objects")

    feeds: list[dict[str, str]] = []
    for index, feed in enumerate(raw_feeds, start=1):
        if not isinstance(feed, dict):
            raise ValueError(f"Feed #{index} must be an object")

        name = str(feed.get("name", "")).strip()
        url = str(feed.get("url", "")).strip()
        category = str(feed.get("category", "")).strip()
        mode = str(feed.get("mode", "keyword")).strip().lower() or "keyword"
        role = str(feed.get("role", "general")).strip().lower() or "general"
        if not name or not url:
            raise ValueError(f"Feed #{index} must include non-empty name and url")

        feeds.append({"name": name, "url": url, "category": category, "mode": mode, "role": role})
    return feeds


def markdown_escape(value: Any) -> str:
    text = str(value) if value is not None else ""
    return text.replace("\n", " ").replace("\r", " ").replace("|", "\\|")


def check_feed(feed: dict[str, str]) -> dict[str, Any]:
    result = {
        "name": feed["name"],
        "url": feed["url"],
        "category": feed.get("category", ""),
        "mode": feed.get("mode", "keyword"),
        "role": feed.get("role", "general"),
        "status": "failed",
        "entries_count": 0,
        "error_message": "",
    }

    try:
        parsed_feed = feedparser.parse(feed["url"])
    except Exception as exc:
        result["error_message"] = str(exc)
        return result

    result["entries_count"] = len(parsed_feed.entries)
    bozo_reason = ""
    if parsed_feed.bozo:
        bozo_reason = str(getattr(parsed_feed, "bozo_exception", "Unknown feed parse warning"))
        result["error_message"] = bozo_reason

    if result["entries_count"] > 0:
        result["status"] = "ok_with_warning" if bozo_reason else "ok"
        return result

    result["status"] = "failed" if bozo_reason else "empty"
    return result


def sort_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    status_order = {"ok": 0, "ok_with_warning": 1, "empty": 2, "failed": 3}
    return sorted(results, key=lambda result: (status_order.get(str(result["status"]), 99), result["name"]))


def status_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"ok": 0, "ok_with_warning": 0, "empty": 0, "failed": 0}
    for result in results:
        status = str(result["status"])
        if status in counts:
            counts[status] += 1
    return counts


def print_results(results: list[dict[str, Any]]) -> None:
    counts = status_counts(results)
    print(
        "Total: {total} | ok: {ok} | ok_with_warning: {ok_with_warning} | empty: {empty} | failed: {failed}".format(
            total=len(results),
            ok=counts["ok"],
            ok_with_warning=counts["ok_with_warning"],
            empty=counts["empty"],
            failed=counts["failed"],
        )
    )
    print()
    print("| name | role | mode | status | entries_count | error_message |")
    print("| --- | --- | --- | --- | ---: | --- |")
    for result in results:
        print(
            "| {name} | {role} | {mode} | {status} | {entries_count} | {error_message} |".format(
                name=markdown_escape(result["name"]),
                role=markdown_escape(result["role"]),
                mode=markdown_escape(result["mode"]),
                status=markdown_escape(result["status"]),
                entries_count=result["entries_count"],
                error_message=markdown_escape(result["error_message"]),
            )
        )


def main() -> None:
    feeds = normalize_feeds(load_json(FEEDS_FILE))
    results = sort_results([check_feed(feed) for feed in feeds])
    print_results(results)


if __name__ == "__main__":
    main()
