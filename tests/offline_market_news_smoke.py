from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from holdings import Holding, HoldingsConfig  # noqa: E402
from market_news import analyze_market_news  # noqa: E402


@dataclass(frozen=True)
class ArticleFixture:
    title: str
    summary: str
    source: str
    feed_role: str
    link: str
    matched_keywords: dict[str, list[str]]
    published_at: datetime = datetime.now(timezone.utc)


def article(
    title: str,
    summary: str,
    link: str,
    role: str = "market",
    keywords: dict[str, list[str]] | None = None,
) -> ArticleFixture:
    return ArticleFixture(
        title=title,
        summary=summary,
        source="离线测试源",
        feed_role=role,
        link=link,
        matched_keywords=keywords or {},
    )


def main() -> None:
    holdings = HoldingsConfig(
        holdings=(
            Holding(
                code="601179",
                name="中国西电",
                market="A股",
                sector="电力设备",
                watch_tags=("特高压", "电网设备"),
                notes="观察是否跟随电网投资周期",
            ),
            Holding(
                code="002202",
                name="金风科技",
                market="A股",
                sector="风电",
                watch_tags=("海上风电",),
                notes="观察订单和政策催化",
            ),
        ),
        source_path=None,
    )
    articles = [
        article(
            "央行公开市场操作释放流动性，A股成交量回升",
            "利率、汇率和风险偏好成为今日观察变量。",
            "https://example.com/market-liquidity",
        ),
        article(
            "国家电网启动特高压设备招标，中国西电所在电力设备链条受关注",
            "招标订单和电网投资节奏可能成为产业催化。",
            "https://example.com/grid-tender",
            keywords={"财经股票": ["特高压", "电力设备"]},
        ),
        article(
            "海外风电项目披露新订单，海上风电产业链关注度上升",
            "金风科技所属风电方向需要验证订单持续性。",
            "https://example.com/wind-order",
            keywords={"财经股票": ["风电"]},
        ),
        article(
            "某上市公司收到交易所监管函，后续将披露整改进展",
            "监管和处罚事项需要作为风险线索观察。",
            "https://example.com/regulatory-risk",
        ),
        article(
            "普通消费电子新品体验活动举行",
            "没有明确市场变量。",
            "https://example.com/consumer-event",
            role="tech_industry",
        ),
        article(
            "多家公司讨论品牌出海和渠道建设",
            "这条只命中宽泛观察标签，不应直接挂到具体持仓。",
            "https://example.com/broad-overseas",
        ),
    ]

    analysis = analyze_market_news(articles, holdings)

    assert any("A股成交量" in item.title for item in analysis.market_events)
    assert any("特高压设备招标" in item.title for item in analysis.industry_catalysts)
    assert any("海外风电项目" in item.title for item in analysis.industry_catalysts)
    assert any("RSS 候选新闻" in point for point in analysis.environment_points)
    assert any("风险/反证" in point for point in analysis.environment_points)
    assert any("特高压" in clue or "订单" in clue for clue in analysis.theme_clues)
    assert any("后续将披露" in point for point in analysis.watch_points)
    assert any("真实行情" in question for question in analysis.deep_dive_questions)

    holding_map = {match.holding_title: match for match in analysis.holding_related_news}
    assert "601179 中国西电" in holding_map
    assert "002202 金风科技" in holding_map
    assert any("中国西电" in item.title for item in holding_map["601179 中国西电"].matches)
    assert any("风电" in item.title for item in holding_map["002202 金风科技"].matches)
    assert not any(
        "品牌出海" in item.title
        for match in analysis.holding_related_news
        for item in match.matches
    )
    assert "普通消费电子新品体验活动举行" not in [item.title for item in analysis.market_events]

    print("offline market news smoke passed")


if __name__ == "__main__":
    main()
