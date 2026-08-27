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
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence
from urllib.error import URLError

from canonical_domain import (
    FailureCode,
    ItemFailure,
    StageName,
    StageResult,
    StageStatus,
    normalize_canonical_datetime,
    normalize_language,
)


@dataclass(frozen=True)
class SourceConfig:
    """The non-legacy source metadata needed by v1.x ingest."""

    name: str
    url: str
    language: str = "und"

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("source name must be a non-empty string")
        if not isinstance(self.url, str) or not self.url.strip():
            raise ValueError("source url must be a non-empty string")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "url", self.url.strip())
        object.__setattr__(self, "language", normalize_language(self.language))


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


def source_identifier(source: SourceConfig) -> str:
    """Return a stable, non-content source identifier for failure metadata."""

    basis = f"{source.name}\n{source.url}".encode("utf-8")
    return f"src_{hashlib.sha256(basis).hexdigest()[:24]}"


def normalize_sources(raw_sources: Any) -> tuple[SourceConfig, ...]:
    """Load only source name, URL, and language from the active feed config."""

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
            )
        )
    return tuple(sources)


def load_sources(path: Path) -> tuple[SourceConfig, ...]:
    """Read the existing active feed configuration without copying its list."""

    with path.open("r", encoding="utf-8") as file:
        return normalize_sources(json.load(file))


def fetch_source(source: SourceConfig) -> Any:
    """Reuse the mature Gen1 HTTP/feedparser retry boundary without its semantics."""

    from main import parse_feed_with_retry

    return parse_feed_with_retry({"name": source.name, "url": source.url})


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
        reason = getattr(current, "reason", None)
        if isinstance(reason, TimeoutError):
            return FailureCode.TIMEOUT
        if isinstance(current, (OSError, URLError)):
            return FailureCode.TRANSPORT_FAILED
        current = current.__cause__ or current.__context__
    return FailureCode.SOURCE_FETCH_FAILED


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def collect_sources(
    sources: Sequence[SourceConfig],
    *,
    fetcher: FeedFetcher | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> StageResult[SourceBatch]:
    """Fetch each configured source and retain successful source batches."""

    active_fetcher = fetcher or fetch_source
    successful_batches: list[SourceBatch] = []
    failures: list[ItemFailure] = []

    for source in tuple(sources):
        item_id = source_identifier(source) if isinstance(source, SourceConfig) else None
        try:
            if not isinstance(source, SourceConfig):
                raise ValueError("sources must contain SourceConfig objects")
            parsed_feed = active_fetcher(source)
            entries = _feed_entries(parsed_feed)
            collected_at = normalize_canonical_datetime(clock(), "collected_at")
            raw_entries = tuple(
                _extract_raw_entry(source, entry, ordinal)
                for ordinal, entry in enumerate(entries, start=1)
            )
            successful_batches.append(
                SourceBatch(source=source, collected_at=collected_at, entries=raw_entries)
            )
        except Exception as error:
            failures.append(ItemFailure(item_id=item_id, code=_failure_code(error)))

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
    "collect_sources",
    "fetch_source",
    "flatten_source_batches",
    "load_sources",
    "normalize_sources",
    "source_identifier",
]
