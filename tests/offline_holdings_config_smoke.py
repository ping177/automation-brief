from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INIT_SCRIPT = PROJECT_ROOT / "scripts" / "init_holdings_config.py"
VALIDATE_SCRIPT = PROJECT_ROOT / "scripts" / "validate_holdings_config.py"
RUN_DAILY_SCRIPT = PROJECT_ROOT / "scripts" / "run_daily_digest.sh"
MAIN_SCRIPT = PROJECT_ROOT / "main.py"


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["AUTOMATION_BRIEF_OFFLINE_MARKET_DATA"] = "1"
    return subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        check=False,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def valid_payload() -> dict[str, object]:
    return {
        "holdings": [
            {
                "code": "TEST001",
                "name": "测试标的",
                "market": "A股",
                "sector": "测试行业",
                "watch_tags": ["测试标签"],
                "notes": "只写观察备注",
            }
        ]
    }


def main() -> None:
    fixture_dir = Path(tempfile.mkdtemp(prefix="automation-brief-holdings-"))
    example_path = fixture_dir / "holdings.example.json"
    holdings_path = fixture_dir / "holdings.json"
    write_json(example_path, valid_payload())

    init_result = run_command(
        [
            sys.executable,
            str(INIT_SCRIPT),
            "--holdings",
            str(holdings_path),
            "--example",
            str(example_path),
        ]
    )
    assert init_result.returncode == 0, init_result.stderr
    assert holdings_path.exists()
    assert "Created local holdings config" in init_result.stdout
    assert "ignored by Git" in init_result.stdout

    first_content = holdings_path.read_text(encoding="utf-8")
    holdings_path.write_text(first_content.replace("测试标的", "已保留标的"), encoding="utf-8")
    second_init_result = run_command(
        [
            sys.executable,
            str(INIT_SCRIPT),
            "--holdings",
            str(holdings_path),
            "--example",
            str(example_path),
        ]
    )
    assert second_init_result.returncode == 0, second_init_result.stderr
    assert "not overwritten" in second_init_result.stdout
    assert "已保留标的" in holdings_path.read_text(encoding="utf-8")

    valid_result = run_command([sys.executable, str(VALIDATE_SCRIPT), "--holdings", str(holdings_path)])
    assert valid_result.returncode == 0, valid_result.stdout + valid_result.stderr
    assert "Holdings config is valid." in valid_result.stdout

    invalid_json_path = fixture_dir / "invalid-json.json"
    invalid_json_path.write_text('{"holdings": [', encoding="utf-8")
    invalid_json_result = run_command(
        [sys.executable, str(VALIDATE_SCRIPT), "--holdings", str(invalid_json_path)]
    )
    assert invalid_json_result.returncode == 1
    assert "Invalid JSON" in invalid_json_result.stdout

    invalid_fields_path = fixture_dir / "invalid-fields.json"
    write_json(
        invalid_fields_path,
        {
            "holdings": [
                {
                    "code": "TEST001",
                    "name": "测试标的",
                    "market": "A股",
                    "sector": "测试行业",
                    "watch_tags": "测试标签",
                    "extra": "unsupported",
                }
            ]
        },
    )
    invalid_fields_result = run_command(
        [sys.executable, str(VALIDATE_SCRIPT), "--holdings", str(invalid_fields_path)]
    )
    assert invalid_fields_result.returncode == 1
    assert "watch_tags must be a list" in invalid_fields_result.stdout
    assert "missing required fields: notes" in invalid_fields_result.stdout
    assert "unsupported fields: extra" in invalid_fields_result.stdout

    sensitive_path = fixture_dir / "sensitive.json"
    sensitive_payload = valid_payload()
    sensitive_payload["holdings"][0]["cost"] = "123.45"  # type: ignore[index]
    sensitive_payload["holdings"][0]["market_value"] = "67890"  # type: ignore[index]
    write_json(sensitive_path, sensitive_payload)
    sensitive_result = run_command([sys.executable, str(VALIDATE_SCRIPT), "--holdings", str(sensitive_path)])
    assert sensitive_result.returncode == 0
    assert "WARNING:" in sensitive_result.stdout
    assert "cost" in sensitive_result.stdout
    assert "market_value" in sensitive_result.stdout
    assert "123.45" not in sensitive_result.stdout
    assert "67890" not in sensitive_result.stdout

    output_dir = fixture_dir / "output"
    empty_feeds_path = fixture_dir / "feeds.json"
    empty_keywords_path = fixture_dir / "keywords.json"
    write_json(empty_feeds_path, [])
    write_json(empty_keywords_path, {})
    market_result = run_command(
        [
            sys.executable,
            str(MAIN_SCRIPT),
            "--config",
            str(fixture_dir / "missing-config.json"),
            "--feeds",
            str(empty_feeds_path),
            "--keywords",
            str(empty_keywords_path),
            "--report-type",
            "market_brief",
            "--output",
            str(output_dir),
            "--date",
            "2026-06-26",
        ]
    )
    assert market_result.returncode == 0, market_result.stdout + market_result.stderr
    market_output = output_dir / "market-brief-2026-06-26.md"
    assert market_output.exists()
    assert "Mode: market_brief" in market_output.read_text(encoding="utf-8")

    daily_script_text = RUN_DAILY_SCRIPT.read_text(encoding="utf-8")
    assert '"$PYTHON_BIN" "$PROJECT_DIR/main.py"' in daily_script_text
    assert "--report-type" not in daily_script_text
    assert "market_brief" not in daily_script_text

    print("offline holdings config smoke passed")


if __name__ == "__main__":
    main()
