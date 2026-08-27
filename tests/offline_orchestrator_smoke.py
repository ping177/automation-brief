"""Offline smoke tests for Generation 2 orchestration composition."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Callable, Mapping, Sequence
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from brief_renderer import BriefRenderResult  # noqa: E402
from canonical_domain import (  # noqa: E402
    FailureCode,
    GenerationStatus,
    ItemFailure,
    StageName,
    StageResult,
    StageStatus,
)
from collector import SourceConfig  # noqa: E402
from llm_gateway import GatewayError  # noqa: E402
from orchestrator import run_generation_2  # noqa: E402
from project_paths import ProjectPaths  # noqa: E402
from v1_artifacts import ArtifactPersistenceError, V1ArtifactManager  # noqa: E402


REPORT_DATE = date(2026, 8, 27)
WINDOW_START = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc)
COLLECTED_AT = datetime(2026, 8, 27, 1, 0, tzinfo=timezone.utc)
TARGET_LANGUAGE = "zh-CN"
ID_PATTERN = re.compile(r'"(event_candidate_id|event_id)":"([^"]+)"')
V17_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "v1_7" / "representative_morning.json"
V17_EXPECTED_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "v1_7" / "representative_morning.expected.json"
)
ARTIFACT_CLOCK = datetime(2026, 8, 27, 2, 3, 4, 500000, tzinfo=timezone.utc)


class FakeFeed:
    def __init__(self, entries: list[dict[str, str]]) -> None:
        self.entries = entries


class FakeEmbedder:
    def embed(self, text: str) -> tuple[float, float]:
        return (1.0, 0.0) if "Alpha" in text else (0.0, 1.0)


class RepresentativeEmbedder:
    def __init__(
        self,
        embeddings: Mapping[str, Sequence[float]],
        cluster_by_title: Mapping[str, str],
    ) -> None:
        self.embeddings = {
            topic: tuple(float(value) for value in vector)
            for topic, vector in embeddings.items()
        }
        self.cluster_by_title = dict(cluster_by_title)

    def embed(self, text: str) -> tuple[float, ...]:
        cluster = next(
            (
                cluster
                for title, cluster in self.cluster_by_title.items()
                if text.startswith(f"query: {title}")
            ),
            None,
        )
        if cluster is None or cluster not in self.embeddings:
            raise ValueError("fixture embedding lookup is missing")
        return self.embeddings[cluster]


class SelectorGateway:
    def __init__(self, *, fail: bool = False, reverse: bool = False) -> None:
        self.fail = fail
        self.reverse = reverse
        self.calls = 0

    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        self.calls += 1
        if self.fail:
            raise GatewayError("provider_failed", 1)
        candidate_ids = [
            value
            for key, value in ID_PATTERN.findall(messages[-1]["content"])
            if key == "event_candidate_id"
        ]
        candidate_ids = list(dict.fromkeys(candidate_ids))
        if self.reverse:
            candidate_ids.reverse()
        return {
            "selected": [
                {"event_candidate_id": candidate_id, "order": order}
                for order, candidate_id in enumerate(candidate_ids, start=1)
            ]
        }


class ClassifierGateway:
    def __init__(
        self,
        fail_calls: set[int] | None = None,
        parse_fail_calls: set[int] | None = None,
    ) -> None:
        self.fail_calls = fail_calls or set()
        self.parse_fail_calls = parse_fail_calls or set()
        self.calls = 0

    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        self.calls += 1
        if self.calls in self.parse_fail_calls:
            raise GatewayError(
                "response_parse_failed",
                1,
                parse_reason="assistant_content_invalid_json",
            )
        if self.calls in self.fail_calls:
            raise GatewayError("timeout", 1)
        event_id = next(
            value for key, value in ID_PATTERN.findall(messages[-1]["content"]) if key == "event_id"
        )
        return {"classifications": [{"event_id": event_id, "category": "geopolitics"}]}


class WriterGateway:
    def __init__(self, fail_calls: set[int] | None = None) -> None:
        self.fail_calls = fail_calls or set()
        self.calls = 0
        self.input_ids: list[str] = []
        self.unclassified_ids: list[str] = []

    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        self.calls += 1
        content = messages[-1]["content"]
        event_id = next(value for key, value in ID_PATTERN.findall(content) if key == "event_id")
        self.input_ids.append(event_id)
        if '"category":null' in content:
            self.unclassified_ids.append(event_id)
        if self.calls in self.fail_calls:
            raise GatewayError("provider_failed", 1)
        return {
            "writings": [
                {
                    "event_id": event_id,
                    "title_zh": f"事件{self.calls}",
                    "summary_zh": "这是由离线证据支持的事件摘要。",
                    "why_it_matters_zh": "该事件改变了相关公共事务的现状。",
                }
            ]
        }


class RepresentativeSelectorGateway:
    def __init__(
        self,
        selected_clusters: Sequence[str],
        *,
        fail: bool = False,
        malformed_cluster: str | None = None,
    ) -> None:
        self.selected_clusters = tuple(selected_clusters)
        self.fail = fail
        self.malformed_cluster = malformed_cluster
        self.calls = 0

    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        self.calls += 1
        if self.fail:
            raise GatewayError("provider_failed", 1)
        projection = json.loads(messages[-1]["content"].split("\n", 1)[1])
        candidates = projection["event_candidates"]

        candidate_by_topic = {
            _topic_from_title(candidate["articles"][0]["title"]): candidate
            for candidate in candidates
        }
        selected = [candidate_by_topic[topic] for topic in self.selected_clusters]
        response_items = [
            {"event_candidate_id": candidate["event_candidate_id"], "order": order}
            for order, candidate in enumerate(selected, start=1)
        ]
        if self.malformed_cluster is not None:
            malformed = candidate_by_topic[self.malformed_cluster]
            response_items.append(
                {"event_candidate_id": malformed["event_candidate_id"], "order": 0}
            )
        return {"selected": response_items}


class RepresentativeWriterGateway:
    def __init__(self, writing_by_topic: Mapping[str, Mapping[str, str]]) -> None:
        self.writing_by_topic = {
            topic: dict(writing) for topic, writing in writing_by_topic.items()
        }
        self.input_ids: list[str] = []

    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        projection = json.loads(messages[-1]["content"].split("\n", 1)[1])
        event = projection["events"][0]
        event_id = event["event_id"]
        self.input_ids.append(event_id)
        topic = _topic_from_title(event["articles"][0]["title"])
        return {"writings": [{"event_id": event_id, **self.writing_by_topic[topic]}]}


class RepresentativeClassifierGateway:
    def __init__(
        self,
        categories_by_topic: Mapping[str, str],
        *,
        malformed_topics: Sequence[str] = (),
    ) -> None:
        self.categories_by_topic = dict(categories_by_topic)
        self.malformed_topics = frozenset(malformed_topics)
        self.calls = 0

    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        self.calls += 1
        projection = json.loads(messages[-1]["content"].split("\n", 1)[1])
        event = projection["events"][0]
        event_id = event["event_id"]
        topic = _topic_from_title(event["articles"][0]["title"])
        category = (
            "not-a-category"
            if topic in self.malformed_topics
            else self.categories_by_topic[topic]
        )
        return {"classifications": [{"event_id": event_id, "category": category}]}


def _topic_from_title(title: str) -> str:
    normalized = title.casefold()
    if "alpha" in normalized:
        return "A"
    if "beta" in normalized:
        return "B"
    if any(fragment in normalized for fragment in ("chipmaker", "packaging", "云客户")):
        return "C"
    if "rail" in normalized:
        return "D"
    raise ValueError("fixture topic cannot be derived from title")


def _load_representative_fixture() -> dict[str, Any]:
    payload = json.loads(V17_FIXTURE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("v1.7 fixture must be an object")
    return payload


def representative_sources(fixture: Mapping[str, Any] | None = None) -> tuple[SourceConfig, ...]:
    payload = fixture or _load_representative_fixture()
    return tuple(
        SourceConfig(source["name"], source["url"], source["language"])
        for source in payload["sources"]
    )


def representative_fetcher(
    source: SourceConfig,
    fixture: Mapping[str, Any] | None = None,
) -> FakeFeed:
    payload = fixture or _load_representative_fixture()
    source_payload = next(
        item for item in payload["sources"] if item["name"] == source.name
    )
    return FakeFeed(
        [
            {
                key: entry[key]
                for key in ("title", "link", "summary", "published")
                if key in entry
            }
            for entry in source_payload["entries"]
        ]
    )


def sources() -> tuple[SourceConfig, ...]:
    return (SourceConfig("Fixture", "https://fixture.example/feed.xml", "en"),)


def feed(*, empty: bool = False) -> FakeFeed:
    if empty:
        return FakeFeed([])
    return FakeFeed(
        [
            {
                "title": "Alpha event",
                "link": "https://fixture.example/alpha",
                "published": "2026-08-26T08:00:00+00:00",
            },
            {
                "title": "Beta event",
                "link": "https://fixture.example/beta",
                "published": "2026-08-26T09:00:00+00:00",
            },
        ]
    )


def manager(root: Path, *, clock: Callable[[], datetime] | None = None) -> V1ArtifactManager:
    paths = ProjectPaths(repo_root=PROJECT_ROOT, data_root=root)
    if clock is None:
        return V1ArtifactManager(paths)
    return V1ArtifactManager(paths, clock=clock)


def run(
    root: Path,
    *,
    run_id: str,
    fetcher: Any | None = None,
    selector: SelectorGateway | None = None,
    classifier: ClassifierGateway | None = None,
    writer: WriterGateway | None = None,
):
    return run_generation_2(
        report_date=REPORT_DATE,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        target_language=TARGET_LANGUAGE,
        sources=sources(),
        selector_gateway=selector or SelectorGateway(),
        classifier_gateway=classifier or ClassifierGateway(),
        writer_gateway=writer or WriterGateway(),
        embedder_factory=FakeEmbedder,
        artifact_manager=manager(root),
        run_id=run_id,
        collector_fetcher=fetcher or (lambda _: feed()),
        clock=lambda: COLLECTED_AT,
    )


def stage_names(result: Any) -> tuple[StageName, ...]:
    return tuple(stage_result.stage for stage_result in result.stage_results)


def _project_stage_result(result: StageResult[Any]) -> dict[str, Any]:
    projection: dict[str, Any] = {
        "stage": result.stage.value,
        "status": result.status.value,
        "output_count": len(result.outputs),
    }
    if result.failures:
        projection["failures"] = [failure.to_dict() for failure in result.failures]
    if result.diagnostic_ref is not None:
        projection["diagnostic_ref"] = result.diagnostic_ref
    return projection


def _project_artifacts(result: Any) -> dict[str, Any]:
    # Snapshot only relative inventory and stable manifest outcome fields;
    # timestamps, hashes, byte counts, and diagnostic filenames are noise.
    if result.run_dir is None or not result.run_dir.is_dir():
        raise AssertionError("successful or failed run must have a final artifact directory")
    run_dir = result.run_dir
    manifest = json.loads(run_dir.joinpath("manifest.json").read_text(encoding="utf-8"))
    files: list[str] = []
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(run_dir).as_posix()
        if relative.startswith("diagnostics/"):
            relative = "diagnostics/<diagnostic>.json"
        files.append(relative)
    diagnostic_refs = sorted(
        json.loads(path.read_text(encoding="utf-8")).get("diagnostic_ref")
        for path in run_dir.joinpath("diagnostics").glob("*.json")
    ) if run_dir.joinpath("diagnostics").is_dir() else []
    return {
        "run_id": result.run_id,
        "files": files,
        "diagnostic_refs": diagnostic_refs,
        "manifest": {
            "state": manifest["state"],
            "run_status": manifest["run_status"],
            "warnings": manifest["warnings"],
        },
    }


def _project_selected_event(event: Any) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "selection_order": event.selection_order,
    }


def _project_classified_event(event: Any) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "category": (
            None if event.classification is None else event.classification.category.value
        ),
    }


def _project_written_event(event: Any) -> dict[str, Any]:
    return {
        **_project_classified_event(event),
        "writing": None if event.writing is None else event.writing.to_dict(),
    }


def _project_run(result: Any) -> dict[str, Any]:
    stages = {stage.stage: stage for stage in result.stage_results}
    cluster_result = stages.get(StageName.EVENT_CLUSTER)
    selector_result = stages.get(StageName.EVENT_SELECTOR)
    classifier_result = stages.get(StageName.EVENT_CLASSIFIER)
    writer_result = stages.get(StageName.EVENT_WRITER)
    return {
        "generation_outcome": result.generation_outcome,
        "stage_results": [_project_stage_result(stage) for stage in result.stage_results],
        "clusters": (
            []
            if cluster_result is None
            else [candidate.to_dict() for candidate in cluster_result.outputs]
        ),
        "selected": (
            []
            if selector_result is None
            else [_project_selected_event(event) for event in selector_result.outputs]
        ),
        "classified": (
            []
            if classifier_result is None
            else [_project_classified_event(event) for event in classifier_result.outputs]
        ),
        "written": (
            []
            if writer_result is None
            else [_project_written_event(event) for event in writer_result.outputs]
        ),
        "brief": None if result.brief is None else result.brief.to_dict(),
        "artifacts": _project_artifacts(result),
    }


def run_representative(
    root: Path,
    *,
    run_id: str,
    empty: bool = False,
    partial: bool = False,
    selector_failed: bool = False,
    writer_failed: bool = False,
) -> Any:
    fixture = _load_representative_fixture()
    report_date = date.fromisoformat(fixture["report_date"])
    window_start = datetime.fromisoformat(fixture["window_start"])
    window_end = datetime.fromisoformat(fixture["window_end"])
    collected_at = datetime.fromisoformat(fixture["collected_at"])
    configured_sources = representative_sources(fixture)
    cluster_by_title = {
        entry["title"]: entry["cluster"]
        for source in fixture["sources"]
        for entry in source["entries"]
    }
    selector = RepresentativeSelectorGateway(
        fixture["selected_clusters"],
        fail=selector_failed,
        malformed_cluster="D" if partial else None,
    )
    classifier = RepresentativeClassifierGateway(
        fixture["categories"],
        malformed_topics=("B",) if partial else (),
    )
    writer: Any
    if writer_failed:
        writer = WriterGateway(set(range(1, len(fixture["selected_clusters"]) + 1)))
    else:
        writer = RepresentativeWriterGateway(fixture["writing"])

    def fetcher(source: SourceConfig) -> FakeFeed:
        return FakeFeed([]) if empty else representative_fetcher(source, fixture)

    return run_generation_2(
        report_date=report_date,
        window_start=window_start,
        window_end=window_end,
        target_language=fixture["target_language"],
        sources=configured_sources,
        selector_gateway=selector,
        classifier_gateway=classifier,
        writer_gateway=writer,
        embedder_factory=lambda: RepresentativeEmbedder(
            fixture["embeddings"], cluster_by_title
        ),
        artifact_manager=manager(root, clock=lambda: ARTIFACT_CLOCK),
        run_id=run_id,
        collector_fetcher=fetcher,
        clock=lambda: collected_at,
    )


def test_clean_run_preserves_selector_order_and_full_stage_order(root: Path) -> None:
    selector = SelectorGateway(reverse=True)
    result = run(root, run_id="clean", selector=selector)

    assert result.generation_outcome == "complete"
    assert result.brief is not None
    assert result.brief.generation_status is GenerationStatus.COMPLETE
    assert result.rendered_markdown is not None
    assert stage_names(result) == tuple(StageName)[:-1]
    clustered = result.stage_results[3].outputs
    selected = result.stage_results[4].outputs
    assert [event.article_ids for event in selected] == [
        candidate.article_ids for candidate in reversed(clustered)
    ]
    assert result.brief.event_ids == tuple(event.event_id for event in selected)
    assert [event.selection_order for event in selected] == [1, 2]
    assert result.run_dir is not None and result.run_dir.is_dir()
    checkpoints = sorted(
        path.name for path in result.run_dir.joinpath("stage-results").glob("*.json")
    )
    assert checkpoints == [
        "01-collector.json",
        "02-normalizer.json",
        "03-article-dedup.json",
        "04-event-cluster.json",
        "05-event-selector.json",
        "06-event-classifier.json",
        "07-event-writer.json",
        "08-brief-renderer.json",
    ]


def test_representative_reader_layout_runs_full_pipeline(root: Path) -> None:
    expected = json.loads(V17_EXPECTED_PATH.read_text(encoding="utf-8"))
    result = run_representative(root, run_id="v17-clean")

    assert _project_run(result) == expected["clean"]
    assert result.run_dir is not None
    collected_batches = json.loads(
        result.run_dir.joinpath("stage-results/01-collector.json").read_text(
            encoding="utf-8"
        )
    )["payload"]["outputs"]
    assert all(
        "cluster" not in entry
        for batch in collected_batches
        for entry in batch["entries"]
    )
    normalized_articles = json.loads(
        result.run_dir.joinpath("objects/articles-normalized.json").read_text(
            encoding="utf-8"
        )
    )["objects"]
    assert all("cluster" not in item["payload"] for item in normalized_articles)
    assert all(
        not re.match(r"^\[[A-Z]\]\s", item["payload"]["title"])
        for item in normalized_articles
    )
    rendered_markdown = result.run_dir.joinpath("morning-brief.md").read_text(
        encoding="utf-8"
    )
    assert rendered_markdown == (
        PROJECT_ROOT
        .joinpath("tests/fixtures/v1_7/representative_morning.expected.md")
        .read_text(encoding="utf-8")
    )
    assert "## 今日要闻" not in rendered_markdown
    assert [
        line for line in rendered_markdown.splitlines() if line.startswith("## ")
    ] == ["## *科技与 AI*", "## *宏观与政策*"]
    assert [
        line for line in rendered_markdown.splitlines() if line.startswith("### ")
    ] == [
        '### <span style="color: var(--text-accent);"><strong>芯片产业链出现多方进展</strong></span>',
        '### <span style="color: var(--text-accent);"><strong>阿尔法各方公布紧急协调安排</strong></span>',
        '### <span style="color: var(--text-accent);"><strong>贝塔央行下调基准利率</strong></span>',
    ]
    assert rendered_markdown.count("摘要：") == 3
    assert rendered_markdown.count("<details>") == 3
    assert rendered_markdown.count("<ul>") == 3
    assert rendered_markdown.count("<li>") == 7
    assert "\n- " not in rendered_markdown
    repeat = run_representative(root.joinpath("repeat"), run_id="v17-clean")
    assert _project_run(repeat) == expected["clean"]
    assert repeat.rendered_markdown == result.rendered_markdown


def test_v17_snapshot_matrix_covers_empty_partial_and_hard_stops(root: Path) -> None:
    expected = json.loads(V17_EXPECTED_PATH.read_text(encoding="utf-8"))
    scenarios = {
        "empty": {"empty": True},
        "partial": {"partial": True},
        "selector_failed": {"selector_failed": True},
        "writer_all_failed": {"writer_failed": True},
    }
    for name, options in scenarios.items():
        result = run_representative(root, run_id=f"v17-{name}", **options)
        assert _project_run(result) == expected[name]
        if name == "partial":
            assert result.rendered_markdown is not None
            assert "> 本次简报部分生成，可能存在少量遗漏。" in (
                result.rendered_markdown
            )
            assert [
                line
                for line in result.rendered_markdown.splitlines()
                if line.startswith("## ")
            ] == ["## *科技与 AI*", "## *宏观与政策*", "## *其他*"]
            assert "不应进入简报的事件" not in result.rendered_markdown
        if name in {"selector_failed", "writer_all_failed"}:
            assert result.rendered_markdown is None


def test_classifier_partial_overlays_without_dropping_writer_inputs(root: Path) -> None:
    classifier = ClassifierGateway({2})
    writer = WriterGateway()
    result = run(root, run_id="classifier-partial", classifier=classifier, writer=writer)

    selected = result.stage_results[4].outputs
    classifier_result = result.stage_results[5]
    assert classifier_result.status is StageStatus.PARTIAL
    assert writer.input_ids == [event.event_id for event in selected]
    assert writer.unclassified_ids == [selected[1].event_id]
    assert result.brief is not None
    assert result.brief.generation_status is GenerationStatus.PARTIAL
    artifact = json.loads(
        result.run_dir.joinpath("objects/events-writer-input.json").read_text(encoding="utf-8")
    )
    assert [entry["payload"]["event_id"] for entry in artifact["objects"]] == [
        event.event_id for event in selected
    ]


def test_classifier_all_failed_still_writes_every_selected_event(root: Path) -> None:
    writer = WriterGateway()
    result = run(
        root,
        run_id="classifier-failed",
        classifier=ClassifierGateway({1, 2}),
        writer=writer,
    )

    selected = result.stage_results[4].outputs
    assert result.stage_results[5].status is StageStatus.FAILED
    assert writer.input_ids == [event.event_id for event in selected]
    assert writer.unclassified_ids == writer.input_ids
    assert all(event.classification is None for event in result.stage_results[6].outputs)
    assert result.brief is not None
    assert result.brief.generation_status is GenerationStatus.PARTIAL


def test_provider_diagnostic_is_durable_before_referenced_checkpoint(root: Path) -> None:
    result = run(
        root,
        run_id="diagnostic-ref",
        classifier=ClassifierGateway(parse_fail_calls={2}),
    )

    checkpoint = json.loads(
        result.run_dir.joinpath("stage-results/06-event-classifier.json").read_text(
            encoding="utf-8"
        )
    )
    diagnostic_ref = checkpoint["payload"]["diagnostic_ref"]
    assert diagnostic_ref == "llm_gateway:assistant_content_invalid_json"
    diagnostics = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in result.run_dir.joinpath("diagnostics").glob("*.json")
    ]
    assert any(item["diagnostic_ref"] == diagnostic_ref for item in diagnostics)


def test_writer_partial_renders_only_successful_written_events(root: Path) -> None:
    result = run(root, run_id="writer-partial", writer=WriterGateway({2}))

    selected = result.stage_results[4].outputs
    written = result.stage_results[6].outputs
    assert len(selected) == 2 and len(written) == 1
    assert result.stage_results[6].status is StageStatus.PARTIAL
    assert result.brief is not None
    assert result.brief.event_ids == (written[0].event_id,)
    assert result.brief.generation_status is GenerationStatus.PARTIAL


def test_writer_all_failed_and_selector_failed_hard_stop_without_brief(root: Path) -> None:
    writer_failed = run(root, run_id="writer-failed", writer=WriterGateway({1, 2}))
    assert writer_failed.generation_outcome == "failed"
    assert writer_failed.brief is None
    assert StageName.BRIEF_RENDERER not in stage_names(writer_failed)
    assert writer_failed.run_dir.joinpath("stage-results/07-event-writer.json").exists()
    assert not writer_failed.run_dir.joinpath("brief.json").exists()

    classifier = ClassifierGateway()
    writer = WriterGateway()
    selector_failed = run(
        root,
        run_id="selector-failed",
        selector=SelectorGateway(fail=True),
        classifier=classifier,
        writer=writer,
    )
    assert selector_failed.generation_outcome == "failed"
    assert selector_failed.brief is None
    assert classifier.calls == 0 and writer.calls == 0
    assert stage_names(selector_failed)[-1] is StageName.EVENT_SELECTOR


def test_collector_partial_and_empty_runs_derive_mechanical_status(root: Path) -> None:
    partial_sources = (
        SourceConfig("Good", "https://good.example/feed.xml", "en"),
        SourceConfig("Bad", "https://bad.example/feed.xml", "en"),
    )

    def partial_fetcher(source: SourceConfig) -> FakeFeed:
        if source.name == "Bad":
            raise TimeoutError("offline timeout")
        return FakeFeed([])

    partial = run_generation_2(
        report_date=REPORT_DATE,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        target_language=TARGET_LANGUAGE,
        sources=partial_sources,
        selector_gateway=SelectorGateway(),
        classifier_gateway=ClassifierGateway(),
        writer_gateway=WriterGateway(),
        embedder_factory=FakeEmbedder,
        artifact_manager=manager(root),
        run_id="source-partial-empty",
        collector_fetcher=partial_fetcher,
        clock=lambda: COLLECTED_AT,
    )
    assert partial.brief is not None
    assert partial.brief.event_ids == ()
    assert partial.brief.generation_status is GenerationStatus.PARTIAL

    clean = run(root, run_id="clean-empty", fetcher=lambda _: feed(empty=True))
    assert clean.brief is not None
    assert clean.brief.event_ids == ()
    assert clean.brief.generation_status is GenerationStatus.COMPLETE


def test_collector_failure_and_checkpoint_failure_stop_downstream(root: Path) -> None:
    selector = SelectorGateway()
    collector_failed = run(
        root,
        run_id="collector-failed",
        fetcher=lambda _: (_ for _ in ()).throw(TimeoutError("offline")),
        selector=selector,
    )
    assert collector_failed.generation_outcome == "failed"
    assert collector_failed.brief is None
    assert selector.calls == 0
    assert stage_names(collector_failed) == (StageName.COLLECTOR,)

    downstream_selector = SelectorGateway()
    original = __import__("v1_artifacts").ArtifactRun.persist_stage_result

    def fail_collector_checkpoint(self: Any, result: Any, **kwargs: Any):
        if result.stage is StageName.COLLECTOR:
            raise ArtifactPersistenceError("fixture checkpoint failure")
        return original(self, result, **kwargs)

    with patch("v1_artifacts.ArtifactRun.persist_stage_result", new=fail_collector_checkpoint):
        try:
            run(root, run_id="checkpoint-failed", selector=downstream_selector)
        except ArtifactPersistenceError:
            pass
        else:
            raise AssertionError("artifact persistence failure was swallowed")
    assert downstream_selector.calls == 0


def test_renderer_failure_finalizes_failed_run_without_brief(root: Path) -> None:
    failed_render = BriefRenderResult(
        stage_result=StageResult(
            stage=StageName.BRIEF_RENDERER,
            status=StageStatus.FAILED,
            failures=(ItemFailure(code=FailureCode.RENDER_FAILED),),
        ),
        markdown=None,
    )
    with patch("orchestrator.render_brief", return_value=failed_render):
        result = run(root, run_id="renderer-failed")

    assert result.generation_outcome == "failed"
    assert result.brief is None
    assert stage_names(result)[-1] is StageName.BRIEF_RENDERER
    assert result.run_dir.joinpath("stage-results/08-brief-renderer.json").exists()
    assert not result.run_dir.joinpath("brief.json").exists()


def test_window_exclusion_is_diagnostic_not_failure(root: Path) -> None:
    def mixed_window(_: SourceConfig) -> FakeFeed:
        return FakeFeed(
            [
                {
                    "title": "Inside",
                    "link": "https://fixture.example/inside",
                    "published": "2026-08-26T08:00:00+00:00",
                },
                {
                    "title": "Outside",
                    "link": "https://fixture.example/outside",
                    "published": "2026-08-25T08:00:00+00:00",
                },
            ]
        )

    result = run(root, run_id="window-exclusion", fetcher=mixed_window)
    assert result.stage_results[1].status is StageStatus.SUCCEEDED
    diagnostics = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in result.run_dir.joinpath("diagnostics").glob("*.json")
    ]
    diagnostic = next(
        item for item in diagnostics if item["record"].get("reason") == "report_window_admission"
    )
    assert diagnostic["record"]["excluded_count"] == 1


def test_generation_one_routing_remains_unwired() -> None:
    main_source = PROJECT_ROOT.joinpath("main.py").read_text(encoding="utf-8")
    assert "run_generation_2" not in main_source
    assert "from orchestrator" not in main_source


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="automation-brief-orchestrator-", dir="/private/tmp") as temp:
        root = Path(temp)
        test_clean_run_preserves_selector_order_and_full_stage_order(root)
        test_representative_reader_layout_runs_full_pipeline(root)
        test_v17_snapshot_matrix_covers_empty_partial_and_hard_stops(root)
        test_classifier_partial_overlays_without_dropping_writer_inputs(root)
        test_classifier_all_failed_still_writes_every_selected_event(root)
        test_provider_diagnostic_is_durable_before_referenced_checkpoint(root)
        test_writer_partial_renders_only_successful_written_events(root)
        test_writer_all_failed_and_selector_failed_hard_stop_without_brief(root)
        test_collector_partial_and_empty_runs_derive_mechanical_status(root)
        test_collector_failure_and_checkpoint_failure_stop_downstream(root)
        test_renderer_failure_finalizes_failed_run_without_brief(root)
        test_window_exclusion_is_diagnostic_not_failure(root)
    test_generation_one_routing_remains_unwired()
    print("offline orchestrator smoke passed")


if __name__ == "__main__":
    main()
