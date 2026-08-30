"""Deterministic v1.2 source collection boundary.

The collector is intentionally side-by-side with Generation 1.  It keeps only
the source metadata needed by the canonical Article pipeline and emits small
source-scoped raw batches for the normalizer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import time as time_module
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence
import urllib.request
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import feedparser

from canonical_domain import (
    FailureCode,
    ItemFailure,
    StageName,
    StageResult,
    StageStatus,
    normalize_canonical_datetime,
    normalize_language,
)


FEED_FETCH_ATTEMPTS = 2
FEED_FETCH_RETRY_DELAY_SECONDS = 3
FEED_FETCH_TIMEOUT_SECONDS = 15
FEED_ACCEPT_HEADER = (
    "application/atom+xml, application/rss+xml, application/xml, text/xml, */*"
)


@dataclass(frozen=True)
class SourceConfig:
    """The non-legacy source metadata needed by v1.x ingest."""

    name: str
    url: str
    language: str = "und"
    timezone: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("source name must be a non-empty string")
        if not isinstance(self.url, str) or not self.url.strip():
            raise ValueError("source url must be a non-empty string")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "url", self.url.strip())
        object.__setattr__(self, "language", normalize_language(self.language))
        if self.timezone is None:
            return
        if not isinstance(self.timezone, str):
            raise ValueError("source timezone must be a string or None")
        normalized_timezone = self.timezone.strip()
        if not normalized_timezone:
            raise ValueError("source timezone must be a non-empty IANA timezone")
        try:
            ZoneInfo(normalized_timezone)
        except (OSError, ValueError, ZoneInfoNotFoundError) as error:
            raise ValueError("source timezone must be a valid IANA timezone") from error
        object.__setattr__(self, "timezone", normalized_timezone)


@dataclass(frozen=True)
class RawFeedEntry:
    """Small, temporary representation extracted from one feed entry."""

    source: SourceConfig
    ordinal: int
    entry_id: str | None
    title: str | None
    link: str | None
    summary: str | None
    description: str | None
    published: str | None
    updated: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceConfig):
            raise ValueError("raw entry source must be SourceConfig")
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int) or self.ordinal < 1:
            raise ValueError("raw entry ordinal must be a positive integer")

    @property
    def item_id(self) -> str:
        return f"{source_identifier(self.source)}:{self.ordinal}"


@dataclass(frozen=True)
class SourceBatch:
    """One successfully fetched source, including a legal zero-entry batch."""

    source: SourceConfig
    collected_at: datetime
    entries: tuple[RawFeedEntry, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceConfig):
            raise ValueError("source batch source must be SourceConfig")
        object.__setattr__(
            self,
            "collected_at",
            normalize_canonical_datetime(self.collected_at, "collected_at"),
        )
        if isinstance(self.entries, (str, bytes)):
            raise ValueError("source batch entries must be iterable")
        normalized_entries = tuple(self.entries)
        if any(not isinstance(entry, RawFeedEntry) for entry in normalized_entries):
            raise ValueError("source batch entries must contain RawFeedEntry objects")
        if any(entry.source != self.source for entry in normalized_entries):
            raise ValueError("source batch entries must belong to the batch source")
        object.__setattr__(self, "entries", normalized_entries)


class FeedFetcher(Protocol):
    def __call__(self, source: SourceConfig) -> Any:
        ...


SourceDiagnosticSink = Callable[[Mapping[str, Any]], Any]


@dataclass(frozen=True)
class SourceFetchOutcome:
    """Secret-safe runtime metadata returned by the formal RSS adapter."""

    parsed_feed: Any
    attempt_count: int
    http_status: int | None
    duration_ms: float


class SourceFetchError(RuntimeError):
    """Exhausted or deterministic source failure with bounded metadata."""

    def __init__(
        self,
        *,
        attempt_count: int,
        http_status: int | None,
        duration_ms: float,
    ) -> None:
        self.attempt_count = attempt_count
        self.http_status = http_status
        self.duration_ms = duration_ms
        super().__init__("source fetch failed")


def source_identifier(source: SourceConfig) -> str:
    """Return a stable, non-content source identifier for failure metadata."""

    basis = f"{source.name}\n{source.url}".encode("utf-8")
    return f"src_{hashlib.sha256(basis).hexdigest()[:24]}"


def normalize_sources(raw_sources: Any) -> tuple[SourceConfig, ...]:
    """Load non-legacy source metadata from the active feed config."""

    if not isinstance(raw_sources, list):
        raise ValueError("feeds.json must be a list of source objects")

    sources: list[SourceConfig] = []
    for index, raw_source in enumerate(raw_sources, start=1):
        if not isinstance(raw_source, Mapping):
            raise ValueError(f"Source #{index} must be an object")
        name = raw_source.get("name")
        url = raw_source.get("url")
        sources.append(
            SourceConfig(
                name=name.strip() if isinstance(name, str) else "",
                url=url.strip() if isinstance(url, str) else "",
                language=raw_source.get("language"),
                timezone=raw_source.get("timezone"),
            )
        )
    return tuple(sources)


def load_sources(path: Path) -> tuple[SourceConfig, ...]:
    """Read the existing active feed configuration without copying its list."""

    with path.open("r", encoding="utf-8") as file:
        return normalize_sources(json.load(file))


def _http_status(response: Any) -> int | None:
    status = getattr(response, "status", None)
    if status is None and callable(getattr(response, "getcode", None)):
        status = response.getcode()
    return status if type(status) is int and 100 <= status <= 599 else None


def _retryable_source_error(error: BaseException) -> bool:
    if isinstance(error, HTTPError):
        return error.code == 429 or 500 <= error.code <= 599
    if isinstance(error, TimeoutError):
        return True
    if isinstance(error, URLError):
        return True
    return isinstance(error, OSError)


def _source_fetch_error(
    started_at: float,
    *,
    attempt_count: int,
    http_status: int | None,
) -> SourceFetchError:
    return SourceFetchError(
        attempt_count=attempt_count,
        http_status=http_status,
        duration_ms=round((time_module.perf_counter() - started_at) * 1000, 3),
    )


def fetch_source(source: SourceConfig) -> SourceFetchOutcome:
    """Fetch and parse one source without importing the Generation 1 runtime."""

    if not isinstance(source, SourceConfig):
        raise ValueError("source must be SourceConfig")
    started_at = time_module.perf_counter()
    for attempt in range(1, FEED_FETCH_ATTEMPTS + 1):
        try:
            request = urllib.request.Request(
                source.url,
                headers={
                    "User-Agent": feedparser.USER_AGENT,
                    "Accept": FEED_ACCEPT_HEADER,
                },
            )
            with urllib.request.urlopen(
                request,
                timeout=FEED_FETCH_TIMEOUT_SECONDS,
            ) as response:
                payload = response.read()
                response_headers = {
                    key.lower(): value for key, value in response.headers.items()
                }
                response_headers.setdefault("content-location", response.geturl())
                http_status = _http_status(response)
        except Exception as error:
            error_status = error.code if isinstance(error, HTTPError) else None
            if _retryable_source_error(error) and attempt < FEED_FETCH_ATTEMPTS:
                time_module.sleep(FEED_FETCH_RETRY_DELAY_SECONDS)
                continue
            raise _source_fetch_error(
                started_at,
                attempt_count=attempt,
                http_status=error_status,
            ) from error
        try:
            parsed_feed = feedparser.parse(payload, response_headers=response_headers)
        except Exception as error:
            raise _source_fetch_error(
                started_at,
                attempt_count=attempt,
                http_status=http_status,
            ) from error
        if parsed_feed.bozo and len(parsed_feed.entries) == 0:
            parse_error = getattr(
                parsed_feed,
                "bozo_exception",
                RuntimeError("feed parse failed"),
            )
            if not isinstance(parse_error, BaseException):
                parse_error = RuntimeError("feed parse failed")
            raise _source_fetch_error(
                started_at,
                attempt_count=attempt,
                http_status=http_status,
            ) from parse_error
        return SourceFetchOutcome(
            parsed_feed=parsed_feed,
            attempt_count=attempt,
            http_status=http_status,
            duration_ms=round((time_module.perf_counter() - started_at) * 1000, 3),
        )
    raise AssertionError("bounded source attempts exhausted without a result")


def _entry_value(entry: Any, key: str) -> Any:
    if isinstance(entry, Mapping):
        return entry.get(key)
    return getattr(entry, key, None)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _extract_raw_entry(source: SourceConfig, entry: Any, ordinal: int) -> RawFeedEntry:
    entry_id = _entry_value(entry, "id") or _entry_value(entry, "guid")
    return RawFeedEntry(
        source=source,
        ordinal=ordinal,
        entry_id=_optional_string(entry_id),
        title=_optional_string(_entry_value(entry, "title")),
        link=_optional_string(_entry_value(entry, "link")),
        summary=_optional_string(_entry_value(entry, "summary")),
        description=_optional_string(_entry_value(entry, "description")),
        published=_optional_string(_entry_value(entry, "published")),
        updated=_optional_string(_entry_value(entry, "updated")),
    )


def _feed_entries(parsed_feed: Any) -> tuple[Any, ...]:
    raw_entries = (
        parsed_feed.get("entries")
        if isinstance(parsed_feed, Mapping)
        else getattr(parsed_feed, "entries", None)
    )
    if raw_entries is None:
        raise ValueError("parsed feed has no entries collection")
    if isinstance(raw_entries, (str, bytes)):
        raise ValueError("parsed feed entries must be iterable")
    try:
        return tuple(raw_entries)
    except TypeError as exc:
        raise ValueError("parsed feed entries must be iterable") from exc


def _failure_code(error: BaseException) -> FailureCode:
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, TimeoutError):
            return FailureCode.TIMEOUT
        if isinstance(current, HTTPError):
            return FailureCode.SOURCE_FETCH_FAILED
        reason = getattr(current, "reason", None)
        if isinstance(reason, TimeoutError):
            return FailureCode.TIMEOUT
        if isinstance(current, (OSError, URLError)):
            return FailureCode.TRANSPORT_FAILED
        current = current.__cause__ or current.__context__
    return FailureCode.SOURCE_FETCH_FAILED


def _emit_source_diagnostic(
    sink: SourceDiagnosticSink | None,
    *,
    source_ref: str,
    status: str,
    metadata: SourceFetchOutcome | SourceFetchError,
    failure_code: FailureCode | None = None,
) -> None:
    if sink is None:
        return
    record: dict[str, Any] = {
        "source_ref": source_ref,
        "status": status,
        "attempt": metadata.attempt_count,
        "duration_ms": metadata.duration_ms,
    }
    if metadata.http_status is not None:
        record["http_status"] = metadata.http_status
    if failure_code is not None:
        record["failure_code"] = failure_code.value
    try:
        sink(record)
    except Exception:
        pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def collect_sources(
    sources: Sequence[SourceConfig],
    *,
    fetcher: FeedFetcher | None = None,
    clock: Callable[[], datetime] = _utc_now,
    diagnostic_sink: SourceDiagnosticSink | None = None,
) -> StageResult[SourceBatch]:
    """Fetch each configured source and retain successful source batches."""

    active_fetcher = fetcher or fetch_source
    successful_batches: list[SourceBatch] = []
    failures: list[ItemFailure] = []

    for source in tuple(sources):
        item_id = source_identifier(source) if isinstance(source, SourceConfig) else None
        fetch_metadata: SourceFetchOutcome | None = None
        try:
            if not isinstance(source, SourceConfig):
                raise ValueError("sources must contain SourceConfig objects")
            fetched = active_fetcher(source)
            if isinstance(fetched, SourceFetchOutcome):
                fetch_metadata = fetched
                parsed_feed = fetched.parsed_feed
            else:
                parsed_feed = fetched
            entries = _feed_entries(parsed_feed)
            collected_at = normalize_canonical_datetime(clock(), "collected_at")
            raw_entries = tuple(
                _extract_raw_entry(source, entry, ordinal)
                for ordinal, entry in enumerate(entries, start=1)
            )
            successful_batches.append(
                SourceBatch(source=source, collected_at=collected_at, entries=raw_entries)
            )
            if fetch_metadata is not None and item_id is not None:
                _emit_source_diagnostic(
                    diagnostic_sink,
                    source_ref=item_id,
                    status="succeeded",
                    metadata=fetch_metadata,
                )
        except Exception as error:
            failure_code = _failure_code(error)
            failures.append(ItemFailure(item_id=item_id, code=failure_code))
            diagnostic_metadata = (
                error if isinstance(error, SourceFetchError) else fetch_metadata
            )
            if diagnostic_metadata is not None and item_id is not None:
                _emit_source_diagnostic(
                    diagnostic_sink,
                    source_ref=item_id,
                    status="failed",
                    metadata=diagnostic_metadata,
                    failure_code=failure_code,
                )

    if failures and successful_batches:
        status = StageStatus.PARTIAL
    elif failures:
        status = StageStatus.FAILED
    else:
        status = StageStatus.SUCCEEDED

    return StageResult(
        stage=StageName.COLLECTOR,
        status=status,
        outputs=tuple(successful_batches),
        failures=tuple(failures),
    )


def flatten_source_batches(batches: Iterable[SourceBatch]) -> tuple[RawFeedEntry, ...]:
    """Expand successful source batches for normalizer consumption."""

    return tuple(entry for batch in batches for entry in batch.entries)


__all__ = [
    "FeedFetcher",
    "RawFeedEntry",
    "SourceBatch",
    "SourceConfig",
    "SourceDiagnosticSink",
    "SourceFetchError",
    "SourceFetchOutcome",
    "collect_sources",
    "fetch_source",
    "flatten_source_batches",
    "load_sources",
    "normalize_sources",
    "source_identifier",
]
