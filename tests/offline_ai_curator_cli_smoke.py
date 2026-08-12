from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def run_shadow_cli(
    candidate_path: Path,
    response_path: Path,
    output_dir: Path | None,
    data_root: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{PROJECT_ROOT / '.venv' / 'bin'}:{env.get('PATH', '')}"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CODEX_SANDBOX_NETWORK_DISABLED"] = "1"
    output_base = output_dir or data_root / "default-shadow-output"
    args = [
        "python3",
        str(PROJECT_ROOT / "scripts" / "run_ai_curator_shadow.py"),
        "--candidate-fixture",
        str(candidate_path),
        "--fixture-response",
        str(response_path),
        "--data-root",
        str(data_root),
        "--feeds",
        str(output_base.parent / "missing-feeds.json"),
        "--keywords",
        str(output_base.parent / "missing-keywords.json"),
        "--config",
        str(output_base.parent / "missing-config.json"),
    ]
    if output_dir is not None:
        args.extend(["--output-dir", str(output_dir)])
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
