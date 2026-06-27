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
        article(
            "AI 圆桌访谈热议 IPO 和大模型 ROI",
            "泛圆桌和访谈内容没有具体融资、订单、监管或行情变量。",
            "https://example.com/ai-roundtable",
            role="ai_industry",
            keywords={"AI方向": ["AI", "大模型"]},
        ),
        article(
            "人工智能算力需求推高数据中心电力投资预期",
            "大模型训练带动算力、电网负荷和数据中心电力改造关注。",
            "https://example.com/ai-power",
            role="ai_industry",
            keywords={"AI方向": ["人工智能", "算力", "数据中心电力"]},
        ),
        article(
            "普通食品检验结果公布，消费维权案例持续发酵",
            "普通消费维权和食品检验不应进入市场投研核心段落。",
            "https://example.com/consumer-rights",
            role="general",
        ),
        article(
            "NanmiCoder/MediaCrawler",
            "GitHub Trending 工具条目即使命中 AI 或支付，也不应进入市场投研核心段落。",
            "https://example.com/github-trending-tool",
            role="ai_tools",
            keywords={"AI方向": ["AI", "支付"]},
        ),
        article(
            "9点1氪｜苹果涨价引山姆代购潮；DeepSeek大规模招聘；黄金再度跌破4000美元",
            "综合快讯合集同时包含 A股、港股、美股、下滑、融资、风险等多个子事件词。",
            "https://example.com/kr-roundup",
            role="global_tech_business",
            keywords={"财经股票": ["A股", "港股", "美股", "融资"]},
        ),
        article(
            "氪星晚报 ｜智元旗下灵巧手估值10亿美元，成立仅5个月首季实现盈利；DeepSeek计划扩招",
            "综合晚报合集不应因交易所、风险等上下文词被判为政策监管。",
            "https://example.com/kr-evening-roundup",
            role="global_tech_business",
            keywords={"AI方向": ["AI", "估值"]},
        ),
        article(
            "中科闻歌开盘暴涨81%，北京再增一家硬科技IPO",
            "上市首日涨幅和 IPO 属于公司资本事件，不是宏观风险。",
            "https://example.com/ipo-surge",
            role="global_tech_business",
            keywords={"财经股票": ["IPO", "上市"]},
        ),
        article(
            "压上全部现金也要跨界并购？昔日集成灶龙头*ST帅电保壳豪赌，拟收购电力设备资产",
            "只命中电力设备泛行业词，不应挂到具体关注对象。",
            "https://example.com/st-power-equipment",
            role="market",
            keywords={"财经股票": ["并购", "电力设备"]},
        ),
    ]

    analysis = analyze_market_news(articles, holdings)

    assert any("A股成交量" in item.title for item in analysis.market_events)
    assert any(
        "中科闻歌开盘暴涨" in item.title and item.news_type == "公司融资 / IPO"
        for item in analysis.market_events
    )
    assert any("特高压设备招标" in item.title for item in analysis.industry_catalysts)
    assert any("海外风电项目" in item.title for item in analysis.industry_catalysts)
    assert any("数据中心电力" in item.title for item in analysis.industry_catalysts)
    assert all(item.relevance_score >= 60 for item in analysis.market_events)
    assert all(item.relevance_score >= 55 for item in analysis.industry_catalysts)
    assert any(item.news_type == "政策监管" for item in analysis.market_events + analysis.industry_catalysts)
    assert any(item.news_type == "产业催化" for item in analysis.industry_catalysts)
    assert not any("9点1氪" in item.title or "氪星晚报" in item.title for item in analysis.market_events)
    assert not any("DeepSeek" in item.title and item.news_type == "政策监管" for item in analysis.market_events)
    assert any("RSS 候选新闻" in point for point in analysis.environment_points)
    assert any("风险/反证" in point for point in analysis.environment_points)
    assert not any("9点1氪" in point or "氪星晚报" in point for point in analysis.environment_points)
    assert any("电网设备" in clue or "特高压" in clue for clue in analysis.theme_clues)
    assert sum("AI / 算力 / 数据中心电力" in clue for clue in analysis.theme_clues) == 1
    assert not any(clue == "新闻线索指向：AI" for clue in analysis.theme_clues)
    assert not any(clue == "新闻线索指向：人工智能" for clue in analysis.theme_clues)
    assert any("后续将披露" in point for point in analysis.watch_points)
    assert any("真实行情" in question for question in analysis.deep_dive_questions)
    assert any("流动性" in item.reason or "风险偏好" in item.reason for item in analysis.market_events)
    assert any("电网投资" in item.reason or "订单" in item.reason for item in analysis.industry_catalysts)

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
    assert not any(
        "圆桌访谈" in item.title or "食品检验" in item.title
        for match in analysis.holding_related_news
        for item in match.matches
    )
    assert not any(
        "*ST帅电" in item.title
        for match in analysis.holding_related_news
        for item in match.matches
    )
    assert "普通消费电子新品体验活动举行" not in [item.title for item in analysis.market_events]
    excluded_titles = {
        item.title
        for item in (
            analysis.market_events
            + analysis.industry_catalysts
            + tuple(item for point in analysis.holding_related_news for item in point.matches)
        )
    }
    assert "AI 圆桌访谈热议 IPO 和大模型 ROI" not in excluded_titles
    assert "普通食品检验结果公布，消费维权案例持续发酵" not in excluded_titles
    assert "NanmiCoder/MediaCrawler" not in excluded_titles
    assert not any("9点1氪" in title or "氪星晚报" in title for title in excluded_titles)
    assert not any("：直接指向" in point or "：包含" in point for point in analysis.watch_points)

    print("offline market news smoke passed")


if __name__ == "__main__":
    main()
