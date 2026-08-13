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
from ai_curator_provider import (  # noqa: E402
    DEEPSEEK_PROVIDER_CONFIG,
    PHASE_3B_FIXTURE_INPUT_MODE,
    PHASE_4_LIVE_INPUT_MODE,
    DeepSeekCuratorProvider,
    OpenAICompatibleProviderError,
)
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


PHASE_3B_MAX_CANDIDATE_COUNT = 2
PHASE_3B_MAX_PROVIDER_REQUEST_BODY_BYTES = 4096
DEFAULT_MAX_EVENTS = 5
PHASE_4_LIVE_MAX_CANDIDATE_COUNT = 200
PHASE_4_LIVE_MAX_EVENTS = 10
PHASE_4_LIVE_MAX_PROVIDER_REQUEST_BODY_BYTES = 200000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an offline AI Curator shadow preview.")
    parser.add_argument("--fixture-response", type=Path, help="Local JSON CuratorResponse fixture")
    parser.add_argument("--candidate-fixture", type=Path, help="Local JSON CandidateArticle fixture")
    parser.add_argument("--feeds", type=Path, default=DEFAULT_FEEDS_FILE, help="Path to feeds.json")
    parser.add_argument("--keywords", type=Path, default=DEFAULT_KEYWORDS_FILE, help="Path to keywords.json")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_FILE, help="Path to config.json")
    parser.add_argument("--output-dir", type=Path, help="Override shadow artifact directory")
    parser.add_argument("--data-root", type=Path, help="Override canonical runtime data root")
    parser.add_argument("--date", help="Report date, defaults to today. Example: 2026-07-16")
    parser.add_argument(
        "--max-events",
        type=int,
        help="Override the input-mode event capacity (default: 5; phase4_live: 10).",
    )
    parser.add_argument(
        "--real-provider",
        choices=("deepseek",),
        help="Explicitly opt into a real provider; omitted means fixture provider.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and measure the selected real-provider request without transport.",
    )
    parser.add_argument(
        "--input-mode",
        choices=(PHASE_3B_FIXTURE_INPUT_MODE, PHASE_4_LIVE_INPUT_MODE),
        default=PHASE_3B_FIXTURE_INPUT_MODE,
        help="Explicit provider input policy; phase4_live is never inferred.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _validate_cli_mode(args)
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
    request = build_curator_request(
        candidates,
        report_date=report_date,
        max_events=_max_events_for_args(args),
    )
    trace_records = candidate_trace_records(candidates, legacy_items)
    if candidate_failures:
        trace_records.append(
            {
                "trace_type": "fetch_failures",
                "candidate_failures": list(candidate_failures),
            }
    )

    output_dir = args.output_dir or paths.ai_curator_shadow_dir
    if args.real_provider == "deepseek" and args.dry_run:
        _print_deepseek_preflight(
            request,
            input_mode=args.input_mode,
        )
        return

    run_id = create_run_id()
    if args.real_provider == "deepseek":
        _run_real_provider(
            request=request,
            report_date=report_date,
            trace_records=trace_records,
            output_dir=output_dir,
            run_id=run_id,
            legacy_evaluation=legacy_evaluation,
            candidate_window_start=candidate_window_start,
            candidate_window_end=candidate_window_end,
            input_mode=args.input_mode,
        )
        return

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


def _validate_cli_mode(args: argparse.Namespace) -> None:
    if args.real_provider is None and args.fixture_response is None:
        raise ValueError("--fixture-response is required unless --real-provider is selected")
    if args.real_provider is not None and args.candidate_fixture is None:
        raise ValueError("--real-provider requires --candidate-fixture")
    if args.real_provider is not None and args.fixture_response is not None:
        raise ValueError("--fixture-response cannot be combined with --real-provider")
    if args.dry_run and args.real_provider != "deepseek":
        raise ValueError("--dry-run requires --real-provider deepseek")
    if args.dry_run and args.candidate_fixture is None:
        raise ValueError("--dry-run requires --candidate-fixture")
    if args.input_mode == PHASE_4_LIVE_INPUT_MODE and args.real_provider != "deepseek":
        raise ValueError("--input-mode phase4_live requires --real-provider deepseek")


def _max_events_for_args(args: argparse.Namespace) -> int:
    if args.max_events is not None:
        return args.max_events
    if args.input_mode == PHASE_4_LIVE_INPUT_MODE:
        return PHASE_4_LIVE_MAX_EVENTS
    return DEFAULT_MAX_EVENTS


def _provider_limits(input_mode: str) -> tuple[int, int]:
    if input_mode == PHASE_3B_FIXTURE_INPUT_MODE:
        return PHASE_3B_MAX_CANDIDATE_COUNT, PHASE_3B_MAX_PROVIDER_REQUEST_BODY_BYTES
    if input_mode == PHASE_4_LIVE_INPUT_MODE:
        return PHASE_4_LIVE_MAX_CANDIDATE_COUNT, PHASE_4_LIVE_MAX_PROVIDER_REQUEST_BODY_BYTES
    raise ValueError(f"unsupported provider input mode: {input_mode}")


def _print_deepseek_preflight(
    request,
    *,
    input_mode: str,
) -> None:  # noqa: ANN001
    max_candidate_count, max_provider_request_body_bytes = _provider_limits(input_mode)
    provider = DeepSeekCuratorProvider(
        config=DEEPSEEK_PROVIDER_CONFIG,
        max_candidate_count=max_candidate_count,
        max_provider_request_body_bytes=max_provider_request_body_bytes,
        input_mode=input_mode,
    )
    prepared = provider.prepare_request(request)
    metadata = provider.last_call_metadata
    if metadata is None:
        raise RuntimeError("DeepSeek provider prepared request without metadata")
    summary = {
        "mode": "dry_run",
        "provider_id": DEEPSEEK_PROVIDER_CONFIG.provider_id,
        "model": DEEPSEEK_PROVIDER_CONFIG.model,
        "endpoint": DEEPSEEK_PROVIDER_CONFIG.endpoint,
        "input_mode": input_mode,
        "original_candidate_count": len(request.articles),
        "candidate_count": len(prepared.request.articles),
        "source_excluded_count": metadata.source_excluded_count,
        "max_events": prepared.request.max_events,
        "max_candidate_count": max_candidate_count,
        "summary_max_chars": metadata.summary_max_chars,
        "summaries_capped_count": metadata.summaries_capped_count,
        "summaries_unchanged_count": metadata.summaries_unchanged_count,
        "curator_request_bytes": prepared.curator_request_bytes,
        "provider_request_body_bytes": prepared.provider_request_body_bytes,
        "max_provider_request_body_bytes": max_provider_request_body_bytes,
        "max_tokens": DEEPSEEK_PROVIDER_CONFIG.max_tokens,
        "timeout": DEEPSEEK_PROVIDER_CONFIG.timeout,
        "max_attempts": DEEPSEEK_PROVIDER_CONFIG.max_attempts,
        "thinking_mode": DEEPSEEK_PROVIDER_CONFIG.thinking_type,
        "json_mode": DEEPSEEK_PROVIDER_CONFIG.response_format_type == "json_object",
        "stream": DEEPSEEK_PROVIDER_CONFIG.stream,
        "target_language": request.target_language,
        "transport_calls": 0,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def _run_real_provider(
    *,
    request,
    report_date: date,
    trace_records,
    output_dir: Path,
    run_id: str,
    legacy_evaluation: str,
    candidate_window_start,
    candidate_window_end,
    input_mode: str,
) -> None:  # noqa: ANN001
    max_candidate_count, max_provider_request_body_bytes = _provider_limits(input_mode)
    provider = DeepSeekCuratorProvider(
        config=DEEPSEEK_PROVIDER_CONFIG,
        max_candidate_count=max_candidate_count,
        max_provider_request_body_bytes=max_provider_request_body_bytes,
        input_mode=input_mode,
    )
    try:
        response = provider.curate(request)
    except OpenAICompatibleProviderError as exc:
        metadata = provider.last_call_metadata
        artifact_request = provider.last_prepared_request or request
        has_prepared_request = provider.last_prepared_request is not None
        paths = write_shadow_run(
            output_dir,
            report_date=report_date,
            request=artifact_request,
            response=None,
            trace_records=trace_records,
            run_info=ShadowRunInfo(
                status="failed",
                provider_id=DEEPSEEK_PROVIDER_CONFIG.provider_id,
                model=DEEPSEEK_PROVIDER_CONFIG.model,
                api_key_env=DEEPSEEK_PROVIDER_CONFIG.api_key_env,
                attempts=exc.attempts,
                validation_status=metadata.validation_status if metadata else "failed",
                failure_stage=exc.failure_stage,
                failure_code=exc.failure_code,
                failure_diagnostic_code=exc.diagnostic_code,
                failure_diagnostic_path=exc.diagnostic_path,
                failure_diagnostic_article_id=exc.diagnostic_article_id,
                legacy_evaluation=legacy_evaluation,
                candidate_window_start=candidate_window_start,
                candidate_window_end=candidate_window_end,
                input_mode=input_mode,
                original_candidate_count=len(request.articles),
                source_excluded_count=(
                    metadata.source_excluded_count
                    if metadata and has_prepared_request
                    else None
                ),
                summary_max_chars=(
                    metadata.summary_max_chars
                    if metadata and has_prepared_request and input_mode == PHASE_4_LIVE_INPUT_MODE
                    else None
                ),
                summaries_capped_count=(
                    metadata.summaries_capped_count
                    if metadata and has_prepared_request and input_mode == PHASE_4_LIVE_INPUT_MODE
                    else None
                ),
                summaries_unchanged_count=(
                    metadata.summaries_unchanged_count
                    if metadata and has_prepared_request and input_mode == PHASE_4_LIVE_INPUT_MODE
                    else None
                ),
                max_candidate_count=max_candidate_count,
                max_provider_request_body_bytes=max_provider_request_body_bytes,
                curator_request_bytes=(
                    metadata.curator_request_bytes
                    if metadata and has_prepared_request
                    else None
                ),
                provider_request_body_bytes=(
                    metadata.provider_request_body_bytes
                    if metadata and has_prepared_request
                    else None
                ),
            ),
            run_id=run_id,
        )
        print(f"Real-provider run failed: {paths.run_dir}", file=sys.stderr)
        raise

    metadata = provider.last_call_metadata
    if metadata is None:
        raise RuntimeError("DeepSeek provider completed without call metadata")
    artifact_request = provider.last_prepared_request
    if artifact_request is None:
        raise RuntimeError("DeepSeek provider completed without prepared request")
    paths = write_shadow_run(
        output_dir,
        report_date=report_date,
        request=artifact_request,
        response=response,
        trace_records=trace_records,
        run_info=ShadowRunInfo(
            status="succeeded",
            provider_id=metadata.provider_id,
            model=metadata.model,
            api_key_env=metadata.api_key_env,
            attempts=metadata.attempts,
            validation_status=metadata.validation_status,
            legacy_evaluation=legacy_evaluation,
            candidate_window_start=candidate_window_start,
            candidate_window_end=candidate_window_end,
            input_mode=input_mode,
            original_candidate_count=len(request.articles),
            source_excluded_count=metadata.source_excluded_count,
            summary_max_chars=(
                metadata.summary_max_chars
                if input_mode == PHASE_4_LIVE_INPUT_MODE
                else None
            ),
            summaries_capped_count=(
                metadata.summaries_capped_count
                if input_mode == PHASE_4_LIVE_INPUT_MODE
                else None
            ),
            summaries_unchanged_count=(
                metadata.summaries_unchanged_count
                if input_mode == PHASE_4_LIVE_INPUT_MODE
                else None
            ),
            max_candidate_count=max_candidate_count,
            max_provider_request_body_bytes=max_provider_request_body_bytes,
            curator_request_bytes=metadata.curator_request_bytes,
            provider_request_body_bytes=metadata.provider_request_body_bytes,
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
            failure_diagnostic_code=exc.diagnostic_code,
            failure_diagnostic_path=exc.diagnostic_path,
            failure_diagnostic_article_id=exc.diagnostic_article_id,
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
