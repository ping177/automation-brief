from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from holdings import Holding, HoldingsConfig  # noqa: E402
from ai_curator import (  # noqa: E402
    CandidateArticle,
    CuratedEvent,
    CuratorResponse,
    candidate_trace_records,
)
from ai_curator_provider import (  # noqa: E402
    DEEPSEEK_PROVIDER_CONFIG,
    PHASE_4_LIVE_INPUT_MODE,
    PHASE_4_LIVE_MAX_CANDIDATE_COUNT,
    PHASE_4_LIVE_MAX_PROVIDER_REQUEST_BODY_BYTES,
    DeepSeekCuratorProvider,
    OpenAICompatibleProviderError,
)
from main import DigestSections, NewsItem, ReportConfig, build_digest_sections, normalize_config  # noqa: E402
import main as main_module  # noqa: E402
from market_analysis import HoldingObservation, MarketBriefContext  # noqa: E402
from market_brief_writer import DIRECT_TRADING_ADVICE_TERMS  # noqa: E402
from market_data import MarketDataFailure, MarketQuote, MarketSnapshot  # noqa: E402
from market_news import (  # noqa: E402
    HOLDING_RELATION_CLEAR,
    HoldingNewsMatch,
    MarketNewsAnalysis,
    NewsInsight,
    NEWS_TYPE_COMPANY_OPERATING,
    NEWS_TYPE_MACRO_RISK,
)
from overnight_brief_writer import (  # noqa: E402
    OVERNIGHT_BRIEF_SECTIONS,
    render_overnight_brief_markdown,
)


REPORT_DATE = date(2026, 8, 13)
PUBLISHED_AT = datetime(2026, 8, 13, 7, 30, tzinfo=timezone.utc)


def news_item(title: str, link: str, *, role: str = "breaking_news", summary: str = "事件摘要。") -> NewsItem:
    return NewsItem(
        title=title,
        source="离线测试源",
        feed_name="离线测试源",
        feed_role=role,
        published="Thu, 13 Aug 2026 07:30:00 GMT",
        published_at=PUBLISHED_AT,
        link=link,
        summary=summary,
        matched_keywords={},
    )


def market_snapshot(
    *,
    indexes: tuple[MarketQuote, ...] = (),
    holdings: tuple[MarketQuote, ...] = (),
    failures: tuple[MarketDataFailure, ...] = (),
    watch_signals: tuple[str, ...] = ("观察主要指数涨跌是否继续支持风险偏好。",),
) -> MarketSnapshot:
    return MarketSnapshot(
        data_date=REPORT_DATE,
        market_data_date=date(2026, 8, 12),
        environment_note="离线测试行情环境。",
        indexes=indexes,
        holdings=holdings,
        failures=failures,
        strong_1d=(),
        strong_5d=(),
        trend_20d=(),
        catalysts=(),
        watch_signals=watch_signals,
    )


def empty_news_analysis(
    *,
    market_events: tuple[NewsInsight, ...] = (),
    watch_points: tuple[str, ...] = (),
    holding_related_news: tuple[HoldingNewsMatch, ...] = (),
) -> MarketNewsAnalysis:
    return MarketNewsAnalysis(
        market_events=market_events,
        industry_catalysts=(),
        environment_points=(),
        theme_clues=(),
        watch_points=watch_points,
        deep_dive_questions=(),
        holding_related_news=holding_related_news,
    )


def context(
    *,
    snapshot: MarketSnapshot | None = None,
    holdings: tuple[Holding, ...] = (),
    observations: tuple[HoldingObservation, ...] = (),
    news: MarketNewsAnalysis | None = None,
    feed_failures: tuple[tuple[str, str], ...] = (),
) -> MarketBriefContext:
    holdings_config = HoldingsConfig(
        holdings=holdings,
        source_path=Path("fixture-holdings.json") if holdings else None,
        used_example=False,
    )
    return MarketBriefContext(
        snapshot=snapshot or market_snapshot(),
        holdings_config=holdings_config,
        holding_observations=observations,
        news_analysis=news or empty_news_analysis(),
        feed_failures=feed_failures,
    )


def render(
    *,
    core_items: tuple[NewsItem, ...] = (),
    market_items: tuple[NewsItem, ...] = (),
    brief_context: MarketBriefContext | None = None,
    curated_events: tuple[CuratedEvent, ...] | None = None,
    candidate_by_id: dict[str, CandidateArticle] | None = None,
) -> str:
    return render_overnight_brief_markdown(
        core_items,
        market_items,
        brief_context or context(),
        report_date=REPORT_DATE,
        generated_at=datetime(2026, 8, 13, 8, 0, tzinfo=timezone.utc),
        curated_events=curated_events,
        candidate_by_id=candidate_by_id,
    )


def curator_candidate(
    article_id: str,
    title: str,
    link: str,
    *,
    source: str = "English RSS Source",
) -> CandidateArticle:
    published_at = datetime(2026, 8, 13, 7, 0, tzinfo=timezone.utc)
    return CandidateArticle(
        article_id=article_id,
        title=title,
        summary="English source summary that must not reach the reader-facing brief.",
        source=source,
        feed_name=source,
        feed_role="breaking_news",
        published_at=published_at,
        link=link,
        normalized_link=link,
        report_date=REPORT_DATE,
        collected_at=published_at,
        language="en",
    )


def curated_event(
    event_id: str,
    title: str,
    category: str,
    evidence_article_ids: tuple[str, ...],
    *,
    uncertainty: str = "",
    importance: str = "must_know",
    confidence: str = "high",
) -> CuratedEvent:
    return CuratedEvent(
        event_id=event_id,
        canonical_title=title,
        summary="中文事件摘要，直接供读者阅读。",
        category=category,
        importance=importance,
        why_important="中文重要性说明。",
        evidence_article_ids=evidence_article_ids,
        novelty="new_event",
        confidence=confidence,
        uncertainties=(uncertainty,) if uncertainty else (),
    )


class RecordingCurator:
    def __init__(self, response: CuratorResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.requests = []

    def curate(self, request):  # noqa: ANN001
        self.requests.append(request)
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


class OfflineProviderTransport:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.payload = payload
        self.calls: list[tuple[object, float]] = []

    def __call__(self, request: object, timeout: float) -> tuple[int, bytes]:
        self.calls.append((request, timeout))
        assert self.payload is not None
        envelope = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(self.payload, ensure_ascii=False),
                    },
                }
            ]
        }
        return 200, json.dumps(envelope, ensure_ascii=False).encode("utf-8")


@contextmanager
def temporary_env(name: str, value: str | None) -> Iterator[None]:
    previous = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def provider_event_payload(article_id: str) -> dict[str, object]:
    return {
        "schema_version": "ai_curator_shadow_v1",
        "report_date": REPORT_DATE.isoformat(),
        "events": [
            {
                "event_id": "event-auditable",
                "canonical_title": "可审计的中文事件",
                "summary": "中文事件摘要，直接供读者阅读。",
                "category": "macro_policy",
                "importance": "important",
                "why_important": "该事件由候选证据支持。",
                "evidence_article_ids": [article_id],
                "novelty": "new_event",
                "confidence": "high",
                "uncertainties": ["继续观察后续执行。"],
            }
        ],
        "rejected_article_ids": [],
        "warnings": [],
    }


def test_curator_success_projects_events_without_legacy_news() -> None:
    market_candidate = curator_candidate(
        "candidate-market",
        "English market source headline",
        "https://example.com/market-source",
        source="English Market Source",
    )
    core_candidate = curator_candidate(
        "candidate-core",
        "English core source headline",
        "https://example.com/core-source",
        source="English Core Source",
    )
    market_event = curated_event(
        "event-market",
        "央行释放流动性信号",
        "financial_markets",
        (market_candidate.article_id,),
        uncertainty="继续观察利率预期是否变化。",
        importance="important",
    )
    core_event = curated_event(
        "event-core",
        "主要经济体达成新的安全安排",
        "geopolitics",
        (core_candidate.article_id,),
        uncertainty="继续观察执行细节是否落地。",
        importance="important",
    )
    duplicate_title_event = curated_event(
        "event-same-title",
        market_event.canonical_title,
        "energy_commodities",
        (core_candidate.article_id,),
    )
    response = CuratorResponse(
        schema_version="ai_curator_shadow_v1",
        report_date=REPORT_DATE,
        events=(market_event, core_event, duplicate_title_event),
        rejected_article_ids=(),
        warnings=(),
    )
    provider = RecordingCurator(response=response)
    curated_response = main_module.curate_overnight_candidates(
        (market_candidate, core_candidate),
        REPORT_DATE,
        provider=provider,
    )
    assert curated_response is response
    assert provider.requests[0].max_events == 20

    legacy_core = news_item(
        "LEGACY English headline that must not be rendered",
        "https://example.com/legacy-core",
        summary="LEGACY English summary that must not be rendered",
    )
    legacy_market = news_item(
        "LEGACY market headline that must not be rendered",
        "https://example.com/legacy-market",
        role="market",
    )
    markdown = render(
        core_items=(legacy_core,),
        market_items=(legacy_market,),
        curated_events=curated_response.events,
        candidate_by_id={
            market_candidate.article_id: market_candidate,
            core_candidate.article_id: core_candidate,
        },
    )
    assert "LEGACY English headline" not in markdown
    assert "LEGACY market headline" not in markdown
    assert "LEGACY English summary" not in markdown
    assert markdown.count(market_event.canonical_title) == 2
    assert core_event.canonical_title in markdown
    assert "English Market Source" in markdown
    assert "https://example.com/market-source" in markdown
    assert "English Core Source" in markdown
    assert "https://example.com/core-source" in markdown
    market_section = markdown.split("## 二、隔夜市场", 1)[1].split("## 三、今日值得关注", 1)[0]
    core_section = markdown.split("## 一、昨夜最重要的事", 1)[1].split("## 二、隔夜市场", 1)[0]
    assert market_event.canonical_title in market_section
    assert core_event.canonical_title in core_section
    assert "继续观察利率预期是否变化。" in markdown
    assert "继续观察执行细节是否落地。" in markdown
    assert "English source summary" not in markdown
    assert "暂无明确的市场新闻或市场信号。" not in market_section


def test_curator_success_with_no_market_events_shows_market_empty_state() -> None:
    event = curated_event(
        "event-core-only",
        "主要经济体发布新的政策安排",
        "geopolitics",
        ("candidate-core-only",),
    )
    markdown = render(curated_events=(event,))
    market_section = markdown.split("## 二、隔夜市场", 1)[1].split(
        "## 三、今日值得关注", 1
    )[0]
    assert "暂无明确的市场新闻或市场信号。" in market_section


def test_curator_reader_projection_hides_background_events() -> None:
    must_know = curated_event(
        "event-must-know",
        "重大政策事件",
        "macro_policy",
        (),
        importance="must_know",
    )
    important = curated_event(
        "event-important",
        "重要地缘事件",
        "geopolitics",
        (),
        importance="important",
    )
    background_core = curated_event(
        "event-background-core",
        "低价值背景事件",
        "geopolitics",
        (),
        uncertainty="背景事件后续仍有普通事实待确认",
        importance="background",
    )
    background_market = curated_event(
        "event-background-market",
        "低价值背景市场事件",
        "financial_markets",
        (),
        importance="background",
    )
    important_market = curated_event(
        "event-important-market",
        "重要市场事件",
        "financial_markets",
        (),
        importance="important",
    )
    markdown = render(
        brief_context=context(snapshot=market_snapshot(watch_signals=())),
        curated_events=(
            must_know,
            important,
            background_core,
            background_market,
            important_market,
        ),
    )
    core_section = markdown.split("## 一、昨夜最重要的事", 1)[1].split(
        "## 二、隔夜市场", 1
    )[0]
    market_section = markdown.split("## 二、隔夜市场", 1)[1].split(
        "## 三、今日值得关注", 1
    )[0]
    watch_section = markdown.split("## 三、今日值得关注", 1)[1].split("---", 1)[0]

    assert must_know.canonical_title in core_section
    assert important.canonical_title in core_section
    assert important_market.canonical_title in market_section
    assert background_core.canonical_title not in markdown
    assert background_market.canonical_title not in markdown
    assert "背景事件后续仍有普通事实待确认" not in watch_section


def test_curated_watch_prefers_meaningful_event_variables() -> None:
    low_value_public_safety = curated_event(
        "event-fire",
        "地方船厂发生火灾",
        "public_safety",
        (),
        uncertainty="火灾原因及具体伤亡情况尚不明确",
    )
    low_value_legal = curated_event(
        "event-lawsuit",
        "政治人物因帖文遭起诉",
        "geopolitics",
        (),
        uncertainty="指控尚未经法院裁决",
        importance="background",
    )
    macro_event = curated_event(
        "event-policy",
        "央行流动性操作",
        "macro_policy",
        (),
        uncertainty="后续流动性投放是否改变市场利率预期",
        importance="important",
    )
    geopolitical_event = curated_event(
        "event-hormuz",
        "关键航道风险升温",
        "geopolitics",
        (),
        uncertainty="后续通行受限是否进一步影响能源运输",
        importance="important",
    )
    markdown = render(
        brief_context=context(snapshot=market_snapshot(watch_signals=())),
        curated_events=(
            low_value_public_safety,
            low_value_legal,
            macro_event,
            geopolitical_event,
        ),
    )
    watch_section = markdown.split("## 三、今日值得关注", 1)[1].split("---", 1)[0]

    assert "后续流动性投放是否改变市场利率预期" in watch_section
    assert "后续通行受限是否进一步影响能源运输" in watch_section
    assert "火灾原因及具体伤亡情况尚不明确" not in watch_section
    assert "指控尚未经法院裁决" not in watch_section
    assert watch_section.count("- ") == 2


def test_curated_watch_accepts_must_know_event_variable() -> None:
    event = curated_event(
        "event-must-know-policy",
        "重大政策安排",
        "macro_policy",
        (),
        uncertainty="后续政策执行是否改变流动性预期",
        importance="must_know",
    )
    markdown = render(
        brief_context=context(snapshot=market_snapshot(watch_signals=())),
        curated_events=(event,),
    )
    watch_section = markdown.split("## 三、今日值得关注", 1)[1].split("---", 1)[0]

    assert "后续政策执行是否改变流动性预期" in watch_section


def test_curated_watch_can_use_unexplained_holding_anomaly() -> None:
    holding = Holding(
        code="601179",
        name="中国西电",
        market="A股",
        sector="电力设备",
        watch_tags=("特高压",),
        notes="观察订单和公告。",
    )
    quote = MarketQuote(
        "中国西电",
        "601179",
        -3.20,
        None,
        "fixture",
        "2026-08-12T15:00:00+08:00",
    )
    markdown = render(
        brief_context=context(
            snapshot=market_snapshot(
                indexes=(
                    MarketQuote("上证指数", "000001", 1.10, None, "fixture", "2026-08-12T15:00:00+08:00"),
                    MarketQuote("深成指", "399001", 0.90, None, "fixture", "2026-08-12T15:00:00+08:00"),
                ),
                holdings=(quote,),
                watch_signals=(),
            ),
            holdings=(holding,),
            observations=(
                HoldingObservation(
                    title="601179 中国西电",
                    code="601179",
                    name="中国西电",
                    sector="电力设备",
                    watch_tags=("特高压",),
                    notes="观察订单和公告。",
                    observation="已读取关注对象；结合可用行情和新闻线索观察，不输出交易动作。",
                    quote=quote,
                ),
            ),
        ),
        curated_events=(),
    )
    watch_section = markdown.split("## 三、今日值得关注", 1)[1].split("---", 1)[0]

    assert "持仓变量：当前 RSS 尚未解释该异常波动" in watch_section


def test_curated_watch_does_not_fill_to_three_items() -> None:
    event = curated_event(
        "event-policy-only",
        "央行政策安排",
        "macro_policy",
        (),
        uncertainty="后续政策执行范围是否扩大",
        importance="important",
    )
    markdown = render(
        brief_context=context(snapshot=market_snapshot(watch_signals=())),
        curated_events=(event,),
    )
    watch_section = markdown.split("## 三、今日值得关注", 1)[1].split("---", 1)[0]

    assert watch_section.count("- ") == 1
    assert "暂无明确的延续观察变量。" not in watch_section


def test_overnight_curator_success_persists_auditable_artifacts() -> None:
    retained = curator_candidate(
        "candidate-retained",
        "Retained English source headline",
        "https://example.com/retained",
        source="English Source",
    )
    excluded = curator_candidate(
        "candidate-excluded",
        "Excluded daily tools headline",
        "https://example.com/excluded",
        source="GitHub Trending Python Daily",
    )
    provider_payload = provider_event_payload(retained.article_id)
    provider_payload["events"].append(  # type: ignore[union-attr]
        {
            "event_id": "event-background-auditable",
            "canonical_title": "仅保留在 artifact 的背景事件",
            "summary": "该背景事件不进入 Morning Brief reader-facing projection。",
            "category": "company_industry",
            "importance": "background",
            "why_important": "保留完整 CuratorResponse 以供审计。",
            "evidence_article_ids": [retained.article_id],
            "novelty": "new_event",
            "confidence": "high",
            "uncertainties": [],
        }
    )
    provider = DeepSeekCuratorProvider(
        transport=OfflineProviderTransport(provider_payload),
        max_candidate_count=PHASE_4_LIVE_MAX_CANDIDATE_COUNT,
        max_provider_request_body_bytes=PHASE_4_LIVE_MAX_PROVIDER_REQUEST_BODY_BYTES,
        input_mode=PHASE_4_LIVE_INPUT_MODE,
    )
    with TemporaryDirectory(dir="/private/tmp") as temp_dir:
        artifact_root = Path(temp_dir) / "runs" / "ai-curator-shadow"
        with temporary_env(DEEPSEEK_PROVIDER_CONFIG.api_key_env, "offline-test-key"):
            response = main_module.curate_overnight_candidates(
                (retained, excluded),
                REPORT_DATE,
                provider=provider,
                artifact_root=artifact_root,
                trace_records=candidate_trace_records((retained, excluded), []),
                legacy_evaluation="keyword_gate_approximation",
            )

        assert response is not None
        run_dirs = [path for path in artifact_root.iterdir() if path.is_dir()]
        assert len(run_dirs) == 1
        run_dir = run_dirs[0]
        assert run_dir.name.startswith("overnight-")
        run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        request_payload = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
        response_payload = json.loads((run_dir / "response.json").read_text(encoding="utf-8"))
        trace_payload = json.loads((run_dir / "trace.json").read_text(encoding="utf-8"))

        assert run_payload["status"] == "succeeded"
        assert run_payload["input_mode"] == PHASE_4_LIVE_INPUT_MODE
        assert run_payload["original_candidate_count"] == 2
        assert run_payload["candidate_count"] == 1
        assert run_payload["source_excluded_count"] == 1
        assert run_payload["validation_status"] == "passed"
        assert len(request_payload["articles"]) == 1
        assert request_payload["articles"][0]["article_id"] == retained.article_id
        assert request_payload["articles"][0]["title"] == retained.title
        assert request_payload["articles"][0]["summary"] == retained.summary
        assert {item["article_id"] for item in trace_payload} == {
            retained.article_id,
            excluded.article_id,
        }
        assert response_payload["events"][0]["canonical_title"] == "可审计的中文事件"
        assert response_payload["events"][0]["evidence_article_ids"] == [retained.article_id]
        assert response_payload["events"][1]["importance"] == "background"
        assert response_payload["events"][1]["canonical_title"] == "仅保留在 artifact 的背景事件"

        reader_markdown = render(curated_events=response.events)
        assert "可审计的中文事件" in reader_markdown
        assert "仅保留在 artifact 的背景事件" not in reader_markdown


def test_overnight_curator_failure_persists_failure_and_keeps_legacy_fallback() -> None:
    candidate = curator_candidate(
        "candidate-failure-artifact",
        "Failure source headline",
        "https://example.com/failure-artifact",
    )
    provider = DeepSeekCuratorProvider(
        transport=OfflineProviderTransport(provider_event_payload(candidate.article_id)),
        max_candidate_count=PHASE_4_LIVE_MAX_CANDIDATE_COUNT,
        max_provider_request_body_bytes=PHASE_4_LIVE_MAX_PROVIDER_REQUEST_BODY_BYTES,
        input_mode=PHASE_4_LIVE_INPUT_MODE,
    )
    with TemporaryDirectory(dir="/private/tmp") as temp_dir:
        artifact_root = Path(temp_dir) / "runs" / "ai-curator-shadow"
        with temporary_env(DEEPSEEK_PROVIDER_CONFIG.api_key_env, None):
            response = main_module.curate_overnight_candidates(
                (candidate,),
                REPORT_DATE,
                provider=provider,
                artifact_root=artifact_root,
                trace_records=candidate_trace_records((candidate,), []),
                legacy_evaluation="keyword_gate_approximation",
            )

        assert response is None
        run_dirs = [path for path in artifact_root.iterdir() if path.is_dir()]
        assert len(run_dirs) == 1
        run_dir = run_dirs[0]
        run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        assert run_payload["status"] == "failed"
        assert run_payload["failure_stage"] == "configuration"
        assert run_payload["failure_code"] == "missing_api_key"
        assert run_payload["validation_status"] == "failed"
        assert (run_dir / "request.json").exists()
        assert not (run_dir / "response.json").exists()

        fallback_markdown = render(
            core_items=(
                news_item(
                    "Legacy fallback headline",
                    "https://example.com/fallback-artifact",
                    summary="Legacy fallback summary.",
                ),
            ),
            curated_events=None,
        )
        assert "Legacy fallback headline" in fallback_markdown
        assert "Legacy fallback summary" in fallback_markdown


def test_curator_provider_failure_returns_whole_news_fallback_signal() -> None:
    candidate = curator_candidate(
        "candidate-failure",
        "English failure source headline",
        "https://example.com/failure-source",
    )
    provider = RecordingCurator(
        error=OpenAICompatibleProviderError("transport", "timeout", 2)
    )
    assert (
        main_module.curate_overnight_candidates(
            (candidate,),
            REPORT_DATE,
            provider=provider,
        )
        is None
    )
    fallback_markdown = render(
        core_items=(
            news_item(
                "Legacy fallback headline",
                "https://example.com/fallback",
                summary="Legacy fallback summary.",
            ),
        ),
        curated_events=None,
    )
    assert "Legacy fallback headline" in fallback_markdown
    assert "Legacy fallback summary" in fallback_markdown
    assert "## 二、隔夜市场" in fallback_markdown
    assert "## 四、持仓异常" not in fallback_markdown


def test_curated_holding_news_requires_evidence_overlap_and_keeps_legacy_body_hidden() -> None:
    holding = Holding(
        code="601179",
        name="中国西电",
        market="A股",
        sector="电力设备",
        watch_tags=("特高压",),
        notes="观察订单和公告。",
    )
    candidate = curator_candidate(
        "candidate-holding",
        "English holding source headline",
        "https://example.com/holding-source",
    )
    event = curated_event(
        "event-holding",
        "中国西电出现新的经营事件",
        "company_industry",
        (candidate.article_id,),
    )
    legacy_holding_news = NewsInsight(
        title="LEGACY holding headline must stay hidden",
        source="Legacy Market Source",
        link=candidate.link,
        reason="Legacy rule reason must stay hidden.",
        relevance_score=95,
        news_type=NEWS_TYPE_COMPANY_OPERATING,
        holding_relation=HOLDING_RELATION_CLEAR,
    )
    markdown = render(
        curated_events=(event,),
        candidate_by_id={candidate.article_id: candidate},
        brief_context=context(
            holdings=(holding,),
            observations=(
                HoldingObservation(
                    title="601179 中国西电",
                    code="601179",
                    name="中国西电",
                    sector="电力设备",
                    watch_tags=("特高压",),
                    notes="观察订单和公告。",
                    observation="已读取关注对象；结合可用行情和新闻线索观察，不输出交易动作。",
                ),
            ),
            news=empty_news_analysis(
                holding_related_news=(
                    HoldingNewsMatch("601179 中国西电", (legacy_holding_news,)),
                ),
            ),
        ),
    )
    assert "## 四、持仓异常" in markdown
    assert "高精度匹配：相关中文事件已在前文展示" in markdown
    assert "LEGACY holding headline" not in markdown
    assert "Legacy rule reason" not in markdown
    assert "English holding source headline" not in markdown


def main() -> None:
    test_curator_success_projects_events_without_legacy_news()
    test_curator_success_with_no_market_events_shows_market_empty_state()
    test_curator_reader_projection_hides_background_events()
    test_overnight_curator_success_persists_auditable_artifacts()
    test_overnight_curator_failure_persists_failure_and_keeps_legacy_fallback()
    test_curator_provider_failure_returns_whole_news_fallback_signal()
    test_curated_holding_news_requires_evidence_overlap_and_keeps_legacy_body_hidden()
    test_curated_watch_accepts_must_know_event_variable()
    assert normalize_config({"report_type": "overnight_brief"}).report_type == "overnight_brief"

    important = news_item(
        "央行宣布降息，市场重新评估流动性预期",
        "https://example.com/liquidity",
        summary="央行公布新的利率安排，市场关注后续流动性变化。",
    )
    digest_sections = build_digest_sections([important], ReportConfig(report_type="digest"))
    assert digest_sections == DigestSections(core=[important], market=[], watch=[], quick_scan=[])

    duplicate_market_event = NewsInsight(
        title=f"{important.title}（市场新闻）",
        source=important.source,
        link="https://example.com/liquidity-market",
        reason="宏观流动性变量需要继续观察。",
        relevance_score=92,
        news_type=NEWS_TYPE_MACRO_RISK,
    )
    duplicate_markdown = render(
        core_items=tuple(digest_sections.core),
        brief_context=context(news=empty_news_analysis(market_events=(duplicate_market_event,))),
    )
    assert duplicate_markdown.startswith("# 早间简报｜2026-08-13")
    for section in OVERNIGHT_BRIEF_SECTIONS[:3]:
        assert section in duplicate_markdown
    assert "## 四、持仓异常" not in duplicate_markdown
    assert duplicate_markdown.count(important.title) == 1
    assert "（市场新闻）" not in duplicate_markdown
    assert "前一交易日 A 股指数数据" in duplicate_markdown
    assert not any(term in duplicate_markdown for term in DIRECT_TRADING_ADVICE_TERMS)

    forbidden_markdown = render(
        core_items=(
            news_item(
                "某公司目标价上调，建议买入",
                "https://example.com/advice",
                summary="建议卖出并设置止损，仓位需要调整。",
            ),
        )
    )
    assert "目标价" not in forbidden_markdown
    assert "仓位" not in forbidden_markdown
    assert not any(term in forbidden_markdown for term in DIRECT_TRADING_ADVICE_TERMS)

    watch_markdown = render(
        core_items=(important,),
        brief_context=context(
            news=empty_news_analysis(
                watch_points=(
                    f"观察 {important.title} 是否出现正式文件。",
                    "观察汇率和利率变量是否继续变化。",
                    "观察市场风险偏好是否扩散。",
                    "观察政策执行范围是否扩大。",
                    "观察外部商品价格是否出现新的方向。",
                )
            )
        ),
    )
    watch_section = watch_markdown.split("## 三、今日值得关注", 1)[1].split("---", 1)[0]
    assert watch_section.count("- ") <= 3
    assert "观察汇率和利率变量是否继续变化" in watch_section
    assert important.title not in watch_section
    assert "观察外部商品价格是否出现新的方向" not in watch_section

    holding = Holding(
        code="601179",
        name="中国西电",
        market="A股",
        sector="电力设备",
        watch_tags=("特高压",),
        notes="观察订单和公告。",
    )
    holding_news = NewsInsight(
        title="中国西电公告重大订单，经营变量进入观察范围",
        source="离线测试源",
        link="https://example.com/holding-order",
        reason="公司经营事件直接命中关注对象。",
        relevance_score=90,
        news_type=NEWS_TYPE_COMPANY_OPERATING,
        holding_relation=HOLDING_RELATION_CLEAR,
    )
    holding_markdown = render(
        brief_context=context(
            holdings=(holding,),
            observations=(
                HoldingObservation(
                    title="601179 中国西电",
                    code="601179",
                    name="中国西电",
                    sector="电力设备",
                    watch_tags=("特高压",),
                    notes="观察订单和公告。",
                    observation="已读取关注对象；结合可用行情和新闻线索观察，不输出交易动作。",
                ),
            ),
            news=empty_news_analysis(
                market_events=(holding_news,),
                holding_related_news=(HoldingNewsMatch("601179 中国西电", (holding_news,)),),
            ),
        )
    )
    assert "## 四、持仓异常" in holding_markdown
    assert "601179 中国西电" in holding_markdown
    assert "高精度匹配" in holding_markdown

    anomaly_markdown = render(
        brief_context=context(
            snapshot=market_snapshot(
                indexes=(
                    MarketQuote("上证指数", "000001", 1.10, None, "fixture", "2026-08-12T15:00:00+08:00"),
                    MarketQuote("深成指", "399001", 0.90, None, "fixture", "2026-08-12T15:00:00+08:00"),
                ),
                holdings=(
                    MarketQuote(
                        "中国西电",
                        "601179",
                        -3.20,
                        None,
                        "fixture",
                        "2026-08-12T15:00:00+08:00",
                    ),
                ),
            ),
            holdings=(holding,),
            observations=(
                HoldingObservation(
                    title="601179 中国西电",
                    code="601179",
                    name="中国西电",
                    sector="电力设备",
                    watch_tags=("特高压",),
                    notes="观察订单和公告。",
                    observation="已读取关注对象；结合可用行情和新闻线索观察，不输出交易动作。",
                    quote=MarketQuote(
                        "中国西电",
                        "601179",
                        -3.20,
                        None,
                        "fixture",
                        "2026-08-12T15:00:00+08:00",
                    ),
                ),
            ),
        )
    )
    assert "## 四、持仓异常" in anomaly_markdown
    assert "异常提示：主要指数整体偏强" in anomaly_markdown

    missing_data_markdown = render(
        brief_context=context(
            snapshot=market_snapshot(
                failures=(MarketDataFailure(scope="indexes", message="offline failure"),)
            ),
            feed_failures=(("失效 RSS", "timeout"),),
        )
    )
    assert "指数行情：数据暂不可用" in missing_data_markdown
    assert "本次不做该项判断" in missing_data_markdown
    assert "失效 RSS" in missing_data_markdown
    assert "## 四、持仓异常" not in missing_data_markdown

    with TemporaryDirectory(prefix="automation-brief-overnight-") as temp_dir:
        temp_root = Path(temp_dir)
        holdings_path = temp_root / "holdings.json"
        holdings_path.write_text('{"holdings": []}\n', encoding="utf-8")
        original_fetch_market_snapshot = main_module.fetch_market_snapshot
        main_module.fetch_market_snapshot = lambda report_date, holdings_config: market_snapshot()
        try:
            output_file = main_module.write_markdown(
                [important],
                {},
                temp_root / "reports",
                REPORT_DATE,
                ReportConfig(report_type="overnight_brief"),
                [],
                holdings_path=holdings_path,
            )
        finally:
            main_module.fetch_market_snapshot = original_fetch_market_snapshot
        assert output_file.name == "morning-brief-2026-08-13.md"
        assert output_file.read_text(encoding="utf-8").startswith("# 早间简报｜2026-08-13")

    print("morning brief unified smoke passed")


if __name__ == "__main__":
    main()
