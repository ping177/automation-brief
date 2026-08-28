"""Generation 2 artifact and checkpoint persistence.

This module is deliberately small and domain-neutral.  It owns only the
filesystem lifecycle for one caller-supplied ``run_id``; semantic stages,
report identity, selection, writing, rendering, and delivery remain outside
the module.

The implementation is side-by-side with the Generation 1 artifact surface.
It borrows the repository's staging/atomic-write safety pattern without
reusing the legacy artifact schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Mapping
import uuid

from canonical_domain import (
    Brief,
    CONTRACT_VERSION,
    CanonicalContractError,
    StageName,
    StageResult,
    serialize_brief,
    serialize_domain,
    serialize_stage_result,
)
from project_paths import ProjectPaths, get_project_paths


ARTIFACT_SCHEMA_VERSION = "v1.6-artifact-schema"
ARTIFACT_ROOT_NAME = "event-driven-morning-brief"

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_DIAGNOSTIC_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_RUN_STATUSES = frozenset({"complete", "partial", "failed", "stopped"})

_STAGE_ORDER = {
    StageName.COLLECTOR.value: 1,
    StageName.NORMALIZER.value: 2,
    StageName.ARTICLE_DEDUP.value: 3,
    StageName.EVENT_CLUSTER.value: 4,
    StageName.EVENT_SELECTOR.value: 5,
    StageName.EVENT_CLASSIFIER.value: 6,
    StageName.EVENT_WRITER.value: 7,
    StageName.BRIEF_RENDERER.value: 8,
    StageName.DELIVERY.value: 9,
}

_DIAGNOSTIC_FIELDS = frozenset(
    {
        "code",
        "failure_code",
        "http_status",
        "reason",
        "status",
        "parse_reason",
        "validation_path",
        "provider",
        "provider_id",
        "model",
        "attempt",
        "duration_ms",
        "excluded_count",
        "source_ref",
        "article_ref",
        "event_ref",
        "batch_ref",
        "request_bytes",
        "response_bytes",
        "request_body_bytes",
        "response_body_bytes",
        "model_id",
        "model_revision",
        "projection_version",
        "clustering_algorithm_version",
        "edge_policy_version",
        "threshold",
        "base_similarity_floor",
        "high_confidence_threshold",
        "title_identity_min_span",
    }
)

_SENSITIVE_KEY_PARTS = (
    "authorization",
    "api_key",
    "apikey",
    "credential",
    "password",
    "secret",
    "token",
    "header",
    "environment",
    "env",
    "exception",
    "raw",
    "payload",
    "request",
    "response",
    "body",
)


class ArtifactError(RuntimeError):
    """Base class for safe artifact lifecycle errors."""


class ArtifactValidationError(ArtifactError, ValueError):
    """Raised when caller input cannot be safely represented."""


class ArtifactPersistenceError(ArtifactError):
    """Raised when a durable artifact/checkpoint operation fails."""


class DuplicateRunError(ArtifactError):
    """Raised when a run id is already finalized or still staged."""


class RunStateError(ArtifactError):
    """Raised when a finalized or broken run is used again."""


@dataclass(frozen=True)
class ArtifactPaths:
    """Paths published for one finalized Generation 2 run."""

    run_dir: Path
    manifest_path: Path
    stage_results_dir: Path
    objects_dir: Path
    diagnostics_dir: Path
    brief_json: Path
    markdown: Path

    @classmethod
    def from_run_dir(cls, run_dir: Path) -> "ArtifactPaths":
        resolved = Path(run_dir)
        return cls(
            run_dir=resolved,
            manifest_path=resolved / "manifest.json",
            stage_results_dir=resolved / "stage-results",
            objects_dir=resolved / "objects",
            diagnostics_dir=resolved / "diagnostics",
            brief_json=resolved / "brief.json",
            markdown=resolved / "morning-brief.md",
        )

@dataclass
class ArtifactRun:
    """Mutable handle for one staging run.

    The handle never creates a run id.  The future orchestrator supplies the
    id once and keeps it immutable for the lifetime of this handle.
    """

    manager: "V1ArtifactManager" = field(repr=False)
    run_id: str
    staging_dir: Path
    created_at: datetime
    _state: str = field(default="staging", init=False, repr=False)
    _artifact_broken: bool = field(default=False, init=False, repr=False)
    _warnings: list[dict[str, str]] = field(default_factory=list, init=False, repr=False)

    @property
    def final_dir(self) -> Path:
        return self.manager.artifact_root / self.run_id

    @property
    def run_dir(self) -> Path:
        return self.final_dir if self.is_finalized else self.staging_dir

    @property
    def manifest_path(self) -> Path:
        return (
            self.final_dir / "manifest.json"
            if self.is_finalized
            else self.staging_dir / "manifest.json"
        )

    @property
    def is_finalized(self) -> bool:
        return self._state == "finalized"

    def persist_stage_result(
        self,
        result: StageResult[Any],
        *,
        checkpoint_name: str | None = None,
        output_serializer: Callable[[Any], Any] | None = None,
        diagnostic_record: Mapping[str, Any] | None = None,
    ) -> Path:
        return self.manager._persist_stage_result(
            self,
            result,
            checkpoint_name=checkpoint_name,
            output_serializer=output_serializer,
            diagnostic_record=diagnostic_record,
        )

    def persist_objects(
        self,
        name: str,
        values: Iterable[Any],
    ) -> Path | None:
        return self.manager._persist_objects(self, name, values)

    def persist_diagnostic(
        self,
        record: Mapping[str, Any],
        *,
        diagnostic_ref: str | None = None,
    ) -> str:
        return self.manager._persist_diagnostic(
            self,
            record,
            diagnostic_ref=diagnostic_ref,
        )

    def persist_brief(self, brief: Brief, markdown: str) -> tuple[Path, Path]:
        return self.manager._persist_brief(self, brief, markdown)

    def finalize(
        self,
        *,
        run_status: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactPaths:
        return self.manager._finalize_run(
            self,
            run_status=run_status,
            metadata=metadata,
        )


class V1ArtifactManager:
    """Persist one Generation 2 run using staging and atomic publication."""

    def __init__(
        self,
        paths: ProjectPaths | None = None,
        *,
        data_root: Path | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if paths is not None and data_root is not None:
            raise ArtifactValidationError("provide paths or data_root, not both")
        self.paths = paths or get_project_paths(data_root=data_root)
        self.artifact_root = self.paths.runs_dir / ARTIFACT_ROOT_NAME
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def start_run(
        self,
        run_id: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ArtifactRun:
        """Create a durable staging run for a caller-supplied ``run_id``."""

        _validate_run_id(run_id)
        safe_metadata = _sanitize_runtime_mapping(metadata or {}, context="metadata")
        created_at = _utc_timestamp(now or self._clock())
        try:
            self.artifact_root.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError, TypeError):
            raise ArtifactPersistenceError("unable to create artifact root") from None

        final_dir = self.artifact_root / run_id
        if final_dir.exists():
            raise DuplicateRunError("run_id already finalized")
        staging_dir = self.artifact_root / f".{run_id}.staging"
        try:
            staging_dir.mkdir()
        except FileExistsError:
            raise DuplicateRunError("run_id has an existing staging run") from None
        except (OSError, ValueError, TypeError):
            raise ArtifactPersistenceError("unable to create artifact staging run") from None

        run = ArtifactRun(self, run_id, staging_dir, created_at)
        manifest = {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "contract_version": CONTRACT_VERSION,
            "run_id": run_id,
            "created_at": _datetime_text(created_at),
            "state": "staging",
            "run_status": None,
            "metadata": safe_metadata,
            "warnings": [],
            "files": {},
        }
        try:
            _atomic_write_json(run.manifest_path, manifest)
        except Exception:
            self._record_persistence_failure(run, "start_run")
            raise ArtifactPersistenceError("unable to persist artifact run manifest") from None
        return run

    def _persist_stage_result(
        self,
        run: ArtifactRun,
        result: StageResult[Any],
        *,
        checkpoint_name: str | None = None,
        output_serializer: Callable[[Any], Any] | None = None,
        diagnostic_record: Mapping[str, Any] | None = None,
    ) -> Path:
        """Durably persist a canonical ``StageResult`` before downstream use.

        If a diagnostic is supplied, the result is serialized with a ref only
        after the safe diagnostic file is durable.  The in-memory result is
        never mutated.
        """

        self._assert_active(run)
        if not isinstance(result, StageResult):
            raise ArtifactValidationError("persist_stage_result requires StageResult")
        stage_result = result
        resolved_checkpoint = _checkpoint_filename(checkpoint_name or stage_result.stage.value)
        persisted_result = stage_result
        requested_ref = stage_result.diagnostic_ref
        if diagnostic_record is not None:
            try:
                persisted_ref = self._persist_diagnostic(
                    run,
                    diagnostic_record,
                    diagnostic_ref=requested_ref,
                )
            except (ArtifactValidationError, ArtifactPersistenceError):
                run._warnings.append(
                    {
                        "kind": "diagnostic",
                        "stage": stage_result.stage.value,
                        "code": "persistence_failed",
                    }
                )
                persisted_ref = None
            # A supplied diagnostic is the only authority for retaining the
            # linkage.  On any diagnostic failure, force the persisted copy to
            # carry no ref rather than leaving a dangling original value.
            requested_ref = persisted_ref
        elif requested_ref is not None and not self._diagnostic_is_durable(run, requested_ref):
            requested_ref = None

        if requested_ref != stage_result.diagnostic_ref:
            persisted_result = replace(stage_result, diagnostic_ref=requested_ref)

        path = run.staging_dir / "stage-results" / f"{resolved_checkpoint}.json"
        try:
            encoded = serialize_stage_result(
                persisted_result,
                output_serializer=_stage_output_serializer(output_serializer),
            )
            _reject_sensitive_payload(_decode_json_value(encoded))
            self._write_new_artifact(path, encoded)
        except ArtifactPersistenceError:
            self._record_persistence_failure(run, f"stage_result:{resolved_checkpoint}")
            raise
        except (CanonicalContractError, TypeError, ValueError, OverflowError):
            self._record_persistence_failure(run, f"stage_result:{resolved_checkpoint}")
            raise ArtifactPersistenceError("stage result serialization failed") from None
        return path

    def _persist_objects(
        self,
        run: ArtifactRun,
        name: str,
        values: Iterable[Any],
    ) -> Path | None:
        """Persist a non-empty ordered collection of canonical domain objects."""

        self._assert_active(run)
        filename = _artifact_filename(name)
        if isinstance(values, (str, bytes)):
            raise ArtifactValidationError("object values must be iterable")
        try:
            items = tuple(values)
        except TypeError:
            raise ArtifactValidationError("object values must be iterable") from None
        if not items:
            return None

        entries: list[Any] = []
        try:
            for item in items:
                encoded = serialize_domain(item)
                entry = _decode_json_value(encoded)
                _validate_json_value(entry)
                entries.append(entry)
        except ArtifactValidationError:
            raise
        except (CanonicalContractError, TypeError, ValueError, OverflowError):
            raise ArtifactValidationError("object collection must contain canonical domain objects") from None

        payload: dict[str, Any] = {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "artifact_type": "canonical_objects",
            "objects": entries,
        }

        path = run.staging_dir / "objects" / filename
        try:
            self._write_new_artifact(path, _json_bytes(payload))
        except ArtifactPersistenceError:
            self._record_persistence_failure(run, f"objects:{filename}")
            raise
        return path

    def _persist_diagnostic(
        self,
        run: ArtifactRun,
        record: Mapping[str, Any],
        *,
        diagnostic_ref: str | None = None,
    ) -> str:
        """Persist an allowlisted diagnostic and return its opaque ref."""

        self._assert_active(run)
        if not isinstance(record, Mapping):
            raise ArtifactValidationError("diagnostic record must be an object")
        safe_record = _sanitize_diagnostic_mapping(record)
        resolved_ref = _validate_or_create_diagnostic_ref(diagnostic_ref, safe_record)
        payload = {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "diagnostic_ref": resolved_ref,
            "record": safe_record,
        }
        path = run.staging_dir / "diagnostics" / _diagnostic_filename(resolved_ref)
        encoded = _json_bytes(payload)
        if path.exists():
            try:
                if path.read_bytes() == encoded:
                    return resolved_ref
            except OSError:
                raise ArtifactPersistenceError("unable to verify existing diagnostic") from None
            raise ArtifactPersistenceError("diagnostic ref already has different content")
        try:
            self._write_new_artifact(path, encoded)
        except ArtifactPersistenceError:
            raise
        return resolved_ref

    def _persist_brief(self, run: ArtifactRun, brief: Brief, markdown: str) -> tuple[Path, Path]:
        """Persist the canonical Brief and opaque reader-facing Markdown."""

        self._assert_active(run)
        if not isinstance(brief, Brief):
            raise ArtifactValidationError("brief must be canonical Brief")
        if not isinstance(markdown, str):
            raise ArtifactValidationError("markdown must be text")
        brief_path = run.staging_dir / "brief.json"
        markdown_path = run.staging_dir / "morning-brief.md"
        try:
            self._write_new_artifact(brief_path, serialize_brief(brief))
            self._write_new_artifact(markdown_path, markdown.encode("utf-8"))
        except ArtifactPersistenceError:
            self._record_persistence_failure(run, "brief")
            raise
        except (CanonicalContractError, TypeError, ValueError, UnicodeError):
            self._record_persistence_failure(run, "brief")
            raise ArtifactPersistenceError("brief serialization failed") from None
        return brief_path, markdown_path

    def _finalize_run(
        self,
        run: ArtifactRun,
        *,
        run_status: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactPaths:
        """Verify staged files and atomically publish an immutable run dir."""

        self._assert_active(run)
        if run._artifact_broken:
            raise ArtifactPersistenceError("artifact run has an unresolved persistence failure")
        resolved_status = _safe_status(run_status)
        extra_metadata = _sanitize_runtime_mapping(metadata or {}, context="metadata")
        try:
            manifest = json.loads(run.manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or manifest.get("state") != "staging":
                raise ArtifactPersistenceError("staging manifest is invalid")
            if resolved_status in {"complete", "partial"} and not (
                (run.staging_dir / "brief.json").is_file()
                and (run.staging_dir / "morning-brief.md").is_file()
            ):
                raise ArtifactPersistenceError(
                    "publishable run status requires brief.json and morning-brief.md"
                )
            merged_metadata = dict(manifest.get("metadata") or {})
            merged_metadata.update(extra_metadata)
            file_records = _file_integrity_records(run.staging_dir)
            manifest.update(
                {
                    "state": "finalized",
                    "run_status": resolved_status,
                    "finalized_at": _datetime_text(_utc_timestamp(self._clock())),
                    "metadata": merged_metadata,
                    "warnings": sorted(run._warnings, key=lambda item: (item["kind"], item["stage"], item["code"])),
                    "files": file_records,
                }
            )
            _atomic_write_json(run.manifest_path, manifest)
            _verify_integrity(run.staging_dir, manifest)
            final_dir = run.final_dir
            if final_dir.exists():
                raise DuplicateRunError("run_id already finalized")
            os.replace(run.staging_dir, final_dir)
            _fsync_directory(self.artifact_root)
        except DuplicateRunError:
            self._record_persistence_failure(run, "finalize_duplicate")
            raise
        except ArtifactPersistenceError:
            self._record_persistence_failure(run, "finalize")
            raise
        except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError):
            self._record_persistence_failure(run, "finalize")
            raise ArtifactPersistenceError("artifact finalization failed") from None
        run._state = "finalized"
        return ArtifactPaths.from_run_dir(run.final_dir)

    def _assert_active(self, run: ArtifactRun) -> None:
        if not isinstance(run, ArtifactRun) or run.manager is not self:
            raise RunStateError("run handle does not belong to this manager")
        if run._state != "staging":
            raise RunStateError("artifact run is not staging")
        if run._artifact_broken:
            raise ArtifactPersistenceError("artifact run has an unresolved persistence failure")
        if not run.staging_dir.exists():
            raise RunStateError("staging directory is unavailable")

    def _write_new_artifact(self, path: Path, data: bytes) -> None:
        if path.exists():
            raise ArtifactPersistenceError("artifact path already exists")
        try:
            _atomic_write(path, data)
        except ArtifactPersistenceError:
            raise
        except Exception:
            # Keep injected/low-level I/O details out of the public error and
            # preserve the caller-visible persistence failure semantics.
            raise ArtifactPersistenceError("atomic artifact write failed") from None

    def _diagnostic_is_durable(self, run: ArtifactRun, diagnostic_ref: str) -> bool:
        try:
            resolved_ref = _validate_diagnostic_ref(diagnostic_ref)
        except ArtifactValidationError:
            return False
        path = run.staging_dir / "diagnostics" / _diagnostic_filename(resolved_ref)
        if not path.is_file():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return False
        return isinstance(payload, Mapping) and payload.get("diagnostic_ref") == resolved_ref

    def _record_persistence_failure(self, run: ArtifactRun, operation: str) -> None:
        run._artifact_broken = True
        evidence = {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "kind": "artifact_persistence_failure",
            "operation": _safe_one_line(operation),
            "code": "persistence_failed",
            "recorded_at": _datetime_text(_utc_timestamp(self._clock())),
        }
        try:
            manifest_path = run.staging_dir / "manifest.json"
            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if isinstance(manifest, dict):
                    manifest.update(
                        {
                            "state": "failed",
                            "run_status": "persistence_failed",
                            "files": {},
                        }
                    )
                    _atomic_write_json(manifest_path, manifest)
        except Exception:
            pass
        try:
            _atomic_write_json(run.staging_dir / "failure.json", evidence)
        except Exception:
            # The original persistence error remains the caller-visible error;
            # no raw exception text is copied into a recovery artifact.
            pass


def _stage_output_serializer(
    serializer: Callable[[Any], Any] | None,
) -> Callable[[Any], Any] | None:
    if serializer is None:
        return None

    def serialize_output(value: Any) -> Any:
        return _decode_json_value(serializer(value))

    return serialize_output


def _checkpoint_filename(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArtifactValidationError("checkpoint name must be non-empty")
    raw = value.strip()
    if raw.endswith(".json"):
        raw = raw[:-5]
    if not _NAME_PATTERN.fullmatch(raw.replace("-", "_")):
        raise ArtifactValidationError("checkpoint name must be filesystem-safe")
    if raw in _STAGE_ORDER:
        return f"{_STAGE_ORDER[raw]:02d}-{raw.replace('_', '-')}"
    if re.fullmatch(r"\d{2}-[A-Za-z0-9][A-Za-z0-9_.-]*", raw):
        return raw
    return raw


def _artifact_filename(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArtifactValidationError("artifact name must be non-empty")
    filename = value.strip()
    if filename.endswith(".json"):
        filename = filename[:-5]
    if not _NAME_PATTERN.fullmatch(filename):
        raise ArtifactValidationError("artifact name must be filesystem-safe")
    return f"{filename}.json"


def _validate_run_id(run_id: str) -> None:
    if not isinstance(run_id, str) or not _RUN_ID_PATTERN.fullmatch(run_id):
        raise ArtifactValidationError("run_id must be filesystem-safe")


def _validate_diagnostic_ref(value: str) -> str:
    if not isinstance(value, str) or not _DIAGNOSTIC_REF_PATTERN.fullmatch(value):
        raise ArtifactValidationError("diagnostic_ref must be a bounded opaque token")
    return value


def _validate_or_create_diagnostic_ref(
    value: str | None,
    safe_record: Mapping[str, Any],
) -> str:
    if value is not None:
        return _validate_diagnostic_ref(value)
    return f"diag_{hashlib.sha256(_json_bytes(safe_record)).hexdigest()[:24]}"


def _diagnostic_filename(diagnostic_ref: str) -> str:
    digest = hashlib.sha256(diagnostic_ref.encode("utf-8")).hexdigest()[:24]
    return f"diag-{digest}.json"


def _utc_timestamp(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ArtifactValidationError("artifact timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _datetime_text(value: datetime) -> str:
    return _utc_timestamp(value).isoformat()


def _safe_status(value: str) -> str:
    if not isinstance(value, str) or value not in _RUN_STATUSES:
        raise ArtifactValidationError("run_status must be complete, partial, failed, or stopped")
    return value


def _safe_one_line(value: Any, limit: int = 256) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    return text[:limit]


def _is_sensitive_key(key: str) -> bool:
    lower = key.lower()
    if lower.endswith("_bytes"):
        return False
    return any(part in lower for part in _SENSITIVE_KEY_PARTS)


def _sanitize_runtime_mapping(
    value: Mapping[str, Any], *, context: str, depth: int = 0
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ArtifactValidationError(f"{context} must be an object")
    if depth > 3:
        raise ArtifactValidationError("runtime metadata is too deeply nested")
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not _KEY_PATTERN.fullmatch(key) or _is_sensitive_key(key):
            raise ArtifactValidationError(f"{context} contains a non-allowlisted key")
        sanitized[key] = _sanitize_runtime_value(item, depth=depth)
    return sanitized


def _sanitize_runtime_value(value: Any, *, depth: int) -> Any:
    if depth > 3:
        raise ArtifactValidationError("runtime metadata is too deeply nested")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        if abs(value) > 10**12:
            raise ArtifactValidationError("runtime numeric metadata is out of bounds")
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or abs(value) > 10**12:
            raise ArtifactValidationError("runtime numeric metadata is out of bounds")
        return value
    if isinstance(value, str):
        return _safe_one_line(value)
    if isinstance(value, Mapping):
        return _sanitize_runtime_mapping(value, context="nested metadata", depth=depth + 1)
    if isinstance(value, (list, tuple)):
        if len(value) > 64:
            raise ArtifactValidationError("runtime metadata list is out of bounds")
        return [_sanitize_runtime_value(item, depth=depth + 1) for item in value]
    raise ArtifactValidationError("runtime metadata value is not safely serializable")


def _sanitize_diagnostic_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ArtifactValidationError("diagnostic record must be an object")
    safe: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or key not in _DIAGNOSTIC_FIELDS:
            raise ArtifactValidationError("diagnostic field is not allowlisted")
        if key.endswith("_bytes") or key in {
            "attempt",
            "excluded_count",
            "http_status",
        }:
            if isinstance(item, bool) or not isinstance(item, int) or item < 0 or item > 10**9:
                raise ArtifactValidationError("diagnostic count must be a bounded non-negative integer")
            safe[key] = item
        elif key == "duration_ms":
            if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
                raise ArtifactValidationError("diagnostic duration must be finite")
            if item < 0 or item > 10**9:
                raise ArtifactValidationError("diagnostic duration is out of bounds")
            safe[key] = item
        elif key in {
            "threshold",
            "base_similarity_floor",
            "high_confidence_threshold",
        }:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ArtifactValidationError("diagnostic threshold must be numeric")
            if not math.isfinite(float(item)) or not -1 <= item <= 1:
                raise ArtifactValidationError("diagnostic threshold is out of bounds")
            safe[key] = float(item)
        elif key == "title_identity_min_span":
            if isinstance(item, bool) or not isinstance(item, int) or not 1 <= item <= 256:
                raise ArtifactValidationError("diagnostic span must be a bounded positive integer")
            safe[key] = item
        elif not isinstance(item, str):
            raise ArtifactValidationError("diagnostic text metadata must be text")
        else:
            safe[key] = _safe_one_line(item)
    return safe


def _json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise ArtifactValidationError("value is not deterministically serializable") from None


def _decode_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, (bytes, bytearray)):
        try:
            return json.loads(bytes(value).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            raise ArtifactValidationError("serialized object is not valid JSON") from None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _validate_json_value(value: Any, *, depth: int = 0) -> None:
    if depth > 8:
        raise ArtifactValidationError("serialized object is too deeply nested")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ArtifactValidationError("serialized object contains a non-finite number")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ArtifactValidationError("serialized object keys must be text")
            _validate_json_value(item, depth=depth + 1)
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item, depth=depth + 1)
        return
    raise ArtifactValidationError("serialized object is not JSON-compatible")


def _reject_sensitive_payload(value: Any, *, depth: int = 0) -> None:
    """Reject secret/raw-provider-shaped keys in caller-projected payloads."""

    if depth > 8:
        raise ArtifactValidationError("serialized object is too deeply nested")
    if isinstance(value, Mapping):
        if {"contract_version", "object_type", "payload"}.issubset(value):
            _reject_sensitive_payload(value["payload"], depth=depth + 1)
            return
        for key, item in value.items():
            if isinstance(key, str) and _is_sensitive_key(key):
                raise ArtifactValidationError("serialized object contains a sensitive field")
            _reject_sensitive_payload(item, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            _reject_sensitive_payload(item, depth=depth + 1)


def _file_integrity_records(staging_dir: Path) -> dict[str, dict[str, int | str]]:
    records: dict[str, dict[str, int | str]] = {}
    for path in sorted(staging_dir.rglob("*")):
        if not path.is_file() or path.name in {"manifest.json", "failure.json"}:
            continue
        if path.name.startswith(".") and ".tmp-" in path.name:
            raise ArtifactPersistenceError("staging contains an incomplete temporary file")
        try:
            data = path.read_bytes()
        except OSError:
            raise ArtifactPersistenceError("staged artifact could not be read for integrity verification") from None
        relative = path.relative_to(staging_dir).as_posix()
        records[relative] = {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    return records


def _verify_integrity(staging_dir: Path, manifest: Mapping[str, Any]) -> None:
    if manifest.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise ArtifactPersistenceError("manifest schema integrity check failed")
    expected = manifest.get("files")
    if not isinstance(expected, Mapping):
        raise ArtifactPersistenceError("manifest file index is invalid")
    actual = _file_integrity_records(staging_dir)
    if dict(expected) != actual:
        raise ArtifactPersistenceError("staged artifact integrity check failed")
    for relative, record in expected.items():
        if not isinstance(relative, str) or not isinstance(record, Mapping):
            raise ArtifactPersistenceError("manifest file record is invalid")
        path = staging_dir / relative
        if not path.is_file():
            raise ArtifactPersistenceError("manifest references a missing artifact")
        if record.get("bytes") != path.stat().st_size:
            raise ArtifactPersistenceError("artifact byte count integrity check failed")
        if record.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ArtifactPersistenceError("artifact digest integrity check failed")


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_write(path, _json_bytes(payload))


def _atomic_write(path: Path, data: bytes) -> None:
    """Write one file durably, then atomically replace its target."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.tmp-{uuid.uuid4().hex[:12]}"
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    except (OSError, TypeError, ValueError):
        try:
            temporary.unlink()
        except OSError:
            pass
        raise ArtifactPersistenceError("atomic artifact write failed") from None


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


__all__ = [
    "ARTIFACT_ROOT_NAME",
    "ARTIFACT_SCHEMA_VERSION",
    "ArtifactError",
    "ArtifactPaths",
    "ArtifactPersistenceError",
    "ArtifactRun",
    "ArtifactValidationError",
    "DuplicateRunError",
    "RunStateError",
    "V1ArtifactManager",
]
