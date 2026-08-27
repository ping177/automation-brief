"""Deterministic v1.2 conversion from raw source batches to canonical Articles."""

from __future__ import annotations

import html
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterable

from canonical_domain import (
    Article,
    CanonicalContractError,
    FailureCode,
    ItemFailure,
    StageName,
    StageResult,
    StageStatus,
    datetime_in_report_window,
    normalize_canonical_datetime,
    validate_report_window,
)
from collector import RawFeedEntry, SourceBatch


_HTML_TAG = re.compile(r"<[^>]*>")
_WHITESPACE = re.compile(r"\s+")


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("text field must be a string")
    unescaped = html.unescape(value)
    without_tags = _HTML_TAG.sub(" ", unescaped)
    normalized = _WHITESPACE.sub(" ", without_tags).strip()
    return normalized or None


def _selected_timestamp(entry: RawFeedEntry) -> str | None:
    for value in (entry.published, entry.updated):
        if value is not None and not isinstance(value, str):
            raise ValueError("source timestamp must be a string")
        if value is not None and value.strip():
            return value.strip()
    return None


def parse_source_timestamp(value: str | None) -> datetime | None:
    """Parse a source timestamp and enforce the canonical aware-UTC rule."""

    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("source timestamp must be a string")
    if not value.strip():
        return None
    text = value.strip()
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        normalized_text = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            parsed = datetime.fromisoformat(normalized_text)
        except ValueError as exc:
            raise ValueError("source timestamp is not parseable") from exc
    return normalize_canonical_datetime(parsed, "published_at")


def _normalize_entry(batch: SourceBatch, entry: RawFeedEntry) -> Article:
    title = _clean_text(entry.title)
    if title is None:
        raise ValueError("title is required")

    if entry.link is not None and not isinstance(entry.link, str):
        raise ValueError("link must be a string")
    url = entry.link.strip() if entry.link is not None and entry.link.strip() else None
    published_at = parse_source_timestamp(_selected_timestamp(entry))
    summary = _clean_text(entry.summary) or _clean_text(entry.description)

    return Article.from_source(
        source=entry.source.name,
        url=url,
        published_at=published_at,
        collected_at=batch.collected_at,
        language=entry.source.language,
        title=title,
        summary=summary,
    )


def normalize_source_batches(batches: Iterable[SourceBatch]) -> StageResult[Article]:
    """Normalize each raw item independently and retain valid Articles."""

    if isinstance(batches, (str, bytes)):
        return StageResult(
            stage=StageName.NORMALIZER,
            status=StageStatus.FAILED,
            failures=(ItemFailure(code=FailureCode.INVALID_INPUT),),
        )

    articles: list[Article] = []
    failures: list[ItemFailure] = []
    try:
        iterable = iter(batches)
    except TypeError:
        return StageResult(
            stage=StageName.NORMALIZER,
            status=StageStatus.FAILED,
            failures=(ItemFailure(code=FailureCode.INVALID_INPUT),),
        )

    for batch in iterable:
        if not isinstance(batch, SourceBatch):
            failures.append(ItemFailure(code=FailureCode.INVALID_INPUT))
            continue
        for entry in batch.entries:
            if not isinstance(entry, RawFeedEntry):
                failures.append(ItemFailure(code=FailureCode.ITEM_VALIDATION_FAILED))
                continue
            try:
                articles.append(_normalize_entry(batch, entry))
            except (CanonicalContractError, TypeError, ValueError, OverflowError):
                failures.append(
                    ItemFailure(
                        item_id=entry.item_id,
                        code=FailureCode.ITEM_VALIDATION_FAILED,
                    )
                )

    if failures and articles:
        status = StageStatus.PARTIAL
    elif failures:
        status = StageStatus.FAILED
    else:
        status = StageStatus.SUCCEEDED
    return StageResult(
        stage=StageName.NORMALIZER,
        status=status,
        outputs=tuple(articles),
        failures=tuple(failures),
    )


def admit_articles_to_report_window(
    articles: Iterable[Article],
    window_start: datetime,
    window_end: datetime,
) -> tuple[Article, ...]:
    """Retain Articles admitted by the frozen inclusive report-window rule."""

    normalized_start, normalized_end = validate_report_window(window_start, window_end)
    if isinstance(articles, (str, bytes)):
        raise ValueError("articles must be an iterable")
    try:
        values = tuple(articles)
    except TypeError:
        raise ValueError("articles must be an iterable") from None
    if any(not isinstance(article, Article) for article in values):
        raise ValueError("articles must contain Article objects")
    return tuple(
        article
        for article in values
        if article.published_at is None
        or datetime_in_report_window(article.published_at, normalized_start, normalized_end)
    )


__all__ = [
    "admit_articles_to_report_window",
    "normalize_source_batches",
    "parse_source_timestamp",
]
