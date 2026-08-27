from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_DAILY_SCRIPT = PROJECT_ROOT / "scripts" / "run_daily_digest.sh"
PLIST_EXAMPLE = PROJECT_ROOT / "scripts" / "com.ping.automation-brief.daily.plist.example"
sys.path.insert(0, str(PROJECT_ROOT))


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _run_daily_shell(
    fixture_dir: Path,
    *,
    report_type: str | None,
    existing_key: str | None = None,
    env_file_content: str | None = None,
    expected_key: str | None = None,
    cwd: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    repo_root = fixture_dir / "shell-repo"
    script_path = repo_root / "scripts" / RUN_DAILY_SCRIPT.name
    script_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RUN_DAILY_SCRIPT, script_path)
    if env_file_content is not None:
        (repo_root / ".env.local").write_text(env_file_content, encoding="utf-8")

    calls_path = fixture_dir / "python-calls.log"
    fake_python = repo_root / ".venv" / "bin" / "python"
    _write_executable(
        fake_python,
        """#!/bin/sh
set -eu
actual_key=${AUTOMATION_BRIEF_CURATOR_API_KEY:-}
expected_key=${AUTOMATION_BRIEF_EXPECTED_KEY:-}
if [ -n "$expected_key" ] && [ "$actual_key" = "$expected_key" ]; then
  credential_state=expected
elif [ -n "$actual_key" ]; then
  credential_state=unexpected
else
  credential_state=unavailable
fi
printf '%s | credential=%s\n' "$*" "$credential_state" >> "$AUTOMATION_BRIEF_TEST_CALLS"
""",
    )

    env = os.environ.copy()
    env.update(
        {
            "AUTOMATION_BRIEF_CAFFEINATED": "1",
            "AUTOMATION_BRIEF_TEST_CALLS": str(calls_path),
        }
    )
    if existing_key is None:
        env.pop("AUTOMATION_BRIEF_CURATOR_API_KEY", None)
    else:
        env["AUTOMATION_BRIEF_CURATOR_API_KEY"] = existing_key
    if expected_key is None:
        env.pop("AUTOMATION_BRIEF_EXPECTED_KEY", None)
    else:
        env["AUTOMATION_BRIEF_EXPECTED_KEY"] = expected_key

    command = [str(script_path)]
    if report_type is not None:
        command.append(report_type)
    result = subprocess.run(
        command,
        cwd=cwd or repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    python_calls = calls_path.read_text(encoding="utf-8").splitlines() if calls_path.exists() else []
    return result, python_calls


def test_shell_defaults_to_digest_and_routes_downstream(fixture_dir: Path) -> None:
    result, python_calls = _run_daily_shell(
        fixture_dir,
        report_type=None,
        env_file_content="AUTOMATION_BRIEF_CURATOR_API_KEY=fixture-digest-secret\n",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert len(python_calls) == 3
    assert "main.py --report-type digest | credential=unavailable" in python_calls[0]
    assert "publish_mobile_digest.py --report-type digest | credential=unavailable" in python_calls[1]
    assert "send_bark_notification.py --report-type digest | credential=unavailable" in python_calls[2]
    assert "fixture-digest-secret" not in result.stdout + result.stderr


def test_shell_overnight_loads_project_env_and_routes_downstream(fixture_dir: Path) -> None:
    caller_dir = fixture_dir / "caller"
    caller_dir.mkdir(parents=True, exist_ok=True)
    result, python_calls = _run_daily_shell(
        fixture_dir,
        report_type="overnight_brief",
        env_file_content='AUTOMATION_BRIEF_CURATOR_API_KEY="fixture-env-secret"\n',
        expected_key="fixture-env-secret",
        cwd=caller_dir,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "curator credential available" in result.stdout
    assert "fixture-env-secret" not in result.stdout + result.stderr
    assert len(python_calls) == 3
    assert all("--report-type overnight_brief" in call for call in python_calls)
    assert all("credential=expected" in call for call in python_calls)


def test_shell_existing_env_key_takes_precedence_over_project_env(fixture_dir: Path) -> None:
    result, python_calls = _run_daily_shell(
        fixture_dir,
        report_type="overnight_brief",
        existing_key="fixture-existing-secret",
        env_file_content="AUTOMATION_BRIEF_CURATOR_API_KEY=fixture-file-secret\n",
        expected_key="fixture-existing-secret",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "curator credential available" in result.stdout
    assert "fixture-existing-secret" not in result.stdout + result.stderr
    assert "fixture-file-secret" not in result.stdout + result.stderr
    assert all("credential=expected" in call for call in python_calls)


def test_shell_missing_project_env_keeps_fallback_available(fixture_dir: Path) -> None:
    result, python_calls = _run_daily_shell(fixture_dir, report_type="overnight_brief")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "curator credential unavailable; fallback remains available" in result.stdout
    assert len(python_calls) == 3
    assert all("--report-type overnight_brief" in call for call in python_calls)
    assert all("credential=unavailable" in call for call in python_calls)


def test_shell_project_env_without_curator_key_keeps_fallback_available(fixture_dir: Path) -> None:
    result, python_calls = _run_daily_shell(
        fixture_dir,
        report_type="overnight_brief",
        env_file_content="BARK_URL=https://example.invalid/device\n",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "curator credential unavailable; fallback remains available" in result.stdout
    assert len(python_calls) == 3
    assert all("credential=unavailable" in call for call in python_calls)


def test_shell_unknown_report_type_fails_closed(fixture_dir: Path) -> None:
    result, python_calls = _run_daily_shell(fixture_dir, report_type="market_brief")

    assert result.returncode != 0
    assert "Unsupported report type" in result.stderr
    assert python_calls == []


def test_mobile_and_bark_route_by_report_type(fixture_dir: Path) -> None:
    import scripts.publish_mobile_digest as publish_mobile_digest
    import scripts.send_bark_notification as send_bark_notification
    from project_paths import get_project_paths

    data_root = fixture_dir / "data-root"
    paths = get_project_paths(repo_root=PROJECT_ROOT, data_root=data_root)
    paths.reports_dir.mkdir(parents=True, exist_ok=True)
    report_date = date.today().isoformat()
    daily_report = paths.reports_dir / f"daily-news-{report_date}.md"
    morning_report = paths.reports_dir / f"morning-brief-{report_date}.md"
    daily_report.write_text("Displayed items: 7\n\nDaily fixture\n", encoding="utf-8")
    morning_report.write_text("Displayed items: must not be used\n\nMorning fixture\n", encoding="utf-8")

    mobile_digest_dir = fixture_dir / "mobile-digest"
    mobile_morning_dir = fixture_dir / "mobile-morning"
    digest_env = fixture_dir / "digest.env"
    morning_env = fixture_dir / "morning.env"
    digest_env.write_text(f"MOBILE_DIGEST_DIR={mobile_digest_dir}\n", encoding="utf-8")
    morning_env.write_text(f"MOBILE_DIGEST_DIR={mobile_morning_dir}\n", encoding="utf-8")

    assert publish_mobile_digest.main(
        data_root=data_root,
        env_file=digest_env,
        report_type="digest",
    ) == 0
    assert (mobile_digest_dir / daily_report.name).exists()

    assert publish_mobile_digest.main(
        data_root=data_root,
        env_file=morning_env,
        report_type="overnight_brief",
    ) == 0
    assert (mobile_morning_dir / morning_report.name).exists()
    assert not (mobile_morning_dir / daily_report.name).exists()

    bark_env = fixture_dir / "bark.env"
    bark_env.write_text(
        "BARK_URL=https://example.invalid/device\n"
        "OBSIDIAN_VAULT_NAME=FixtureVault\n"
        "MOBILE_DIGEST_RELATIVE_PATH=Briefs\n",
        encoding="utf-8",
    )
    sent: list[tuple[str, str, str, str]] = []

    def fake_send_notification(bark_url: str, title: str, body: str, url: str = "") -> None:
        sent.append((bark_url, title, body, url))

    with patch.object(send_bark_notification, "send_notification", fake_send_notification):
        assert send_bark_notification.main(
            data_root=data_root,
            env_file=bark_env,
            report_type="digest",
        ) == 0
        assert send_bark_notification.main(
            data_root=data_root,
            env_file=bark_env,
            report_type="overnight_brief",
        ) == 0

    assert sent[0][1] == "每日早间回顾已生成"
    assert f"reports/{daily_report.name}" in sent[0][2]
    assert "Displayed items: 7" in sent[0][2]
    assert parse_qs(urlparse(sent[0][3]).query)["file"] == [f"Briefs/{daily_report.name}"]

    assert sent[1][1] == "早间简报已生成"
    assert f"reports/{morning_report.name}" in sent[1][2]
    assert "Displayed items" not in sent[1][2]
    assert parse_qs(urlparse(sent[1][3]).query)["file"] == [f"Briefs/{morning_report.name}"]


def test_downstream_unknown_report_type_fails_closed(fixture_dir: Path) -> None:
    import scripts.publish_mobile_digest as publish_mobile_digest
    import scripts.send_bark_notification as send_bark_notification

    fixture_dir.mkdir(parents=True, exist_ok=True)
    data_root = fixture_dir / "data-root"
    env_file = fixture_dir / "routing.env"
    env_file.write_text(
        f"MOBILE_DIGEST_DIR={fixture_dir / 'mobile'}\n"
        "BARK_URL=https://example.invalid/device\n",
        encoding="utf-8",
    )

    assert publish_mobile_digest.main(
        data_root=data_root,
        env_file=env_file,
        report_type="market_brief",
    ) != 0
    with patch.object(send_bark_notification, "send_notification") as send_mock:
        assert send_bark_notification.main(
            data_root=data_root,
            env_file=env_file,
            report_type="market_brief",
        ) != 0
    send_mock.assert_not_called()


def test_plist_selects_overnight_brief() -> None:
    plist_bytes = PLIST_EXAMPLE.read_bytes()
    plist = plistlib.loads(plist_bytes)
    assert plist["Label"] == "com.ping.automation-brief.daily"
    assert plist["ProgramArguments"] == [
        "/Users/wp/Projects/自动化简报/scripts/run_daily_digest.sh",
        "overnight_brief",
    ]
    assert plist["StartCalendarInterval"] == {"Hour": 8, "Minute": 0}
    assert b"AUTOMATION_BRIEF_CURATOR_API_KEY" not in plist_bytes


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="automation-brief-production-routing-", dir="/private/tmp") as temp_dir:
        fixture_dir = Path(temp_dir)
        test_shell_defaults_to_digest_and_routes_downstream(fixture_dir / "shell-default")
        test_shell_overnight_loads_project_env_and_routes_downstream(fixture_dir / "shell-env-file")
        test_shell_existing_env_key_takes_precedence_over_project_env(fixture_dir / "shell-env-precedence")
        test_shell_missing_project_env_keeps_fallback_available(fixture_dir / "shell-env-missing")
        test_shell_project_env_without_curator_key_keeps_fallback_available(fixture_dir / "shell-env-no-key")
        test_shell_unknown_report_type_fails_closed(fixture_dir / "shell-unknown")
        test_mobile_and_bark_route_by_report_type(fixture_dir / "downstream")
        test_downstream_unknown_report_type_fails_closed(fixture_dir / "unknown")
        test_plist_selects_overnight_brief()
    print("offline production routing smoke passed")


if __name__ == "__main__":
    main()
