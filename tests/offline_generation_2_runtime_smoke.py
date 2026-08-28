"""Offline acceptance for the formal Generation 2 runtime and manual CLI."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timezone
from io import StringIO
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from urllib.error import HTTPError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from canonical_domain import FailureCode, StageStatus, TARGET_LANGUAGE  # noqa: E402
import collector as collector_module  # noqa: E402
from collector import SourceConfig, collect_sources, fetch_source  # noqa: E402
import generation_2_runtime as runtime_module  # noqa: E402
from generation_2_runtime import (  # noqa: E402
    DEEPSEEK_API_KEY_ENV,
    Generation2Runtime,
    Generation2RuntimeConfigurationError,
    MorningBriefReportSlot,
    build_generation_2_runtime,
    resolve_morning_brief_report_slot,
)
from event_cluster import MODEL_ID, MODEL_REVISION  # noqa: E402
from llm_gateway import GatewayResponse  # noqa: E402
from project_paths import ProjectPaths  # noqa: E402
from run_generation_2_shadow import main as shadow_main  # noqa: E402
from v1_artifacts import ARTIFACT_ROOT_NAME, V1ArtifactManager  # noqa: E402


REPORT_DATE = date(2026, 8, 28)
WINDOW_START = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc)
COLLECTED_AT = datetime(2026, 8, 28, 0, 5, tzinfo=timezone.utc)


class FakeFeed:
    def __init__(
        self,
        *,
        bozo: bool = False,
        entries=None,
        bozo_exception: BaseException | None = None,
    ) -> None:
        self.bozo = bozo
        self.bozo_exception = bozo_exception
        self.entries = entries if entries is not None else [
            {
                "title": "Alpha central bank announces policy change",
                "link": "https://fixture.example/alpha",
                "summary": "Alpha central bank changed a benchmark policy setting.",
                "published": "2026-08-27T23:30:00+00:00",
            },
            {
                "title": "Beta technology company publishes results",
                "link": "https://fixture.example/beta",
                "summary": "Beta published a separate technology result.",
                "published": "2026-08-27T22:30:00+00:00",
            },
        ]


class FakeHTTPResponse:
    headers = {"Content-Type": "application/rss+xml"}

    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return b"offline-feed"

    def geturl(self) -> str:
        return "https://fixture.example/feed.xml"


class FakeEmbedder:
    def embed(self, text: str) -> tuple[float, float]:
        return (1.0, 0.0) if "Alpha" in text else (0.0, 1.0)


class FakeGenerationGateway:
    def complete_json(self, messages, *, parameters=None):
        assert parameters is None
        content = messages[-1]["content"]
        _, separator, encoded = content.partition("\n")
        assert separator
        projection = json.loads(encoded)
        if "event_candidates" in projection:
            candidate_id = projection["event_candidates"][0]["event_candidate_id"]
            payload = {
                "selected": [{"event_candidate_id": candidate_id, "order": 1}]
            }
        else:
            event_id = projection["events"][0]["event_id"]
            if "target_language" in projection:
                payload = {
                    "writings": [
                        {
                            "event_id": event_id,
                            "title_zh": "阿尔法央行调整政策",
                            "summary_zh": "阿尔法央行公布了基准政策调整。",
                            "why_it_matters_zh": "该调整改变了现行政策环境。",
                        }
                    ]
                }
            else:
                payload = {
                    "classifications": [
                        {"event_id": event_id, "category": "macro_policy"}
                    ]
                }
        return GatewayResponse(
            payload=payload,
            attempts=1,
            provider_id="offline",
            model="fixture",
        )


def fake_runtime(data_root: Path) -> Generation2Runtime:
    paths = ProjectPaths(repo_root=PROJECT_ROOT, data_root=data_root)
    gateway = FakeGenerationGateway()
    return Generation2Runtime(
        sources=(SourceConfig("Fixture", "https://fixture.example/feed.xml", "en"),),
        selector_gateway=gateway,
        classifier_gateway=gateway,
        writer_gateway=gateway,
        embedder_factory=FakeEmbedder,
        artifact_manager=V1ArtifactManager(paths),
    )


def test_report_slot_is_canonical_and_deterministic() -> None:
    first = resolve_morning_brief_report_slot("2026-08-28")
    second = resolve_morning_brief_report_slot(REPORT_DATE)

    assert first == second == MorningBriefReportSlot(
        report_date=REPORT_DATE,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        target_language=TARGET_LANGUAGE,
    )


def test_default_report_date_uses_shanghai_calendar_date() -> None:
    slot = resolve_morning_brief_report_slot(
        None,
        clock=lambda: datetime(2026, 8, 27, 16, 30, tzinfo=timezone.utc),
    )
    assert slot.report_date == REPORT_DATE
    assert slot.window_end == WINDOW_END


def test_invalid_report_dates_fail_closed() -> None:
    for invalid in (
        "2026-02-30",
        "2026/08/28",
        "20260828",
        "",
        datetime(2026, 8, 28),
    ):
        try:
            resolve_morning_brief_report_slot(invalid)  # type: ignore[arg-type]
        except Generation2RuntimeConfigurationError:
            pass
        else:
            raise AssertionError(f"invalid report date was accepted: {invalid!r}")


def test_formal_feed_fetcher_is_independent_and_bounded() -> None:
    parsed_feed = FakeFeed()
    source = SourceConfig("Fixture", "https://fixture.example/feed.xml", "en")
    with (
        patch.object(
            collector_module.urllib.request,
            "urlopen",
            return_value=FakeHTTPResponse(),
        ) as urlopen,
        patch.object(collector_module.feedparser, "parse", return_value=parsed_feed) as parse,
    ):
        fetched = fetch_source(source)

    assert urlopen.call_count == 1
    assert urlopen.call_args.kwargs["timeout"] == collector_module.FEED_FETCH_TIMEOUT_SECONDS
    assert fetched.parsed_feed is parsed_feed
    assert fetched.attempt_count == 1
    assert fetched.http_status == 200
    assert fetched.duration_ms >= 0
    parse.assert_called_once_with(
        b"offline-feed",
        response_headers={
            "content-type": "application/rss+xml",
            "content-location": "https://fixture.example/feed.xml",
        },
    )


def _collect_with_default_fetcher(*, responses, parsed_feed: FakeFeed):
    diagnostics: list[dict[str, object]] = []
    source = SourceConfig("Fixture", "https://fixture.example/feed.xml", "en")
    with (
        patch.object(collector_module.urllib.request, "urlopen", side_effect=responses) as urlopen,
        patch.object(collector_module.feedparser, "parse", return_value=parsed_feed),
        patch.object(collector_module.time_module, "sleep") as sleep,
    ):
        result = collect_sources(
            (source,),
            clock=lambda: COLLECTED_AT,
            diagnostic_sink=lambda record: diagnostics.append(dict(record)),
        )
    return result, diagnostics, urlopen.call_count, sleep.call_count


def test_timeout_retries_once_and_keeps_timeout_taxonomy() -> None:
    result, diagnostics, calls, sleeps = _collect_with_default_fetcher(
        responses=[TimeoutError("offline timeout"), FakeHTTPResponse()],
        parsed_feed=FakeFeed(),
    )
    assert result.status is StageStatus.SUCCEEDED
    assert calls == 2 and sleeps == 1
    assert diagnostics[0]["attempt"] == 2
    assert diagnostics[0]["status"] == "succeeded"


def test_exhausted_timeout_and_transport_keep_specific_taxonomy() -> None:
    for errors, expected_code in (
        ([TimeoutError("offline timeout"), TimeoutError("offline timeout")], FailureCode.TIMEOUT),
        ([OSError("offline transport"), OSError("offline transport")], FailureCode.TRANSPORT_FAILED),
    ):
        result, diagnostics, calls, sleeps = _collect_with_default_fetcher(
            responses=errors,
            parsed_feed=FakeFeed(),
        )
        assert result.status is StageStatus.FAILED
        assert result.failures[0].code is expected_code
        assert calls == 2 and sleeps == 1
        assert diagnostics[0]["attempt"] == 2
        assert diagnostics[0]["failure_code"] == expected_code.value


def test_http_429_and_5xx_retry_once() -> None:
    for status in (429, 503):
        result, diagnostics, calls, sleeps = _collect_with_default_fetcher(
            responses=[
                HTTPError("https://fixture.example/feed.xml", status, "offline", None, None),
                FakeHTTPResponse(),
            ],
            parsed_feed=FakeFeed(),
        )
        assert result.status is StageStatus.SUCCEEDED
        assert calls == 2 and sleeps == 1
        assert diagnostics[0]["attempt"] == 2


def test_http_404_does_not_retry_and_is_source_fetch_failed() -> None:
    result, diagnostics, calls, sleeps = _collect_with_default_fetcher(
        responses=[HTTPError("https://fixture.example/feed.xml", 404, "offline", None, None)],
        parsed_feed=FakeFeed(),
    )
    assert result.status is StageStatus.FAILED
    assert result.failures[0].code is FailureCode.SOURCE_FETCH_FAILED
    assert calls == 1 and sleeps == 0
    assert diagnostics[0]["attempt"] == 1
    assert diagnostics[0]["http_status"] == 404
    assert diagnostics[0]["failure_code"] == FailureCode.SOURCE_FETCH_FAILED.value


def test_deterministic_bozo_failure_does_not_retry() -> None:
    result, diagnostics, calls, sleeps = _collect_with_default_fetcher(
        responses=[FakeHTTPResponse()],
        parsed_feed=FakeFeed(
            bozo=True,
            entries=[],
            bozo_exception=ValueError("offline parse failure"),
        ),
    )
    assert result.status is StageStatus.FAILED
    assert result.failures[0].code is FailureCode.SOURCE_FETCH_FAILED
    assert calls == 1 and sleeps == 0
    assert diagnostics[0]["attempt"] == 1
    assert "exception" not in diagnostics[0]


def test_fake_dependencies_run_the_full_runtime_without_delivery() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-runtime-", dir="/private/tmp") as temp:
        data_root = Path(temp) / "data"
        runtime = fake_runtime(data_root)
        result = runtime.run(
            resolve_morning_brief_report_slot(REPORT_DATE),
            run_id="manual-offline-runtime",
            collector_fetcher=lambda source: FakeFeed(),
            clock=lambda: COLLECTED_AT,
        )

        assert result.generation_outcome == "complete"
        assert result.brief is not None and len(result.brief.event_ids) == 1
        assert result.run_dir == (
            data_root / "runs" / ARTIFACT_ROOT_NAME / "manual-offline-runtime"
        )
        assert result.run_dir.joinpath("brief.json").exists()
        assert result.run_dir.joinpath("morning-brief.md").exists()
        assert not data_root.joinpath("reports").exists()
        assert set(path.name for path in data_root.joinpath("runs").iterdir()) == {
            ARTIFACT_ROOT_NAME
        }


def test_real_runtime_requires_process_key_before_external_work() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-no-key-", dir="/private/tmp") as temp:
        root = Path(temp)
        feeds = root / "feeds.json"
        feeds.write_text(
            json.dumps([{"name": "Fixture", "url": "https://fixture.example/feed"}]),
            encoding="utf-8",
        )
        cache = root / "model-cache"
        cache.mkdir()
        cache.joinpath("sentinel").write_text("offline", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            try:
                build_generation_2_runtime(
                    provider="deepseek",
                    feeds_path=feeds,
                    data_root=root / "data",
                    model_cache=cache,
                )
            except Generation2RuntimeConfigurationError as error:
                assert "credential" in str(error).lower()
            else:
                raise AssertionError("missing DeepSeek key was accepted")


def test_real_runtime_requires_existing_nonempty_model_cache() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-no-cache-", dir="/private/tmp") as temp:
        root = Path(temp)
        feeds = root / "feeds.json"
        feeds.write_text(
            json.dumps([{"name": "Fixture", "url": "https://fixture.example/feed"}]),
            encoding="utf-8",
        )
        with patch.dict(os.environ, {DEEPSEEK_API_KEY_ENV: "offline-secret"}, clear=True):
            try:
                build_generation_2_runtime(
                    provider="deepseek",
                    feeds_path=feeds,
                    data_root=root / "data",
                    model_cache=root / "missing-cache",
                )
            except Generation2RuntimeConfigurationError as error:
                assert "model cache" in str(error).lower()
            else:
                raise AssertionError("missing model cache was accepted")


def test_runtime_builder_preflights_and_reuses_the_pinned_local_embedder() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-builder-", dir="/private/tmp") as temp:
        root = Path(temp)
        data_root = root / "data"
        feeds = root / "feeds.json"
        feeds.write_text(
            json.dumps([{"name": "Fixture", "url": "https://fixture.example/feed", "language": "en"}]),
            encoding="utf-8",
        )
        cache = root / "model-cache"
        cache.mkdir()
        cache.joinpath("sentinel").write_text("offline", encoding="utf-8")
        captured: dict[str, object] = {}
        embedder = FakeEmbedder()

        def build_embedder(**kwargs):
            captured.update(kwargs)
            return embedder

        gateway = FakeGenerationGateway()
        with (
            patch.dict(os.environ, {DEEPSEEK_API_KEY_ENV: "offline-secret"}, clear=True),
            patch.object(runtime_module, "SentenceTransformerEmbedder", side_effect=build_embedder),
            patch.object(
                runtime_module,
                "build_deepseek_generation_2_gateway",
                return_value=gateway,
            ),
        ):
            runtime = build_generation_2_runtime(
                provider="deepseek",
                feeds_path=feeds,
                data_root=data_root,
                model_cache=cache,
            )
            assert captured == {
                "model_id": MODEL_ID,
                "model_revision": MODEL_REVISION,
                "cache_folder": str(cache),
                "local_files_only": True,
            }
            assert runtime.embedder_factory() is embedder
            with (
                patch.object(
                    collector_module.urllib.request,
                    "urlopen",
                    return_value=FakeHTTPResponse(),
                ),
                patch.object(collector_module.feedparser, "parse", return_value=FakeFeed()),
            ):
                result = runtime.run(
                    resolve_morning_brief_report_slot(REPORT_DATE),
                    run_id="formal-builder-offline",
                    clock=lambda: COLLECTED_AT,
                )

        assert result.generation_outcome == "complete"
        assert result.run_dir == (
            data_root / "runs" / ARTIFACT_ROOT_NAME / "formal-builder-offline"
        )
        assert not data_root.joinpath("reports").exists()
        diagnostic_records = [
            json.loads(path.read_text(encoding="utf-8"))["record"]
            for path in result.run_dir.joinpath("diagnostics").glob("*.json")
        ]
        source_records = [record for record in diagnostic_records if "source_ref" in record]
        assert len(source_records) == 1
        assert source_records[0]["attempt"] == 1
        assert source_records[0]["http_status"] == 200
        assert source_records[0]["status"] == "succeeded"
        assert "header" not in source_records[0]


def test_wrong_nonempty_model_cache_fails_before_collection() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-wrong-cache-", dir="/private/tmp") as temp:
        root = Path(temp)
        feeds = root / "feeds.json"
        feeds.write_text(
            json.dumps([{"name": "Fixture", "url": "https://fixture.example/feed"}]),
            encoding="utf-8",
        )
        cache = root / "model-cache"
        cache.mkdir()
        cache.joinpath("unrelated-file").write_text("offline", encoding="utf-8")
        with (
            patch.dict(os.environ, {DEEPSEEK_API_KEY_ENV: "offline-secret"}, clear=True),
            patch.object(
                runtime_module,
                "SentenceTransformerEmbedder",
                side_effect=RuntimeError("offline cache miss"),
            ),
            patch.object(collector_module.urllib.request, "urlopen") as urlopen,
        ):
            try:
                build_generation_2_runtime(
                    provider="deepseek",
                    feeds_path=feeds,
                    data_root=root / "data",
                    model_cache=cache,
                )
            except Generation2RuntimeConfigurationError as error:
                assert "local model cache" in str(error).lower()
            else:
                raise AssertionError("wrong nonempty model cache was accepted")
        assert urlopen.call_count == 0


def test_manual_cli_is_a_thin_artifact_only_entrypoint() -> None:
    with tempfile.TemporaryDirectory(prefix="generation-2-cli-", dir="/private/tmp") as temp:
        data_root = Path(temp) / "data"

        def builder(**kwargs):
            assert kwargs["provider"] == "deepseek"
            assert kwargs["data_root"] == data_root
            return fake_runtime(data_root)

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = shadow_main(
                [
                    "--date",
                    REPORT_DATE.isoformat(),
                    "--real-provider",
                    "deepseek",
                    "--data-root",
                    str(data_root),
                    "--run-id",
                    "manual-cli-offline",
                ],
                runtime_builder=builder,
                collector_fetcher=lambda source: FakeFeed(),
                clock=lambda: COLLECTED_AT,
            )

        assert exit_code == 0, stderr.getvalue()
        output = json.loads(stdout.getvalue())
        assert output["generation_outcome"] == "complete"
        assert output["report_date"] == REPORT_DATE.isoformat()
        assert output["window_start"] == WINDOW_START.isoformat()
        assert output["window_end"] == WINDOW_END.isoformat()
        assert output["run_id"] == "manual-cli-offline"
        assert Path(output["artifact_dir"]) == (
            data_root / "runs" / ARTIFACT_ROOT_NAME / "manual-cli-offline"
        )
        assert not data_root.joinpath("reports").exists()


def test_runtime_and_cli_have_no_gen1_semantic_or_delivery_dependencies() -> None:
    runtime_source = PROJECT_ROOT.joinpath("generation_2_runtime.py").read_text(encoding="utf-8")
    collector_source = PROJECT_ROOT.joinpath("collector.py").read_text(encoding="utf-8")
    cli_source = PROJECT_ROOT.joinpath("scripts/run_generation_2_shadow.py").read_text(
        encoding="utf-8"
    )
    combined = runtime_source + "\n" + collector_source + "\n" + cli_source
    forbidden = (
        "legacy_items_from_candidates",
        "curate_overnight_candidates",
        "write_overnight_brief_markdown",
        "publish_mobile_digest",
        "send_bark_notification",
        "BARK_URL",
        "MOBILE_DIGEST_DIR",
        "OBSIDIAN_",
    )
    assert all(token not in combined for token in forbidden)
    assert "from main import" not in combined
    assert "import main" not in combined


def main() -> None:
    test_report_slot_is_canonical_and_deterministic()
    test_default_report_date_uses_shanghai_calendar_date()
    test_invalid_report_dates_fail_closed()
    test_formal_feed_fetcher_is_independent_and_bounded()
    test_timeout_retries_once_and_keeps_timeout_taxonomy()
    test_http_429_and_5xx_retry_once()
    test_http_404_does_not_retry_and_is_source_fetch_failed()
    test_deterministic_bozo_failure_does_not_retry()
    test_fake_dependencies_run_the_full_runtime_without_delivery()
    test_real_runtime_requires_process_key_before_external_work()
    test_real_runtime_requires_existing_nonempty_model_cache()
    test_runtime_builder_preflights_and_reuses_the_pinned_local_embedder()
    test_wrong_nonempty_model_cache_fails_before_collection()
    test_manual_cli_is_a_thin_artifact_only_entrypoint()
    test_runtime_and_cli_have_no_gen1_semantic_or_delivery_dependencies()
    print("offline Generation 2 runtime smoke passed")


if __name__ == "__main__":
    main()
