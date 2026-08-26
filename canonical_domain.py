"""Canonical v1.1 domain objects for the event-driven morning brief.

This module is deliberately side-by-side with the Gen1 implementation.  It
contains only the v1.1 domain foundation and uses standard-library types and
JSON serialization so that the foundation can be exercised offline.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields, replace
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Callable, Generic, Iterable, Mapping, TypeVar
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


CONTRACT_VERSION = "v1.0-core-data-contract"
TARGET_LANGUAGE = "zh-CN"
LANGUAGE_VALUES = frozenset({"zh-CN", "en", "und"})


class CanonicalContractError(ValueError):
    """Raised when a value violates the frozen canonical data contract."""


class EventCategory(str, Enum):
    GEOPOLITICS = "geopolitics"
    MACRO_POLICY = "macro_policy"
    FINANCIAL_MARKETS = "financial_markets"
    ENERGY_COMMODITIES = "energy_commodities"
    CHINA_POLICY = "china_policy"
    COMPANY_INDUSTRY = "company_industry"
    TECHNOLOGY_AI = "technology_ai"
    PUBLIC_SAFETY = "public_safety"
    OTHER = "other"


class GenerationStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"


class StageStatus(str, Enum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class StageName(str, Enum):
    COLLECTOR = "collector"
    NORMALIZER = "normalizer"
    ARTICLE_DEDUP = "article_dedup"
    EVENT_CLUSTER = "event_cluster"
    EVENT_SELECTOR = "event_selector"
    EVENT_CLASSIFIER = "event_classifier"
    EVENT_WRITER = "event_writer"
    BRIEF_RENDERER = "brief_renderer"
    DELIVERY = "delivery"


class FailureCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    SOURCE_FETCH_FAILED = "source_fetch_failed"
    TIMEOUT = "timeout"
    TRANSPORT_FAILED = "transport_failed"
    PROVIDER_FAILED = "provider_failed"
    RESPONSE_PARSE_FAILED = "response_parse_failed"
    ITEM_VALIDATION_FAILED = "item_validation_failed"
    UNKNOWN_REFERENCE = "unknown_reference"
    LOCAL_MODEL_FAILED = "local_model_failed"
    RENDER_FAILED = "render_failed"
    PERSISTENCE_FAILED = "persistence_failed"
    DELIVERY_FAILED = "delivery_failed"


_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ID_PATTERNS = {
    "article": re.compile(r"^art_[0-9a-f]{24}$"),
    "event": re.compile(r"^evt_[0-9a-f]{24}$"),
    "brief": re.compile(r"^brief_[0-9a-f]{24}$"),
}


def _contract_error(message: str) -> CanonicalContractError:
    return CanonicalContractError(message)


def _require_exact_keys(payload: Mapping[str, Any], expected: Iterable[str], context: str) -> None:
    if not isinstance(payload, Mapping):
        raise _contract_error(f"{context} must be a JSON object")
    actual = set(payload)
    expected_set = set(expected)
    if actual != expected_set:
        missing = sorted(expected_set - actual)
        extra = sorted(actual - expected_set)
        details: list[str] = []
        if missing:
            details.append(f"missing={missing}")
        if extra:
            details.append(f"extra={extra}")
        raise _contract_error(f"{context} keys are not canonical: {', '.join(details)}")


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _contract_error(f"{field_name} must be a non-empty string")
    return value


def _optional_text(value: Any, field_name: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise _contract_error(f"{field_name} must be a string or null")
    return value


def normalize_language(value: Any) -> str:
    """Normalize source language labels using the frozen Article vocabulary."""

    normalized = str(value or "").strip().replace("_", "-").lower()
    canonical = {"zh-cn": "zh-CN", "en": "en", "und": "und"}.get(normalized, "und")
    return canonical if canonical in LANGUAGE_VALUES else "und"


def _normalize_datetime(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise _contract_error(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise _contract_error(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def normalize_canonical_datetime(value: datetime, field_name: str = "datetime") -> datetime:
    """Normalize an aware datetime using the canonical UTC contract."""

    return _normalize_datetime(value, field_name)


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise _contract_error(f"{field_name} must be an ISO-8601 datetime string")
    normalized_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized_value)
    except ValueError as exc:
        raise _contract_error(f"{field_name} must be a valid ISO-8601 datetime") from exc
    return _normalize_datetime(parsed, field_name)


def _datetime_to_string(value: datetime, field_name: str) -> str:
    return _normalize_datetime(value, field_name).isoformat()


def _normalize_report_date(value: date | str) -> date:
    if isinstance(value, datetime):
        raise _contract_error("report_date must be a date or YYYY-MM-DD string, not datetime")
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not _DATE_PATTERN.fullmatch(value):
        raise _contract_error("report_date must be formatted as YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise _contract_error("report_date must be a valid calendar date") from exc


def validate_report_window(
    window_start: datetime, window_end: datetime
) -> tuple[datetime, datetime]:
    """Normalize an inclusive report window to UTC and validate its ordering."""

    normalized_start = _normalize_datetime(window_start, "window_start")
    normalized_end = _normalize_datetime(window_end, "window_end")
    if normalized_end <= normalized_start:
        raise _contract_error("window_end must be later than window_start")
    return normalized_start, normalized_end


def datetime_in_report_window(value: datetime, window_start: datetime, window_end: datetime) -> bool:
    """Return whether an aware datetime falls inside the inclusive window."""

    normalized_value = _normalize_datetime(value, "value")
    normalized_start, normalized_end = validate_report_window(window_start, window_end)
    return normalized_start <= normalized_value <= normalized_end


def normalize_canonical_url(url: str) -> str:
    """Return the contract's canonical HTTP(S) URL representation."""

    if not isinstance(url, str) or not url.strip():
        raise _contract_error("url must be a non-empty string")
    candidate = url.strip()
    try:
        parsed = urlsplit(candidate)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            raise _contract_error("url must be an absolute HTTP(S) URL")
        if parsed.hostname is None:
            raise _contract_error("url must be an absolute HTTP(S) URL")
        _ = parsed.port
        if parsed.username is not None or parsed.password is not None:
            raise _contract_error("url must not contain credentials")
    except ValueError as exc:
        raise _contract_error("url must be a valid absolute HTTP(S) URL") from exc
    if any(character.isspace() for character in parsed.netloc):
        raise _contract_error("url must be a valid absolute HTTP(S) URL")
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in {"fbclid", "gclid"} and not key.lower().startswith("utm_")
    ]
    normalized_parts = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        query=urlencode(query_items, doseq=True),
        fragment="",
    )
    path = normalized_parts.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return urlunsplit(
        (
            normalized_parts.scheme.lower(),
            normalized_parts.netloc.lower(),
            path,
            normalized_parts.query,
            "",
        )
    )


def _validate_id(value: Any, kind: str, field_name: str) -> str:
    if not isinstance(value, str) or not _ID_PATTERNS[kind].fullmatch(value):
        raise _contract_error(f"{field_name} must match the canonical {kind} ID format")
    return value


def _canonical_article_ids(article_ids: Iterable[str], *, sort: bool) -> tuple[str, ...]:
    if isinstance(article_ids, (str, bytes)):
        raise _contract_error("article_ids must be an iterable of article IDs")
    try:
        values = tuple(article_ids)
    except TypeError as exc:
        raise _contract_error("article_ids must be an iterable of article IDs") from exc
    for article_id in values:
        _validate_id(article_id, "article", "article_id")
    if len(set(values)) != len(values):
        raise _contract_error("article_ids must not contain duplicates")
    if not values:
        raise _contract_error("article_ids must not be empty")
    canonical = tuple(sorted(values)) if sort else values
    if not sort and canonical != values:
        raise _contract_error("article_ids must be lexicographically sorted")
    return canonical


def _canonical_event_ids(event_ids: Iterable[str]) -> tuple[str, ...]:
    if isinstance(event_ids, (str, bytes)):
        raise _contract_error("event_ids must be an iterable of event IDs")
    try:
        values = tuple(event_ids)
    except TypeError as exc:
        raise _contract_error("event_ids must be an iterable of event IDs") from exc
    for event_id in values:
        _validate_id(event_id, "event", "event_id")
    if len(set(values)) != len(values):
        raise _contract_error("event_ids must not contain duplicates")
    return values


def stable_article_id(
    canonical_url: str | None,
    source: str,
    title: str,
    published_at: datetime | None,
) -> str:
    """Derive the stable article ID from the frozen identity basis."""

    normalized_url = None if canonical_url is None else normalize_canonical_url(canonical_url)
    if normalized_url is None and published_at is None:
        raise _contract_error("linkless article identity requires published_at")
    normalized_published_at = (
        None if published_at is None else _normalize_datetime(published_at, "published_at")
    )
    _required_text(source, "source")
    _required_text(title, "title")
    if normalized_url:
        basis = f"link:{normalized_url}"
    else:
        published_value = (
            _datetime_to_string(normalized_published_at, "published_at")
            if normalized_published_at
            else ""
        )
        normalized_title = " ".join(title.lower().split())
        basis = f"fallback:{source.strip().lower()}:{normalized_title}:{published_value}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]
    return f"art_{digest}"


def stable_event_candidate_id(article_ids: Iterable[str]) -> str:
    canonical_ids = _canonical_article_ids(article_ids, sort=True)
    digest = hashlib.sha256("\n".join(canonical_ids).encode("utf-8")).hexdigest()[:24]
    return f"evt_{digest}"


def stable_brief_id(
    report_date: date | str,
    window_start: datetime,
    window_end: datetime,
    target_language: str = TARGET_LANGUAGE,
) -> str:
    normalized_date = _normalize_report_date(report_date)
    normalized_start, normalized_end = validate_report_window(window_start, window_end)
    if target_language != TARGET_LANGUAGE:
        raise _contract_error(f"target_language must be {TARGET_LANGUAGE}")
    basis = "|".join(
        (
            normalized_date.isoformat(),
            _datetime_to_string(normalized_start, "window_start"),
            _datetime_to_string(normalized_end, "window_end"),
            target_language,
        )
    )
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]
    return f"brief_{digest}"


@dataclass(frozen=True)
class Article:
    article_id: str
    source: str
    url: str | None
    canonical_url: str | None
    published_at: datetime | None
    collected_at: datetime
    language: str
    title: str
    summary: str | None

    def __post_init__(self) -> None:
        _validate_id(self.article_id, "article", "article_id")
        _required_text(self.source, "source")
        _required_text(self.title, "title")
        if self.url is not None and not isinstance(self.url, str):
            raise _contract_error("url must be a string or null")
        if self.url is not None:
            normalized_url = normalize_canonical_url(self.url)
            if self.canonical_url != normalized_url:
                raise _contract_error("canonical_url must match the normalized url")
        elif self.canonical_url is not None:
            raise _contract_error("canonical_url must be null when url is null")
        if self.canonical_url is not None:
            normalized_canonical_url = normalize_canonical_url(self.canonical_url)
            object.__setattr__(self, "canonical_url", normalized_canonical_url)
        normalized_published_at = (
            None
            if self.published_at is None
            else _normalize_datetime(self.published_at, "published_at")
        )
        if self.url is None and normalized_published_at is None:
            raise _contract_error("linkless article requires published_at")
        object.__setattr__(self, "published_at", normalized_published_at)
        object.__setattr__(self, "collected_at", _normalize_datetime(self.collected_at, "collected_at"))
        object.__setattr__(self, "language", normalize_language(self.language))
        _optional_text(self.summary, "summary")
        expected_id = stable_article_id(
            self.canonical_url,
            self.source,
            self.title,
            self.published_at,
        )
        if self.article_id != expected_id:
            raise _contract_error("article_id does not match the canonical identity basis")

    @classmethod
    def from_source(
        cls,
        source: str,
        url: str | None,
        published_at: datetime | None,
        collected_at: datetime,
        language: str,
        title: str,
        summary: str | None = None,
    ) -> "Article":
        canonical_url = None if url is None else normalize_canonical_url(url)
        article_id = stable_article_id(canonical_url, source, title, published_at)
        return cls(
            article_id=article_id,
            source=source,
            url=url,
            canonical_url=canonical_url,
            published_at=published_at,
            collected_at=collected_at,
            language=language,
            title=title,
            summary=summary,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "article_id": self.article_id,
            "source": self.source,
            "url": self.url,
            "canonical_url": self.canonical_url,
            "published_at": (
                None if self.published_at is None else _datetime_to_string(self.published_at, "published_at")
            ),
            "collected_at": _datetime_to_string(self.collected_at, "collected_at"),
            "language": self.language,
            "title": self.title,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Article":
        _require_exact_keys(payload, (field.name for field in fields(cls)), "Article")
        published_at = (
            None if payload["published_at"] is None else _parse_datetime(payload["published_at"], "published_at")
        )
        return cls(
            article_id=payload["article_id"],
            source=payload["source"],
            url=payload["url"],
            canonical_url=payload["canonical_url"],
            published_at=published_at,
            collected_at=_parse_datetime(payload["collected_at"], "collected_at"),
            language=payload["language"],
            title=payload["title"],
            summary=payload["summary"],
        )


@dataclass(frozen=True)
class EventCandidate:
    event_candidate_id: str
    article_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_id(self.event_candidate_id, "event", "event_candidate_id")
        canonical_ids = _canonical_article_ids(self.article_ids, sort=False)
        object.__setattr__(self, "article_ids", canonical_ids)
        expected_id = stable_event_candidate_id(canonical_ids)
        if self.event_candidate_id != expected_id:
            raise _contract_error("event_candidate_id does not match article membership")

    @classmethod
    def from_article_ids(cls, article_ids: Iterable[str]) -> "EventCandidate":
        canonical_ids = _canonical_article_ids(article_ids, sort=True)
        return cls(
            event_candidate_id=stable_event_candidate_id(canonical_ids),
            article_ids=canonical_ids,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_candidate_id": self.event_candidate_id,
            "article_ids": list(self.article_ids),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EventCandidate":
        _require_exact_keys(payload, (field.name for field in fields(cls)), "EventCandidate")
        return cls(
            event_candidate_id=payload["event_candidate_id"],
            article_ids=payload["article_ids"],
        )


@dataclass(frozen=True)
class EventClassification:
    category: EventCategory

    def __post_init__(self) -> None:
        try:
            category = self.category if isinstance(self.category, EventCategory) else EventCategory(self.category)
        except (TypeError, ValueError) as exc:
            raise _contract_error("category is not an allowed canonical event category") from exc
        object.__setattr__(self, "category", category)

    def to_dict(self) -> dict[str, Any]:
        return {"category": self.category.value}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EventClassification":
        _require_exact_keys(payload, (field.name for field in fields(cls)), "EventClassification")
        return cls(category=payload["category"])


@dataclass(frozen=True)
class EventWriting:
    title_zh: str
    summary_zh: str
    why_it_matters_zh: str

    def __post_init__(self) -> None:
        _required_text(self.title_zh, "title_zh")
        _required_text(self.summary_zh, "summary_zh")
        _required_text(self.why_it_matters_zh, "why_it_matters_zh")

    def to_dict(self) -> dict[str, Any]:
        return {
            "title_zh": self.title_zh,
            "summary_zh": self.summary_zh,
            "why_it_matters_zh": self.why_it_matters_zh,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EventWriting":
        _require_exact_keys(payload, (field.name for field in fields(cls)), "EventWriting")
        return cls(
            title_zh=payload["title_zh"],
            summary_zh=payload["summary_zh"],
            why_it_matters_zh=payload["why_it_matters_zh"],
        )


@dataclass(frozen=True)
class Event:
    event_id: str
    article_ids: tuple[str, ...]
    selection_order: int
    classification: EventClassification | None = None
    writing: EventWriting | None = None

    def __post_init__(self) -> None:
        _validate_id(self.event_id, "event", "event_id")
        canonical_ids = _canonical_article_ids(self.article_ids, sort=False)
        object.__setattr__(self, "article_ids", canonical_ids)
        expected_id = stable_event_candidate_id(canonical_ids)
        if self.event_id != expected_id:
            raise _contract_error("event_id does not match article membership")
        if isinstance(self.selection_order, bool) or not isinstance(self.selection_order, int):
            raise _contract_error("selection_order must be a positive integer")
        if self.selection_order < 1:
            raise _contract_error("selection_order must be a positive integer")
        if self.classification is not None and not isinstance(self.classification, EventClassification):
            raise _contract_error("classification must be EventClassification or null")
        if self.writing is not None and not isinstance(self.writing, EventWriting):
            raise _contract_error("writing must be EventWriting or null")

    @classmethod
    def from_candidate(cls, candidate: EventCandidate, selection_order: int) -> "Event":
        if not isinstance(candidate, EventCandidate):
            raise _contract_error("candidate must be an EventCandidate")
        return cls(
            event_id=candidate.event_candidate_id,
            article_ids=candidate.article_ids,
            selection_order=selection_order,
        )

    def with_classification(self, classification: EventClassification) -> "Event":
        if not isinstance(classification, EventClassification):
            raise _contract_error("classification must be EventClassification")
        return replace(self, classification=classification)

    def with_writing(self, writing: EventWriting) -> "Event":
        if not isinstance(writing, EventWriting):
            raise _contract_error("writing must be EventWriting")
        return replace(self, writing=writing)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "article_ids": list(self.article_ids),
            "selection_order": self.selection_order,
            "classification": None if self.classification is None else self.classification.to_dict(),
            "writing": None if self.writing is None else self.writing.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Event":
        _require_exact_keys(payload, (field.name for field in fields(cls)), "Event")
        classification = (
            None
            if payload["classification"] is None
            else EventClassification.from_dict(payload["classification"])
        )
        writing = None if payload["writing"] is None else EventWriting.from_dict(payload["writing"])
        return cls(
            event_id=payload["event_id"],
            article_ids=payload["article_ids"],
            selection_order=payload["selection_order"],
            classification=classification,
            writing=writing,
        )


def validate_event_selection_order(events: Iterable[Event]) -> None:
    """Validate that a selected event sequence uses unique contiguous order."""

    values = tuple(events)
    if any(not isinstance(event, Event) for event in values):
        raise _contract_error("events must contain only Event objects")
    event_ids = tuple(event.event_id for event in values)
    orders = tuple(event.selection_order for event in values)
    if len(set(event_ids)) != len(event_ids):
        raise _contract_error("event_id must be unique within a selected sequence")
    if len(set(orders)) != len(orders) or orders != tuple(range(1, len(orders) + 1)):
        raise _contract_error("selection_order must be unique and contiguous from 1")


@dataclass(frozen=True)
class Brief:
    brief_id: str
    report_date: date
    window_start: datetime
    window_end: datetime
    target_language: str
    event_ids: tuple[str, ...]
    generation_status: GenerationStatus

    def __post_init__(self) -> None:
        _validate_id(self.brief_id, "brief", "brief_id")
        normalized_date = _normalize_report_date(self.report_date)
        object.__setattr__(self, "report_date", normalized_date)
        normalized_start, normalized_end = validate_report_window(self.window_start, self.window_end)
        object.__setattr__(self, "window_start", normalized_start)
        object.__setattr__(self, "window_end", normalized_end)
        if self.target_language != TARGET_LANGUAGE:
            raise _contract_error(f"target_language must be {TARGET_LANGUAGE}")
        object.__setattr__(self, "event_ids", _canonical_event_ids(self.event_ids))
        try:
            status = (
                self.generation_status
                if isinstance(self.generation_status, GenerationStatus)
                else GenerationStatus(self.generation_status)
            )
        except (TypeError, ValueError) as exc:
            raise _contract_error("generation_status is not canonical") from exc
        object.__setattr__(self, "generation_status", status)
        expected_id = stable_brief_id(
            normalized_date,
            normalized_start,
            normalized_end,
            self.target_language,
        )
        if self.brief_id != expected_id:
            raise _contract_error("brief_id does not match the report slot")

    @classmethod
    def from_report_slot(
        cls,
        report_date: date | str,
        window_start: datetime,
        window_end: datetime,
        event_ids: Iterable[str] = (),
        generation_status: GenerationStatus = GenerationStatus.COMPLETE,
        target_language: str = TARGET_LANGUAGE,
    ) -> "Brief":
        normalized_date = _normalize_report_date(report_date)
        normalized_start, normalized_end = validate_report_window(window_start, window_end)
        brief_id = stable_brief_id(
            normalized_date,
            normalized_start,
            normalized_end,
            target_language,
        )
        return cls(
            brief_id=brief_id,
            report_date=normalized_date,
            window_start=normalized_start,
            window_end=normalized_end,
            target_language=target_language,
            event_ids=tuple(event_ids),
            generation_status=generation_status,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "brief_id": self.brief_id,
            "report_date": self.report_date.isoformat(),
            "window_start": _datetime_to_string(self.window_start, "window_start"),
            "window_end": _datetime_to_string(self.window_end, "window_end"),
            "target_language": self.target_language,
            "event_ids": list(self.event_ids),
            "generation_status": self.generation_status.value,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Brief":
        _require_exact_keys(payload, (field.name for field in fields(cls)), "Brief")
        return cls(
            brief_id=payload["brief_id"],
            report_date=payload["report_date"],
            window_start=_parse_datetime(payload["window_start"], "window_start"),
            window_end=_parse_datetime(payload["window_end"], "window_end"),
            target_language=payload["target_language"],
            event_ids=payload["event_ids"],
            generation_status=payload["generation_status"],
        )


@dataclass(frozen=True)
class ItemFailure:
    item_id: str | None = None
    code: FailureCode | str = ""

    def __post_init__(self) -> None:
        if self.item_id is not None:
            _required_text(self.item_id, "item_id")
        try:
            code = self.code if isinstance(self.code, FailureCode) else FailureCode(self.code)
        except (TypeError, ValueError) as exc:
            raise _contract_error("code is not an allowed canonical failure code") from exc
        object.__setattr__(self, "code", code)

    def to_dict(self) -> dict[str, Any]:
        return {"item_id": self.item_id, "code": self.code.value}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ItemFailure":
        _require_exact_keys(payload, (field.name for field in fields(cls)), "ItemFailure")
        return cls(item_id=payload["item_id"], code=payload["code"])


T = TypeVar("T")


@dataclass(frozen=True)
class StageResult(Generic[T]):
    stage: StageName | str
    status: StageStatus | str
    outputs: tuple[T, ...] = ()
    failures: tuple[ItemFailure, ...] = ()
    diagnostic_ref: str | None = None

    def __post_init__(self) -> None:
        try:
            stage = self.stage if isinstance(self.stage, StageName) else StageName(self.stage)
        except (TypeError, ValueError) as exc:
            raise _contract_error("stage is not a canonical stage name") from exc
        try:
            status = self.status if isinstance(self.status, StageStatus) else StageStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise _contract_error("status is not a canonical stage status") from exc
        if isinstance(self.outputs, (str, bytes)):
            raise _contract_error("outputs must be an iterable of stage outputs")
        if isinstance(self.failures, (str, bytes)):
            raise _contract_error("failures must be an iterable of ItemFailure")
        try:
            outputs = tuple(self.outputs)
            failures = tuple(self.failures)
        except TypeError as exc:
            raise _contract_error("outputs and failures must be iterable") from exc
        if any(not isinstance(failure, ItemFailure) for failure in failures):
            raise _contract_error("failures must contain only ItemFailure objects")
        if self.diagnostic_ref is not None:
            _required_text(self.diagnostic_ref, "diagnostic_ref")
        if status is StageStatus.SUCCEEDED and failures:
            raise _contract_error("succeeded StageResult must have no failures")
        if status is StageStatus.PARTIAL and (not outputs or not failures):
            raise _contract_error("partial StageResult requires outputs and failures")
        if status is StageStatus.FAILED and (outputs or not failures):
            raise _contract_error("failed StageResult requires failures and no outputs")
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "outputs", outputs)
        object.__setattr__(self, "failures", failures)

    def to_dict(self, output_serializer: Callable[[T], Any] | None = None) -> dict[str, Any]:
        serializer = output_serializer or _serialize_output
        return {
            "stage": self.stage.value,
            "status": self.status.value,
            "outputs": [serializer(output) for output in self.outputs],
            "failures": [failure.to_dict() for failure in self.failures],
            "diagnostic_ref": self.diagnostic_ref,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        output_loader: Callable[[Any], T] | None = None,
    ) -> "StageResult[T]":
        _require_exact_keys(payload, (field.name for field in fields(cls)), "StageResult")
        raw_outputs = payload["outputs"]
        raw_failures = payload["failures"]
        if not isinstance(raw_outputs, list) or not isinstance(raw_failures, list):
            raise _contract_error("StageResult outputs and failures must be JSON arrays")
        loader = output_loader or (lambda output: output)
        return cls(
            stage=payload["stage"],
            status=payload["status"],
            outputs=tuple(loader(output) for output in raw_outputs),
            failures=tuple(ItemFailure.from_dict(failure) for failure in raw_failures),
            diagnostic_ref=payload["diagnostic_ref"],
        )


def _serialize_output(output: Any) -> Any:
    if hasattr(output, "to_dict") and callable(output.to_dict):
        return output.to_dict()
    try:
        json.dumps(output, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise _contract_error("stage output is not deterministically serializable") from exc
    return output


_OBJECT_TYPES: dict[str, type[Any]] = {
    "Article": Article,
    "EventCandidate": EventCandidate,
    "EventClassification": EventClassification,
    "EventWriting": EventWriting,
    "Event": Event,
    "Brief": Brief,
    "ItemFailure": ItemFailure,
    "StageResult": StageResult,
}


def _envelope(object_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "object_type": object_type,
        "payload": dict(payload),
    }


def _serialize_envelope(object_type: str, payload: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            _envelope(object_type, payload),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _contract_error("domain object could not be serialized") from exc


def _load_serialized(value: bytes | bytearray | str | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        payload: Any = value
    elif isinstance(value, (bytes, bytearray)):
        try:
            payload = json.loads(bytes(value).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _contract_error("serialized domain value is not valid UTF-8 JSON") from exc
    elif isinstance(value, str):
        try:
            payload = json.loads(value)
        except json.JSONDecodeError as exc:
            raise _contract_error("serialized domain value is not valid JSON") from exc
    else:
        raise _contract_error("serialized domain value must be bytes, string, or mapping")
    if not isinstance(payload, Mapping):
        raise _contract_error("serialized domain value must be a JSON object")
    return payload


def _unwrap(
    value: bytes | bytearray | str | Mapping[str, Any], expected_type: str | None = None
) -> tuple[str, Mapping[str, Any]]:
    envelope = _load_serialized(value)
    _require_exact_keys(envelope, ("contract_version", "object_type", "payload"), "serialization envelope")
    if envelope["contract_version"] != CONTRACT_VERSION:
        raise _contract_error("unsupported contract_version")
    object_type = envelope["object_type"]
    if not isinstance(object_type, str) or object_type not in _OBJECT_TYPES:
        raise _contract_error("unknown canonical object_type")
    if expected_type is not None and object_type != expected_type:
        raise _contract_error(f"expected {expected_type}, got {object_type}")
    payload = envelope["payload"]
    if not isinstance(payload, Mapping):
        raise _contract_error("serialization payload must be a JSON object")
    return object_type, payload


def _serialize_typed(value: Any, object_class: type[Any]) -> bytes:
    object_type = object_class.__name__
    if not isinstance(value, object_class):
        raise _contract_error(f"serialize_{object_type.lower()} requires {object_type}")
    return _serialize_envelope(object_type, value.to_dict())


def _deserialize_typed(
    value: bytes | bytearray | str | Mapping[str, Any], object_class: type[Any]
) -> Any:
    _, payload = _unwrap(value, object_class.__name__)
    return object_class.from_dict(payload)


def serialize_article(article: Article) -> bytes:
    return _serialize_typed(article, Article)


def deserialize_article(value: bytes | bytearray | str | Mapping[str, Any]) -> Article:
    return _deserialize_typed(value, Article)


def serialize_event_candidate(candidate: EventCandidate) -> bytes:
    return _serialize_typed(candidate, EventCandidate)


def deserialize_event_candidate(value: bytes | bytearray | str | Mapping[str, Any]) -> EventCandidate:
    return _deserialize_typed(value, EventCandidate)


def serialize_event_classification(classification: EventClassification) -> bytes:
    return _serialize_typed(classification, EventClassification)


def deserialize_event_classification(value: bytes | bytearray | str | Mapping[str, Any]) -> EventClassification:
    return _deserialize_typed(value, EventClassification)


def serialize_event_writing(writing: EventWriting) -> bytes:
    return _serialize_typed(writing, EventWriting)


def deserialize_event_writing(value: bytes | bytearray | str | Mapping[str, Any]) -> EventWriting:
    return _deserialize_typed(value, EventWriting)


def serialize_event(event: Event) -> bytes:
    return _serialize_typed(event, Event)


def deserialize_event(value: bytes | bytearray | str | Mapping[str, Any]) -> Event:
    return _deserialize_typed(value, Event)


def serialize_brief(brief: Brief) -> bytes:
    return _serialize_typed(brief, Brief)


def deserialize_brief(value: bytes | bytearray | str | Mapping[str, Any]) -> Brief:
    return _deserialize_typed(value, Brief)


def serialize_item_failure(failure: ItemFailure) -> bytes:
    return _serialize_typed(failure, ItemFailure)


def deserialize_item_failure(value: bytes | bytearray | str | Mapping[str, Any]) -> ItemFailure:
    return _deserialize_typed(value, ItemFailure)


def serialize_stage_result(
    result: StageResult[Any], output_serializer: Callable[[Any], Any] | None = None
) -> bytes:
    if not isinstance(result, StageResult):
        raise _contract_error("serialize_stage_result requires StageResult")
    return _serialize_envelope("StageResult", result.to_dict(output_serializer=output_serializer))


def deserialize_stage_result(
    value: bytes | bytearray | str | Mapping[str, Any],
    output_loader: Callable[[Any], Any] | None = None,
) -> StageResult[Any]:
    _, payload = _unwrap(value, "StageResult")
    return StageResult.from_dict(payload, output_loader=output_loader)


def serialize_domain(
    value: Any, output_serializer: Callable[[Any], Any] | None = None
) -> bytes:
    serializers: tuple[tuple[type[Any], Callable[[Any], bytes]], ...] = (
        (Article, serialize_article),
        (EventCandidate, serialize_event_candidate),
        (EventClassification, serialize_event_classification),
        (EventWriting, serialize_event_writing),
        (Event, serialize_event),
        (Brief, serialize_brief),
        (ItemFailure, serialize_item_failure),
    )
    for object_type, serializer in serializers:
        if isinstance(value, object_type):
            return serializer(value)
    if isinstance(value, StageResult):
        return serialize_stage_result(value, output_serializer=output_serializer)
    raise _contract_error("value is not a canonical domain object")


def deserialize_domain(
    value: bytes | bytearray | str | Mapping[str, Any],
    output_loader: Callable[[Any], Any] | None = None,
) -> Any:
    object_type, payload = _unwrap(value)
    object_class = _OBJECT_TYPES[object_type]
    if object_type == "StageResult":
        return StageResult.from_dict(payload, output_loader=output_loader)
    return object_class.from_dict(payload)


__all__ = [
    "Article",
    "Brief",
    "CONTRACT_VERSION",
    "CanonicalContractError",
    "Event",
    "EventCandidate",
    "EventCategory",
    "EventClassification",
    "EventWriting",
    "FailureCode",
    "GenerationStatus",
    "ItemFailure",
    "LANGUAGE_VALUES",
    "StageName",
    "StageResult",
    "StageStatus",
    "TARGET_LANGUAGE",
    "datetime_in_report_window",
    "deserialize_article",
    "deserialize_brief",
    "deserialize_domain",
    "deserialize_event",
    "deserialize_event_candidate",
    "deserialize_event_classification",
    "deserialize_event_writing",
    "deserialize_item_failure",
    "deserialize_stage_result",
    "normalize_canonical_url",
    "normalize_canonical_datetime",
    "normalize_language",
    "serialize_article",
    "serialize_brief",
    "serialize_domain",
    "serialize_event",
    "serialize_event_candidate",
    "serialize_event_classification",
    "serialize_event_writing",
    "serialize_item_failure",
    "serialize_stage_result",
    "stable_article_id",
    "stable_brief_id",
    "stable_event_candidate_id",
    "validate_event_selection_order",
    "validate_report_window",
]
