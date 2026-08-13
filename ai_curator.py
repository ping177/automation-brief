from __future__ import annotations

import hashlib
import json
import urllib.parse
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Protocol, Sequence


SCHEMA_VERSION = "ai_curator_shadow_v1"
TARGET_LANGUAGE = "zh-CN"
SELECTION_GOAL = "global_major_events"
PHASE_4_PROVIDER_SUMMARY_MAX_CHARS = 500
LANGUAGE_VALUES = frozenset({"zh-CN", "en", "und"})

IMPORTANCE_VALUES = frozenset({"must_know", "important", "background"})
NOVELTY_VALUES = frozenset(
    {"new_event", "material_update", "repeated_without_material_update"}
)
CONFIDENCE_VALUES = frozenset({"high", "medium", "low"})
CATEGORY_VALUES = frozenset(
    {
        "geopolitics",
        "macro_policy",
        "financial_markets",
        "energy_commodities",
        "china_policy",
        "company_industry",
        "technology_ai",
        "public_safety",
        "other",
    }
)
REJECT_REASON_VALUES = frozenset(
    {
        "duplicate",
        "low_significance",
        "local_or_narrow_scope",
        "promotional",
        "opinion_without_new_fact",
        "stale_or_repeated",
        "insufficient_information",
    }
)
TRADING_ADVICE_TERMS = ("买入", "卖出", "目标价", "加仓", "减仓", "止损", "止盈")


class CuratorContractError(ValueError):
    """A contract failure with bounded, non-content diagnostic metadata."""

    def __init__(
        self,
        message: str,
        *,
        diagnostic_code: str = "contract_error",
        diagnostic_path: str = "",
        diagnostic_article_id: str = "",
    ) -> None:
        super().__init__(message)
        self.diagnostic_code = diagnostic_code
        self.diagnostic_path = diagnostic_path
        self.diagnostic_article_id = diagnostic_article_id


def normalize_language(value: Any) -> str:
    normalized = str(value or "").strip().replace("_", "-").lower()
    canonical = {"zh-cn": "zh-CN", "en": "en", "und": "und"}.get(normalized, "und")
    return canonical if canonical in LANGUAGE_VALUES else "und"


@dataclass(frozen=True)
class CandidateArticle:
    article_id: str
    title: str
    summary: str
    source: str
    feed_name: str
    feed_role: str
    published_at: datetime | None
    link: str
    normalized_link: str
    report_date: date
    collected_at: datetime
    published: str = ""
    author: str = ""
    language: str = "und"
    legacy_match_text: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "language", normalize_language(self.language))

    def to_curator_dict(self) -> dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "summary": self.summary,
            "source": self.source,
            "feed_name": self.feed_name,
            "feed_role": self.feed_role,
            "published_at": _datetime_to_str(self.published_at),
            "link": self.link,
            "normalized_link": self.normalized_link,
            "report_date": self.report_date.isoformat(),
            "collected_at": _datetime_to_str(self.collected_at),
            "author": self.author,
            "language": self.language,
        }


@dataclass(frozen=True)
class CuratorRequest:
    schema_version: str
    report_date: date
    window_start: datetime
    window_end: datetime
    articles: tuple[CandidateArticle, ...]
    target_language: str = TARGET_LANGUAGE
    selection_goal: str = SELECTION_GOAL
    max_events: int = 5

    def __post_init__(self) -> None:
        if self.target_language != TARGET_LANGUAGE:
            raise CuratorContractError(
                f"CuratorRequest target_language must be {TARGET_LANGUAGE}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_date": self.report_date.isoformat(),
            "window_start": _datetime_to_str(self.window_start),
            "window_end": _datetime_to_str(self.window_end),
            "target_language": self.target_language,
            "selection_goal": self.selection_goal,
            "max_events": self.max_events,
            "articles": [article.to_curator_dict() for article in self.articles],
        }


@dataclass(frozen=True)
class CuratedEvent:
    event_id: str
    canonical_title: str
    summary: str
    category: str
    importance: str
    why_important: str
    evidence_article_ids: tuple[str, ...]
    novelty: str
    confidence: str
    uncertainties: tuple[str, ...]


@dataclass(frozen=True)
class RejectedArticle:
    article_id: str
    reject_reason: str = "low_significance"


@dataclass(frozen=True)
class CuratorResponse:
    schema_version: str
    report_date: date
    events: tuple[CuratedEvent, ...]
    rejected_article_ids: tuple[RejectedArticle, ...]
    warnings: tuple[str, ...]


class CuratorProvider(Protocol):
    def curate(self, request: CuratorRequest) -> CuratorResponse:
        ...


class FixtureCuratorProvider:
    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path

    def curate(self, request: CuratorRequest) -> CuratorResponse:
        payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        return validate_curator_response(payload, request)


FORBIDDEN_CANDIDATE_FIXTURE_FIELDS = frozenset(
    {
        "holdings",
        "legacy_score",
        "legacy_category",
        "matched_keywords",
        "cost",
        "position",
        "shares",
        "amount",
        "market_value",
        "profit",
        "loss",
        "api_key",
    }
)


def _datetime_to_str(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def load_candidate_fixture(fixture_path: Path) -> tuple[date, tuple[CandidateArticle, ...]]:
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CuratorContractError(f"Candidate fixture not found: {fixture_path}") from exc
    except json.JSONDecodeError as exc:
        raise CuratorContractError(f"Candidate fixture is invalid JSON: {fixture_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise CuratorContractError("Candidate fixture must be a JSON object")
    if payload.get("schema_version") != "1.0":
        raise CuratorContractError("Candidate fixture schema_version must be 1.0")
    report_date = _parse_fixture_date(payload.get("report_date"), "candidate fixture report_date")
    raw_articles = payload.get("articles")
    if not isinstance(raw_articles, list):
        raise CuratorContractError("Candidate fixture articles must be a list")

    articles: list[CandidateArticle] = []
    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    collected_at = datetime.now(timezone.utc)
    for index, raw_article in enumerate(raw_articles, start=1):
        article = _candidate_from_fixture_article(raw_article, report_date, collected_at, index)
        if article.article_id in seen_ids:
            raise CuratorContractError(f"Candidate fixture has duplicate article_id: {article.article_id}")
        key = article.normalized_link or article.article_id
        if key in seen_keys:
            raise CuratorContractError(f"Candidate fixture has duplicate candidate key: {key}")
        seen_ids.add(article.article_id)
        seen_keys.add(key)
        articles.append(article)

    return report_date, tuple(articles)


def _candidate_from_fixture_article(
    raw_article: Any,
    fixture_report_date: date,
    collected_at: datetime,
    index: int,
) -> CandidateArticle:
    if not isinstance(raw_article, dict):
        raise CuratorContractError(f"Candidate fixture article #{index} must be an object")
    forbidden = FORBIDDEN_CANDIDATE_FIXTURE_FIELDS.intersection(str(key).lower() for key in raw_article)
    if forbidden:
        raise CuratorContractError(
            f"Candidate fixture article #{index} includes forbidden fields: {', '.join(sorted(forbidden))}"
        )

    title = _fixture_required_text(raw_article, "title", index)
    source = _fixture_required_text(raw_article, "source", index)
    feed_name = _fixture_required_text(raw_article, "feed_name", index)
    feed_role = _fixture_required_text(raw_article, "feed_role", index)
    if "published_at" not in raw_article:
        raise CuratorContractError(
            f"Candidate fixture article #{index} missing required field: published_at"
        )
    published_at = _parse_fixture_datetime(
        raw_article["published_at"],
        f"candidate fixture article #{index} published_at",
        allow_none=True,
    )
    article_report_date = _parse_fixture_date(raw_article.get("report_date", fixture_report_date.isoformat()), f"candidate fixture article #{index} report_date")
    if article_report_date != fixture_report_date:
        raise CuratorContractError(f"Candidate fixture article #{index} report_date does not match fixture report_date")

    link = str(raw_article.get("link", "")).strip()
    if published_at is None and not link:
        raise CuratorContractError(
            f"Candidate fixture article #{index} requires link when published_at is null"
        )
    provided_normalized_link = str(raw_article.get("normalized_link", "")).strip()
    derived_normalized_link = normalize_article_link(link)
    if link and provided_normalized_link and provided_normalized_link != derived_normalized_link:
        raise CuratorContractError(f"Candidate fixture article #{index} normalized_link conflicts with link")
    normalized_link = provided_normalized_link or derived_normalized_link
    article_id = str(raw_article.get("article_id", "")).strip()
    expected_id = stable_article_id(normalized_link, source, title, published_at)
    if article_id and article_id != expected_id:
        raise CuratorContractError(f"Candidate fixture article #{index} article_id conflicts with stable article_id")
    if not article_id:
        article_id = expected_id

    return CandidateArticle(
        article_id=article_id,
        title=title,
        summary=str(raw_article.get("summary", "")).strip(),
        source=source,
        feed_name=feed_name,
        feed_role=feed_role,
        published_at=published_at,
        link=link,
        normalized_link=normalized_link,
        report_date=fixture_report_date,
        collected_at=collected_at,
        author=str(raw_article.get("author", "")).strip(),
        language=normalize_language(raw_article.get("language")),
    )


def _fixture_required_text(raw_article: dict[str, Any], field_name: str, index: int) -> str:
    value = str(raw_article.get(field_name, "")).strip()
    if not value:
        raise CuratorContractError(f"Candidate fixture article #{index} missing required field: {field_name}")
    return value


def _parse_fixture_date(value: Any, field_name: str) -> date:
    if not isinstance(value, str) or not value.strip():
        raise CuratorContractError(f"{field_name} is required")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise CuratorContractError(f"{field_name} must be YYYY-MM-DD") from exc


def _parse_fixture_datetime(
    value: Any,
    field_name: str,
    *,
    allow_none: bool = False,
) -> datetime | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CuratorContractError(f"{field_name} is required")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise CuratorContractError(f"{field_name} must be an ISO datetime") from exc
    if parsed.tzinfo is None:
        raise CuratorContractError(f"{field_name} must include timezone")
    return parsed


def normalize_article_link(link: str) -> str:
    stripped = (link or "").strip()
    if not stripped:
        return ""
    parsed = urllib.parse.urlsplit(stripped)
    query_items = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in {"fbclid", "gclid"} and not key.lower().startswith("utm_")
    ]
    query = urllib.parse.urlencode(query_items, doseq=True)
    return urllib.parse.urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or parsed.path,
            query,
            "",
        )
    )


def stable_article_id(
    normalized_link: str,
    source: str,
    title: str,
    published_at: datetime | None,
) -> str:
    if normalized_link:
        basis = f"link:{normalized_link}"
    else:
        published_value = _datetime_to_str(published_at) or ""
        normalized_title = " ".join((title or "").lower().split())
        basis = f"fallback:{source.strip().lower()}:{normalized_title}:{published_value}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    return f"art_{digest[:24]}"


def build_curator_request(
    articles: list[CandidateArticle] | tuple[CandidateArticle, ...],
    report_date: date,
    max_events: int = 5,
) -> CuratorRequest:
    article_tuple = tuple(articles)
    published_times = tuple(article.published_at for article in article_tuple if article.published_at)
    if published_times:
        window_start = min(published_times).astimezone(timezone.utc)
        window_end = max(published_times).astimezone(timezone.utc)
    else:
        window_start = datetime.combine(report_date, time.min, tzinfo=timezone.utc)
        window_end = datetime.combine(report_date, time.max, tzinfo=timezone.utc)
    return CuratorRequest(
        schema_version=SCHEMA_VERSION,
        report_date=report_date,
        window_start=window_start,
        window_end=window_end,
        articles=article_tuple,
        target_language=TARGET_LANGUAGE,
        max_events=max_events,
    )


def project_candidate_for_provider(
    article: CandidateArticle,
    *,
    summary_max_chars: int = PHASE_4_PROVIDER_SUMMARY_MAX_CHARS,
) -> CandidateArticle:
    """Create a provider-facing candidate copy without changing the source article."""

    if summary_max_chars < 0:
        raise ValueError("summary_max_chars must be non-negative")
    summary = article.summary
    if isinstance(summary, str) and len(summary) > summary_max_chars:
        summary = summary[:summary_max_chars]
    return replace(article, summary=summary)


def project_curator_request_for_provider(
    request: CuratorRequest,
    *,
    summary_max_chars: int = PHASE_4_PROVIDER_SUMMARY_MAX_CHARS,
) -> CuratorRequest:
    """Create the deterministic provider-facing request projection."""

    projected_articles = tuple(
        project_candidate_for_provider(article, summary_max_chars=summary_max_chars)
        for article in request.articles
    )
    return replace(request, articles=projected_articles)


def validate_curator_response(payload: dict[str, Any], request: CuratorRequest) -> CuratorResponse:
    if not isinstance(payload, dict):
        raise CuratorContractError(
            "Curator response must be an object",
            diagnostic_code="response_not_object",
            diagnostic_path="response",
        )
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise CuratorContractError(
            "Unsupported curator response schema_version",
            diagnostic_code="schema_version_mismatch",
            diagnostic_path="schema_version",
        )
    if payload.get("report_date") != request.report_date.isoformat():
        raise CuratorContractError(
            "Curator response report_date does not match request",
            diagnostic_code="report_date_mismatch",
            diagnostic_path="report_date",
        )

    request_article_ids = [article.article_id for article in request.articles]
    if len(request_article_ids) != len(set(request_article_ids)):
        raise CuratorContractError(
            "CuratorRequest contains duplicate article_id values",
            diagnostic_code="duplicate_request_article_id",
            diagnostic_path="request.articles.article_id",
        )
    valid_article_ids = set(request_article_ids)

    raw_events = payload.get("events", [])
    if not isinstance(raw_events, list):
        raise CuratorContractError(
            "Curator response events must be a list",
            diagnostic_code="events_not_list",
            diagnostic_path="events",
        )
    if len(raw_events) > request.max_events:
        raise CuratorContractError(
            "Curator response exceeds max_events",
            diagnostic_code="max_events_exceeded",
            diagnostic_path="events",
        )

    events: list[CuratedEvent] = []
    event_ids: set[str] = set()
    selected_article_ids: set[str] = set()
    for raw_event in raw_events:
        if not isinstance(raw_event, dict):
            raise CuratorContractError(
                "Curator event must be an object",
                diagnostic_code="event_not_object",
                diagnostic_path="events",
            )
        event = _parse_event(raw_event, valid_article_ids)
        if event.event_id in event_ids:
            raise CuratorContractError(
                "Curator response has duplicate event_id",
                diagnostic_code="duplicate_event_id",
                diagnostic_path="events.event_id",
            )
        event_ids.add(event.event_id)
        selected_article_ids.update(event.evidence_article_ids)
        events.append(event)

    rejected = _parse_rejected(payload.get("rejected_article_ids", []), valid_article_ids)
    rejected_ids = {item.article_id for item in rejected}
    overlap = selected_article_ids.intersection(rejected_ids)
    if overlap:
        overlap_article_id = sorted(overlap)[0]
        raise CuratorContractError(
            f"Article cannot be both selected and rejected: {overlap_article_id}",
            diagnostic_code="selected_rejected_overlap",
            diagnostic_path="selected_rejected_article_ids",
            diagnostic_article_id=overlap_article_id,
        )

    warnings = payload.get("warnings", [])
    if not isinstance(warnings, list):
        raise CuratorContractError(
            "Curator warnings must be a list",
            diagnostic_code="warnings_not_list",
            diagnostic_path="warnings",
        )
    return CuratorResponse(
        schema_version=SCHEMA_VERSION,
        report_date=request.report_date,
        events=tuple(events),
        rejected_article_ids=tuple(rejected),
        warnings=tuple(str(item) for item in warnings if str(item).strip()),
    )


def _parse_event(raw_event: dict[str, Any], valid_article_ids: set[str]) -> CuratedEvent:
    event_id = _required_text(raw_event, "event_id")
    canonical_title = _required_text(raw_event, "canonical_title")
    summary = _required_text(raw_event, "summary")
    why_important = _required_text(raw_event, "why_important")
    category = _enum_value(raw_event, "category", CATEGORY_VALUES)
    importance = _enum_value(raw_event, "importance", IMPORTANCE_VALUES)
    novelty = _enum_value(raw_event, "novelty", NOVELTY_VALUES)
    confidence = _enum_value(raw_event, "confidence", CONFIDENCE_VALUES)
    evidence = raw_event.get("evidence_article_ids", [])
    if not isinstance(evidence, list) or not evidence:
        raise CuratorContractError(
            "Curator event must include at least one evidence article",
            diagnostic_code="evidence_required",
            diagnostic_path="events.evidence_article_ids",
        )
    evidence_ids = tuple(str(item).strip() for item in evidence if str(item).strip())
    if len(evidence_ids) != len(evidence) or not set(evidence_ids).issubset(valid_article_ids):
        raise CuratorContractError(
            "Curator event references unknown evidence_article_ids",
            diagnostic_code="unknown_evidence_article_id",
            diagnostic_path="events.evidence_article_ids",
        )
    if len(evidence_ids) != len(set(evidence_ids)):
        raise CuratorContractError(
            f"Curator event {event_id} has duplicate evidence_article_ids",
            diagnostic_code="duplicate_evidence_article_id",
            diagnostic_path="events.evidence_article_ids",
        )
    uncertainties = raw_event.get("uncertainties", [])
    if not isinstance(uncertainties, list):
        raise CuratorContractError(
            "Curator event uncertainties must be a list",
            diagnostic_code="uncertainties_not_list",
            diagnostic_path="events.uncertainties",
        )
    return CuratedEvent(
        event_id=event_id,
        canonical_title=canonical_title,
        summary=summary,
        category=category,
        importance=importance,
        why_important=why_important,
        evidence_article_ids=evidence_ids,
        novelty=novelty,
        confidence=confidence,
        uncertainties=tuple(str(item) for item in uncertainties if str(item).strip()),
    )


def _parse_rejected(raw_rejected: Any, valid_article_ids: set[str]) -> tuple[RejectedArticle, ...]:
    if not isinstance(raw_rejected, list):
        raise CuratorContractError(
            "Curator rejected_article_ids must be a list",
            diagnostic_code="rejected_article_ids_not_list",
            diagnostic_path="rejected_article_ids",
        )
    rejected: list[RejectedArticle] = []
    seen: set[str] = set()
    for item in raw_rejected:
        if isinstance(item, str):
            article_id = item.strip()
            reject_reason = "low_significance"
        elif isinstance(item, dict):
            article_id = str(item.get("article_id", "")).strip()
            reject_reason = str(item.get("reject_reason", "low_significance")).strip()
        else:
            raise CuratorContractError(
                "Rejected article must be a string or object",
                diagnostic_code="rejected_article_invalid_type",
                diagnostic_path="rejected_article_ids",
            )
        if not article_id or article_id not in valid_article_ids:
            raise CuratorContractError(
                "Rejected article references unknown article_id",
                diagnostic_code="unknown_rejected_article_id",
                diagnostic_path="rejected_article_ids.article_id",
            )
        if article_id in seen:
            raise CuratorContractError(
                "Curator response has duplicate rejected article_id",
                diagnostic_code="duplicate_rejected_article_id",
                diagnostic_path="rejected_article_ids.article_id",
            )
        if reject_reason not in REJECT_REASON_VALUES:
            raise CuratorContractError(
                "Curator response has invalid reject_reason",
                diagnostic_code="invalid_reject_reason",
                diagnostic_path="rejected_article_ids.reject_reason",
            )
        seen.add(article_id)
        rejected.append(RejectedArticle(article_id=article_id, reject_reason=reject_reason))
    return tuple(rejected)


def _required_text(payload: dict[str, Any], field_name: str) -> str:
    value = str(payload.get(field_name, "")).strip()
    if not value:
        raise CuratorContractError(
            f"Curator response field is required: {field_name}",
            diagnostic_code="missing_required_field",
            diagnostic_path=f"events.{field_name}",
        )
    return value


def _enum_value(payload: dict[str, Any], field_name: str, allowed: frozenset[str]) -> str:
    value = _required_text(payload, field_name)
    if value not in allowed:
        raise CuratorContractError(
            f"Curator response has invalid {field_name}: {value}",
            diagnostic_code="invalid_enum_value",
            diagnostic_path=f"events.{field_name}",
        )
    return value


def candidate_trace_records(candidates: tuple[CandidateArticle, ...] | list[CandidateArticle], legacy_items: list[Any]) -> list[dict[str, Any]]:
    legacy_by_link = {
        normalize_article_link(str(getattr(item, "link", ""))): item
        for item in legacy_items
        if normalize_article_link(str(getattr(item, "link", "")))
    }
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        legacy_item = legacy_by_link.get(candidate.normalized_link)
        matched_keywords = getattr(legacy_item, "matched_keywords", {}) if legacy_item else {}
        records.append(
            {
                "article_id": candidate.article_id,
                "title": candidate.title,
                "source": candidate.source,
                "feed_name": candidate.feed_name,
                "feed_role": candidate.feed_role,
                "published_at": _datetime_to_str(candidate.published_at),
                "link": candidate.link,
                "normalized_link": candidate.normalized_link,
                "report_date": candidate.report_date.isoformat(),
                "legacy_keyword_matched": bool(matched_keywords),
                "legacy_matched_keywords": matched_keywords,
                "legacy_selected": legacy_item is not None,
                "legacy_score": None,
                "legacy_category": "",
                "legacy_reject_reason": "" if legacy_item else "not_selected_by_legacy_keyword_gate_or_limits",
            }
        )
    return records


def candidate_collection_window(
    candidates: Sequence[CandidateArticle],
) -> tuple[datetime | None, datetime | None]:
    collected_at = tuple(candidate.collected_at for candidate in candidates)
    if not collected_at:
        return None, None
    return min(collected_at), max(collected_at)


def render_shadow_preview(
    response: CuratorResponse,
    request: CuratorRequest,
    trace_records: list[dict[str, Any]],
) -> str:
    article_by_id = {article.article_id: article for article in request.articles}
    lines = [
        "# AI Curator Shadow Preview",
        "",
        f"Report date: {request.report_date.isoformat()}",
        f"Schema: {request.schema_version}",
        "",
        "## Curated Events",
        "",
    ]
    if not response.events:
        lines.extend(["No curated events in fixture response.", ""])
    for event in response.events:
        lines.extend(
            [
                f"### {_sanitize_preview_text(event.canonical_title)}",
                f"- Importance: {event.importance}",
                f"- Category: {event.category}",
                f"- Why important: {_sanitize_preview_text(event.why_important)}",
                f"- Novelty: {event.novelty}",
                f"- Confidence: {event.confidence}",
                "- Evidence articles:",
            ]
        )
        for article_id in event.evidence_article_ids:
            article = article_by_id[article_id]
            lines.append(f"  - {_sanitize_preview_text(article.title)} ({article.source})")
        if event.uncertainties:
            lines.append(f"- Uncertainties: {'; '.join(_sanitize_preview_text(item) for item in event.uncertainties)}")
        lines.append("")

    lines.extend(["## Rejected Candidates Summary", ""])
    if response.rejected_article_ids:
        reason_counts: dict[str, int] = {}
        for rejected in response.rejected_article_ids:
            reason_counts[rejected.reject_reason] = reason_counts.get(rejected.reject_reason, 0) + 1
        for reason, count in sorted(reason_counts.items()):
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- None.")
    lines.append("")

    lines.extend(["## Validation Warnings", ""])
    if response.warnings:
        for warning in response.warnings:
            lines.append(f"- {_sanitize_preview_text(warning)}")
    else:
        lines.append("- None.")
    lines.append("")

    legacy_selected_count = sum(1 for record in trace_records if record.get("legacy_selected"))
    legacy_keyword_count = sum(1 for record in trace_records if record.get("legacy_keyword_matched"))
    lines.extend(
        [
            "## Legacy Comparison Summary",
            "",
            f"- Candidate articles: {len(request.articles)}",
            f"- Legacy keyword matched: {legacy_keyword_count}",
            f"- Legacy selected: {legacy_selected_count}",
            f"- Curated events: {len(response.events)}",
            "",
        ]
    )
    return "\n".join(lines)


def _sanitize_preview_text(value: str) -> str:
    cleaned = str(value)
    for term in TRADING_ADVICE_TERMS:
        cleaned = cleaned.replace(term, "交易导向表述")
    return cleaned.replace("|", "\\|").strip()
