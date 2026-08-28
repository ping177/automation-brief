#!/usr/bin/env python3
"""Run Generation 2 and publish its finalized Morning Brief artifact.

This is a production publication adapter only.  Generation 2 owns collection,
semantic stages, rendering, and immutable run artifacts; this adapter owns the
small boundary that promotes a finalized Markdown artifact to the canonical
Morning Brief report path.  Delivery remains outside this command.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from generation_2_runtime import (  # noqa: E402
    DEFAULT_FEEDS_PATH,
    DEEPSEEK_PROVIDER_ID,
    Generation2RuntimeConfigurationError,
    build_generation_2_runtime,
    resolve_morning_brief_report_slot,
)
from project_paths import get_project_paths  # noqa: E402


FINALIZED_MARKDOWN_NAME = "morning-brief.md"
PUBLISHABLE_OUTCOMES = frozenset({"complete", "partial"})
SUCCESS_PUBLICATION_STATUSES = frozenset({"published", "already_present"})


class PublicationError(RuntimeError):
    """A safe, operator-facing publication failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PublicationResult:
    """Small structured result emitted by the production adapter."""

    run_id: str | None
    generation_outcome: str
    artifact_path: Path | None
    report_path: Path | None
    artifact_digest: str | None
    report_digest: str | None
    publication_status: str
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_digest": self.artifact_digest,
            "artifact_path": None if self.artifact_path is None else str(self.artifact_path),
            "error_code": self.error_code,
            "generation_outcome": self.generation_outcome,
            "publication_status": self.publication_status,
            "report_digest": self.report_digest,
            "report_path": None if self.report_path is None else str(self.report_path),
            "run_id": self.run_id,
        }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        help="Morning Brief report date (YYYY-MM-DD); defaults to the Shanghai calendar date",
    )
    parser.add_argument("--feeds", type=Path, default=DEFAULT_FEEDS_PATH)
    parser.add_argument("--data-root", type=Path, help="Override canonical runtime data root")
    parser.add_argument("--model-cache", type=Path, help="Override the local embedding model cache")
    parser.add_argument("--run-id", help="Optional explicit Generation 2 run identity")
    return parser.parse_args(argv)


def _result_run_id(result: object) -> str | None:
    value = getattr(result, "run_id", None)
    return value if isinstance(value, str) and value else None


def _result_artifact_path(result: object) -> Path | None:
    run_dir = getattr(result, "run_dir", None)
    if not isinstance(run_dir, (str, Path)):
        return None
    return Path(run_dir) / FINALIZED_MARKDOWN_NAME


def _read_finalized_artifact(
    result: object,
    *,
    expected_outcome: str,
) -> tuple[Path, bytes, str]:
    """Read and verify the immutable finalized artifact, never staging output."""

    run_id = _result_run_id(result)
    artifact_path = _result_artifact_path(result)
    if run_id is None or artifact_path is None:
        raise PublicationError("artifact_invalid")
    run_dir = artifact_path.parent
    if run_dir.name != run_id:
        raise PublicationError("artifact_invalid")
    manifest_path = run_dir / "manifest.json"
    if (
        not run_dir.is_dir()
        or run_dir.is_symlink()
        or manifest_path.is_symlink()
        or not manifest_path.is_file()
    ):
        raise PublicationError("artifact_invalid")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise PublicationError("artifact_invalid") from None

    if not isinstance(manifest, Mapping):
        raise PublicationError("artifact_invalid")
    if (
        manifest.get("state") != "finalized"
        or manifest.get("run_id") != run_id
        or manifest.get("run_status") != expected_outcome
    ):
        raise PublicationError("artifact_invalid")

    files = manifest.get("files")
    file_record = files.get(FINALIZED_MARKDOWN_NAME) if isinstance(files, Mapping) else None
    if not isinstance(file_record, Mapping) or artifact_path.is_symlink() or not artifact_path.is_file():
        raise PublicationError("artifact_invalid")

    try:
        data = artifact_path.read_bytes()
    except (OSError, UnicodeError):
        raise PublicationError("artifact_invalid") from None
    digest = hashlib.sha256(data).hexdigest()
    if file_record.get("bytes") != len(data) or file_record.get("sha256") != digest:
        raise PublicationError("artifact_invalid")
    return artifact_path, data, digest


def _digest_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, UnicodeError):
        raise PublicationError("publication_failed") from None


def _existing_report_digest(path: Path) -> str | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, UnicodeError):
        return None


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        raise PublicationError("publication_failed") from None
    try:
        os.fsync(descriptor)
    except OSError:
        raise PublicationError("publication_failed") from None
    finally:
        os.close(descriptor)


def _atomic_publish(data: bytes, destination: Path, digest: str) -> str:
    """Install a complete report atomically without overwriting a collision."""

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise PublicationError("publication_failed") from None

    if destination.is_symlink():
        raise PublicationError("report_collision")
    if destination.exists():
        if destination.is_file() and _digest_file(destination) == digest:
            return "already_present"
        raise PublicationError("report_collision")

    temporary = destination.parent / f".{destination.name}.tmp-{uuid.uuid4().hex[:12]}"
    file_descriptor: int | None = None
    try:
        try:
            file_descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(file_descriptor, "wb") as output:
                file_descriptor = None
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
        except (OSError, TypeError, ValueError):
            raise PublicationError("publication_failed") from None

        try:
            # link() is an atomic no-overwrite install on the same filesystem.
            # It closes the check-then-write race while preserving collision policy.
            os.link(temporary, destination)
        except FileExistsError:
            if destination.is_file() and not destination.is_symlink() and _digest_file(destination) == digest:
                return "already_present"
            raise PublicationError("report_collision") from None
        except OSError:
            raise PublicationError("publication_failed") from None

        try:
            temporary.unlink()
        except OSError:
            # The destination is already a complete file; a leftover temp is
            # harmless but must not turn a successful publication into a rewrite.
            pass
        _fsync_directory(destination.parent)
        return "published"
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        try:
            temporary.unlink()
        except OSError:
            pass


def publish_generation_result(
    result: object,
    *,
    report_path: Path,
) -> PublicationResult:
    """Publish one finalized Generation 2 result according to outcome policy."""

    outcome = getattr(result, "generation_outcome", None)
    normalized_outcome = outcome if isinstance(outcome, str) else "failed"
    run_id = _result_run_id(result)
    artifact_path = _result_artifact_path(result)

    if normalized_outcome not in PUBLISHABLE_OUTCOMES:
        return PublicationResult(
            run_id=run_id,
            generation_outcome=normalized_outcome,
            artifact_path=artifact_path,
            report_path=report_path,
            artifact_digest=None,
            report_digest=None,
            publication_status="generation_failed",
            error_code="generation_failed",
        )

    try:
        finalized_path, data, digest = _read_finalized_artifact(
            result,
            expected_outcome=normalized_outcome,
        )
    except PublicationError as error:
        return PublicationResult(
            run_id=run_id,
            generation_outcome=normalized_outcome,
            artifact_path=artifact_path,
            report_path=report_path,
            artifact_digest=None,
            report_digest=None,
            publication_status=error.code,
            error_code=error.code,
        )

    try:
        publication_status = _atomic_publish(data, report_path, digest)
    except PublicationError as error:
        return PublicationResult(
            run_id=run_id,
            generation_outcome=normalized_outcome,
            artifact_path=finalized_path,
            report_path=report_path,
            artifact_digest=digest,
            report_digest=_existing_report_digest(report_path),
            publication_status=error.code,
            error_code=error.code,
        )

    return PublicationResult(
        run_id=run_id,
        generation_outcome=normalized_outcome,
        artifact_path=finalized_path,
        report_path=report_path,
        artifact_digest=digest,
        report_digest=digest,
        publication_status=publication_status,
    )


def _runtime_failure_result(
    *,
    report_path: Path | None,
    error_code: str,
) -> PublicationResult:
    return PublicationResult(
        run_id=None,
        generation_outcome="failed",
        artifact_path=None,
        report_path=report_path,
        artifact_digest=None,
        report_digest=None,
        publication_status="runtime_failed",
        error_code=error_code,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    runtime_builder: Callable[..., Any] = build_generation_2_runtime,
    clock: Callable[[], datetime] | None = None,
) -> int:
    args = parse_args(argv)
    paths = get_project_paths(repo_root=PROJECT_ROOT, data_root=args.data_root)
    report_path: Path | None = None
    try:
        slot_options = {} if clock is None else {"clock": clock}
        slot = resolve_morning_brief_report_slot(args.date, **slot_options)
        report_path = paths.reports_dir / f"morning-brief-{slot.report_date.isoformat()}.md"
        runtime = runtime_builder(
            provider=DEEPSEEK_PROVIDER_ID,
            feeds_path=args.feeds,
            data_root=args.data_root,
            model_cache=args.model_cache,
        )
        run_options: dict[str, Any] = {"run_id": args.run_id}
        if clock is not None:
            run_options["clock"] = clock
        result = runtime.run(slot, **run_options)
    except Generation2RuntimeConfigurationError:
        output = _runtime_failure_result(
            report_path=report_path,
            error_code="runtime_configuration_failed",
        )
        print(json.dumps(output.to_dict(), ensure_ascii=False, sort_keys=True))
        return 2
    except Exception:
        output = _runtime_failure_result(report_path=report_path, error_code="runtime_failed")
        print(json.dumps(output.to_dict(), ensure_ascii=False, sort_keys=True))
        return 1

    publication = publish_generation_result(result, report_path=report_path)
    print(json.dumps(publication.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if publication.publication_status in SUCCESS_PUBLICATION_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FINALIZED_MARKDOWN_NAME",
    "PUBLISHABLE_OUTCOMES",
    "PublicationError",
    "PublicationResult",
    "main",
    "parse_args",
    "publish_generation_result",
]
