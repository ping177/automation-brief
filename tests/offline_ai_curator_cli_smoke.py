from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def run_shadow_cli(candidate_path: Path, response_path: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{PROJECT_ROOT / '.venv' / 'bin'}:{env.get('PATH', '')}"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CODEX_SANDBOX_NETWORK_DISABLED"] = "1"
    return subprocess.run(
        [
            "python3",
            str(PROJECT_ROOT / "scripts" / "run_ai_curator_shadow.py"),
            "--candidate-fixture",
            str(candidate_path),
            "--fixture-response",
            str(response_path),
            "--output-dir",
            str(output_dir),
            "--feeds",
            str(output_dir.parent / "missing-feeds.json"),
            "--keywords",
            str(output_dir.parent / "missing-keywords.json"),
            "--config",
            str(output_dir.parent / "missing-config.json"),
        ],
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


def main() -> None:
    with TemporaryDirectory(dir="/private/tmp") as temp_dir:
        temp_path = Path(temp_dir)
        candidate_path = temp_path / "candidates.json"
        response_path = temp_path / "response.json"
        output_dir = temp_path / "shadow-output"
        write_json(candidate_path, valid_candidate_fixture())
        write_json(response_path, valid_response_fixture())

        result = run_shadow_cli(candidate_path, response_path, output_dir)
        assert result.returncode == 0, result.stderr

        preview_path = output_dir / "ai-curator-shadow-2026-07-16.md"
        request_path = output_dir / "ai-curator-shadow-request-2026-07-16.json"
        trace_path = output_dir / "ai-curator-shadow-trace-2026-07-16.json"
        assert preview_path.exists()
        assert request_path.exists()
        assert trace_path.exists()

        preview = preview_path.read_text(encoding="utf-8")
        assert "Fixture central banks coordinate liquidity support" in preview
        assert "Fixture Source" in preview

        request_payload = json.loads(request_path.read_text(encoding="utf-8"))
        request_text = json.dumps(request_payload, ensure_ascii=False)
        for forbidden in ("legacy_score", "legacy_category", "matched_keywords", "holdings", "成本", "仓位", "盈亏", "API key"):
            assert forbidden not in request_text
        assert len(request_payload["articles"]) == 2
        assert any(article["link"] == "" for article in request_payload["articles"])

        trace_payload = json.loads(trace_path.read_text(encoding="utf-8"))
        assert any(record["title"] == "Fixture linkless emergency policy statement" for record in trace_payload)

        bad_candidate_path = temp_path / "bad-candidates.json"
        bad_candidate_path.write_text("{not json", encoding="utf-8")
        bad_result = run_shadow_cli(bad_candidate_path, response_path, temp_path / "bad-output")
        assert bad_result.returncode != 0
        assert "candidate fixture" in bad_result.stderr.lower()

        forbidden_candidate_path = temp_path / "forbidden-candidates.json"
        forbidden_payload = valid_candidate_fixture()
        forbidden_payload["articles"][0]["matched_keywords"] = {"forbidden": ["field"]}  # type: ignore[index]
        write_json(forbidden_candidate_path, forbidden_payload)
        forbidden_result = run_shadow_cli(forbidden_candidate_path, response_path, temp_path / "forbidden-output")
        assert forbidden_result.returncode != 0
        assert "forbidden fields" in forbidden_result.stderr.lower()

        missing_result = run_shadow_cli(temp_path / "missing-candidates.json", response_path, temp_path / "missing-output")
        assert missing_result.returncode != 0
        assert "candidate fixture" in missing_result.stderr.lower()

    print("offline ai curator cli smoke passed")


if __name__ == "__main__":
    main()
