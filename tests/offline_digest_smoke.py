from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from main import (  # noqa: E402
    NewsItem,
    ReportConfig,
    build_digest_sections,
    extract_url_date,
    market_impact,
    one_line_theme,
    quick_scan_type,
    stale_by_url_date,
)


def make_item(
    title: str,
    summary: str = "",
    role: str = "tech_industry",
    link: str = "https://example.com",
    source: str | None = None,
    feed_name: str | None = None,
) -> NewsItem:
    source_name = source or f"测试源-{link.rsplit('/', 1)[-1]}"
    return NewsItem(
        title=title,
        source=source_name,
        feed_name=feed_name or source_name,
        feed_role=role,
        published="now",
        published_at=datetime.now(timezone.utc),
        link=link,
        summary=summary,
        matched_keywords={},
    )


def all_links(sections) -> list[str]:
    return [item.link for item in sections.core + sections.market + sections.watch + sections.quick_scan]


def main() -> None:
    config = ReportConfig(report_type="digest", max_quick_scan_items=20)
    assert extract_url_date("http://www.news.cn/fortune/2022-12/14/c_1129206426.htm").isoformat() == "2022-12-14"
    assert extract_url_date("https://www.chinanews.com.cn/gj/2026/06-11/10638363.shtml").isoformat() == "2026-06-11"
    assert stale_by_url_date("http://www.news.cn/fortune/2022-12/14/c_1129206426.htm", config)
    assert stale_by_url_date("http://www.xinhuanet.com/finance/2022-12/10/c_1129197454.htm", config)
    assert stale_by_url_date("http://www.news.cn/tech/2020-10/26/c_1126656082.htm", config)
    assert not stale_by_url_date("https://www.chinanews.com.cn/gj/2026/06-11/10638363.shtml", config)
    assert not stale_by_url_date("https://www.chinanews.com.cn/gn/2026/06-11/10638357.shtml", config)

    items = [
        make_item(
            "48元的良心日游，揭露了国产单机的最大困境 | 游戏风向标",
            link="https://example.com/game",
        ),
        make_item(
            "腾讯超级 QQ 秀及小窝业务调整，8 月 11 日起无法使用",
            link="https://example.com/qq-show",
        ),
        make_item(
            "美联储今晚公布利率决议",
            role="market",
            link="https://example.com/fed",
        ),
        make_item(
            "某公司将发布新品手机",
            link="https://example.com/phone",
        ),
        make_item(
            "近500名海峡两岸暨港澳青年在香港畅谈融合发展",
            role="breaking_news",
            link="https://example.com/youth",
        ),
        make_item(
            "一名中国籍女性在东京遭抢劫受伤",
            role="breaking_news",
            link="https://example.com/robbery",
        ),
        make_item(
            "中国运动员樊振东当选德甲赛季最佳球员",
            role="breaking_news",
            link="https://example.com/fanzhendong",
        ),
        make_item(
            "我国成功发射通信技术试验卫星二十五号",
            role="breaking_news",
            link="https://example.com/satellite",
        ),
        make_item(
            "黑龙江鹤岗：衔接资金巧当“酵母” 以资本活水激活乡村振兴动能",
            role="breaking_news",
            link="https://example.com/hegang",
        ),
        make_item(
            "虚增利润超1195万！起底科创板“流感第一股”ST南新财务造假",
            role="market",
            link="https://example.com/st-nanxin",
        ),
        make_item(
            "商务部：全面零关税举措助力中非共同发展",
            role="breaking_news",
            link="https://example.com/tariff",
        ),
        make_item(
            "ChinaJoy前沿展区展示多款互动娱乐产品",
            role="tech_industry",
            link="https://example.com/chinajoy",
        ),
        make_item(
            "水上飞行器完成首飞，探索低空出行新场景",
            role="tech_industry",
            link="https://example.com/watercraft",
        ),
        make_item(
            "最前线｜坦途科技全球首款消费级水上飞行器首飞，拓展水陆空场景出行生态",
            role="tech_industry",
            link="https://example.com/tantu-watercraft",
        ),
        make_item(
            "广州汽车产业实现整车芯片100%设计国产化",
            role="tech_industry",
            link="https://example.com/guangzhou-chip",
        ),
        make_item(
            "“构建科技大宣传格局 讲好中国科技创新故事”座谈会召开",
            role="breaking_news",
            link="https://example.com/science-meeting",
        ),
        make_item(
            "GitHub Trending Python Daily: useful-ai-tool",
            role="ai_tools",
            link="https://example.com/github-trending",
        ),
        make_item(
            "人工智能成为推动中国外贸增长新引擎",
            role="market",
            link="https://example.com/ai-trade",
        ),
        make_item(
            "时代锐评丨阿里出招，钉钉换帅：AI将重构大厂的组织进化",
            role="market",
            link="https://example.com/dingtalk-ai",
        ),
        make_item(
            "SpaceX估值冲上1.75万亿美元，是泡沫还是真金？AI模型深度拆解",
            role="market",
            link="https://example.com/spacex-valuation",
        ),
    ]

    sections = build_digest_sections(items, config)
    links = all_links(sections)
    market_links = [item.link for item in sections.market]
    watch_links = [item.link for item in sections.watch]
    quick_links = [item.link for item in sections.quick_scan]

    assert "https://example.com/game" not in links
    assert "https://example.com/qq-show" not in watch_links
    assert "https://example.com/fed" in watch_links
    assert "https://example.com/fed" not in market_links
    assert "https://example.com/phone" not in watch_links
    assert "https://example.com/youth" not in [item.link for item in sections.core]
    assert "https://example.com/robbery" not in [item.link for item in sections.core]
    assert "https://example.com/robbery" not in quick_links
    assert "https://example.com/fanzhendong" not in quick_links
    assert "https://example.com/satellite" in [item.link for item in sections.core]
    assert "https://example.com/hegang" not in market_links
    assert "https://example.com/st-nanxin" in market_links
    assert "https://example.com/tariff" not in watch_links
    assert "https://example.com/chinajoy" not in market_links
    assert "https://example.com/chinajoy" in quick_links
    assert "https://example.com/watercraft" not in market_links
    assert "https://example.com/watercraft" in quick_links
    assert "https://example.com/tantu-watercraft" not in market_links
    assert "https://example.com/tantu-watercraft" in quick_links
    assert "https://example.com/tariff" in quick_links
    tariff_item = next(item for item in sections.quick_scan if item.link == "https://example.com/tariff")
    assert quick_scan_type(tariff_item) == "政策背景"
    assert "https://example.com/guangzhou-chip" not in watch_links
    assert "https://example.com/guangzhou-chip" in quick_links
    assert "https://example.com/science-meeting" not in watch_links
    assert "https://example.com/github-trending" not in links
    assert "https://example.com/ai-trade" not in market_links
    assert "https://example.com/ai-trade" in quick_links
    assert "https://example.com/dingtalk-ai" not in market_links
    assert "https://example.com/dingtalk-ai" in quick_links
    assert "https://example.com/spacex-valuation" in market_links
    spacex_item = next(item for item in sections.market if item.link == "https://example.com/spacex-valuation")
    assert "资本市场" in market_impact(spacex_item) or "估值" in market_impact(spacex_item)
    assert "AI 产业关注度" not in market_impact(spacex_item)
    assert "政策预期和相关板块发酵" not in one_line_theme(sections)
    assert "新能源、电力设备、风电" not in one_line_theme(sections)
    assert "科技成长方向是否延续" not in one_line_theme(sections)
    assert one_line_theme(sections) == "主线信号仍不够集中，建议重点扫读政策、市场与科技产业动态的后续变化。"
    assert len(links) == len(set(links))

    same_source_items = [
        make_item(
            f"36氪科技产业观察 {index}",
            role="tech_industry",
            link=f"https://example.com/36kr-{index}",
            source="36氪",
            feed_name="36氪",
        )
        for index in range(5)
    ]
    same_source_sections = build_digest_sections(
        same_source_items,
        ReportConfig(report_type="digest", max_quick_scan_items=10, max_quick_scan_items_per_source=3),
    )
    assert sum(1 for item in same_source_sections.quick_scan if item.source == "36氪") == 3

    quick_only_sections = build_digest_sections(
        [
            make_item(
                "科技公司展示多款 AI 工具更新",
                role="tech_industry",
                link="https://example.com/quick-ai-1",
            ),
            make_item(
                "半导体产业链举行新品交流活动",
                role="tech_industry",
                link="https://example.com/quick-ai-2",
            ),
        ],
        ReportConfig(report_type="digest", max_quick_scan_items=10),
    )
    assert "科技成长方向是否延续" not in one_line_theme(quick_only_sections)

    same_market_source_items = [
        make_item(
            f"A股上市公司财报业绩跟踪 {index}",
            role="market",
            link=f"https://example.com/stock-market-{index}",
            source="股票股市资讯",
            feed_name="股票股市资讯",
        )
        for index in range(5)
    ]
    same_market_source_sections = build_digest_sections(
        same_market_source_items,
        ReportConfig(report_type="digest", max_market_signals=10, max_market_signals_per_source=3),
    )
    assert sum(1 for item in same_market_source_sections.market if item.source == "股票股市资讯") == 3

    core_noise_sections = build_digest_sections(
        [
            make_item(
                "北京海淀通报“鹅腿阿姨卖鸭腿”：正核查，将依法依规处置",
                role="breaking_news",
                link="https://example.com/goose-duck",
            ),
            make_item(
                "某地通报摊贩经营问题",
                role="breaking_news",
                link="https://example.com/vendor-local",
            ),
            make_item(
                "证监会对某上市公司财务造假立案调查",
                role="market",
                link="https://example.com/csrc-fraud",
            ),
            make_item(
                "国家市场监管总局发布食品安全专项整治政策",
                role="breaking_news",
                link="https://example.com/food-safety-policy",
            ),
        ],
        ReportConfig(report_type="digest", max_quick_scan_items=10),
    )
    core_noise_core_links = [item.link for item in core_noise_sections.core]
    core_noise_market_links = [item.link for item in core_noise_sections.market]
    assert "https://example.com/goose-duck" not in core_noise_core_links
    assert "https://example.com/vendor-local" not in core_noise_core_links
    assert "https://example.com/csrc-fraud" in core_noise_market_links
    assert "https://example.com/food-safety-policy" in core_noise_core_links
    assert "鹅腿阿姨" not in one_line_theme(core_noise_sections)

    print("offline digest smoke passed")


if __name__ == "__main__":
    main()
