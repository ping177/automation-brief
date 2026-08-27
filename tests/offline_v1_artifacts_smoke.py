"""Offline smoke tests for the Generation 2 artifact/checkpoint seam.

The smoke intentionally uses a temporary canonical data root.  It is a
direct-script test (not pytest) and never imports Generation 1 routing,
delivery, provider, or legacy artifact schemas.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from canonical_domain import (  # noqa: E402
    Article,
    Brief,
    Event,
    EventCandidate,
    EventWriting,
    FailureCode,
    GenerationStatus,
    ItemFailure,
    StageName,
    StageResult,
    StageStatus,
    CONTRACT_VERSION,
    deserialize_brief,
    deserialize_domain,
    deserialize_stage_result,
)
from project_paths import ProjectPaths  # noqa: E402
from v1_artifacts import (  # noqa: E402
    ARTIFACT_ROOT_NAME,
    ArtifactPersistenceError,
    ArtifactValidationError,
    DuplicateRunError,
    RunStateError,
    V1ArtifactManager,
)


REPORT_DATE = date(2026, 8, 27)
WINDOW_START = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc)
COLLECTED_AT = datetime(2026, 8, 27, 1, 0, tzinfo=timezone.utc)
CREATED_AT = datetime(2026, 8, 27, 2, 3, 4, 500000, tzinfo=timezone.utc)


def article(key: str) -> Article:
    return Article.from_source(
        source=f"Fixture Source {key}",
        url=f"https://fixture.example/{key}",
        published_at=COLLECTED_AT,
        collected_at=COLLECTED_AT,
        language="en",
        title=f"Fixture article {key}",
        summary=f"Fixture summary {key}.",
    )


def event_for(item: Article, order: int = 1) -> Event:
    candidate = EventCandidate.from_article_ids((item.article_id,))
    return Event.from_candidate(candidate, selection_order=order).with_writing(
        EventWriting(
            title_zh="固定中文标题",
            summary_zh="固定中文摘要。",
            why_it_matters_zh="固定重要性说明。",
        )
    )


def brief_for(event: Event, status: GenerationStatus = GenerationStatus.COMPLETE) -> Brief:
    return Brief.from_report_slot(
        report_date=REPORT_DATE,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        event_ids=(event.event_id,),
        generation_status=status,
    )


def success(stage: StageName, *outputs: object) -> StageResult[object]:
    return StageResult(stage=stage, status=StageStatus.SUCCEEDED, outputs=outputs)


def failure(stage: StageName, item_id: str | None = None) -> StageResult[object]:
    return StageResult(
        stage=stage,
        status=StageStatus.FAILED,
        failures=(ItemFailure(item_id=item_id, code=FailureCode.TIMEOUT),),
    )


def manager_for(root: Path) -> V1ArtifactManager:
    return V1ArtifactManager(
        ProjectPaths(repo_root=PROJECT_ROOT, data_root=root),
        clock=lambda: CREATED_AT,
    )


def test_staging_manifest_and_canonical_round_trip(fixture_dir: Path) -> None:
    manager = manager_for(fixture_dir / "data")
    item = article("round-trip")
    event = event_for(item)
    brief = brief_for(event)
    run = manager.start_run("20260827T020304.500000Z-roundtrip", metadata={"report_date": REPORT_DATE.isoformat()})

    assert run.staging_dir.parent == manager.artifact_root
    assert run.staging_dir.name == ".20260827T020304.500000Z-roundtrip.staging"
    assert not run.final_dir.exists()
    assert json.loads(run.manifest_path.read_text(encoding="utf-8"))["state"] == "staging"

    articles_path = run.persist_objects("articles", (item,))
    events_path = run.persist_objects("events-written", (event,))
    stage_path = run.persist_stage_result(success(StageName.EVENT_WRITER, event))
    brief_json, markdown = run.persist_brief(brief, "# 固定简报\n")
    final = run.finalize(run_status="complete")

    assert final.run_dir == manager.artifact_root / run.run_id
    assert final.run_dir.is_dir()
    assert final.manifest_path == final.run_dir / "manifest.json"
    assert articles_path is not None and articles_path.name == "articles.json"
    assert events_path is not None and events_path.name == "events-written.json"
    assert stage_path.name == "07-event-writer.json"
    assert brief_json.name == "brief.json"
    assert markdown.name == "morning-brief.md"
    assert not (fixture_dir / "data" / "reports").exists()

    loaded_brief = deserialize_brief(final.brief_json.read_bytes())
    assert loaded_brief == brief
    loaded_stage = deserialize_stage_result(
        (final.run_dir / "stage-results/07-event-writer.json").read_bytes(),
        output_loader=Event.from_dict,
    )
    assert loaded_stage == success(StageName.EVENT_WRITER, event)
    article_collection = json.loads((final.run_dir / "objects/articles.json").read_text(encoding="utf-8"))
    event_collection = json.loads((final.run_dir / "objects/events-written.json").read_text(encoding="utf-8"))
    assert "contract_version" not in article_collection
    assert "object_type" not in article_collection
    assert all(entry["contract_version"] == CONTRACT_VERSION for entry in article_collection["objects"])
    assert tuple(deserialize_domain(entry) for entry in article_collection["objects"]) == (item,)
    assert tuple(deserialize_domain(entry) for entry in event_collection["objects"]) == (event,)
    manifest = json.loads(final.manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == run.run_id
    assert manifest["state"] == "finalized"
    assert manifest["run_status"] == "complete"
    assert manifest["files"]["brief.json"]["sha256"]
    assert manifest["files"]["morning-brief.md"]["bytes"] == len("# 固定简报\n".encode("utf-8"))

    # A second run with the same canonical inputs produces byte-identical
    # checkpoint/object/brief artifacts; only its caller-owned run identity
    # differs.
    second_run = manager.start_run("20260827T020304.500000Z-roundtrip-2")
    second_run.persist_objects("articles", (item,))
    second_run.persist_objects("events-written", (event,))
    second_run.persist_stage_result(success(StageName.EVENT_WRITER, event))
    second_run.persist_brief(brief, "# 固定简报\n")
    second_final = second_run.finalize(run_status="complete")
    for relative in (
        "objects/articles.json",
        "objects/events-written.json",
        "stage-results/07-event-writer.json",
        "brief.json",
        "morning-brief.md",
    ):
        assert (final.run_dir / relative).read_bytes() == (second_final.run_dir / relative).read_bytes()


def test_business_stage_failure_keeps_earlier_checkpoints_without_downstream_fakes(fixture_dir: Path) -> None:
    manager = manager_for(fixture_dir / "data")
    item = article("business-failure")
    run = manager.start_run("business-failure")
    earlier = run.persist_stage_result(success(StageName.COLLECTOR, "source-batch"))
    failed_selector = run.persist_stage_result(failure(StageName.EVENT_SELECTOR))
    final = run.finalize(run_status="failed")

    assert earlier.name == "01-collector.json"
    assert failed_selector.name == "05-event-selector.json"
    assert (final.run_dir / "stage-results/01-collector.json").exists()
    assert (final.run_dir / "stage-results/05-event-selector.json").exists()
    assert not (final.run_dir / "stage-results/06-event-classifier.json").exists()
    assert not (final.run_dir / "stage-results/07-event-writer.json").exists()
    assert not (final.run_dir / "brief.json").exists()
    assert not (final.run_dir / "objects/articles.json").exists()


def test_finalized_run_is_immutable_and_duplicate_run_id_fails_closed(fixture_dir: Path) -> None:
    manager = manager_for(fixture_dir / "data")
    run = manager.start_run("immutable")
    try:
        manager.start_run("immutable")
    except DuplicateRunError:
        pass
    else:
        raise AssertionError("active staging claim allowed a duplicate run_id")
    run.persist_stage_result(success(StageName.COLLECTOR, "batch"))
    final = run.finalize(run_status="failed")
    before = final.manifest_path.read_bytes()

    try:
        run.persist_stage_result(success(StageName.NORMALIZER, "article"))
    except RunStateError:
        pass
    else:
        raise AssertionError("finalized run accepted a new checkpoint")
    assert final.manifest_path.read_bytes() == before

    try:
        manager.start_run("immutable")
    except DuplicateRunError:
        pass
    else:
        raise AssertionError("duplicate run_id was accepted")


def test_checkpoint_write_failure_leaves_non_publishable_staging_evidence(fixture_dir: Path) -> None:
    manager = manager_for(fixture_dir / "data")
    run = manager.start_run("checkpoint-write-failure")

    original_atomic_write = __import__("v1_artifacts")._atomic_write

    def fail_checkpoint(path: Path, data: bytes) -> None:
        if path.parent.name == "stage-results":
            raise OSError("do not expose this")
        original_atomic_write(path, data)

    with patch("v1_artifacts._atomic_write", side_effect=fail_checkpoint):
        try:
            run.persist_stage_result(success(StageName.COLLECTOR, "batch"))
        except ArtifactPersistenceError:
            pass
        else:
            raise AssertionError("checkpoint persistence failure was swallowed")

    assert not run.final_dir.exists()
    assert run.staging_dir.exists()
    evidence = run.staging_dir / "failure.json"
    assert evidence.exists()
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["kind"] == "artifact_persistence_failure"
    assert "do not expose" not in evidence.read_text(encoding="utf-8")
    try:
        run.finalize(run_status="failed")
    except ArtifactPersistenceError:
        pass
    else:
        raise AssertionError("broken staging run was finalized")


def test_finalization_failure_does_not_publish_final_directory(fixture_dir: Path) -> None:
    manager = manager_for(fixture_dir / "data")
    run = manager.start_run("finalization-failure")
    run.persist_stage_result(success(StageName.COLLECTOR, "batch"))
    original_replace = __import__("v1_artifacts").os.replace

    def fail_publish(source: str | bytes | Path, destination: str | bytes | Path) -> None:
        if Path(source) == run.staging_dir and Path(destination) == run.final_dir:
            raise OSError("publish failure must stay safe")
        original_replace(source, destination)

    with patch("v1_artifacts.os.replace", side_effect=fail_publish):
        try:
            run.finalize(run_status="failed")
        except ArtifactPersistenceError:
            pass
        else:
            raise AssertionError("finalization failure was swallowed")

    assert not run.final_dir.exists()
    assert run.staging_dir.exists()
    assert (run.staging_dir / "failure.json").exists()


def test_recovery_write_failure_does_not_replace_primary_persistence_error(fixture_dir: Path) -> None:
    manager = manager_for(fixture_dir / "data")
    run = manager.start_run("recovery-write-failure")

    with patch("v1_artifacts._atomic_write", side_effect=OSError("all writes unavailable")):
        try:
            run.persist_stage_result(success(StageName.COLLECTOR, "batch"))
        except ArtifactPersistenceError as exc:
            assert "all writes unavailable" not in str(exc)
        else:
            raise AssertionError("primary persistence failure was swallowed")

    assert not run.final_dir.exists()
    assert run.staging_dir.exists()
    assert not (run.staging_dir / "failure.json").exists()


def test_publishable_status_requires_brief_and_markdown(fixture_dir: Path) -> None:
    manager = manager_for(fixture_dir / "data")
    for run_status in ("complete", "partial"):
        run = manager.start_run(f"missing-brief-{run_status}")
        try:
            run.finalize(run_status=run_status)
        except ArtifactPersistenceError:
            pass
        else:
            raise AssertionError(f"{run_status} run finalized without Brief artifacts")
        assert not run.final_dir.exists()

    invalid = manager.start_run("invalid-status")
    try:
        invalid.finalize(run_status="finalized")
    except ArtifactValidationError:
        pass
    else:
        raise AssertionError("filesystem lifecycle state was accepted as a generation outcome")


def test_safe_diagnostic_ref_is_persisted_only_after_safe_record(fixture_dir: Path) -> None:
    manager = manager_for(fixture_dir / "data")
    run = manager.start_run("diagnostic-safe")
    diagnostic_ref = run.persist_diagnostic(
        {
            "provider": "fixture-provider",
            "model": "fixture-model",
            "attempt": 2,
            "duration_ms": 125,
            "status": "response_parse_failed",
            "parse_reason": "invalid_shape",
            "event_ref": "evt_fixture",
            "request_bytes": 123,
            "response_bytes": 456,
        },
        diagnostic_ref="llm_gateway:parse_failed",
    )
    result = StageResult(
        stage=StageName.EVENT_WRITER,
        status=StageStatus.FAILED,
        failures=(ItemFailure(code=FailureCode.RESPONSE_PARSE_FAILED),),
        diagnostic_ref=diagnostic_ref,
    )
    stage_path = run.persist_stage_result(result)
    payload = json.loads(stage_path.read_text(encoding="utf-8"))
    assert payload["payload"]["diagnostic_ref"] == diagnostic_ref
    diagnostic_files = list(run.staging_dir.joinpath("diagnostics").glob("*.json"))
    assert len(diagnostic_files) == 1
    diagnostic_text = diagnostic_files[0].read_text(encoding="utf-8")
    assert "fixture-provider" in diagnostic_text
    assert "Authorization" not in diagnostic_text
    assert "api-key" not in diagnostic_text


def test_diagnostic_persistence_failure_strips_ref_without_dangling_link(fixture_dir: Path) -> None:
    manager = manager_for(fixture_dir / "data")
    run = manager.start_run("diagnostic-failure")
    result = StageResult(
        stage=StageName.EVENT_WRITER,
        status=StageStatus.FAILED,
        failures=(ItemFailure(code=FailureCode.PROVIDER_FAILED),),
        diagnostic_ref="llm_gateway:provider_failed",
    )
    original_atomic_write = __import__("v1_artifacts")._atomic_write

    def fail_diagnostic(path: Path, data: bytes) -> None:
        if path.parent.name == "diagnostics":
            raise OSError("diagnostic I/O must not leak")
        original_atomic_write(path, data)

    with patch("v1_artifacts._atomic_write", side_effect=fail_diagnostic):
        stage_path = run.persist_stage_result(
            result,
            diagnostic_record={"provider": "fixture", "status": "provider_failed"},
        )

    persisted = json.loads(stage_path.read_text(encoding="utf-8"))
    assert persisted["payload"]["diagnostic_ref"] is None
    assert result.diagnostic_ref == "llm_gateway:provider_failed"
    assert not (run.staging_dir / "diagnostics").exists()
    final = run.finalize(run_status="failed")
    manifest = json.loads(final.manifest_path.read_text(encoding="utf-8"))
    assert manifest["warnings"] == [
        {"code": "persistence_failed", "kind": "diagnostic", "stage": "event_writer"}
    ]


def test_forbidden_diagnostic_fields_are_rejected_and_not_written(fixture_dir: Path) -> None:
    manager = manager_for(fixture_dir / "data")
    run = manager.start_run("diagnostic-rejected")
    try:
        run.persist_diagnostic(
            {"Authorization": "Bearer secret"},
            diagnostic_ref="bad-diagnostic",
        )
    except ArtifactValidationError:
        pass
    else:
        raise AssertionError("forbidden diagnostic field was accepted")
    assert not (run.staging_dir / "diagnostics").exists()


def test_empty_object_collection_does_not_create_fake_checkpoint(fixture_dir: Path) -> None:
    manager = manager_for(fixture_dir / "data")
    run = manager.start_run("empty-objects")
    assert run.persist_objects("articles", ()) is None
    run.persist_stage_result(success(StageName.COLLECTOR))
    final = run.finalize(run_status="failed")
    assert not (final.run_dir / "objects/articles.json").exists()
    assert (final.run_dir / "stage-results/01-collector.json").exists()


def test_stage_output_serializer_is_retained_but_object_store_is_canonical_only(fixture_dir: Path) -> None:
    manager = manager_for(fixture_dir / "data")
    run = manager.start_run("serializer-boundary")
    source_batch = object()
    checkpoint = run.persist_stage_result(
        success(StageName.COLLECTOR, source_batch),
        checkpoint_name="01-collector-batch-01",
        output_serializer=lambda value: {"source_ref": "fixture"} if value is source_batch else None,
    )
    persisted = deserialize_stage_result(checkpoint.read_bytes())
    assert persisted.outputs == ({"source_ref": "fixture"},)

    try:
        run.persist_objects("non-canonical", (source_batch,))
    except ArtifactValidationError:
        pass
    else:
        raise AssertionError("object store accepted a non-canonical object")
    assert not (run.staging_dir / "objects/non-canonical.json").exists()


def test_artifact_module_is_generation_two_domain_neutral() -> None:
    source = (PROJECT_ROOT / "v1_artifacts.py").read_text(encoding="utf-8")
    for forbidden_module in (
        "event_selector",
        "event_classifier",
        "event_writer",
        "llm_gateway",
        "ai_curator",
        "overnight_brief_writer",
        "main",
        "market_brief_writer",
    ):
        assert f"import {forbidden_module}" not in source
        assert f"from {forbidden_module}" not in source
    assert ARTIFACT_ROOT_NAME == "event-driven-morning-brief"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="automation-brief-v1-artifacts-", dir="/private/tmp") as temp_dir:
        fixture_dir = Path(temp_dir)
        test_staging_manifest_and_canonical_round_trip(fixture_dir)
        test_business_stage_failure_keeps_earlier_checkpoints_without_downstream_fakes(fixture_dir)
        test_finalized_run_is_immutable_and_duplicate_run_id_fails_closed(fixture_dir)
        test_checkpoint_write_failure_leaves_non_publishable_staging_evidence(fixture_dir)
        test_finalization_failure_does_not_publish_final_directory(fixture_dir)
        test_recovery_write_failure_does_not_replace_primary_persistence_error(fixture_dir)
        test_publishable_status_requires_brief_and_markdown(fixture_dir)
        test_safe_diagnostic_ref_is_persisted_only_after_safe_record(fixture_dir)
        test_diagnostic_persistence_failure_strips_ref_without_dangling_link(fixture_dir)
        test_forbidden_diagnostic_fields_are_rejected_and_not_written(fixture_dir)
        test_empty_object_collection_does_not_create_fake_checkpoint(fixture_dir)
        test_stage_output_serializer_is_retained_but_object_store_is_canonical_only(fixture_dir)
        test_artifact_module_is_generation_two_domain_neutral()
    print("offline v1 artifacts smoke passed")


if __name__ == "__main__":
    main()
