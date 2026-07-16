from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ai_curator import (  # noqa: E402
    FixtureCuratorProvider,
    build_curator_request,
    candidate_trace_records,
    load_candidate_fixture,
    render_shadow_preview,
)
from main import (  # noqa: E402
    DEFAULT_CONFIG_FILE,
    DEFAULT_FEEDS_FILE,
    DEFAULT_KEYWORDS_FILE,
    DEFAULT_OUTPUT_DIR,
    candidate_text,
    collect_candidate_articles,
    load_json,
    load_optional_json,
    match_keywords,
    news_item_from_candidate,
    normalize_config,
    normalize_feeds,
    normalize_keywords,
    parse_report_date,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an offline AI Curator shadow preview.")
    parser.add_argument("--fixture-response", required=True, type=Path, help="Local JSON CuratorResponse fixture")
    parser.add_argument("--candidate-fixture", type=Path, help="Local JSON CandidateArticle fixture")
    parser.add_argument("--feeds", type=Path, default=DEFAULT_FEEDS_FILE, help="Path to feeds.json")
    parser.add_argument("--keywords", type=Path, default=DEFAULT_KEYWORDS_FILE, help="Path to keywords.json")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_FILE, help="Path to config.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR / "ai-curator-shadow")
    parser.add_argument("--date", help="Report date, defaults to today. Example: 2026-07-16")
    parser.add_argument("--max-events", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report_date = parse_report_date(args.date) if args.date else date.today()
    if args.candidate_fixture:
        fixture_report_date, candidates = load_candidate_fixture(args.candidate_fixture)
        if args.date and fixture_report_date != report_date:
            raise ValueError("Candidate fixture report_date does not match --date")
        report_date = fixture_report_date
        candidate_failures = ()
        legacy_items = []
    else:
        raw_config = load_optional_json(args.config)
        config = normalize_config(raw_config)
        feeds = normalize_feeds(load_json(args.feeds))
        keywords = normalize_keywords(load_json(args.keywords))

        candidates, candidate_failures = collect_candidate_articles(feeds, config, report_date)
        feed_mode_by_name = {feed["name"]: feed["mode"] for feed in feeds}
        legacy_items = legacy_items_from_candidates(candidates, keywords, feed_mode_by_name, config.max_items_per_feed)
    request = build_curator_request(candidates, report_date=report_date, max_events=args.max_events)
    response = FixtureCuratorProvider(args.fixture_response).curate(request)
    trace_records = candidate_trace_records(candidates, legacy_items)
    if candidate_failures:
        trace_records.append(
            {
                "trace_type": "fetch_failures",
                "candidate_failures": list(candidate_failures),
            }
        )

    preview = render_shadow_preview(response, request, trace_records)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_path = output_dir / f"ai-curator-shadow-{report_date.isoformat()}.md"
    trace_path = output_dir / f"ai-curator-shadow-trace-{report_date.isoformat()}.json"
    request_path = output_dir / f"ai-curator-shadow-request-{report_date.isoformat()}.json"

    preview_path.write_text(preview, encoding="utf-8")
    trace_path.write_text(json.dumps(trace_records, ensure_ascii=False, indent=2), encoding="utf-8")
    request_path.write_text(json.dumps(request.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Shadow preview written: {preview_path}")
    print(f"Candidate trace written: {trace_path}")
    print(f"Curator request written: {request_path}")


def legacy_items_from_candidates(candidates, keywords, feed_mode_by_name, max_items_per_feed):  # noqa: ANN001
    seen_links: set[str] = set()
    feed_counts: dict[str, int] = {}
    legacy_items = []
    for candidate in candidates:
        if not candidate.link:
            continue
        matched = match_keywords(candidate_text(candidate), keywords)
        feed_mode = feed_mode_by_name.get(candidate.feed_name, "keyword")
        if feed_mode == "keyword" and not matched:
            continue
        if candidate.link in seen_links:
            continue
        if feed_counts.get(candidate.feed_name, 0) >= max_items_per_feed:
            continue
        seen_links.add(candidate.link)
        feed_counts[candidate.feed_name] = feed_counts.get(candidate.feed_name, 0) + 1
        legacy_items.append(news_item_from_candidate(candidate, matched))
    return legacy_items


if __name__ == "__main__":
    main()
