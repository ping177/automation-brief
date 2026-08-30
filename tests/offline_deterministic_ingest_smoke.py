from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from canonical_domain import Article, FailureCode, StageName, StageStatus  # noqa: E402
from collector import (  # noqa: E402
    RawFeedEntry,
    SourceBatch,
    SourceConfig,
    collect_sources,
    flatten_source_batches,
    load_sources,
    normalize_sources,
    source_identifier,
)
from normalizer import (  # noqa: E402
    admit_articles_to_report_window,
    normalize_source_batches,
    qualify_source_snapshots,
)
from article_dedup import deduplicate_articles  # noqa: E402


COLLECTED_AT = datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc)


@dataclass
class FakeFeed:
    entries: list[dict[str, str]]


def source(name: str, *, timezone_name: str | None = None) -> SourceConfig:
    return SourceConfig(
        name=name,
        url=f"https://{name.lower()}.example/feed.xml",
        language="en",
        timezone=timezone_name,
    )


def test_source_config_drops_legacy_metadata() -> None:
    sources = normalize_sources(
        [
            {
                "name": "Fixture Feed",
                "url": "https://example.com/feed.xml",
                "language": "zh-cn",
                "category": "legacy-category",
                "mode": "keyword",
                "role": "market",
            }
        ]
    )
    assert sources == (SourceConfig("Fixture Feed", "https://example.com/feed.xml", "zh-CN"),)
    assert not hasattr(sources[0], "category")
    assert not hasattr(sources[0], "mode")
    assert not hasattr(sources[0], "role")


def test_source_timezone_is_optional_and_validated() -> None:
    configured = SourceConfig(
        "UTC source",
        "https://example.com/feed.xml",
        "en",
        timezone=" UTC ",
    )
    assert configured.timezone == "UTC"
    assert source_identifier(configured) == source_identifier(
        SourceConfig("UTC source", "https://example.com/feed.xml", "en")
    )

    normalized = normalize_sources(
        [
            {
                "name": "UTC source",
                "url": "https://example.com/feed.xml",
                "language": "en",
                "timezone": "UTC",
            }
        ]
    )
    assert normalized == (configured,)

    for invalid in ("", "Not/AZone", 42, True):
        try:
            SourceConfig(
                "Invalid timezone",
                "https://example.com/feed.xml",
                "en",
                timezone=invalid,  # type: ignore[arg-type]
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid source timezone was accepted: {invalid!r}")


def test_load_sources_reuses_active_feed_config_projection() -> None:
    sources = load_sources(PROJECT_ROOT / "feeds.json")

    assert sources
    assert all(isinstance(config, SourceConfig) for config in sources)
    assert all(config.language in {"zh-CN", "en", "und"} for config in sources)
    assert all(not hasattr(config, "mode") for config in sources)
    assert all(not hasattr(config, "role") for config in sources)


def test_load_sources_preserves_only_declared_investing_timezone() -> None:
    sources = load_sources(PROJECT_ROOT / "feeds.json")
    investing = next(source for source in sources if source.name == "Investing.com 中文财经")

    assert investing.timezone == "UTC"
    assert [source.timezone for source in sources].count(None) == len(sources) - 1


def test_collector_keeps_successful_empty_batch_and_isolates_failure() -> None:
    first = source("First")
    second = source("Second")

    def fetcher(config: SourceConfig) -> FakeFeed:
        if config == second:
            raise TimeoutError("fixture timeout")
        return FakeFeed(entries=[])

    result = collect_sources((first, second), fetcher=fetcher, clock=lambda: COLLECTED_AT)

    assert result.stage == StageName.COLLECTOR
    assert result.status == StageStatus.PARTIAL
    assert len(result.outputs) == 1
    assert isinstance(result.outputs[0], SourceBatch)
    assert result.outputs[0].source == first
    assert result.outputs[0].entries == ()
    assert result.outputs[0].collected_at == COLLECTED_AT
    assert result.failures[0].code == FailureCode.TIMEOUT
    assert flatten_source_batches(result.outputs) == ()


def test_all_successful_empty_sources_are_successful() -> None:
    result = collect_sources(
        (source("First"), source("Second")),
        fetcher=lambda _: FakeFeed(entries=[]),
        clock=lambda: COLLECTED_AT,
    )

    assert result.status == StageStatus.SUCCEEDED
    assert result.failures == ()
    assert len(result.outputs) == 2
    assert flatten_source_batches(result.outputs) == ()


def test_all_source_failures_are_failed() -> None:
    def fetcher(_: SourceConfig) -> FakeFeed:
        raise RuntimeError("fixture failure")

    result = collect_sources(
        (source("First"), source("Second")),
        fetcher=fetcher,
        clock=lambda: COLLECTED_AT,
    )

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert len(result.failures) == 2
    assert {failure.code for failure in result.failures} == {FailureCode.SOURCE_FETCH_FAILED}


def test_gen1_fetch_retry_preserves_root_cause_without_changing_message() -> None:
    import main

    root_cause = TimeoutError("fixture timeout")
    with (
        patch.object(main, "FEED_FETCH_ATTEMPTS", 1),
        patch.object(main.urllib.request, "urlopen", side_effect=root_cause),
    ):
        try:
            main.parse_feed_with_retry(
                {"name": "Cause fixture", "url": "https://example.com/feed.xml"}
            )
        except RuntimeError as error:
            assert str(error) == "fixture timeout"
            assert error.__cause__ is root_cause
        else:
            raise AssertionError("feed retry unexpectedly succeeded")


def test_collector_types_preserved_timeout_and_transport_causes() -> None:
    failures = (
        (TimeoutError("fixture timeout"), FailureCode.TIMEOUT),
        (OSError("fixture transport"), FailureCode.TRANSPORT_FAILED),
    )
    for index, (root_cause, expected_code) in enumerate(failures, start=1):
        def fetcher(_: SourceConfig, *, cause: BaseException = root_cause) -> FakeFeed:
            raise RuntimeError(str(cause)) from cause

        result = collect_sources(
            (source(f"Cause {index}"),),
            fetcher=fetcher,
            clock=lambda: COLLECTED_AT,
        )

        assert result.status is StageStatus.FAILED
        assert result.failures[0].code is expected_code


def test_malformed_source_feed_isolated_from_successful_source() -> None:
    first = source("Valid source")
    second = source("Malformed source")

    def fetcher(config: SourceConfig) -> FakeFeed | dict[str, str]:
        if config == second:
            return {"entries": "not-an-entry-list"}
        return FakeFeed(entries=[])

    result = collect_sources((first, second), fetcher=fetcher, clock=lambda: COLLECTED_AT)

    assert result.status == StageStatus.PARTIAL
    assert len(result.outputs) == 1
    assert result.outputs[0].source == first
    assert result.failures[0].code == FailureCode.SOURCE_FETCH_FAILED


def test_successful_entries_are_extracted_without_raw_payload() -> None:
    configured = source("Fixture")
    result = collect_sources(
        (configured,),
        fetcher=lambda _: FakeFeed(
            entries=[
                {
                    "id": "fixture-1",
                    "title": "  A title  ",
                    "link": "https://example.com/story?utm_source=fixture",
                    "summary": "A summary.",
                    "description": "A description.",
                    "published": "Wed, 26 Aug 2026 08:00:00 +0000",
                }
            ]
        ),
        clock=lambda: COLLECTED_AT,
    )

    entry = flatten_source_batches(result.outputs)[0]
    assert entry.source == configured
    assert entry.ordinal == 1
    assert entry.entry_id == "fixture-1"
    assert entry.title == "  A title  "
    assert entry.link == "https://example.com/story?utm_source=fixture"
    assert entry.published == "Wed, 26 Aug 2026 08:00:00 +0000"
    assert not hasattr(entry, "raw_payload")


def source_batch(source_config: SourceConfig, entries: list[dict[str, str | None]]) -> SourceBatch:
    raw_entries = tuple(
        entry_for(source_config, ordinal, values)
        for ordinal, values in enumerate(entries, start=1)
    )
    return SourceBatch(source=source_config, collected_at=COLLECTED_AT, entries=raw_entries)


def entry_for(
    source_config: SourceConfig,
    ordinal: int,
    values: dict[str, str | None],
) -> RawFeedEntry:
    return RawFeedEntry(
        source=source_config,
        ordinal=ordinal,
        entry_id=values.get("id"),
        title=values.get("title"),
        link=values.get("link"),
        summary=values.get("summary"),
        description=values.get("description"),
        published=values.get("published"),
        updated=values.get("updated"),
    )


def test_normalizer_emits_only_canonical_articles() -> None:
    configured = source("Normalizer")
    result = normalize_source_batches(
        (
            source_batch(
                configured,
                [
                    {
                        "title": "  A <b>title</b>  ",
                        "link": "https://Example.com/story/?utm_source=fixture#fragment",
                        "summary": "<p>A&nbsp;summary.</p>",
                        "description": "ignored fallback",
                        "published": "2026-08-26T16:00:00+08:00",
                    }
                ],
            ),
        )
    )

    assert result.stage == StageName.NORMALIZER
    assert result.status == StageStatus.SUCCEEDED
    assert result.failures == ()
    assert len(result.outputs) == 1
    article = result.outputs[0]
    assert isinstance(article, Article)
    assert article.source == configured.name
    assert article.url == "https://Example.com/story/?utm_source=fixture#fragment"
    assert article.canonical_url == "https://example.com/story"
    assert article.published_at == datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc)
    assert article.collected_at == COLLECTED_AT
    assert article.title == "A title"
    assert article.summary == "A summary."
    assert article.language == "en"
    assert set(article.__dataclass_fields__) == {
        "article_id",
        "source",
        "url",
        "canonical_url",
        "published_at",
        "collected_at",
        "language",
        "title",
        "summary",
    }


def test_normalizer_localizes_naive_timestamp_with_declared_source_timezone() -> None:
    configured = source("UTC timestamp", timezone_name="UTC")
    result = normalize_source_batches(
        (
            source_batch(
                configured,
                [
                    {
                        "title": "UTC publication",
                        "link": "https://example.com/utc-publication",
                        "published": "2026-08-29 23:35:10",
                    }
                ],
            ),
        )
    )

    assert result.status == StageStatus.SUCCEEDED
    assert result.failures == ()
    assert result.outputs[0].published_at == datetime(
        2026, 8, 29, 23, 35, 10, tzinfo=timezone.utc
    )


def test_normalizer_keeps_naive_timestamp_fail_closed_without_source_timezone() -> None:
    result = normalize_source_batches(
        (
            source_batch(
                source("Undeclared timestamp"),
                [
                    {
                        "title": "Undeclared publication",
                        "link": "https://example.com/undeclared-publication",
                        "published": "2026-08-29 23:35:10",
                    }
                ],
            ),
        )
    )

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures[0].code == FailureCode.ITEM_VALIDATION_FAILED


def test_normalizer_does_not_override_already_aware_timestamp() -> None:
    configured = source("Aware timestamp", timezone_name="UTC")
    result = normalize_source_batches(
        (
            source_batch(
                configured,
                [
                    {
                        "title": "Offset publication",
                        "link": "https://example.com/offset-publication",
                        "published": "2026-08-29T23:35:10+08:00",
                    }
                ],
            ),
        )
    )

    assert result.status == StageStatus.SUCCEEDED
    assert result.outputs[0].published_at == datetime(
        2026, 8, 29, 15, 35, 10, tzinfo=timezone.utc
    )


def test_investing_representative_timestamp_normalizes_to_utc() -> None:
    investing = next(
        config
        for config in load_sources(PROJECT_ROOT / "feeds.json")
        if config.name == "Investing.com 中文财经"
    )
    result = normalize_source_batches(
        (
            source_batch(
                investing,
                [
                    {
                        "title": "Investing representative",
                        "link": "https://cn.investing.com/news/stock-market-news/article-3543166",
                        "published": "2026-08-29 23:35:10",
                    }
                ],
            ),
        )
    )

    assert result.status == StageStatus.SUCCEEDED
    assert len(result.outputs) == 1
    assert result.outputs[0].published_at == datetime(
        2026, 8, 29, 23, 35, 10, tzinfo=timezone.utc
    )


def test_report_window_uses_localized_source_timestamp_before_admission() -> None:
    configured = source("Window UTC", timezone_name="UTC")
    normalized = normalize_source_batches(
        (
            source_batch(
                configured,
                [
                    {
                        "title": "At UTC start",
                        "link": "https://example.com/window-start",
                        "published": "2026-08-29 00:00:00",
                    },
                    {
                        "title": "At UTC end",
                        "link": "https://example.com/window-end",
                        "published": "2026-08-30 00:00:00",
                    },
                    {
                        "title": "Outside UTC window",
                        "link": "https://example.com/window-outside",
                        "published": "2026-08-28 23:59:59",
                    },
                ],
            ),
        )
    )

    admitted = admit_articles_to_report_window(
        normalized.outputs,
        datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc),
    )

    assert [article.title for article in admitted] == ["At UTC start", "At UTC end"]


def test_source_snapshot_with_parseable_timestamps_is_qualified() -> None:
    batch = source_batch(
        source("Timestamped"),
        [
            {
                "title": "Current story",
                "link": "https://example.com/current",
                "published": "2026-08-26T08:00:00+00:00",
            }
        ],
    )
    diagnostics: list[dict[str, object]] = []

    assert qualify_source_snapshots(
        (batch,), diagnostic_sink=lambda record: diagnostics.append(dict(record))
    ) == (batch,)
    assert diagnostics == []


def test_all_null_timestamp_snapshot_is_excluded_with_bounded_diagnostic() -> None:
    configured = source("Unbounded")
    batch = source_batch(
        configured,
        [
            {
                "title": f"Historical story {index}",
                "link": f"https://example.com/history/{index}",
            }
            for index in range(300)
        ],
    )
    diagnostics: list[dict[str, object]] = []

    assert qualify_source_snapshots(
        (batch,), diagnostic_sink=lambda record: diagnostics.append(dict(record))
    ) == ()
    assert diagnostics == [
        {
            "source_ref": source_identifier(configured),
            "status": "excluded",
            "reason": "source_snapshot_unbounded_recency",
            "excluded_count": 300,
        }
    ]


def test_unbounded_snapshot_does_not_block_timestamped_sibling_source() -> None:
    unbounded = source_batch(
        source("Unbounded sibling"),
        [{"title": "Historical", "link": "https://example.com/historical"}],
    )
    current = source_batch(
        source("Current sibling"),
        [
            {
                "title": "Current",
                "link": "https://example.com/current",
                "published": "2026-08-26T08:00:00+00:00",
            }
        ],
    )

    qualified = qualify_source_snapshots((unbounded, current))
    normalized = normalize_source_batches(qualified)

    assert qualified == (current,)
    assert [article.title for article in normalized.outputs] == ["Current"]


def test_normalizer_allows_missing_published_when_linked() -> None:
    result = normalize_source_batches(
        (
            source_batch(
                source("Linked"),
                [{"title": "Linked story", "link": "https://example.com/linked"}],
            ),
        )
    )

    assert result.status == StageStatus.SUCCEEDED
    assert result.outputs[0].published_at is None


def test_normalizer_requires_timestamp_for_linkless_entry() -> None:
    result = normalize_source_batches(
        (
            source_batch(
                source("Linkless"),
                [{"title": "Linkless story", "link": None}],
            ),
        )
    )

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures[0].code == FailureCode.ITEM_VALIDATION_FAILED


def test_normalizer_rejects_naive_and_malformed_timestamps_without_guessing() -> None:
    configured = source("Timestamp")
    result = normalize_source_batches(
        (
            source_batch(
                configured,
                [
                    {
                        "title": "Naive",
                        "link": "https://example.com/naive",
                        "published": "Wed, 26 Aug 2026 08:00:00",
                        "updated": "2026-08-26T08:00:00+00:00",
                    },
                    {
                        "title": "Malformed",
                        "link": "https://example.com/malformed",
                        "published": "not-a-timestamp",
                        "updated": "2026-08-26T08:00:00+00:00",
                    },
                    {
                        "title": "Valid",
                        "link": "https://example.com/valid",
                        "published": "Wed, 26 Aug 2026 08:00:00 +0000",
                    },
                ],
            ),
        )
    )

    assert result.status == StageStatus.PARTIAL
    assert len(result.outputs) == 1
    assert result.outputs[0].title == "Valid"
    assert len(result.failures) == 2
    assert all(failure.code == FailureCode.ITEM_VALIDATION_FAILED for failure in result.failures)


def test_normalizer_uses_description_only_as_summary_fallback() -> None:
    result = normalize_source_batches(
        (
            source_batch(
                source("Fallback"),
                [
                    {
                        "title": "Fallback story",
                        "link": "https://example.com/fallback",
                        "summary": "   ",
                        "description": "<div>Description&nbsp;text</div>",
                    },
                    {
                        "title": "No summary",
                        "link": "https://example.com/no-summary",
                        "summary": " ",
                        "description": " ",
                    },
                ],
            ),
        )
    )

    assert result.status == StageStatus.SUCCEEDED
    assert [article.summary for article in result.outputs] == ["Description text", None]


def test_report_window_admission_is_inclusive_and_retains_unknown_timestamps() -> None:
    configured = source("Window")
    normalized = normalize_source_batches(
        (
            source_batch(
                configured,
                [
                    {
                        "title": "At start",
                        "link": "https://example.com/at-start",
                        "published": "2026-08-26T00:00:00+00:00",
                    },
                    {
                        "title": "Inside",
                        "link": "https://example.com/inside",
                        "published": "2026-08-26T12:00:00+00:00",
                    },
                    {
                        "title": "At end",
                        "link": "https://example.com/at-end",
                        "published": "2026-08-27T00:00:00+00:00",
                    },
                    {
                        "title": "Unknown",
                        "link": "https://example.com/unknown",
                    },
                    {
                        "title": "Before",
                        "link": "https://example.com/before",
                        "published": "2026-08-25T23:59:59+00:00",
                    },
                    {
                        "title": "After",
                        "link": "https://example.com/after",
                        "published": "2026-08-27T00:00:01+00:00",
                    },
                ],
            ),
        )
    )

    admitted = admit_articles_to_report_window(
        normalized.outputs,
        datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc),
    )

    assert [article.title for article in admitted] == [
        "At start",
        "Inside",
        "At end",
        "Unknown",
    ]


def test_exact_article_dedup_keeps_first_valid_in_ingest_order() -> None:
    result = normalize_source_batches(
        (
            source_batch(
                source("Dedup"),
                [
                    {
                        "title": "First title",
                        "link": "https://example.com/story?utm_source=first",
                        "published": "2026-08-26T08:00:00+00:00",
                    },
                    {
                        "title": "Later title",
                        "link": "https://example.com/story?utm_medium=later",
                        "published": "2026-08-26T09:00:00+00:00",
                    },
                    {
                        "title": "Same event, different URL",
                        "link": "https://other.example/story",
                        "published": "2026-08-26T08:00:00+00:00",
                    },
                    {
                        "title": "First title",
                        "link": "https://third.example/story",
                        "published": "2026-08-26T08:00:00+00:00",
                    },
                ],
            ),
        )
    )
    assert result.status == StageStatus.SUCCEEDED

    deduped = deduplicate_articles(result.outputs)

    assert deduped.stage == StageName.ARTICLE_DEDUP
    assert deduped.status == StageStatus.SUCCEEDED
    assert deduped.failures == ()
    assert [article.title for article in deduped.outputs] == [
        "First title",
        "Same event, different URL",
        "First title",
    ]
    assert deduped.outputs[0].canonical_url == "https://example.com/story"
    assert deduped.outputs[0].title == "First title"


def test_exact_article_dedup_keeps_different_source_reports_separate() -> None:
    first_source = source("First report")
    second_source = source("Second report")
    normalized = normalize_source_batches(
        (
            source_batch(
                first_source,
                [
                    {
                        "title": "Shared title",
                        "link": "https://first.example/event",
                        "published": "2026-08-26T08:00:00+00:00",
                    }
                ],
            ),
            source_batch(
                second_source,
                [
                    {
                        "title": "Shared title",
                        "link": "https://second.example/event",
                        "published": "2026-08-26T08:00:00+00:00",
                    }
                ],
            ),
        )
    )

    result = deduplicate_articles(normalized.outputs)

    assert result.status == StageStatus.SUCCEEDED
    assert len(result.outputs) == 2
    assert [article.source for article in result.outputs] == [
        first_source.name,
        second_source.name,
    ]


def test_exact_article_dedup_preserves_linkless_identity_and_empty_success() -> None:
    linked = normalize_source_batches(
        (
            source_batch(
                source("Empty"),
                [{"title": "A linked article", "link": "https://example.com/linked"}],
            ),
        )
    )
    assert deduplicate_articles(()).status == StageStatus.SUCCEEDED
    assert deduplicate_articles(linked.outputs).outputs == linked.outputs

    linkless = normalize_source_batches(
        (
            source_batch(
                source("Linkless dedup"),
                [
                    {
                        "title": "No link",
                        "link": None,
                        "published": "2026-08-26T08:00:00+00:00",
                    },
                    {
                        "title": "No link",
                        "link": None,
                        "published": "2026-08-26T08:00:00+00:00",
                    },
                ],
            ),
        )
    )
    linkless_deduped = deduplicate_articles(linkless.outputs)
    assert linkless_deduped.status == StageStatus.SUCCEEDED
    assert len(linkless_deduped.outputs) == 1


def test_exact_article_dedup_reports_invalid_items_without_semantic_fallback() -> None:
    valid = normalize_source_batches(
        (
            source_batch(
                source("Invalid"),
                [{"title": "Valid", "link": "https://example.com/valid"}],
            ),
        )
    ).outputs[0]

    result = deduplicate_articles((object(), valid))

    assert result.status == StageStatus.PARTIAL
    assert result.outputs == (valid,)
    assert result.failures[0].code == FailureCode.ITEM_VALIDATION_FAILED


def test_offline_ingest_pipeline_is_deterministic_and_keeps_different_urls() -> None:
    configured = source("Integrated")

    def fetcher(_: SourceConfig) -> FakeFeed:
        return FakeFeed(
            entries=[
                {
                    "title": "First copy",
                    "link": "https://example.com/event?utm_source=one",
                    "published": "2026-08-26T08:00:00+00:00",
                },
                {
                    "title": "Second copy",
                    "link": "https://example.com/event?utm_medium=two",
                    "published": "2026-08-26T08:01:00+00:00",
                },
                {
                    "title": "Same event, another report",
                    "link": "https://another.example/event",
                    "published": "2026-08-26T08:02:00+00:00",
                },
            ]
        )

    collected = collect_sources((configured,), fetcher=fetcher, clock=lambda: COLLECTED_AT)
    normalized = normalize_source_batches(collected.outputs)
    first_run = deduplicate_articles(normalized.outputs)

    repeated_collected = collect_sources((configured,), fetcher=fetcher, clock=lambda: COLLECTED_AT)
    repeated_normalized = normalize_source_batches(repeated_collected.outputs)
    repeated_run = deduplicate_articles(repeated_normalized.outputs)

    assert collected.status == StageStatus.SUCCEEDED
    assert normalized.status == StageStatus.SUCCEEDED
    assert first_run.status == StageStatus.SUCCEEDED
    assert len(first_run.outputs) == 2
    assert [article.title for article in first_run.outputs] == [
        "First copy",
        "Same event, another report",
    ]
    assert [article.article_id for article in first_run.outputs] == [
        article.article_id for article in repeated_run.outputs
    ]
    assert all(not hasattr(article, "category") for article in first_run.outputs)
    assert all(not hasattr(article, "importance") for article in first_run.outputs)


def main() -> None:
    test_source_config_drops_legacy_metadata()
    test_source_timezone_is_optional_and_validated()
    test_load_sources_reuses_active_feed_config_projection()
    test_load_sources_preserves_only_declared_investing_timezone()
    test_collector_keeps_successful_empty_batch_and_isolates_failure()
    test_all_successful_empty_sources_are_successful()
    test_all_source_failures_are_failed()
    test_gen1_fetch_retry_preserves_root_cause_without_changing_message()
    test_collector_types_preserved_timeout_and_transport_causes()
    test_malformed_source_feed_isolated_from_successful_source()
    test_successful_entries_are_extracted_without_raw_payload()
    test_normalizer_emits_only_canonical_articles()
    test_normalizer_localizes_naive_timestamp_with_declared_source_timezone()
    test_normalizer_keeps_naive_timestamp_fail_closed_without_source_timezone()
    test_normalizer_does_not_override_already_aware_timestamp()
    test_investing_representative_timestamp_normalizes_to_utc()
    test_report_window_uses_localized_source_timestamp_before_admission()
    test_source_snapshot_with_parseable_timestamps_is_qualified()
    test_all_null_timestamp_snapshot_is_excluded_with_bounded_diagnostic()
    test_unbounded_snapshot_does_not_block_timestamped_sibling_source()
    test_normalizer_allows_missing_published_when_linked()
    test_normalizer_requires_timestamp_for_linkless_entry()
    test_normalizer_rejects_naive_and_malformed_timestamps_without_guessing()
    test_normalizer_uses_description_only_as_summary_fallback()
    test_report_window_admission_is_inclusive_and_retains_unknown_timestamps()
    test_exact_article_dedup_keeps_first_valid_in_ingest_order()
    test_exact_article_dedup_keeps_different_source_reports_separate()
    test_exact_article_dedup_preserves_linkless_identity_and_empty_success()
    test_exact_article_dedup_reports_invalid_items_without_semantic_fallback()
    test_offline_ingest_pipeline_is_deterministic_and_keeps_different_urls()
    print("offline deterministic ingest smoke passed")


if __name__ == "__main__":
    main()
