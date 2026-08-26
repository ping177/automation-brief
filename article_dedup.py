"""Exact, stable v1.2 deduplication for canonical Article objects."""

from __future__ import annotations

from typing import Iterable

from canonical_domain import (
    Article,
    FailureCode,
    ItemFailure,
    StageName,
    StageResult,
    StageStatus,
)


def _identity_key(article: Article) -> tuple[str, str]:
    """Use only the canonical identity fields; never infer semantic sameness."""

    if article.canonical_url is not None:
        return ("canonical_url", article.canonical_url)
    return ("article_id", article.article_id)


def deduplicate_articles(articles: Iterable[Article]) -> StageResult[Article]:
    """Keep the first valid Article for each exact canonical identity."""

    if isinstance(articles, (str, bytes)):
        return StageResult(
            stage=StageName.ARTICLE_DEDUP,
            status=StageStatus.FAILED,
            failures=(ItemFailure(code=FailureCode.INVALID_INPUT),),
        )
    try:
        iterable = iter(articles)
    except TypeError:
        return StageResult(
            stage=StageName.ARTICLE_DEDUP,
            status=StageStatus.FAILED,
            failures=(ItemFailure(code=FailureCode.INVALID_INPUT),),
        )

    unique_articles: list[Article] = []
    failures: list[ItemFailure] = []
    seen: set[tuple[str, str]] = set()
    for article in iterable:
        if not isinstance(article, Article):
            failures.append(ItemFailure(code=FailureCode.ITEM_VALIDATION_FAILED))
            continue
        key = _identity_key(article)
        if key in seen:
            continue
        seen.add(key)
        unique_articles.append(article)

    if failures and unique_articles:
        status = StageStatus.PARTIAL
    elif failures:
        status = StageStatus.FAILED
    else:
        status = StageStatus.SUCCEEDED
    return StageResult(
        stage=StageName.ARTICLE_DEDUP,
        status=status,
        outputs=tuple(unique_articles),
        failures=tuple(failures),
    )


__all__ = ["deduplicate_articles"]
