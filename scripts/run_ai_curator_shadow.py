from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ai_curator import (  # noqa: E402
    CuratorContractError,
    FixtureCuratorProvider,
    build_curator_request,
    candidate_trace_records,
    load_candidate_fixture,
)
from ai_curator_artifacts import ShadowRunInfo, create_run_id, write_shadow_run  # noqa: E402
from main import (  # noqa: E402
    DEFAULT_CONFIG_FILE,
    DEFAULT_FEEDS_FILE,
    DEFAULT_KEYWORDS_FILE,
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
from project_paths import get_project_paths  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an offline AI Curator shadow preview.")
    parser.add_argument("--fixture-response", required=True, type=Path, help="Local JSON CuratorResponse fixture")
    parser.add_argument("--candidate-fixture", type=Path, help="Local JSON CandidateArticle fixture")
    parser.add_argument("--feeds", type=Path, default=DEFAULT_FEEDS_FILE, help="Path to feeds.json")
    parser.add_argument("--keywords", type=Path, default=DEFAULT_KEYWORDS_FILE, help="Path to keywords.json")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_FILE, help="Path to config.json")
    parser.add_argument("--output-dir", type=Path, help="Override shadow artifact directory")
    parser.add_argument("--data-root", type=Path, help="Override canonical runtime data root")
    parser.add_argument("--date", help="Report date, defaults to today. Example: 2026-07-16")
    parser.add_argument("--max-events", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = get_project_paths(repo_root=PROJECT_ROOT, data_root=args.data_root)
    report_date = parse_report_date(args.date) if args.date else date.today()
    if args.candidate_fixture:
        fixture_report_date, candidates = load_candidate_fixture(args.candidate_fixture)
        if args.date and fixture_report_date != report_date:
            raise ValueError("Candidate fixture report_date does not match --date")
        report_date = fixture_report_date
        candidate_failures = ()
        legacy_items = []
        legacy_evaluation = "not_evaluated"
        candidate_window_start = None
        candidate_window_end = None
    else:
        raw_config = load_optional_json(args.config)
        config = normalize_config(raw_config)
        feeds = normalize_feeds(load_json(args.feeds))
        keywords = normalize_keywords(load_json(args.keywords))

        candidates, candidate_failures = collect_candidate_articles(feeds, config, report_date)
        feed_mode_by_name = {feed["name"]: feed["mode"] for feed in feeds}
        legacy_items = legacy_items_from_candidates(candidates, keywords, feed_mode_by_name, config.max_items_per_feed)
        legacy_evaluation = "keyword_gate_approximation"
        candidate_window_start, candidate_window_end = candidate_collection_window(candidates)
    request = build_curator_request(candidates, report_date=report_date, max_events=args.max_events)
    trace_records = candidate_trace_records(candidates, legacy_items)
    if candidate_failures:
        trace_records.append(
            {
                "trace_type": "fetch_failures",
                "candidate_failures": list(candidate_failures),
            }
        )

    output_dir = args.output_dir or paths.ai_curator_shadow_dir
    run_id = create_run_id()
    try:
        response = FixtureCuratorProvider(args.fixture_response).curate(request)
    except Exception as exc:
        failure_info = _fixture_failure_info(
            exc,
            legacy_evaluation=legacy_evaluation,
            candidate_window_start=candidate_window_start,
            candidate_window_end=candidate_window_end,
        )
        paths = write_shadow_run(
            output_dir,
            report_date=report_date,
            request=request,
            response=None,
            trace_records=trace_records,
            run_info=failure_info,
            run_id=run_id,
        )
        print(f"Shadow run failed: {paths.run_dir}", file=sys.stderr)
        raise

    paths = write_shadow_run(
        output_dir,
        report_date=report_date,
        request=request,
        response=response,
        trace_records=trace_records,
        run_info=ShadowRunInfo(
            status="succeeded",
            provider_id="fixture",
            model="fixture-response",
            api_key_env="",
            attempts=1,
            validation_status="passed",
            legacy_evaluation=legacy_evaluation,
            candidate_window_start=candidate_window_start,
            candidate_window_end=candidate_window_end,
            provider_request_body_bytes=None,
        ),
        run_id=run_id,
    )
    print(f"Shadow run written: {paths.run_dir}")


def _fixture_failure_info(
    exc: Exception,
    *,
    legacy_evaluation: str,
    candidate_window_start,
    candidate_window_end,
) -> ShadowRunInfo:  # noqa: ANN001
    if isinstance(exc, json.JSONDecodeError):
        return ShadowRunInfo(
            status="failed",
            provider_id="fixture",
            model="fixture-response",
            api_key_env="",
            attempts=1,
            validation_status="not_run",
            failure_stage="response_parse",
            failure_code="invalid_json",
            legacy_evaluation=legacy_evaluation,
            candidate_window_start=candidate_window_start,
            candidate_window_end=candidate_window_end,
            provider_request_body_bytes=None,
        )
    if isinstance(exc, CuratorContractError):
        return ShadowRunInfo(
            status="failed",
            provider_id="fixture",
            model="fixture-response",
            api_key_env="",
            attempts=1,
            validation_status="failed",
            failure_stage="validation",
            failure_code="invalid_curator_response",
            legacy_evaluation=legacy_evaluation,
            candidate_window_start=candidate_window_start,
            candidate_window_end=candidate_window_end,
            provider_request_body_bytes=None,
        )
    return ShadowRunInfo(
        status="failed",
        provider_id="fixture",
        model="fixture-response",
        api_key_env="",
        attempts=1,
        validation_status="not_run",
        failure_stage="fixture_provider",
        failure_code="fixture_provider_error",
        legacy_evaluation=legacy_evaluation,
        candidate_window_start=candidate_window_start,
        candidate_window_end=candidate_window_end,
        provider_request_body_bytes=None,
    )


def candidate_collection_window(candidates):  # noqa: ANN001
    collected_at = [candidate.collected_at for candidate in candidates]
    if not collected_at:
        return None, None
    return min(collected_at), max(collected_at)


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
