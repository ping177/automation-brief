from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from ai_curator import build_curator_request, load_candidate_fixture  # noqa: E402
from ai_curator_provider import (  # noqa: E402
    DEEPSEEK_PROVIDER_CONFIG,
    serialize_curator_request,
    serialize_deepseek_request,
)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def run_shadow_cli(
    candidate_path: Path | None,
    response_path: Path,
    output_dir: Path | None,
    data_root: Path,
    *,
    extra_args: list[str] | None = None,
    include_fixture_response: bool = True,
    env_updates: dict[str, str | None] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": f"{PROJECT_ROOT / '.venv' / 'bin'}:{os.defpath}",
        "PYTHONDONTWRITEBYTECODE": "1",
        "CODEX_SANDBOX_NETWORK_DISABLED": "1",
    }
    for name, value in (env_updates or {}).items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    output_base = output_dir or data_root / "default-shadow-output"
    args = [
        "python3",
        str(PROJECT_ROOT / "scripts" / "run_ai_curator_shadow.py"),
        "--data-root",
        str(data_root),
        "--feeds",
        str(output_base.parent / "missing-feeds.json"),
        "--keywords",
        str(output_base.parent / "missing-keywords.json"),
        "--config",
        str(output_base.parent / "missing-config.json"),
    ]
    if candidate_path is not None:
        args.extend(["--candidate-fixture", str(candidate_path)])
    if include_fixture_response:
        args.extend(["--fixture-response", str(response_path)])
    if output_dir is not None:
        args.extend(["--output-dir", str(output_dir)])
    args.extend(extra_args or [])
    return subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def valid_candidate_fixture() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "report_date": "2026-07-16",
        "articles": [
            {
                "title": "Fixture central banks coordinate liquidity support",
                "summary": "Central banks announced a coordinated backstop.",
                "source": "Fixture Source",
                "feed_name": "Fixture Feed",
                "feed_role": "breaking_news",
                "published_at": "2026-07-15T23:30:00+08:00",
                "link": "https://example.com/liquidity?utm_source=rss",
                "normalized_link": "https://example.com/liquidity",
                "report_date": "2026-07-16",
                "extra_note": "unknown non-sensitive fields are ignored",
            },
            {
                "title": "Fixture linkless emergency policy statement",
                "summary": "Policy makers issued a linkless but timestamped statement.",
                "source": "Fixture Source",
                "feed_name": "Fixture Feed",
                "feed_role": "breaking_news",
                "published_at": "2026-07-15T21:10:00+08:00",
                "link": "",
                "normalized_link": "",
                "report_date": "2026-07-16",
            },
        ],
    }


def valid_response_fixture() -> dict[str, object]:
    return {
        "schema_version": "ai_curator_shadow_v1",
        "report_date": "2026-07-16",
        "events": [
            {
                "event_id": "event-fixture",
                "canonical_title": "Fixture central banks coordinate liquidity support",
                "summary": "The fixture event was selected from local candidates.",
                "category": "macro_policy",
                "importance": "must_know",
                "why_important": "It validates the fully offline shadow path.",
                "evidence_article_ids": ["art_eec319deefbbcfb4279c0704"],
                "novelty": "new_event",
                "confidence": "high",
                "uncertainties": [],
            }
        ],
        "rejected_article_ids": [],
        "warnings": [],
    }


def run_dirs(root: Path) -> list[Path]:
    return sorted(path for path in root.iterdir() if path.is_dir()) if root.exists() else []


def main() -> None:
    with TemporaryDirectory(dir="/private/tmp") as temp_dir:
        temp_path = Path(temp_dir)
        candidate_path = temp_path / "candidates.json"
        response_path = temp_path / "response.json"
        output_dir = temp_path / "shadow-output"
        data_root = temp_path / "data-root"
        write_json(candidate_path, valid_candidate_fixture())
        write_json(response_path, valid_response_fixture())

        result = run_shadow_cli(candidate_path, response_path, output_dir, data_root)
        assert result.returncode == 0, result.stderr

        run_dir = run_dirs(output_dir)[0]
        preview_path = run_dir / "review.md"
        request_path = run_dir / "request.json"
        trace_path = run_dir / "trace.json"
        response_artifact_path = run_dir / "response.json"
        assert (run_dir / "run.json").exists()
        assert preview_path.exists()
        assert request_path.exists()
        assert trace_path.exists()
        assert response_artifact_path.exists()
        run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        assert run_payload["provider_request_body_bytes"] is None
        assert run_payload["legacy_evaluation"] == "not_evaluated"
        assert run_payload["candidate_window_start"] is None
        assert run_payload["candidate_window_end"] is None

        preview = preview_path.read_text(encoding="utf-8")
        assert "Fixture central banks coordinate liquidity support" in preview
        assert "Fixture Source" in preview
        assert "Legacy comparison: `not evaluated`" in preview
        assert "Candidate collection window: `not applicable`" in preview

        request_payload = json.loads(request_path.read_text(encoding="utf-8"))
        request_text = json.dumps(request_payload, ensure_ascii=False)
        for forbidden in ("legacy_score", "legacy_category", "matched_keywords", "holdings", "成本", "仓位", "盈亏", "API key"):
            assert forbidden not in request_text
        assert len(request_payload["articles"]) == 2
        assert any(article["link"] == "" for article in request_payload["articles"])
        assert request_payload["target_language"] == "zh-CN"
        assert all(article["language"] == "und" for article in request_payload["articles"])

        trace_payload = json.loads(trace_path.read_text(encoding="utf-8"))
        assert any(record["title"] == "Fixture linkless emergency policy statement" for record in trace_payload)

        default_result = run_shadow_cli(candidate_path, response_path, None, data_root)
        assert default_result.returncode == 0, default_result.stderr
        default_shadow_dir = data_root / "runs" / "ai-curator-shadow"
        assert len(run_dirs(default_shadow_dir)) == 1
        assert (run_dirs(default_shadow_dir)[0] / "review.md").exists()
        assert not (PROJECT_ROOT / "output" / "ai-curator-shadow").exists()

        fixture_with_key_output = temp_path / "fixture-with-key-output"
        fixture_with_key_result = run_shadow_cli(
            candidate_path,
            response_path,
            fixture_with_key_output,
            data_root,
            env_updates={"AUTOMATION_BRIEF_CURATOR_API_KEY": "fake-key-must-not-trigger-real-call"},
        )
        assert fixture_with_key_result.returncode == 0, fixture_with_key_result.stderr
        fixture_with_key_run = run_dirs(fixture_with_key_output)[0]
        fixture_with_key_payload = json.loads((fixture_with_key_run / "run.json").read_text(encoding="utf-8"))
        assert fixture_with_key_payload["provider_id"] == "fixture"
        for artifact_path in fixture_with_key_run.iterdir():
            assert "fake-key-must-not-trigger-real-call" not in artifact_path.read_text(encoding="utf-8")
        assert "fake-key-must-not-trigger-real-call" not in fixture_with_key_result.stdout
        assert "fake-key-must-not-trigger-real-call" not in fixture_with_key_result.stderr

        dry_run_result = run_shadow_cli(
            candidate_path,
            response_path,
            temp_path / "dry-run-output",
            data_root,
            include_fixture_response=False,
            extra_args=["--real-provider", "deepseek", "--dry-run"],
            env_updates={"AUTOMATION_BRIEF_CURATOR_API_KEY": None},
        )
        assert dry_run_result.returncode == 0, dry_run_result.stderr
        dry_run_summary = json.loads(dry_run_result.stdout)
        assert dry_run_summary["mode"] == "dry_run"
        assert dry_run_summary["provider_id"] == "deepseek"
        assert dry_run_summary["model"] == "deepseek-v4-flash"
        assert dry_run_summary["endpoint"] == "https://api.deepseek.com/chat/completions"
        assert dry_run_summary["candidate_count"] == 2
        assert dry_run_summary["max_tokens"] == 8192
        assert dry_run_summary["timeout"] == 90.0
        assert dry_run_summary["max_attempts"] == 2
        assert dry_run_summary["thinking_mode"] == "disabled"
        assert dry_run_summary["json_mode"] is True
        assert dry_run_summary["target_language"] == "zh-CN"
        assert dry_run_summary["transport_calls"] == 0
        assert dry_run_summary["max_candidate_count"] == 2
        assert dry_run_summary["max_provider_request_body_bytes"] == 4096
        assert dry_run_summary["candidate_count"] <= dry_run_summary["max_candidate_count"]
        assert dry_run_summary["provider_request_body_bytes"] <= dry_run_summary["max_provider_request_body_bytes"]
        assert dry_run_summary["provider_request_body_bytes"] > dry_run_summary["curator_request_bytes"]
        assert not run_dirs(temp_path / "dry-run-output")
        assert "AUTOMATION_BRIEF_CURATOR_API_KEY" not in dry_run_result.stdout
        assert "fake-key" not in dry_run_result.stdout

        fixture_report_date, fixture_candidates = load_candidate_fixture(candidate_path)
        fixture_request = build_curator_request(fixture_candidates, fixture_report_date, max_events=5)
        assert dry_run_summary["curator_request_bytes"] == len(serialize_curator_request(fixture_request))
        assert dry_run_summary["provider_request_body_bytes"] == len(
            serialize_deepseek_request(fixture_request, DEEPSEEK_PROVIDER_CONFIG)
        )

        too_many_candidate_path = temp_path / "too-many-candidates.json"
        too_many_payload = valid_candidate_fixture()
        too_many_payload["articles"].append(  # type: ignore[index]
            {
                "title": "Fixture third candidate",
                "summary": "A third candidate must fail closed.",
                "source": "Fixture Source",
                "feed_name": "Fixture Feed",
                "feed_role": "breaking_news",
                "published_at": "2026-07-15T20:00:00+08:00",
                "link": "https://example.com/third-candidate",
                "normalized_link": "https://example.com/third-candidate",
                "report_date": "2026-07-16",
            }
        )
        write_json(too_many_candidate_path, too_many_payload)
        too_many_dry_run = run_shadow_cli(
            too_many_candidate_path,
            response_path,
            temp_path / "too-many-dry-run-output",
            data_root,
            include_fixture_response=False,
            extra_args=["--real-provider", "deepseek", "--dry-run"],
            env_updates={"AUTOMATION_BRIEF_CURATOR_API_KEY": None},
        )
        assert too_many_dry_run.returncode != 0
        assert "candidate_count_limit" in too_many_dry_run.stderr
        assert not run_dirs(temp_path / "too-many-dry-run-output")

        oversized_candidate_path = temp_path / "oversized-candidate.json"
        oversized_payload = valid_candidate_fixture()
        oversized_payload["articles"][0]["summary"] = "x" * 5000  # type: ignore[index]
        write_json(oversized_candidate_path, oversized_payload)
        oversized_dry_run = run_shadow_cli(
            oversized_candidate_path,
            response_path,
            temp_path / "oversized-dry-run-output",
            data_root,
            include_fixture_response=False,
            extra_args=["--real-provider", "deepseek", "--dry-run"],
            env_updates={"AUTOMATION_BRIEF_CURATOR_API_KEY": None},
        )
        assert oversized_dry_run.returncode != 0
        assert "provider_request_body_limit" in oversized_dry_run.stderr
        assert not run_dirs(temp_path / "oversized-dry-run-output")

        real_provider_output = temp_path / "real-provider-output"
        real_provider_result = run_shadow_cli(
            candidate_path,
            response_path,
            real_provider_output,
            data_root,
            include_fixture_response=False,
            extra_args=["--real-provider", "deepseek"],
            env_updates={"AUTOMATION_BRIEF_CURATOR_API_KEY": None},
        )
        assert real_provider_result.returncode != 0
        real_provider_run = run_dirs(real_provider_output)[0]
        real_provider_payload = json.loads((real_provider_run / "run.json").read_text(encoding="utf-8"))
        assert real_provider_payload["provider_id"] == "deepseek"
        assert real_provider_payload["failure_code"] == "missing_api_key"
        assert real_provider_payload["attempts"] == 0
        assert real_provider_payload["provider_request_body_bytes"] <= 4096
        assert not (real_provider_run / "response.json").exists()

        too_many_real_output = temp_path / "too-many-real-output"
        too_many_real_result = run_shadow_cli(
            too_many_candidate_path,
            response_path,
            too_many_real_output,
            data_root,
            include_fixture_response=False,
            extra_args=["--real-provider", "deepseek"],
            env_updates={"AUTOMATION_BRIEF_CURATOR_API_KEY": None},
        )
        assert too_many_real_result.returncode != 0
        too_many_real_run = run_dirs(too_many_real_output)[0]
        too_many_real_payload = json.loads((too_many_real_run / "run.json").read_text(encoding="utf-8"))
        assert too_many_real_payload["failure_code"] == "candidate_count_limit"
        assert too_many_real_payload["attempts"] == 0
        assert not (too_many_real_run / "response.json").exists()

        real_without_fixture = run_shadow_cli(
            None,
            response_path,
            temp_path / "real-without-fixture-output",
            data_root,
            include_fixture_response=False,
            extra_args=["--real-provider", "deepseek"],
            env_updates={"AUTOMATION_BRIEF_CURATOR_API_KEY": None},
        )
        assert real_without_fixture.returncode != 0
        assert "--candidate-fixture" in real_without_fixture.stderr
        assert not run_dirs(temp_path / "real-without-fixture-output")

        unknown_provider_result = run_shadow_cli(
            candidate_path,
            response_path,
            temp_path / "unknown-provider-output",
            data_root,
            include_fixture_response=False,
            extra_args=["--real-provider", "unknown"],
            env_updates={"AUTOMATION_BRIEF_CURATOR_API_KEY": None},
        )
        assert unknown_provider_result.returncode != 0
        assert "invalid choice" in unknown_provider_result.stderr
        assert not run_dirs(temp_path / "unknown-provider-output")

        invalid_response_path = temp_path / "invalid-response.json"
        invalid_response = valid_response_fixture()
        invalid_response["events"][0]["evidence_article_ids"] = ["missing"]  # type: ignore[index]
        write_json(invalid_response_path, invalid_response)
        failed_output = temp_path / "failed-output"
        failed_result = run_shadow_cli(candidate_path, invalid_response_path, failed_output, data_root)
        assert failed_result.returncode != 0
        failed_run_dir = run_dirs(failed_output)[0]
        failed_run_payload = json.loads((failed_run_dir / "run.json").read_text(encoding="utf-8"))
        assert failed_run_payload["status"] == "failed"
        assert failed_run_payload["failure_code"] == "invalid_curator_response"
        assert failed_run_payload["failure_diagnostic"] == {
            "code": "unknown_evidence_article_id",
            "path": "events.evidence_article_ids",
        }
        assert "Failure diagnostic: code=`unknown_evidence_article_id`" in (
            failed_run_dir / "review.md"
        ).read_text(encoding="utf-8")
        assert (failed_run_dir / "request.json").exists()
        assert (failed_run_dir / "trace.json").exists()
        assert not (failed_run_dir / "response.json").exists()

        bad_candidate_path = temp_path / "bad-candidates.json"
        bad_candidate_path.write_text("{not json", encoding="utf-8")
        bad_result = run_shadow_cli(bad_candidate_path, response_path, temp_path / "bad-output", data_root)
        assert bad_result.returncode != 0
        assert "candidate fixture" in bad_result.stderr.lower()

        forbidden_candidate_path = temp_path / "forbidden-candidates.json"
        forbidden_payload = valid_candidate_fixture()
        forbidden_payload["articles"][0]["matched_keywords"] = {"forbidden": ["field"]}  # type: ignore[index]
        write_json(forbidden_candidate_path, forbidden_payload)
        forbidden_result = run_shadow_cli(
            forbidden_candidate_path,
            response_path,
            temp_path / "forbidden-output",
            data_root,
        )
        assert forbidden_result.returncode != 0
        assert "forbidden fields" in forbidden_result.stderr.lower()

        missing_result = run_shadow_cli(
            temp_path / "missing-candidates.json",
            response_path,
            temp_path / "missing-output",
            data_root,
        )
        assert missing_result.returncode != 0
        assert "candidate fixture" in missing_result.stderr.lower()

    print("offline ai curator cli smoke passed")


if __name__ == "__main__":
    main()
