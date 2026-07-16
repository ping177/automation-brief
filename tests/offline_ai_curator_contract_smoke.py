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
    render_shadow_preview,
    validate_curator_response,
)


def candidate(article_id: str, title: str = "Major event") -> CandidateArticle:
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
    )


def valid_request() -> CuratorRequest:
    return build_curator_request(
        [candidate("article-a"), candidate("article-b", "Background item")],
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


def expect_invalid(payload: dict[str, object], request: CuratorRequest) -> None:
    try:
        validate_curator_response(payload, request)
    except CuratorContractError:
        return
    raise AssertionError("Expected invalid curator response")


def main() -> None:
    request = valid_request()
    response = validate_curator_response(valid_payload(), request)
    assert response.events[0].event_id == "event-a"
    assert response.rejected_article_ids[0].reject_reason == "low_significance"

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
