from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
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
    generation_2_exit_code: int = 0,
    publisher_exit_code: int = 0,
    bark_exit_code: int = 0,
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
case "${1:-}" in
  *run_generation_2_production.py)
    exit "${AUTOMATION_BRIEF_TEST_GENERATION_2_EXIT_CODE:-0}"
    ;;
  *publish_mobile_digest.py)
    exit "${AUTOMATION_BRIEF_TEST_PUBLISH_EXIT_CODE:-0}"
    ;;
  *send_bark_notification.py)
    exit "${AUTOMATION_BRIEF_TEST_BARK_EXIT_CODE:-0}"
    ;;
esac
""",
    )

    env = os.environ.copy()
    env.update(
        {
            "AUTOMATION_BRIEF_CAFFEINATED": "1",
            "AUTOMATION_BRIEF_TEST_CALLS": str(calls_path),
            "AUTOMATION_BRIEF_TEST_GENERATION_2_EXIT_CODE": str(generation_2_exit_code),
            "AUTOMATION_BRIEF_TEST_PUBLISH_EXIT_CODE": str(publisher_exit_code),
            "AUTOMATION_BRIEF_TEST_BARK_EXIT_CODE": str(bark_exit_code),
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


def test_shell_generation_2_success_routes_adapter_then_morning_delivery(fixture_dir: Path) -> None:
    result, python_calls = _run_daily_shell(
        fixture_dir,
        report_type="generation_2",
        env_file_content='AUTOMATION_BRIEF_CURATOR_API_KEY="fixture-generation-2-secret"\n',
        expected_key="fixture-generation-2-secret",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "curator credential available" in result.stdout
    assert "fixture-generation-2-secret" not in result.stdout + result.stderr
    assert len(python_calls) == 3
    assert "run_generation_2_production.py" in python_calls[0]
    assert "credential=expected" in python_calls[0]
    assert "publish_mobile_digest.py --report-type overnight_brief" in python_calls[1]
    assert "send_bark_notification.py --report-type overnight_brief" in python_calls[2]
    adapter_match = re.search(r"--date (\d{4}-\d{2}-\d{2})", python_calls[0])
    assert adapter_match is not None
    adapter_date = adapter_match.group(1)
    assert f"--report-date {adapter_date}" in python_calls[1]
    assert f"--report-date {adapter_date}" in python_calls[2]
    assert all("main.py" not in call for call in python_calls)


def test_shell_generation_2_failure_stops_before_delivery_without_gen1_fallback(
    fixture_dir: Path,
) -> None:
    result, python_calls = _run_daily_shell(
        fixture_dir,
        report_type="generation_2",
        env_file_content="AUTOMATION_BRIEF_CURATOR_API_KEY=fixture-generation-2-secret\n",
        expected_key="fixture-generation-2-secret",
        generation_2_exit_code=17,
    )

    assert result.returncode == 17
    assert len(python_calls) == 1
    assert "run_generation_2_production.py" in python_calls[0]
    assert "main.py" not in "\n".join(python_calls)
    assert "publish_mobile_digest.py" not in "\n".join(python_calls)
    assert "send_bark_notification.py" not in "\n".join(python_calls)


def test_shell_generation_2_delivery_channels_are_independent_and_aggregate_status(
    fixture_dir: Path,
) -> None:
    for publisher_exit_code, bark_exit_code, expected_exit_code in (
        (0, 0, 0),
        (17, 0, 1),
        (0, 23, 1),
        (17, 23, 1),
    ):
        result, python_calls = _run_daily_shell(
            fixture_dir / f"publisher-{publisher_exit_code}-bark-{bark_exit_code}",
            report_type="generation_2",
            env_file_content="AUTOMATION_BRIEF_CURATOR_API_KEY=fixture-generation-2-secret\n",
            expected_key="fixture-generation-2-secret",
            publisher_exit_code=publisher_exit_code,
            bark_exit_code=bark_exit_code,
        )

        assert result.returncode == expected_exit_code, result.stdout + result.stderr
        assert len(python_calls) == 3
        assert "run_generation_2_production.py" in python_calls[0]
        assert "publish_mobile_digest.py" in python_calls[1]
        assert "send_bark_notification.py" in python_calls[2]
        assert "delivery aggregate" in result.stdout


def test_delivery_scripts_use_explicit_morning_brief_date(fixture_dir: Path) -> None:
    import scripts.publish_mobile_digest as publish_mobile_digest
    import scripts.send_bark_notification as send_bark_notification
    from project_paths import get_project_paths

    data_root = fixture_dir / "data-root"
    paths = get_project_paths(repo_root=PROJECT_ROOT, data_root=data_root)
    report_date = "2001-02-03"
    report_path = paths.reports_dir / f"morning-brief-{report_date}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("Explicit dated Morning Brief\n", encoding="utf-8")

    mobile_dir = fixture_dir / "mobile"
    mobile_env = fixture_dir / "mobile.env"
    mobile_env.write_text(f"MOBILE_DIGEST_DIR={mobile_dir}\n", encoding="utf-8")
    assert publish_mobile_digest.main(
        data_root=data_root,
        env_file=mobile_env,
        report_type="overnight_brief",
        report_date=report_date,
    ) == 0
    assert (mobile_dir / report_path.name).read_text(encoding="utf-8") == report_path.read_text(
        encoding="utf-8"
    )

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
            report_type="overnight_brief",
            report_date=report_date,
        ) == 0

    assert sent[0][1] == "早间简报已生成"
    assert f"reports/{report_path.name}" in sent[0][2]
    assert parse_qs(urlparse(sent[0][3]).query)["file"] == [f"Briefs/{report_path.name}"]


def test_invalid_or_missing_explicit_morning_brief_date_fails_closed(fixture_dir: Path) -> None:
    import scripts.publish_mobile_digest as publish_mobile_digest
    import scripts.send_bark_notification as send_bark_notification
    from project_paths import get_project_paths

    data_root = fixture_dir / "data-root"
    paths = get_project_paths(repo_root=PROJECT_ROOT, data_root=data_root)
    paths.reports_dir.mkdir(parents=True, exist_ok=True)
    old_report = paths.reports_dir / "morning-brief-2001-02-02.md"
    old_report.write_text("Old dated report\n", encoding="utf-8")
    mobile_env = fixture_dir / "mobile.env"
    mobile_env.write_text(f"MOBILE_DIGEST_DIR={fixture_dir / 'mobile'}\n", encoding="utf-8")
    bark_env = fixture_dir / "bark.env"
    bark_env.write_text("BARK_URL=https://example.invalid/device\n", encoding="utf-8")

    for invalid_date in ("2001-2-3", "2001-02-30"):
        assert publish_mobile_digest.main(
            data_root=data_root,
            env_file=mobile_env,
            report_type="overnight_brief",
            report_date=invalid_date,
        ) == 2

    sent: list[str] = []

    def fake_send_notification(*_args: object, **_kwargs: object) -> None:
        sent.append("sent")

    with patch.object(send_bark_notification, "send_notification", fake_send_notification):
        for invalid_date in ("2001-2-3", "2001-02-30"):
            assert send_bark_notification.main(
                data_root=data_root,
                env_file=bark_env,
                report_type="overnight_brief",
                report_date=invalid_date,
            ) == 2
        assert send_bark_notification.main(
            data_root=data_root,
            env_file=bark_env,
            report_type="overnight_brief",
            report_date="2001-02-03",
        ) == 1

    assert sent == []
    assert not (fixture_dir / "mobile" / "morning-brief-2001-02-03.md").exists()


def test_bark_ambiguous_timeout_is_not_resent_and_does_not_leak_secret(fixture_dir: Path) -> None:
    import scripts.send_bark_notification as send_bark_notification
    from project_paths import get_project_paths

    data_root = fixture_dir / "data-root"
    paths = get_project_paths(repo_root=PROJECT_ROOT, data_root=data_root)
    report_path = paths.reports_dir / "morning-brief-2001-02-03.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("Timeout fixture\n", encoding="utf-8")
    secret_url = "https://api.day.app/fixture-secret-token"
    bark_env = fixture_dir / "bark.env"
    bark_env.write_text(f"BARK_URL={secret_url}\n", encoding="utf-8")
    attempts: list[str] = []

    def fake_send_notification(bark_url: str, *_args: object, **_kwargs: object) -> None:
        attempts.append(bark_url)
        raise TimeoutError(f"request to {secret_url} timed out")

    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch.object(send_bark_notification, "send_notification", fake_send_notification),
        patch.object(send_bark_notification.time, "sleep") as sleep_mock,
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        result = send_bark_notification.main(
            data_root=data_root,
            env_file=bark_env,
            report_type="overnight_brief",
            report_date="2001-02-03",
        )

    assert result == 1
    assert attempts == [secret_url]
    sleep_mock.assert_not_called()
    assert "ambiguous" in stderr.getvalue()
    assert "fixture-secret-token" not in stdout.getvalue() + stderr.getvalue()


def test_bark_transport_failure_is_not_resent(fixture_dir: Path) -> None:
    import scripts.send_bark_notification as send_bark_notification
    from project_paths import get_project_paths

    data_root = fixture_dir / "data-root"
    paths = get_project_paths(repo_root=PROJECT_ROOT, data_root=data_root)
    report_path = paths.reports_dir / "morning-brief-2001-02-03.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("Transport fixture\n", encoding="utf-8")
    secret_url = "https://api.day.app/fixture-transport-token"
    bark_env = fixture_dir / "bark.env"
    bark_env.write_text(f"BARK_URL={secret_url}\n", encoding="utf-8")
    attempts: list[str] = []

    def fake_send_notification(bark_url: str, *_args: object, **_kwargs: object) -> None:
        attempts.append(bark_url)
        raise URLError(f"connection failed for {secret_url}")

    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch.object(send_bark_notification, "send_notification", fake_send_notification),
        patch.object(send_bark_notification.time, "sleep") as sleep_mock,
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        result = send_bark_notification.main(
            data_root=data_root,
            env_file=bark_env,
            report_type="overnight_brief",
            report_date="2001-02-03",
        )

    assert result == 1
    assert attempts == [secret_url]
    sleep_mock.assert_not_called()
    assert "transport_failed" in stderr.getvalue()
    assert "fixture-transport-token" not in stdout.getvalue() + stderr.getvalue()


def test_bark_unexpected_failure_is_sanitized_and_not_resent(fixture_dir: Path) -> None:
    import scripts.send_bark_notification as send_bark_notification
    from project_paths import get_project_paths

    data_root = fixture_dir / "data-root"
    paths = get_project_paths(repo_root=PROJECT_ROOT, data_root=data_root)
    report_path = paths.reports_dir / "morning-brief-2001-02-03.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("Unexpected failure fixture\n", encoding="utf-8")
    secret_url = "https://api.day.app/fixture-unexpected-token"
    bark_env = fixture_dir / "bark.env"
    bark_env.write_text(f"BARK_URL={secret_url}\n", encoding="utf-8")
    attempts: list[str] = []

    def fake_send_notification(bark_url: str, *_args: object, **_kwargs: object) -> None:
        attempts.append(bark_url)
        raise RuntimeError(f"unexpected failure for {secret_url}")

    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch.object(send_bark_notification, "send_notification", fake_send_notification),
        patch.object(send_bark_notification.time, "sleep") as sleep_mock,
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        result = send_bark_notification.main(
            data_root=data_root,
            env_file=bark_env,
            report_type="overnight_brief",
            report_date="2001-02-03",
        )

    assert result == 1
    assert attempts == [secret_url]
    sleep_mock.assert_not_called()
    assert "delivery_failed" in stderr.getvalue()
    assert "fixture-unexpected-token" not in stdout.getvalue() + stderr.getvalue()


def test_bark_explicit_http_retry_classes_remain_bounded_and_safe(fixture_dir: Path) -> None:
    import scripts.send_bark_notification as send_bark_notification
    from project_paths import get_project_paths

    data_root = fixture_dir / "data-root"
    paths = get_project_paths(repo_root=PROJECT_ROOT, data_root=data_root)
    report_path = paths.reports_dir / "morning-brief-2001-02-03.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("HTTP retry fixture\n", encoding="utf-8")
    secret_url = "https://api.day.app/fixture-http-token"
    bark_env = fixture_dir / "bark.env"
    bark_env.write_text(f"BARK_URL={secret_url}\n", encoding="utf-8")
    attempts: list[str] = []
    http_error = HTTPError(secret_url, 503, "fixture-secret-reason", {}, None)

    def fake_send_notification(bark_url: str, *_args: object, **_kwargs: object) -> None:
        attempts.append(bark_url)
        raise http_error

    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch.object(send_bark_notification, "send_notification", fake_send_notification),
        patch.object(send_bark_notification.time, "sleep") as sleep_mock,
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        result = send_bark_notification.main(
            data_root=data_root,
            env_file=bark_env,
            report_type="overnight_brief",
            report_date="2001-02-03",
        )

    assert result == 1
    assert attempts == [secret_url, secret_url, secret_url]
    assert sleep_mock.call_count == 2
    assert "http_503" in stderr.getvalue()
    assert "fixture-http-token" not in stdout.getvalue() + stderr.getvalue()


def test_bark_legacy_default_retry_behavior_remains_without_explicit_date(fixture_dir: Path) -> None:
    import scripts.send_bark_notification as send_bark_notification
    from project_paths import get_project_paths

    data_root = fixture_dir / "data-root"
    paths = get_project_paths(repo_root=PROJECT_ROOT, data_root=data_root)
    report_date = date.today().isoformat()
    report_path = paths.reports_dir / f"morning-brief-{report_date}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("Legacy retry fixture\n", encoding="utf-8")
    bark_env = fixture_dir / "bark.env"
    bark_env.write_text("BARK_URL=https://example.invalid/device\n", encoding="utf-8")
    attempts: list[int] = []

    def fake_send_notification(*_args: object, **_kwargs: object) -> None:
        attempts.append(1)
        raise TimeoutError("legacy fixture timeout")

    with (
        patch.object(send_bark_notification, "send_notification", fake_send_notification),
        patch.object(send_bark_notification.time, "sleep") as sleep_mock,
    ):
        result = send_bark_notification.main(
            data_root=data_root,
            env_file=bark_env,
            report_type="overnight_brief",
        )

    assert result == 1
    assert len(attempts) == 3
    assert sleep_mock.call_count == 2


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


def test_plist_selects_generation_2_without_activation() -> None:
    plist_bytes = PLIST_EXAMPLE.read_bytes()
    plist = plistlib.loads(plist_bytes)
    assert plist["Label"] == "com.ping.automation-brief.daily"
    assert plist["ProgramArguments"] == [
        "/Users/wp/Projects/自动化简报/scripts/run_daily_digest.sh",
        "generation_2",
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
        test_shell_generation_2_success_routes_adapter_then_morning_delivery(
            fixture_dir / "shell-generation-2-success"
        )
        test_shell_generation_2_failure_stops_before_delivery_without_gen1_fallback(
            fixture_dir / "shell-generation-2-failure"
        )
        test_shell_generation_2_delivery_channels_are_independent_and_aggregate_status(
            fixture_dir / "shell-generation-2-delivery-status"
        )
        test_shell_project_env_without_curator_key_keeps_fallback_available(fixture_dir / "shell-env-no-key")
        test_shell_unknown_report_type_fails_closed(fixture_dir / "shell-unknown")
        test_mobile_and_bark_route_by_report_type(fixture_dir / "downstream")
        test_delivery_scripts_use_explicit_morning_brief_date(fixture_dir / "explicit-date")
        test_invalid_or_missing_explicit_morning_brief_date_fails_closed(fixture_dir / "invalid-date")
        test_bark_ambiguous_timeout_is_not_resent_and_does_not_leak_secret(
            fixture_dir / "bark-timeout"
        )
        test_bark_transport_failure_is_not_resent(fixture_dir / "bark-transport")
        test_bark_unexpected_failure_is_sanitized_and_not_resent(fixture_dir / "bark-unexpected")
        test_bark_explicit_http_retry_classes_remain_bounded_and_safe(fixture_dir / "bark-http")
        test_bark_legacy_default_retry_behavior_remains_without_explicit_date(
            fixture_dir / "bark-legacy"
        )
        test_downstream_unknown_report_type_fails_closed(fixture_dir / "unknown")
        test_plist_selects_generation_2_without_activation()
    print("offline production routing smoke passed")


if __name__ == "__main__":
    main()
