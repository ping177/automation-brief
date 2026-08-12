from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ai_curator import (  # noqa: E402
    CandidateArticle,
    CuratedEvent,
    CuratorContractError,
    CuratorRequest,
    FixtureCuratorProvider,
    RejectedArticle,
    build_curator_request,
    load_candidate_fixture,
    render_shadow_preview,
    stable_article_id,
    validate_curator_response,
)


def candidate(article_id: str, title: str = "Major event", language: str = "und") -> CandidateArticle:
    published_at = datetime(2026, 7, 16, 8, 0, tzinfo=timezone.utc)
    return CandidateArticle(
        article_id=article_id,
        title=title,
        summary="A concise source summary.",
        source="Fixture Source",
        feed_name="Fixture Feed",
        feed_role="breaking_news",
        published_at=published_at,
        link=f"https://example.com/{article_id}",
        normalized_link=f"https://example.com/{article_id}",
        report_date=date(2026, 7, 16),
        collected_at=published_at,
        language=language,
    )


def valid_request() -> CuratorRequest:
    return build_curator_request(
        [
            candidate("article-a", language="zh-CN"),
            candidate("article-b", "Background item", "en"),
            candidate("article-c", "Undeclared source item", "und"),
        ],
        report_date=date(2026, 7, 16),
        max_events=2,
    )


def valid_payload() -> dict[str, object]:
    return {
        "schema_version": "ai_curator_shadow_v1",
        "report_date": "2026-07-16",
        "events": [
            {
                "event_id": "event-a",
                "canonical_title": "Global central banks coordinate emergency liquidity line",
                "summary": "Central banks announced a coordinated liquidity backstop.",
                "category": "macro_policy",
                "importance": "must_know",
                "why_important": "It may affect global liquidity expectations.",
                "evidence_article_ids": ["article-a"],
                "novelty": "new_event",
                "confidence": "high",
                "uncertainties": ["Implementation details remain limited."],
            }
        ],
        "rejected_article_ids": [
            {"article_id": "article-b", "reject_reason": "low_significance"}
        ],
        "warnings": ["fixture response"],
    }


def candidate_fixture_article(
    *,
    title: str,
    link: str,
    published_at: str | None,
) -> dict[str, object]:
    article = {
        "title": title,
        "summary": "A fixture candidate summary.",
        "source": "Fixture Source",
        "feed_name": "Fixture Feed",
        "feed_role": "breaking_news",
        "link": link,
        "language": "en",
        "published_at": published_at,
    }
    return article


def assert_fixture_loader_published_at_contract() -> None:
    with TemporaryDirectory() as temp_dir:
        fixture_path = Path(temp_dir) / "candidates.json"

        linked_null_article = candidate_fixture_article(
            title="Linked candidate without timestamp",
            link="https://example.com/linked-null",
            published_at=None,
        )
        fixture_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "report_date": "2026-07-16",
                    "articles": [linked_null_article],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        report_date, articles = load_candidate_fixture(fixture_path)
        assert report_date == date(2026, 7, 16)
        assert len(articles) == 1
        assert articles[0].published_at is None
        assert articles[0].article_id == stable_article_id(
            "https://example.com/linked-null",
            "Fixture Source",
            "Linked candidate without timestamp",
            None,
        )

        timestamped_article = candidate_fixture_article(
            title="Timestamped candidate",
            link="https://example.com/timestamped",
            published_at="2026-07-16T08:00:00+00:00",
        )
        fixture_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "report_date": "2026-07-16",
                    "articles": [timestamped_article],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        _report_date, articles = load_candidate_fixture(fixture_path)
        assert articles[0].published_at == datetime(2026, 7, 16, 8, 0, tzinfo=timezone.utc)

        malformed_article = candidate_fixture_article(
            title="Malformed timestamp candidate",
            link="https://example.com/malformed",
            published_at="not-an-iso-datetime",
        )
        fixture_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "report_date": "2026-07-16",
                    "articles": [malformed_article],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        try:
            load_candidate_fixture(fixture_path)
        except CuratorContractError:
            pass
        else:
            raise AssertionError("Malformed published_at must fail closed")

        missing_timestamp_article = candidate_fixture_article(
            title="Missing timestamp field candidate",
            link="https://example.com/missing-timestamp",
            published_at=None,
        )
        del missing_timestamp_article["published_at"]
        fixture_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "report_date": "2026-07-16",
                    "articles": [missing_timestamp_article],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        try:
            load_candidate_fixture(fixture_path)
        except CuratorContractError:
            pass
        else:
            raise AssertionError("Missing published_at must fail closed")

        linkless_null_article = candidate_fixture_article(
            title="Linkless candidate without timestamp",
            link="",
            published_at=None,
        )
        fixture_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "report_date": "2026-07-16",
                    "articles": [linkless_null_article],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        try:
            load_candidate_fixture(fixture_path)
        except CuratorContractError:
            pass
        else:
            raise AssertionError("Linkless published_at null candidate must fail closed")


def expect_invalid(payload: dict[str, object], request: CuratorRequest) -> None:
    try:
        validate_curator_response(payload, request)
    except CuratorContractError:
        return
    raise AssertionError("Expected invalid curator response")


def expect_invalid_diagnostic(
    payload: dict[str, object],
    request: CuratorRequest,
    diagnostic_code: str,
    diagnostic_path: str,
) -> None:
    try:
        validate_curator_response(payload, request)
    except CuratorContractError as exc:
        assert exc.diagnostic_code == diagnostic_code
        assert exc.diagnostic_path == diagnostic_path
        return
    raise AssertionError(f"Expected invalid curator response: {diagnostic_code}")


def assert_rejection_collection_invariants(request: CuratorRequest) -> None:
    duplicate_rejection = valid_payload()
    duplicate_rejection["rejected_article_ids"] = [
        {"article_id": "article-b", "reject_reason": "low_significance"},
        {"article_id": "article-b", "reject_reason": "promotional"},
    ]
    expect_invalid_diagnostic(
        duplicate_rejection,
        request,
        "duplicate_rejected_article_id",
        "rejected_article_ids.article_id",
    )

    unknown_rejection = valid_payload()
    unknown_rejection["rejected_article_ids"] = [
        {"article_id": "missing-id", "reject_reason": "low_significance"}
    ]
    expect_invalid_diagnostic(
        unknown_rejection,
        request,
        "unknown_rejected_article_id",
        "rejected_article_ids.article_id",
    )

    overlap = valid_payload()
    overlap["rejected_article_ids"] = [
        {"article_id": "article-a", "reject_reason": "duplicate"}
    ]
    expect_invalid_diagnostic(
        overlap,
        request,
        "selected_rejected_overlap",
        "selected_rejected_article_ids",
    )

    valid_multi_rejection = valid_payload()
    valid_multi_rejection["rejected_article_ids"] = [
        {"article_id": "article-b", "reject_reason": "low_significance"},
        {"article_id": "article-c", "reject_reason": "promotional"},
    ]
    response = validate_curator_response(valid_multi_rejection, request)
    assert [item.article_id for item in response.rejected_article_ids] == [
        "article-b",
        "article-c",
    ]


def main() -> None:
    assert_fixture_loader_published_at_contract()
    request = valid_request()
    assert request.target_language == "zh-CN"
    serialized_articles = request.to_dict()["articles"]
    assert [article["language"] for article in serialized_articles] == ["zh-CN", "en", "und"]

    try:
        CuratorRequest(
            schema_version=request.schema_version,
            report_date=request.report_date,
            window_start=request.window_start,
            window_end=request.window_end,
            articles=request.articles,
            target_language="en",
        )
    except CuratorContractError:
        pass
    else:
        raise AssertionError("CuratorRequest must reject non-zh-CN target_language")

    response = validate_curator_response(valid_payload(), request)
    assert response.events[0].event_id == "event-a"
    assert response.rejected_article_ids[0].reject_reason == "low_significance"
    assert_rejection_collection_invariants(request)

    with TemporaryDirectory() as temp_dir:
        fixture_path = Path(temp_dir) / "response.json"
        fixture_path.write_text(json.dumps(valid_payload(), ensure_ascii=False), encoding="utf-8")
        provider_response = FixtureCuratorProvider(fixture_path).curate(request)
    assert provider_response.events[0].canonical_title.startswith("Global central banks")

    payload = valid_payload()
    payload["events"][0]["evidence_article_ids"] = ["missing-id"]  # type: ignore[index]
    expect_invalid(payload, request)

    payload = valid_payload()
    payload["events"][0]["evidence_article_ids"] = []  # type: ignore[index]
    expect_invalid(payload, request)

    payload = valid_payload()
    payload["events"][0]["evidence_article_ids"] = ["article-a", "article-a"]  # type: ignore[index]
    expect_invalid(payload, request)

    payload = valid_payload()
    payload["events"].append(payload["events"][0])  # type: ignore[union-attr,index]
    expect_invalid(payload, request)

    payload = valid_payload()
    payload["events"][0]["importance"] = "critical"  # type: ignore[index]
    expect_invalid(payload, request)

    payload = valid_payload()
    payload["rejected_article_ids"] = [{"article_id": "article-a", "reject_reason": "duplicate"}]
    expect_invalid(payload, request)

    payload = valid_payload()
    payload["events"][0]["canonical_title"] = " "  # type: ignore[index]
    expect_invalid(payload, request)

    payload = valid_payload()
    payload["events"][0]["summary"] = " "  # type: ignore[index]
    expect_invalid(payload, request)

    payload = valid_payload()
    payload["events"][0]["why_important"] = " "  # type: ignore[index]
    expect_invalid(payload, request)

    payload = valid_payload()
    payload["events"].append(
        {
            "event_id": "event-b",
            "canonical_title": "Second event",
            "summary": "A second event.",
            "category": "geopolitics",
            "importance": "important",
            "why_important": "It matters.",
            "evidence_article_ids": ["article-b"],
            "novelty": "material_update",
            "confidence": "medium",
            "uncertainties": [],
        }
    )
    expect_invalid(payload, build_curator_request([candidate("article-a"), candidate("article-b")], date(2026, 7, 16), 1))

    payload = valid_payload()
    payload["events"].append(
        {
            "event_id": "event-b",
            "canonical_title": "Second event using shared evidence",
            "summary": "A second valid event.",
            "category": "geopolitics",
            "importance": "important",
            "why_important": "The same source can support another event in shadow comparison.",
            "evidence_article_ids": ["article-a"],
            "novelty": "material_update",
            "confidence": "medium",
            "uncertainties": [],
        }
    )
    shared_evidence_response = validate_curator_response(payload, build_curator_request([candidate("article-a"), candidate("article-b")], date(2026, 7, 16), 2))
    assert len(shared_evidence_response.events) == 2

    preview = render_shadow_preview(
        validate_curator_response(valid_payload(), request),
        request,
        [{"legacy_keyword_matched": False}, {"legacy_keyword_matched": True}],
    )
    assert "# AI Curator Shadow Preview" in preview
    assert "Global central banks coordinate" in preview
    assert "Evidence articles" in preview
    for forbidden in ("买入", "卖出", "目标价", "加仓", "减仓"):
        assert forbidden not in preview

    print("offline ai curator contract smoke passed")


if __name__ == "__main__":
    main()
