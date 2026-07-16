from __future__ import annotations

from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
for site_packages in (PROJECT_ROOT / ".venv" / "lib").glob("python*/site-packages"):
    sys.path.insert(0, str(site_packages))

import main as main_module  # noqa: E402
from ai_curator import build_curator_request, candidate_trace_records  # noqa: E402
from main import ReportConfig, collect_candidate_articles, collect_news  # noqa: E402


class FakeResponse:
    headers = {"Content-Type": "application/rss+xml; charset=utf-8"}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:  # noqa: ANN001
        return False

    def read(self) -> bytes:
        fresh = format_datetime(datetime.now(timezone.utc), usegmt=True)
        stale = format_datetime(datetime(2020, 1, 1, tzinfo=timezone.utc), usegmt=True)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Fixture</title>
    <item>
      <title>Global ceasefire agreement signed overnight</title>
      <link>https://example.com/world/major-event?utm_source=rss#section</link>
      <description>Major international event with no legacy keywords.</description>
      <pubDate>{fresh}</pubDate>
    </item>
    <item>
      <title>Global ceasefire agreement duplicate</title>
      <link>https://example.com/world/major-event?utm_source=other</link>
      <description>Duplicate canonical link.</description>
      <pubDate>{fresh}</pubDate>
    </item>
	    <item>
	      <title>OpenAI launches enterprise payment workflow</title>
	      <link>https://example.com/ai/openai-payments</link>
	      <description>OpenAI and payments are legacy keywords.</description>
	      <pubDate>{fresh}</pubDate>
	    </item>
	    <item>
	      <title>Major central bank emergency statement without link</title>
	      <description>Policy makers issued a major emergency statement.</description>
	      <pubDate>{fresh}</pubDate>
	    </item>
	    <item>
	      <title>Old global event outside window</title>
	      <link>https://example.com/world/old-event</link>
      <description>Too old for the report window.</description>
      <pubDate>{stale}</pubDate>
    </item>
  </channel>
</rss>
""".encode("utf-8")

    def geturl(self) -> str:
        return "https://example.com/feed.xml"


def fake_parse_feed(_feed):  # noqa: ANN001
    return main_module.feedparser.parse(FakeResponse().read())


def main() -> None:
    original_parse_feed = main_module.parse_feed_with_retry
    feed = {
        "name": "Fixture Feed",
        "url": "https://example.com/feed.xml",
        "mode": "keyword",
        "role": "global_tech_business",
    }
    config = ReportConfig(report_type="digest", max_items_per_feed=10)
    try:
        main_module.parse_feed_with_retry = fake_parse_feed
        candidates, failures = collect_candidate_articles([feed], config, date.today())
        legacy_items, legacy_failures = collect_news(
            [feed],
            {"AI方向": ["OpenAI", "payment"]},
            config,
            date.today(),
        )
        repeated_candidates, _failures = collect_candidate_articles([feed], config, date.today())
    finally:
        main_module.parse_feed_with_retry = original_parse_feed

    assert failures == ()
    assert legacy_failures == []
    assert len(candidates) == 3
    assert any("ceasefire" in item.title for item in candidates)
    assert any("without link" in item.title for item in candidates)
    assert all("Old global event" not in item.title for item in candidates)
    assert sum(1 for item in candidates if item.normalized_link == "https://example.com/world/major-event") == 1
    assert len({item.article_id for item in candidates}) == len(candidates)

    id_by_key = {item.normalized_link or item.title: item.article_id for item in candidates}
    repeated_id_by_key = {item.normalized_link or item.title: item.article_id for item in repeated_candidates}
    assert id_by_key == repeated_id_by_key
    linkless = next(item for item in candidates if "without link" in item.title)
    assert linkless.link == ""
    assert linkless.normalized_link == ""
    assert linkless.article_id.startswith("art_")

    assert len(legacy_items) == 1
    assert legacy_items[0].title == "OpenAI launches enterprise payment workflow"
    assert all("without link" not in item.title for item in legacy_items)

    request = build_curator_request(candidates, report_date=date.today(), max_events=3)
    article_payload = request.to_dict()["articles"][0]
    forbidden_request_fields = {"matched_keywords", "legacy_score", "legacy_category", "holdings", "watch_tags"}
    assert not forbidden_request_fields.intersection(article_payload)

    trace = candidate_trace_records(candidates, legacy_items)
    assert any(record["legacy_keyword_matched"] is False for record in trace)
    assert any(record["legacy_keyword_matched"] is True for record in trace)
    assert any(record["legacy_matched_keywords"] for record in trace)
    forbidden_sensitive_fields = {"cost", "position", "shares", "amount", "market_value", "profit", "loss"}
    assert not any(forbidden_sensitive_fields.intersection(record) for record in trace)

    print("offline ai curator candidate smoke passed")


if __name__ == "__main__":
    main()
