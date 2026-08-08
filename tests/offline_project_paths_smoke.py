from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_SCRIPT = PROJECT_ROOT / "main.py"
sys.path.insert(0, str(PROJECT_ROOT))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def holdings_payload() -> dict[str, object]:
    return {
        "holdings": [
            {
                "code": "FIXTURE001",
                "name": "Fixture holding",
                "market": "fixture",
                "sector": "fixture-sector",
                "watch_tags": ["fixture"],
                "notes": "offline smoke only",
            }
        ]
    }


def run_main(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["AUTOMATION_BRIEF_OFFLINE_MARKET_DATA"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CODEX_SANDBOX_NETWORK_DISABLED"] = "1"
    return subprocess.run(
        [sys.executable, str(MAIN_SCRIPT), *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_resolver_precedence() -> None:
    from project_paths import DATA_ROOT_ENV, get_project_paths

    repo_root = Path("/tmp/automation-brief-fixture-repo")
    environment_root = Path("/tmp/automation-brief-env-root")
    explicit_root = Path("/tmp/automation-brief-explicit-root")
    with patch.dict(os.environ, {DATA_ROOT_ENV: str(environment_root)}, clear=False):
        assert get_project_paths(repo_root=repo_root).data_root == environment_root
        assert get_project_paths(repo_root=repo_root, data_root=explicit_root).data_root == explicit_root

    with patch.dict(os.environ, {}, clear=True):
        default_paths = get_project_paths(repo_root=repo_root)
    assert default_paths.data_root == Path.home() / "Projects" / "_project-data" / "automation-brief"
    assert default_paths.resolve_report_dir("output") == default_paths.reports_dir
    assert default_paths.resolve_report_dir("output", explicit_output=Path("/tmp/explicit-reports")) == Path(
        "/tmp/explicit-reports"
    )
    assert default_paths.ai_curator_shadow_dir == default_paths.data_root / "runs" / "ai-curator-shadow"
    assert default_paths.log_file == default_paths.data_root / "runs" / "daily-news.log"


def test_holdings_source_precedence(fixture_dir: Path) -> None:
    from holdings import load_holdings
    from project_paths import ProjectPaths

    repo_root = fixture_dir / "repo"
    data_root = fixture_dir / "data-root"
    paths = ProjectPaths(repo_root=repo_root, data_root=data_root)
    example_path = paths.example_holdings_file
    canonical_path = paths.holdings_file
    explicit_path = fixture_dir / "explicit-holdings.json"
    write_json(example_path, holdings_payload())

    example_result = load_holdings(paths=paths)
    assert example_result.used_example is True
    assert example_result.source_path == example_path

    write_json(canonical_path, {"holdings": []})
    canonical_result = load_holdings(paths=paths)
    assert canonical_result.used_example is False
    assert canonical_result.source_path == canonical_path
    assert canonical_result.holdings == ()

    canonical_path.unlink()
    example_path.unlink()
    empty_result = load_holdings(paths=paths)
    assert empty_result.source_path is None
    assert empty_result.holdings == ()

    write_json(explicit_path, holdings_payload())
    explicit_result = load_holdings(path=explicit_path, paths=paths)
    assert explicit_result.source_path == explicit_path
    assert explicit_result.used_example is False


def test_canonical_outputs_and_downstream_readers(fixture_dir: Path) -> None:
    from project_paths import get_project_paths
    import scripts.publish_mobile_digest as publish_mobile_digest
    import scripts.send_bark_notification as send_bark_notification

    data_root = fixture_dir / "data-root"
    paths = get_project_paths(repo_root=PROJECT_ROOT, data_root=data_root)
    feeds_path = fixture_dir / "feeds.json"
    keywords_path = fixture_dir / "keywords.json"
    holdings_path = fixture_dir / "holdings.json"
    write_json(feeds_path, [])
    write_json(keywords_path, {})
    write_json(holdings_path, {"holdings": []})
    daily_date = date.today().isoformat()
    legacy_daily_report = PROJECT_ROOT / "output" / f"daily-news-{daily_date}.md"
    legacy_daily_stat = legacy_daily_report.stat() if legacy_daily_report.exists() else None

    daily_result = run_main(
        [
            "--config",
            str(fixture_dir / "missing-config.json"),
            "--feeds",
            str(feeds_path),
            "--keywords",
            str(keywords_path),
            "--report-type",
            "digest",
            "--data-root",
            str(data_root),
            "--date",
            daily_date,
        ],
    )
    assert daily_result.returncode == 0, daily_result.stdout + daily_result.stderr
    daily_report = paths.reports_dir / f"daily-news-{daily_date}.md"
    assert daily_report.exists()

    market_result = run_main(
        [
            "--config",
            str(fixture_dir / "missing-config.json"),
            "--feeds",
            str(feeds_path),
            "--keywords",
            str(keywords_path),
            "--report-type",
            "market_brief",
            "--data-root",
            str(data_root),
            "--holdings",
            str(holdings_path),
            "--date",
            daily_date,
        ],
    )
    assert market_result.returncode == 0, market_result.stdout + market_result.stderr
    assert (paths.reports_dir / f"market-brief-{daily_date}.md").exists()
    assert paths.log_file.exists()
    if legacy_daily_stat is None:
        assert not legacy_daily_report.exists()
    else:
        current_stat = legacy_daily_report.stat()
        assert (current_stat.st_size, current_stat.st_mtime_ns) == (
            legacy_daily_stat.st_size,
            legacy_daily_stat.st_mtime_ns,
        )

    mobile_target = fixture_dir / "mobile"
    env_file = fixture_dir / "test.env"
    env_file.write_text(f"MOBILE_DIGEST_DIR={mobile_target}\n", encoding="utf-8")
    assert publish_mobile_digest.main(data_root=data_root, env_file=env_file) == 0
    assert (mobile_target / daily_report.name).read_text(encoding="utf-8") == daily_report.read_text(
        encoding="utf-8"
    )

    bark_env_file = fixture_dir / "bark.env"
    bark_env_file.write_text("BARK_URL=https://example.invalid/device\n", encoding="utf-8")
    sent: list[tuple[str, str, str, str]] = []

    def fake_send_notification(bark_url: str, title: str, body: str, url: str = "") -> None:
        sent.append((bark_url, title, body, url))

    with patch.object(send_bark_notification, "send_notification", fake_send_notification):
        assert send_bark_notification.main(data_root=data_root, env_file=bark_env_file) == 0
    assert sent
    assert sent[0][0] == "https://example.invalid/device"
    assert f"reports/{daily_report.name}" in sent[0][2]
    assert str(data_root) not in sent[0][2]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="automation-brief-paths-", dir="/private/tmp") as temp_dir:
        fixture_dir = Path(temp_dir)
        test_resolver_precedence()
        test_holdings_source_precedence(fixture_dir)
        test_canonical_outputs_and_downstream_readers(fixture_dir)
    print("offline project paths smoke passed")


if __name__ == "__main__":
    main()
