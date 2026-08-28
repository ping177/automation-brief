"""Formal runtime composition for the Generation 2 Morning Brief.

This module owns production-reusable runtime choices: the canonical daily
report slot, active sources, the frozen local embedding model, the DeepSeek
JSON adapter, and the canonical artifact manager. Delivery and Generation 1
semantics deliberately remain outside this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Protocol, Sequence
from zoneinfo import ZoneInfo

from canonical_domain import Brief, CanonicalContractError, TARGET_LANGUAGE
from collector import FeedFetcher, SourceConfig, load_sources
from event_classifier import ClassifierGateway
from event_cluster import (
    EmbeddingBackend,
    MODEL_ID,
    MODEL_REVISION,
    SentenceTransformerEmbedder,
)
from event_selector import SelectorGateway
from event_writer import WriterGateway
from llm_gateway import (
    HTTPTransport,
    GatewayResponse,
    OpenAICompatibleGatewayConfig,
    OpenAICompatibleJSONGateway,
)
from orchestrator import GenerationRunResult, run_generation_2
from project_paths import ProjectPaths, get_project_paths
from v1_artifacts import V1ArtifactManager


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_FEEDS_PATH = PROJECT_ROOT / "feeds.json"

MORNING_BRIEF_TIMEZONE_NAME = "Asia/Shanghai"
MORNING_BRIEF_TIMEZONE = ZoneInfo(MORNING_BRIEF_TIMEZONE_NAME)
MORNING_BRIEF_CUTOFF = time(hour=8)
MORNING_BRIEF_WINDOW = timedelta(hours=24)

MODEL_CACHE_ENV = "AUTOMATION_BRIEF_MODEL_CACHE"

DEEPSEEK_PROVIDER_ID = "deepseek"
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEEPSEEK_API_KEY_ENV = "AUTOMATION_BRIEF_CURATOR_API_KEY"
DEEPSEEK_TIMEOUT_SECONDS = 90.0
DEEPSEEK_MAX_ATTEMPTS = 2
DEEPSEEK_MAX_TOKENS = 8192
DEEPSEEK_PARAMETERS = {
    "max_tokens": DEEPSEEK_MAX_TOKENS,
    "thinking": {"type": "disabled"},
}
_REPORT_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Generation2RuntimeConfigurationError(ValueError):
    """A formal Generation 2 runtime precondition is not satisfied."""


@dataclass(frozen=True)
class MorningBriefReportSlot:
    """The canonical daily report slot consumed by Generation 2."""

    report_date: date
    window_start: datetime
    window_end: datetime
    target_language: str = TARGET_LANGUAGE

    def __post_init__(self) -> None:
        try:
            validated = Brief.from_report_slot(
                report_date=self.report_date,
                window_start=self.window_start,
                window_end=self.window_end,
                target_language=self.target_language,
            )
        except CanonicalContractError as error:
            raise Generation2RuntimeConfigurationError("invalid Morning Brief report slot") from error
        object.__setattr__(self, "report_date", validated.report_date)
        object.__setattr__(self, "window_start", validated.window_start)
        object.__setattr__(self, "window_end", validated.window_end)
        object.__setattr__(self, "target_language", validated.target_language)


class _JSONGatewayDelegate(Protocol):
    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> GatewayResponse | Mapping[str, Any]:
        ...


class DeepSeekGeneration2Gateway:
    """Apply the frozen DeepSeek parameters to one Generation 2 stage call."""

    def __init__(self, delegate: _JSONGatewayDelegate) -> None:
        if not callable(getattr(delegate, "complete_json", None)):
            raise Generation2RuntimeConfigurationError("invalid DeepSeek gateway delegate")
        self._delegate = delegate

    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> GatewayResponse | Mapping[str, Any]:
        if parameters is not None:
            raise Generation2RuntimeConfigurationError(
                "Generation 2 stage parameters are runtime-owned"
            )
        return self._delegate.complete_json(messages, parameters=DEEPSEEK_PARAMETERS)


@dataclass(frozen=True)
class Generation2Runtime:
    """Production-reusable dependencies for one or more Generation 2 runs."""

    sources: tuple[SourceConfig, ...]
    selector_gateway: SelectorGateway
    classifier_gateway: ClassifierGateway
    writer_gateway: WriterGateway
    embedder_factory: Callable[[], EmbeddingBackend]
    artifact_manager: V1ArtifactManager

    def __post_init__(self) -> None:
        source_values = tuple(self.sources)
        if not source_values or any(not isinstance(source, SourceConfig) for source in source_values):
            raise Generation2RuntimeConfigurationError(
                "Generation 2 requires at least one active SourceConfig"
            )
        object.__setattr__(self, "sources", source_values)
        for gateway in (
            self.selector_gateway,
            self.classifier_gateway,
            self.writer_gateway,
        ):
            if not callable(getattr(gateway, "complete_json", None)):
                raise Generation2RuntimeConfigurationError("Generation 2 gateway is invalid")
        if not callable(self.embedder_factory):
            raise Generation2RuntimeConfigurationError("Generation 2 embedder factory is invalid")
        if not isinstance(self.artifact_manager, V1ArtifactManager):
            raise Generation2RuntimeConfigurationError("Generation 2 artifact manager is invalid")

    def run(
        self,
        report_slot: MorningBriefReportSlot,
        *,
        run_id: str | None = None,
        collector_fetcher: FeedFetcher | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> GenerationRunResult:
        if not isinstance(report_slot, MorningBriefReportSlot):
            raise Generation2RuntimeConfigurationError("report_slot must be canonical")
        runtime_clock = clock or _utc_now
        return run_generation_2(
            report_date=report_slot.report_date,
            window_start=report_slot.window_start,
            window_end=report_slot.window_end,
            target_language=report_slot.target_language,
            sources=self.sources,
            selector_gateway=self.selector_gateway,
            classifier_gateway=self.classifier_gateway,
            writer_gateway=self.writer_gateway,
            embedder_factory=self.embedder_factory,
            artifact_manager=self.artifact_manager,
            run_id=run_id,
            collector_fetcher=collector_fetcher,
            clock=runtime_clock,
        )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_morning_brief_report_slot(
    report_date: date | str | None = None,
    *,
    clock: Callable[[], datetime] = _utc_now,
) -> MorningBriefReportSlot:
    """Resolve the Shanghai 08:00 cutoff and preceding 24-hour UTC window."""

    if report_date is None:
        try:
            now = clock()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                raise ValueError
            resolved_date: date | str = now.astimezone(MORNING_BRIEF_TIMEZONE).date()
        except Exception:
            raise Generation2RuntimeConfigurationError("runtime clock must return an aware datetime") from None
    else:
        resolved_date = report_date

    try:
        if isinstance(resolved_date, datetime):
            raise ValueError
        if isinstance(resolved_date, str):
            if not _REPORT_DATE_PATTERN.fullmatch(resolved_date):
                raise ValueError
            resolved_date = date.fromisoformat(resolved_date)
        if not isinstance(resolved_date, date):
            raise ValueError
    except (TypeError, ValueError):
        raise Generation2RuntimeConfigurationError(
            "report_date must be a valid YYYY-MM-DD calendar date"
        ) from None

    local_window_end = datetime.combine(
        resolved_date,
        MORNING_BRIEF_CUTOFF,
        tzinfo=MORNING_BRIEF_TIMEZONE,
    )
    local_window_start = local_window_end - MORNING_BRIEF_WINDOW
    return MorningBriefReportSlot(
        report_date=resolved_date,
        window_start=local_window_start.astimezone(timezone.utc),
        window_end=local_window_end.astimezone(timezone.utc),
    )


def build_deepseek_generation_2_gateway(
    *,
    transport: HTTPTransport | None = None,
) -> DeepSeekGeneration2Gateway:
    """Build the shared JSON gateway with the accepted DeepSeek profile."""

    delegate = OpenAICompatibleJSONGateway(
        OpenAICompatibleGatewayConfig(
            provider_id=DEEPSEEK_PROVIDER_ID,
            model=DEEPSEEK_MODEL,
            endpoint=DEEPSEEK_ENDPOINT,
            api_key_env=DEEPSEEK_API_KEY_ENV,
            timeout=DEEPSEEK_TIMEOUT_SECONDS,
            max_attempts=DEEPSEEK_MAX_ATTEMPTS,
        ),
        transport=transport,
    )
    return DeepSeekGeneration2Gateway(delegate)


def resolve_generation_2_model_cache(
    paths: ProjectPaths,
    model_cache: Path | None = None,
) -> Path:
    """Resolve and preflight the local-only embedding model cache."""

    if not isinstance(paths, ProjectPaths):
        raise Generation2RuntimeConfigurationError("project paths are invalid")
    if model_cache is not None:
        resolved = Path(model_cache).expanduser()
    else:
        configured = os.environ.get(MODEL_CACHE_ENV, "").strip()
        resolved = (
            Path(configured).expanduser()
            if configured
            else paths.runs_dir / "model-cache"
        )
    try:
        cache_available = resolved.is_dir() and next(resolved.iterdir(), None) is not None
    except OSError:
        cache_available = False
    if not cache_available:
        raise Generation2RuntimeConfigurationError(
            f"Generation 2 model cache is unavailable: {resolved}"
        )
    return resolved


def build_generation_2_runtime(
    *,
    provider: str,
    feeds_path: Path = DEFAULT_FEEDS_PATH,
    data_root: Path | None = None,
    model_cache: Path | None = None,
) -> Generation2Runtime:
    """Build the formal real-provider Generation 2 runtime."""

    if provider != DEEPSEEK_PROVIDER_ID:
        raise Generation2RuntimeConfigurationError("unsupported Generation 2 provider")
    if not os.environ.get(DEEPSEEK_API_KEY_ENV, "").strip():
        raise Generation2RuntimeConfigurationError(
            f"DeepSeek credential is missing from process env: {DEEPSEEK_API_KEY_ENV}"
        )

    paths = get_project_paths(repo_root=PROJECT_ROOT, data_root=data_root)
    cache_path = resolve_generation_2_model_cache(paths, model_cache)
    try:
        embedder = SentenceTransformerEmbedder(
            model_id=MODEL_ID,
            model_revision=MODEL_REVISION,
            cache_folder=str(cache_path),
            local_files_only=True,
        )
    except Exception:
        raise Generation2RuntimeConfigurationError(
            "Generation 2 pinned local model cache is unavailable"
        ) from None
    try:
        sources = load_sources(Path(feeds_path))
    except (OSError, TypeError, ValueError) as error:
        raise Generation2RuntimeConfigurationError("unable to load active Generation 2 sources") from error
    if not sources:
        raise Generation2RuntimeConfigurationError("Generation 2 active source list is empty")

    gateway = build_deepseek_generation_2_gateway()

    def embedder_factory() -> EmbeddingBackend:
        return embedder

    return Generation2Runtime(
        sources=sources,
        selector_gateway=gateway,
        classifier_gateway=gateway,
        writer_gateway=gateway,
        embedder_factory=embedder_factory,
        artifact_manager=V1ArtifactManager(paths),
    )


__all__ = [
    "DEFAULT_FEEDS_PATH",
    "DEEPSEEK_API_KEY_ENV",
    "DEEPSEEK_ENDPOINT",
    "DEEPSEEK_MAX_ATTEMPTS",
    "DEEPSEEK_MAX_TOKENS",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_PROVIDER_ID",
    "DEEPSEEK_TIMEOUT_SECONDS",
    "DeepSeekGeneration2Gateway",
    "Generation2Runtime",
    "Generation2RuntimeConfigurationError",
    "MODEL_CACHE_ENV",
    "MORNING_BRIEF_CUTOFF",
    "MORNING_BRIEF_TIMEZONE_NAME",
    "MORNING_BRIEF_WINDOW",
    "MorningBriefReportSlot",
    "build_deepseek_generation_2_gateway",
    "build_generation_2_runtime",
    "resolve_generation_2_model_cache",
    "resolve_morning_brief_report_slot",
]
