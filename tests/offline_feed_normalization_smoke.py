from __future__ import annotations

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from check_feeds import normalize_feeds as normalize_check_feeds  # noqa: E402
from main import normalize_feeds as normalize_main_feeds  # noqa: E402


def core_fields(feed: dict[str, str]) -> tuple[str, str, str, str]:
    return feed["name"], feed["url"], feed["mode"], feed["role"]


def main() -> None:
    feeds_path = PROJECT_ROOT / "feeds.json"
    example_path = PROJECT_ROOT / "feeds.example.json"
    raw_feeds = json.loads(feeds_path.read_text(encoding="utf-8"))
    raw_examples = json.loads(example_path.read_text(encoding="utf-8"))

    normalized_main = normalize_main_feeds(raw_feeds)
    normalized_check = normalize_check_feeds(raw_feeds)
    assert len(normalized_main) == len(raw_feeds) == 16
    assert len(normalized_check) == len(raw_feeds)
    assert [core_fields(feed) for feed in normalized_main] == [
        core_fields(feed) for feed in normalized_check
    ]
    assert [feed["language"] for feed in normalized_main] == [
        "zh-CN",
        "zh-CN",
        "zh-CN",
        "zh-CN",
        "zh-CN",
        "zh-CN",
        "zh-CN",
        "zh-CN",
        "zh-CN",
        "zh-CN",
        "zh-CN",
        "en",
        "en",
        "en",
        "en",
        "en",
    ]
    assert [feed["language"] for feed in normalized_check] == [
        feed["language"] for feed in normalized_main
    ]

    assert len(normalize_main_feeds(raw_examples)) == len(raw_examples)
    assert len(normalize_check_feeds(raw_examples)) == len(raw_examples)

    variants = [({}, "und"), ({"language": None}, "und"), ({"language": ""}, "und"),
                ({"language": "fr"}, "und"), ({"language": " EN "}, "en"),
                ({"language": "zh-cn"}, "zh-CN")]
    base_feed = {
        "name": "Fixture Feed",
        "url": "https://example.com/feed.xml",
        "mode": "keyword",
        "role": "general",
    }
    for language_patch, expected in variants:
        raw_feed = {**base_feed, **language_patch}
        main_feed = normalize_main_feeds([raw_feed])[0]
        check_feed = normalize_check_feeds([raw_feed])[0]
        assert main_feed["language"] == expected
        assert check_feed["language"] == expected
        assert core_fields(main_feed) == core_fields(base_feed)
        assert core_fields(check_feed) == core_fields(base_feed)

    print("offline feed normalization smoke passed")


if __name__ == "__main__":
    main()
