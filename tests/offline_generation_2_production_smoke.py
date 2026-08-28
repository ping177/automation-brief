"""Offline acceptance for the Generation 2 production publication adapter.

The smoke uses a temporary canonical data root and finalized artifacts created
by the real Generation 2 artifact manager.  The runtime builder is replaced by
a fake, so this test never calls RSS, an LLM provider, Obsidian, or Bark.
"""

from __future__ import annotations

import ast
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from io import StringIO
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from canonical_domain import Brief, GenerationStatus  # noqa: E402
from project_paths import ProjectPaths  # noqa: E402
from v1_artifacts import V1ArtifactManager  # noqa: E402
import run_generation_2_production as production_adapter  # noqa: E402


REPORT_DATE = date(2026, 8, 28)
WINDOW_START = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc)
CREATED_AT = datetime(2026, 8, 28, 0, 1, tzinfo=timezone.utc)


def _finalized_result(
    data_root: Path,
    *,
    run_id: str,
    outcome: str,
    markdown: str | None,
) -> SimpleNamespace:
    paths = ProjectPaths(repo_root=PROJECT_ROOT, data_root=data_root)
    manager = V1ArtifactManager(paths, clock=lambda: CREATED_AT)
    run = manager.start_run(run_id)
    if markdown is not None:
        brief = Brief.from_report_slot(
            report_date=REPORT_DATE,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            generation_status=GenerationStatus(outcome),
        )
        run.persist_brief(brief, markdown)
    final = run.finalize(run_status=outcome)
    return SimpleNamespace(
        run_id=run_id,
        run_dir=final.run_dir,
        generation_outcome=outcome,
        brief=None,
        rendered_markdown=None,
    )


def _staging_result(
    data_root: Path,
    *,
    run_id: str,
    markdown: str,
) -> SimpleNamespace:
    paths = ProjectPaths(repo_root=PROJECT_ROOT, data_root=data_root)
    manager = V1ArtifactManager(paths, clock=lambda: CREATED_AT)
    run = manager.start_run(run_id)
    brief = Brief.from_report_slot(
        report_date=REPORT_DATE,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    )
    run.persist_brief(brief, markdown)
    return SimpleNamespace(
        run_id=run_id,
        run_dir=run.staging_dir,
        generation_outcome="complete",
        brief=None,
        rendered_markdown=None,
    )


def _invoke(
    data_root: Path,
    result_factory,
    *,
    report_date: str | None = REPORT_DATE.isoformat(),
    clock=None,
):
    runtime_calls: list[object] = []

    class FakeRuntime:
        def run(self, slot, **kwargs):
            runtime_calls.append((slot, kwargs))
            return result_factory(slot)

    def builder(**kwargs):
        assert kwargs["provider"] == "deepseek"
        assert kwargs["data_root"] == data_root
        return FakeRuntime()

    argv = ["--data-root", str(data_root)]
    if report_date is not None:
        argv.extend(["--date", report_date])
    stdout = StringIO()
    with redirect_stdout(stdout):
        exit_code = production_adapter.main(
            argv,
            runtime_builder=builder,
            clock=clock,
        )
    output = stdout.getvalue().strip()
    assert output
    return exit_code, json.loads(output), runtime_calls


def test_complete_publishes_finalized_artifact_with_matching_digest() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-production-complete-", dir="/private/tmp") as temp:
        data_root = Path(temp) / "data"
        markdown = "# 早间简报｜2026-08-28\n\n## *其他*\n\n本报告窗口内暂无入选事件。\n"
        code, result, calls = _invoke(
            data_root,
            lambda _slot: _finalized_result(
                data_root,
                run_id="complete-run",
                outcome="complete",
                markdown=markdown,
            ),
        )

        report_path = data_root / "reports" / "morning-brief-2026-08-28.md"
        assert code == 0
        assert report_path.read_text(encoding="utf-8") == markdown
        assert result["generation_outcome"] == "complete"
        assert result["publication_status"] == "published"
        assert result["artifact_digest"] == result["report_digest"]
        assert result["artifact_path"].endswith("complete-run/morning-brief.md")
        assert result["report_path"].endswith("reports/morning-brief-2026-08-28.md")
        assert len(calls) == 1


def test_partial_publishes_without_rewriting_reader_facing_degradation() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-production-partial-", dir="/private/tmp") as temp:
        data_root = Path(temp) / "data"
        markdown = "# 早间简报｜2026-08-28\n\n> 本次简报部分生成，可能存在少量遗漏。\n"
        code, result, _calls = _invoke(
            data_root,
            lambda _slot: _finalized_result(
                data_root,
                run_id="partial-run",
                outcome="partial",
                markdown=markdown,
            ),
        )

        report_path = data_root / "reports" / "morning-brief-2026-08-28.md"
        assert code == 0
        assert result["generation_outcome"] == "partial"
        assert result["publication_status"] == "published"
        assert report_path.read_text(encoding="utf-8") == markdown
        assert "部分生成" in report_path.read_text(encoding="utf-8")


def test_legal_empty_complete_publishes_without_extra_runtime_work() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-production-empty-", dir="/private/tmp") as temp:
        data_root = Path(temp) / "data"
        markdown = "# 早间简报｜2026-08-28\n\n本报告窗口内暂无入选事件。\n"
        code, result, calls = _invoke(
            data_root,
            lambda _slot: _finalized_result(
                data_root,
                run_id="empty-run",
                outcome="complete",
                markdown=markdown,
            ),
        )

        assert code == 0
        assert result["publication_status"] == "published"
        assert "暂无入选事件" in (
            data_root / "reports" / "morning-brief-2026-08-28.md"
        ).read_text(encoding="utf-8")
        assert len(calls) == 1


def test_failed_does_not_create_or_modify_canonical_report() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-production-failed-", dir="/private/tmp") as temp:
        data_root = Path(temp) / "data"
        report_path = data_root / "reports" / "morning-brief-2026-08-28.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        original = b"existing report must remain unchanged\n"
        report_path.write_bytes(original)

        code, result, _calls = _invoke(
            data_root,
            lambda _slot: _finalized_result(
                data_root,
                run_id="failed-run",
                outcome="failed",
                markdown=None,
            ),
        )

        assert code != 0
        assert result["generation_outcome"] == "failed"
        assert result["publication_status"] == "generation_failed"
        assert report_path.read_bytes() == original


def test_failed_without_existing_report_does_not_create_one() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-production-failed-empty-", dir="/private/tmp") as temp:
        data_root = Path(temp) / "data"
        code, result, _calls = _invoke(
            data_root,
            lambda _slot: _finalized_result(
                data_root,
                run_id="failed-empty-run",
                outcome="failed",
                markdown=None,
            ),
        )

        assert code != 0
        assert result["publication_status"] == "generation_failed"
        assert not (data_root / "reports" / "morning-brief-2026-08-28.md").exists()


def test_same_digest_collision_is_idempotent_success() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-production-same-", dir="/private/tmp") as temp:
        data_root = Path(temp) / "data"
        markdown = "# stable report\n"
        first_code, first_result, _calls = _invoke(
            data_root,
            lambda _slot: _finalized_result(
                data_root,
                run_id="same-first",
                outcome="complete",
                markdown=markdown,
            ),
        )
        second_code, second_result, _calls = _invoke(
            data_root,
            lambda _slot: _finalized_result(
                data_root,
                run_id="same-second",
                outcome="complete",
                markdown=markdown,
            ),
        )

        assert first_code == second_code == 0
        assert first_result["publication_status"] == "published"
        assert second_result["publication_status"] == "already_present"
        assert len(list((data_root / "reports").glob("morning-brief-*.md"))) == 1


def test_different_digest_collision_fails_closed_and_preserves_target() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-production-different-", dir="/private/tmp") as temp:
        data_root = Path(temp) / "data"
        first_markdown = "# first report\n"
        second_markdown = "# second report\n"
        _invoke(
            data_root,
            lambda _slot: _finalized_result(
                data_root,
                run_id="different-first",
                outcome="complete",
                markdown=first_markdown,
            ),
        )
        code, result, _calls = _invoke(
            data_root,
            lambda _slot: _finalized_result(
                data_root,
                run_id="different-second",
                outcome="complete",
                markdown=second_markdown,
            ),
        )

        report_path = data_root / "reports" / "morning-brief-2026-08-28.md"
        assert code != 0
        assert result["publication_status"] == "report_collision"
        assert report_path.read_text(encoding="utf-8") == first_markdown


def test_staging_artifact_is_not_publishable() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-production-staging-", dir="/private/tmp") as temp:
        data_root = Path(temp) / "data"
        code, result, _calls = _invoke(
            data_root,
            lambda _slot: _staging_result(
                data_root,
                run_id="staging-run",
                markdown="# staging\n",
            ),
        )

        assert code != 0
        assert result["publication_status"] == "artifact_invalid"
        assert not (data_root / "reports" / "morning-brief-2026-08-28.md").exists()


def test_artifact_run_id_must_match_finalized_directory() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-production-identity-", dir="/private/tmp") as temp:
        data_root = Path(temp) / "data"

        def result_factory(_slot):
            result = _finalized_result(
                data_root,
                run_id="identity-run",
                outcome="complete",
                markdown="# identity\n",
            )
            result.run_id = "different-run"
            return result

        code, result, _calls = _invoke(data_root, result_factory)

        assert code != 0
        assert result["publication_status"] == "artifact_invalid"
        assert not (data_root / "reports" / "morning-brief-2026-08-28.md").exists()


def test_report_date_defaults_to_shanghai_slot_not_host_date() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-production-timezone-", dir="/private/tmp") as temp:
        data_root = Path(temp) / "data"
        clock = lambda: datetime(2026, 8, 27, 16, 30, tzinfo=timezone.utc)
        code, result, calls = _invoke(
            data_root,
            lambda slot: _finalized_result(
                data_root,
                run_id="timezone-run",
                outcome="complete",
                markdown=f"# {slot.report_date.isoformat()}\n",
            ),
            report_date=None,
            clock=clock,
        )

        assert code == 0
        assert result["report_path"].endswith("morning-brief-2026-08-28.md")
        assert calls[0][0].report_date == REPORT_DATE


def test_adapter_has_no_generation_1_semantic_imports() -> None:
    tree = ast.parse(
        Path(production_adapter.__file__).read_text(encoding="utf-8"),
        filename=str(production_adapter.__file__),
    )
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    forbidden = {
        "main",
        "overnight_brief_writer",
        "ai_curator",
        "ai_curator_provider",
        "market_brief_writer",
    }
    assert forbidden.isdisjoint(imports)


def main() -> None:
    test_complete_publishes_finalized_artifact_with_matching_digest()
    test_partial_publishes_without_rewriting_reader_facing_degradation()
    test_legal_empty_complete_publishes_without_extra_runtime_work()
    test_failed_does_not_create_or_modify_canonical_report()
    test_failed_without_existing_report_does_not_create_one()
    test_same_digest_collision_is_idempotent_success()
    test_different_digest_collision_fails_closed_and_preserves_target()
    test_staging_artifact_is_not_publishable()
    test_artifact_run_id_must_match_finalized_directory()
    test_report_date_defaults_to_shanghai_slot_not_host_date()
    test_adapter_has_no_generation_1_semantic_imports()
    print("offline Generation 2 production publication smoke passed")


if __name__ == "__main__":
    main()
