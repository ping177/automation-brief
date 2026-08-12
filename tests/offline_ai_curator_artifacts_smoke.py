from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ai_curator import (  # noqa: E402
    CandidateArticle,
    CuratorContractError,
    CuratorRequest,
    CuratorResponse,
    build_curator_request,
    project_curator_request_for_provider,
    validate_curator_response,
)
from ai_curator_artifacts import (  # noqa: E402
    ShadowRunInfo,
    create_run_id,
    write_shadow_run,
)
from ai_curator_provider import serialize_curator_request  # noqa: E402


REPORT_DATE = date(2026, 7, 16)
PUBLISHED_AT = datetime(2026, 7, 15, 23, 30, tzinfo=timezone.utc)


def candidate(article_id: str, title: str) -> CandidateArticle:
    return CandidateArticle(
        article_id=article_id,
        title=title,
        summary="A concise source summary.",
        source="Fixture Source",
        feed_name="Fixture Feed",
        feed_role="breaking_news",
        published_at=PUBLISHED_AT,
        link=f"https://example.com/{article_id}",
        normalized_link=f"https://example.com/{article_id}",
        report_date=REPORT_DATE,
        collected_at=PUBLISHED_AT,
        language="en",
    )


def request() -> CuratorRequest:
    return build_curator_request(
        [
            candidate("article-a", "Selected event title"),
            candidate("article-b", "Rejected promotional title"),
        ],
        REPORT_DATE,
        max_events=2,
    )


def response(request_value: CuratorRequest) -> CuratorResponse:
    payload = {
        "schema_version": "ai_curator_shadow_v1",
        "report_date": REPORT_DATE.isoformat(),
        "events": [
            {
                "event_id": "event-a",
                "canonical_title": "Selected event",
                "summary": "A concise Chinese event summary.",
                "category": "company_industry",
                "importance": "important",
                "why_important": "It is grounded in the candidate evidence.",
                "evidence_article_ids": ["article-a"],
                "novelty": "new_event",
                "confidence": "high",
                "uncertainties": ["Details remain limited."],
            }
        ],
        "rejected_article_ids": [
            {"article_id": "article-b", "reject_reason": "promotional"}
        ],
        "warnings": [],
    }
    return validate_curator_response(payload, request_value)


def success_info(
    *,
    legacy_evaluation: str = "not_evaluated",
    candidate_window_start: datetime | None = None,
    candidate_window_end: datetime | None = None,
    provider_request_body_bytes: int | None = None,
) -> ShadowRunInfo:
    return ShadowRunInfo(
        status="succeeded",
        provider_id="fixture-provider",
        model="fixture-model",
        api_key_env="AUTOMATION_BRIEF_TEST_API_KEY",
        attempts=1,
        validation_status="passed",
        legacy_evaluation=legacy_evaluation,
        candidate_window_start=candidate_window_start,
        candidate_window_end=candidate_window_end,
        provider_request_body_bytes=provider_request_body_bytes,
    )


def test_successful_run_and_allowlists() -> None:
    with TemporaryDirectory(dir="/private/tmp") as temp_dir:
        root = Path(temp_dir) / "shadow"
        request_value = request()
        response_value = response(request_value)
        paths = write_shadow_run(
            root,
            report_date=REPORT_DATE,
            request=request_value,  # type: ignore[arg-type]
            response=response_value,  # type: ignore[arg-type]
            trace_records=[
                {"article_id": "article-a", "title": "Selected event title", "legacy_selected": True},
                {"article_id": "article-b", "title": "Rejected promotional title", "legacy_selected": False},
            ],
            run_info=success_info(),
            run_id="20260812T120000.000000Z-success",
        )
        assert paths.run_dir == root / "20260812T120000.000000Z-success"
        for path in (paths.run_json, paths.request_json, paths.response_json, paths.trace_json, paths.review_md):
            assert path is not None and path.exists()

        run_payload = json.loads(paths.run_json.read_text(encoding="utf-8"))
        assert run_payload["status"] == "succeeded"
        assert run_payload["provider_id"] == "fixture-provider"
        assert run_payload["model"] == "fixture-model"
        assert run_payload["api_key_env"] == "AUTOMATION_BRIEF_TEST_API_KEY"
        assert run_payload["candidate_count"] == 2
        assert run_payload["legacy_selected_count"] == 1
        assert run_payload["ai_event_count"] == 1
        assert run_payload["curator_request_bytes"] == len(paths.request_json.read_bytes())  # type: ignore[union-attr]
        assert run_payload["curator_request_bytes"] == len(serialize_curator_request(request_value))
        assert run_payload["provider_request_body_bytes"] is None
        assert run_payload["legacy_evaluation"] == "not_evaluated"
        assert run_payload["candidate_window_start"] is None
        assert run_payload["candidate_window_end"] is None
        assert "failure_diagnostic" not in run_payload

        request_payload = json.loads(paths.request_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]
        response_payload = json.loads(paths.response_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]
        assert set(request_payload) == {
            "schema_version",
            "report_date",
            "window_start",
            "window_end",
            "target_language",
            "selection_goal",
            "max_events",
            "articles",
        }
        assert set(response_payload) == {
            "schema_version",
            "report_date",
            "events",
            "rejected_article_ids",
            "warnings",
        }
        review = paths.review_md.read_text(encoding="utf-8")
        assert "A concise Chinese event summary." in review
        assert "Rejected promotional title" in review
        assert "promotional" in review
        assert "Candidate count: `2`" in review
        assert f"Curator request bytes: `{len(serialize_curator_request(request_value))}`" in review
        assert "not applicable" in review
        assert "Legacy comparison: `not evaluated`" in review
        assert "Human Review" in review

        all_bytes = b"".join(path.read_bytes() for path in paths.run_dir.iterdir())
        assert b"unit-test-secret" not in all_bytes
        assert b"Authorization" not in all_bytes


def test_invalid_direct_response_cannot_be_persisted_as_success() -> None:
    with TemporaryDirectory(dir="/private/tmp") as temp_dir:
        root = Path(temp_dir) / "shadow"
        request_value = request()
        invalid_response = replace(
            response(request_value),
            events=(replace(response(request_value).events[0], evidence_article_ids=("missing",)),),
        )
        try:
            write_shadow_run(
                root,
                report_date=REPORT_DATE,
                request=request_value,
                response=invalid_response,
                trace_records=[],
                run_info=success_info(),
                run_id="invalid-response",
            )
        except CuratorContractError:
            pass
        else:
            raise AssertionError("invalid response must fail before success persistence")
        assert not (root / "invalid-response").exists()


def test_report_date_mismatch_cannot_be_persisted_as_success() -> None:
    with TemporaryDirectory(dir="/private/tmp") as temp_dir:
        root = Path(temp_dir) / "shadow"
        request_value = request()
        mismatched_response = replace(response(request_value), report_date=date(2026, 7, 17))
        try:
            write_shadow_run(
                root,
                report_date=REPORT_DATE,
                request=request_value,
                response=mismatched_response,
                trace_records=[],
                run_info=success_info(),
                run_id="report-date-mismatch",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("report-date mismatch must fail before success persistence")
        assert not (root / "report-date-mismatch").exists()


def test_write_failure_does_not_publish_partial_final_directory() -> None:
    with TemporaryDirectory(dir="/private/tmp") as temp_dir:
        root = Path(temp_dir) / "shadow"
        request_value = request()
        response_value = response(request_value)
        original_write_json = __import__("ai_curator_artifacts")._write_json
        call_count = 0

        def fail_during_staging(path: Path, payload: object) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise OSError("simulated artifact write failure")
            original_write_json(path, payload)

        with patch("ai_curator_artifacts._write_json", side_effect=fail_during_staging):
            try:
                write_shadow_run(
                    root,
                    report_date=REPORT_DATE,
                    request=request_value,
                    response=response_value,
                    trace_records=[],
                    run_info=success_info(),
                    run_id="atomic-failure",
                )
            except OSError:
                pass
            else:
                raise AssertionError("injected artifact I/O failure must propagate")

        assert not (root / "atomic-failure").exists()
        assert not any(path.name.startswith(".atomic-failure.tmp-") for path in root.iterdir())


def test_same_day_runs_do_not_overwrite() -> None:
    with TemporaryDirectory(dir="/private/tmp") as temp_dir:
        root = Path(temp_dir) / "shadow"
        request_value = request()
        response_value = response(request_value)
        first = write_shadow_run(
            root,
            report_date=REPORT_DATE,
            request=request_value,  # type: ignore[arg-type]
            response=response_value,  # type: ignore[arg-type]
            trace_records=[],
            run_info=success_info(),
            now=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc),
        )
        second = write_shadow_run(
            root,
            report_date=REPORT_DATE,
            request=request_value,  # type: ignore[arg-type]
            response=response_value,  # type: ignore[arg-type]
            trace_records=[],
            run_info=success_info(),
            now=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc),
        )
        assert first.run_dir != second.run_dir
        assert first.run_dir.exists()
        assert second.run_dir.exists()


def test_review_escapes_model_markdown_and_html() -> None:
    with TemporaryDirectory(dir="/private/tmp") as temp_dir:
        root = Path(temp_dir) / "shadow"
        request_value = request()
        base_response = response(request_value)
        unsafe_event = replace(
            base_response.events[0],
            canonical_title="# [click](javascript:alert(1)) <img src=x onerror=alert(1)>",
            summary="![x](https://evil.example) <script>alert(1)</script> **bold**",
            why_important="`raw` [link](javascript:alert(1))",
            uncertainties=("<iframe src=evil></iframe>",),
        )
        unsafe_response = replace(base_response, events=(unsafe_event,))
        paths = write_shadow_run(
            root,
            report_date=REPORT_DATE,
            request=request_value,
            response=unsafe_response,
            trace_records=[],
            run_info=success_info(),
            run_id="escaped-review",
        )
        review = paths.review_md.read_text(encoding="utf-8")
        assert "<script" not in review
        assert "<img" not in review
        assert "<iframe" not in review
        assert "![x](" not in review
        assert "[link](javascript:" not in review
        assert "alert\\(1\\)" in review


def test_legacy_labels_and_fetch_failure_trace_are_explicit_and_allowlisted() -> None:
    with TemporaryDirectory(dir="/private/tmp") as temp_dir:
        root = Path(temp_dir) / "shadow"
        request_value = request()
        response_value = response(request_value)
        live_paths = write_shadow_run(
            root,
            report_date=REPORT_DATE,
            request=request_value,
            response=response_value,
            trace_records=[
                {
                    "trace_type": "fetch_failures",
                    "candidate_failures": [
                        ("Fixture Feed", "timeout while contacting https://secret.example/token")
                    ],
                }
            ],
            run_info=success_info(
                legacy_evaluation="keyword_gate_approximation",
                candidate_window_start=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc),
                candidate_window_end=datetime(2026, 8, 12, 12, 1, tzinfo=timezone.utc),
                provider_request_body_bytes=2346,
            ),
            run_id="live-approximation",
        )
        trace_payload = json.loads(live_paths.trace_json.read_text(encoding="utf-8"))
        assert trace_payload == [
            {
                "trace_type": "fetch_failures",
                "candidate_failures": [
                    {"feed_name": "Fixture Feed", "failure_code": "timeout"}
                ],
            }
        ]
        assert "secret.example" not in live_paths.trace_json.read_text(encoding="utf-8")
        assert "Legacy comparison: `keyword-gate approximation`" in live_paths.review_md.read_text(encoding="utf-8")
        assert "not the final production digest selection" in live_paths.review_md.read_text(encoding="utf-8")
        assert "Candidate collection window:" in live_paths.review_md.read_text(encoding="utf-8")
        run_payload = json.loads(live_paths.run_json.read_text(encoding="utf-8"))
        assert run_payload["provider_request_body_bytes"] == 2346
        assert run_payload["candidate_window_start"] == "2026-08-12T12:00:00+00:00"


def test_unknown_trace_type_fails_closed() -> None:
    with TemporaryDirectory(dir="/private/tmp") as temp_dir:
        root = Path(temp_dir) / "shadow"
        try:
            write_shadow_run(
                root,
                report_date=REPORT_DATE,
                request=request(),
                response=response(request()),
                trace_records=[{"trace_type": "future_unreviewed_trace", "secret": "value"}],
                run_info=success_info(),
                run_id="unknown-trace",
            )
        except ValueError as exc:
            assert "trace_type" in str(exc)
        else:
            raise AssertionError("unknown trace type must not be silently discarded")
        assert not (root / "unknown-trace").exists()


def test_phase4_artifact_records_policy_and_projected_request() -> None:
    with TemporaryDirectory(dir="/private/tmp") as temp_dir:
        root = Path(temp_dir) / "shadow"
        original_request = request()
        long_article = replace(original_request.articles[0], summary="x" * 600)
        original_request = replace(
            original_request,
            articles=(long_article, original_request.articles[1]),
        )
        projected_request = project_curator_request_for_provider(original_request)
        response_value = response(projected_request)
        paths = write_shadow_run(
            root,
            report_date=REPORT_DATE,
            request=projected_request,
            response=response_value,
            trace_records=[],
            run_info=ShadowRunInfo(
                status="succeeded",
                provider_id="deepseek",
                model="deepseek-v4-flash",
                api_key_env="AUTOMATION_BRIEF_CURATOR_API_KEY",
                attempts=1,
                validation_status="passed",
                input_mode="phase4_live",
                original_candidate_count=2,
                summary_max_chars=500,
                summaries_capped_count=1,
                summaries_unchanged_count=1,
                max_candidate_count=200,
                max_provider_request_body_bytes=200000,
                curator_request_bytes=len(serialize_curator_request(projected_request)),
                provider_request_body_bytes=138631,
            ),
            run_id="phase4-projected",
        )
        run_payload = json.loads(paths.run_json.read_text(encoding="utf-8"))
        assert run_payload["input_mode"] == "phase4_live"
        assert run_payload["original_candidate_count"] == 2
        assert run_payload["summary_max_chars"] == 500
        assert run_payload["summaries_capped_count"] == 1
        assert run_payload["summaries_unchanged_count"] == 1
        assert run_payload["max_candidate_count"] == 200
        assert run_payload["max_provider_request_body_bytes"] == 200000
        request_payload = json.loads(paths.request_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]
        assert request_payload["articles"][0]["summary"] == "x" * 500
        assert "Input mode: `phase4_live`" in paths.review_md.read_text(encoding="utf-8")


def test_failed_run_has_no_response_artifact() -> None:
    with TemporaryDirectory(dir="/private/tmp") as temp_dir:
        root = Path(temp_dir) / "shadow"
        paths = write_shadow_run(
            root,
            report_date=REPORT_DATE,
            request=request(),  # type: ignore[arg-type]
            response=None,
            trace_records=[{"article_id": "article-a", "legacy_selected": True}],
            run_info=ShadowRunInfo(
                status="failed",
                provider_id="fixture-provider",
                model="fixture-model",
                api_key_env="AUTOMATION_BRIEF_TEST_API_KEY",
                attempts=2,
                validation_status="not_run",
                failure_stage="provider",
                failure_code="timeout",
                failure_diagnostic_code="unknown_evidence_article_id",
                failure_diagnostic_path="events.evidence_article_ids",
                failure_diagnostic_article_id="raw-model-response-secret",
            ),
            run_id=create_run_id(datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)),
        )
        assert paths.run_json.exists()
        assert paths.request_json is not None and paths.request_json.exists()
        assert paths.trace_json is not None and paths.trace_json.exists()
        assert paths.response_json is None
        run_payload = json.loads(paths.run_json.read_text(encoding="utf-8"))
        assert run_payload["status"] == "failed"
        assert run_payload["failure_stage"] == "provider"
        assert run_payload["failure_code"] == "timeout"
        assert run_payload["failure_diagnostic"] == {
            "code": "unknown_evidence_article_id",
            "path": "events.evidence_article_ids",
        }
        review = paths.review_md.read_text(encoding="utf-8")
        assert "timeout" in review
        assert "Failure diagnostic: code=`unknown_evidence_article_id`; path=`events.evidence_article_ids`" in review
        all_bytes = b"".join(path.read_bytes() for path in paths.run_dir.iterdir())
        assert b"raw-model-response-secret" not in all_bytes

        policy_paths = write_shadow_run(
            root,
            report_date=REPORT_DATE,
            request=request(),
            response=None,
            trace_records=[{"article_id": "article-a", "legacy_selected": True}],
            run_info=ShadowRunInfo(
                status="failed",
                provider_id="fixture-provider",
                model="fixture-model",
                api_key_env="AUTOMATION_BRIEF_TEST_API_KEY",
                attempts=1,
                validation_status="failed",
                failure_stage="content_policy",
                failure_code="content_policy_violation",
                failure_diagnostic_code="direct_trading_advice",
                failure_diagnostic_path="reader_facing_text",
            ),
            run_id="content-policy-failure",
        )
        policy_payload = json.loads(policy_paths.run_json.read_text(encoding="utf-8"))
        assert policy_payload["failure_diagnostic"] == {
            "code": "direct_trading_advice",
            "path": "reader_facing_text",
        }
        assert "response.json" not in {path.name for path in policy_paths.run_dir.iterdir()}


def main() -> None:
    test_successful_run_and_allowlists()
    test_invalid_direct_response_cannot_be_persisted_as_success()
    test_report_date_mismatch_cannot_be_persisted_as_success()
    test_write_failure_does_not_publish_partial_final_directory()
    test_same_day_runs_do_not_overwrite()
    test_review_escapes_model_markdown_and_html()
    test_legacy_labels_and_fetch_failure_trace_are_explicit_and_allowlisted()
    test_unknown_trace_type_fails_closed()
    test_phase4_artifact_records_policy_and_projected_request()
    test_failed_run_has_no_response_artifact()
    print("offline ai curator artifacts smoke passed")


if __name__ == "__main__":
    main()
