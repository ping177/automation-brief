from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import main as main_module  # noqa: E402
from main import (  # noqa: E402
    NewsItem,
    ReportConfig,
    build_digest_sections,
    extract_url_date,
    fetch_feed,
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
    matched_keywords: dict[str, list[str]] | None = None,
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
        matched_keywords=matched_keywords or {},
    )


def all_links(sections) -> list[str]:
    return [item.link for item in sections.core + sections.market + sections.watch + sections.quick_scan]


def section_for_link(sections, link: str) -> str:
    if link in [item.link for item in sections.core]:
        return "core_event"
    if link in [item.link for item in sections.market]:
        return "market_signal"
    if link in [item.link for item in sections.watch]:
        return "watch_item"
    if link in [item.link for item in sections.quick_scan]:
        return "quick_scan"
    return "drop"


def main() -> None:
    config = ReportConfig(report_type="digest", max_quick_scan_items=20)
    today = datetime.now(timezone.utc).date()
    fresh_chinanews_world_url = f"https://www.chinanews.com.cn/gj/{today:%Y/%m-%d}/10638363.shtml"
    fresh_chinanews_china_url = f"https://www.chinanews.com.cn/gn/{today:%Y/%m-%d}/10638357.shtml"

    assert extract_url_date("http://www.news.cn/fortune/2022-12/14/c_1129206426.htm").isoformat() == "2022-12-14"
    assert extract_url_date(fresh_chinanews_world_url) == today
    assert stale_by_url_date("http://www.news.cn/fortune/2022-12/14/c_1129206426.htm", config)
    assert stale_by_url_date("http://www.xinhuanet.com/finance/2022-12/10/c_1129197454.htm", config)
    assert stale_by_url_date("http://www.news.cn/tech/2020-10/26/c_1126656082.htm", config)
    assert not stale_by_url_date(fresh_chinanews_world_url, config)
    assert not stale_by_url_date(fresh_chinanews_china_url, config)

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
        make_item(
            "Visa to secure payments for shoppers on ChatGPT in OpenAI partnership",
            summary=(
                "Visa and OpenAI are working on ChatGPT payments for AI agents, "
                "merchant checkout and agentic commerce."
            ),
            role="ai_industry",
            link="https://example.com/visa-openai-chatgpt-payments",
            source="AP News",
            feed_name="TechCrunch AI",
        ),
        make_item(
            "首届中国（宁夏）—中亚经贸对接交流会促农贸、新能源合作",
            summary="多方参加交流会，推动农贸与新能源领域合作。",
            role="global_tech_business",
            link="https://example.com/ningxia-trade-meeting",
            source="CNBC Technology",
            feed_name="CNBC Technology",
        ),
        make_item(
            "AI benchmark controversy raises questions about small model performance",
            summary="Researchers debate whether a small model benchmark reflects real product performance.",
            role="ai_industry",
            link="https://example.com/ai-benchmark-small-model",
            source="TechCrunch AI",
            feed_name="TechCrunch AI",
        ),
        make_item(
            "Why Weibo’s tiny VibeThinker-3B has the AI world arguing over benchmarks again",
            summary="The small model performance debate focuses on benchmarks and technical comparisons.",
            role="ai_industry",
            link="https://example.com/weibo-vibethinker-benchmark",
            source="VentureBeat AI",
            feed_name="VentureBeat AI",
        ),
        make_item(
            "Anthropic's Fable shutdown is a big moment for open-source AI",
            summary="The discussion focuses on open-source AI, model access and product direction.",
            role="ai_industry",
            link="https://example.com/anthropic-fable-shutdown",
            source="TechCrunch AI",
            feed_name="TechCrunch AI",
        ),
        make_item(
            "近千人参加人工智能产业论坛",
            summary="论坛已经举行，多位嘉宾参加并讨论行业趋势。",
            role="ai_industry",
            link="https://example.com/ai-forum-attendance",
            source="OpenAI News",
            feed_name="OpenAI News",
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
    assert "https://example.com/visa-openai-chatgpt-payments" in links
    assert "https://example.com/visa-openai-chatgpt-payments" in market_links
    assert "https://example.com/ningxia-trade-meeting" not in market_links
    assert "https://example.com/ningxia-trade-meeting" in quick_links
    ningxia_trade_item = next(item for item in sections.quick_scan if item.link == "https://example.com/ningxia-trade-meeting")
    assert "支付基础设施" not in market_impact(ningxia_trade_item)
    assert "AI 商业化" not in market_impact(ningxia_trade_item)
    assert "https://example.com/ai-benchmark-small-model" not in market_links
    assert "https://example.com/ai-benchmark-small-model" in quick_links
    assert "https://example.com/weibo-vibethinker-benchmark" not in market_links
    assert "https://example.com/weibo-vibethinker-benchmark" in quick_links
    assert "https://example.com/anthropic-fable-shutdown" not in market_links
    assert "https://example.com/anthropic-fable-shutdown" in quick_links
    assert "https://example.com/ai-forum-attendance" not in watch_links
    spacex_item = next(item for item in sections.market if item.link == "https://example.com/spacex-valuation")
    visa_openai_item = next(
        item for item in sections.market if item.link == "https://example.com/visa-openai-chatgpt-payments"
    )
    assert "资本市场" in market_impact(spacex_item) or "估值" in market_impact(spacex_item)
    assert "支付基础设施" in market_impact(visa_openai_item) or "AI 商业化" in market_impact(visa_openai_item)
    assert "AI 产业关注度" not in market_impact(spacex_item)
    assert "政策预期和相关板块发酵" not in one_line_theme(sections)
    assert "新能源、电力设备、风电" not in one_line_theme(sections)
    assert "科技成长方向是否延续" not in one_line_theme(sections)
    assert one_line_theme(sections) == "市场信号较多但主线分散，建议重点观察股价、估值、业绩与政策相关线索。"
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

    real_title_sections = build_digest_sections(
        [
            make_item(
                "Why Weibo’s tiny VibeThinker-3B has the AI world arguing over benchmarks again",
                summary=(
                    "VibeThinker-3B created debate over small model performance, "
                    "benchmarks and technical comparisons. A prior paragraph mentions "
                    "that another AI company raised funding."
                ),
                role="ai_industry",
                link="https://example.com/real-weibo-vibethinker",
                source="VentureBeat AI",
                feed_name="VentureBeat AI",
                matched_keywords={"AI方向": ["AI", "OpenAI", "agent"]},
            ),
            make_item(
                "Z.ai’s open-weights GLM-5.2 beats GPT-5.5 on multiple long-horizon coding benchmarks for 1/6th the cost",
                summary=(
                    "The article compares open-weights model performance on long-horizon coding benchmarks. "
                    "Background context mentions valuation and revenue in the AI sector."
                ),
                role="ai_industry",
                link="https://example.com/real-zai-glm-benchmark",
                source="VentureBeat AI",
                feed_name="VentureBeat AI",
                matched_keywords={"AI方向": ["AI", "OpenAI", "agent"]},
            ),
            make_item(
                "Databricks sales growth tops 80%, but margin are shrinking from swarm of AI agents",
                summary="Databricks sales growth, revenue and margin pressure are tied to AI agent usage.",
                role="ai_industry",
                link="https://example.com/real-databricks-sales-margin",
                source="CNBC Technology",
                feed_name="CNBC Technology",
                matched_keywords={"AI方向": ["AI", "agent"]},
            ),
            make_item(
                "SpaceX rises 4% to leapfrog Amazon in market cap, closes short of Microsoft",
                summary="SpaceX stock movement and market cap put its valuation close to Microsoft.",
                role="global_tech_business",
                link="https://example.com/real-spacex-market-cap",
                source="CNBC Technology",
                feed_name="CNBC Technology",
                matched_keywords={"财经股票": ["stock", "market"]},
            ),
            make_item(
                "SpaceX to acquire Cursor for $60B in stock, days after blockbuster IPO",
                summary="The proposed stock deal would value Cursor at a billion-scale amount after its IPO.",
                role="ai_industry",
                link="https://example.com/real-spacex-cursor-acquisition",
                source="TechCrunch AI",
                feed_name="TechCrunch AI",
                matched_keywords={"AI方向": ["AI", "agent"]},
            ),
            make_item(
                "Visa to secure payments for shoppers on ChatGPT in OpenAI partnership",
                summary="Visa and OpenAI are working on ChatGPT payments, merchant checkout and agentic commerce.",
                role="ai_industry",
                link="https://example.com/real-visa-openai-payments",
                source="AP News",
                feed_name="TechCrunch AI",
                matched_keywords={"AI方向": ["OpenAI", "ChatGPT", "payment"]},
            ),
        ],
        ReportConfig(report_type="digest", max_market_signals=10, max_quick_scan_items=10),
    )
    assert section_for_link(real_title_sections, "https://example.com/real-weibo-vibethinker") == "quick_scan"
    assert section_for_link(real_title_sections, "https://example.com/real-zai-glm-benchmark") == "quick_scan"
    assert section_for_link(real_title_sections, "https://example.com/real-databricks-sales-margin") == "market_signal"
    assert section_for_link(real_title_sections, "https://example.com/real-spacex-market-cap") == "market_signal"
    assert section_for_link(real_title_sections, "https://example.com/real-spacex-cursor-acquisition") == "market_signal"
    assert section_for_link(real_title_sections, "https://example.com/real-visa-openai-payments") == "market_signal"
    real_market_items = {item.link: item for item in real_title_sections.market}
    databricks_reason = market_impact(real_market_items["https://example.com/real-databricks-sales-margin"])
    spacex_reason = market_impact(real_market_items["https://example.com/real-spacex-market-cap"])
    spacex_cursor_reason = market_impact(real_market_items["https://example.com/real-spacex-cursor-acquisition"])
    assert "营收" in databricks_reason or "利润率" in databricks_reason or "sales" in databricks_reason
    assert "估值" in spacex_reason or "market cap" in spacex_reason or "资本市场" in spacex_reason
    assert "并购" in spacex_cursor_reason or "交易规模" in spacex_cursor_reason or "IPO" in spacex_cursor_reason
    assert "支付基础设施" not in databricks_reason
    assert "支付基础设施" not in spacex_reason
    assert "支付基础设施" not in spacex_cursor_reason

    dedup_sections = build_digest_sections(
        [
            make_item(
                "SpaceX to acquire Cursor for $60B in stock, days after blockbuster IPO",
                summary="The proposed stock deal would value Cursor at a billion-scale amount after its IPO.",
                role="ai_industry",
                link="https://example.com/dedup-spacex-cursor-techcrunch",
                source="TechCrunch AI",
                feed_name="TechCrunch AI",
                matched_keywords={"AI方向": ["AI", "agent"]},
            ),
            make_item(
                "SpaceX to acquire the AI coding startup Cursor for $60 billion",
                summary="The acquisition would be structured as a stock deal.",
                role="global_tech_business",
                link="https://example.com/dedup-spacex-cursor-cnbc",
                source="CNBC Technology",
                feed_name="CNBC Technology",
                matched_keywords={"AI方向": ["AI", "Cursor"]},
            ),
            make_item(
                "中国人民银行宣布将出台六项政策措施",
                summary="人民银行将出台政策措施，涉及货币政策、融资支持和市场预期。",
                role="market",
                link="https://example.com/dedup-pboc-policy-measures",
                source="中国新闻网-财经新闻",
                feed_name="中国新闻网-财经新闻",
                matched_keywords={"财经股票": ["人民银行", "政策"]},
            ),
        ],
        ReportConfig(report_type="digest", max_market_signals=2, max_quick_scan_items=10),
    )
    dedup_market_links = [item.link for item in dedup_sections.market]
    dedup_quick_links = [item.link for item in dedup_sections.quick_scan]
    assert sum(1 for link in dedup_market_links if "dedup-spacex-cursor" in link) == 1
    assert sum(1 for link in dedup_market_links + dedup_quick_links if "dedup-spacex-cursor" in link) == 1
    assert "https://example.com/dedup-pboc-policy-measures" in dedup_market_links

    final_dedup_sections = build_digest_sections(
        [
            make_item(
                "SpaceX to acquire Cursor for $60B in stock, days after blockbuster IPO",
                summary="The proposed stock deal would value Cursor at a billion-scale amount after its IPO.",
                role="ai_industry",
                link="https://example.com/final-spacex-cursor-techcrunch",
                source="TechCrunch AI",
                feed_name="TechCrunch AI",
                matched_keywords={"AI方向": ["AI", "agent"]},
            ),
            make_item(
                "SpaceX to acquire the AI coding startup Cursor for $60 billion",
                summary="The acquisition would be structured as a stock deal.",
                role="global_tech_business",
                link="https://example.com/final-spacex-cursor-cnbc",
                source="CNBC Technology",
                feed_name="CNBC Technology",
                matched_keywords={"AI方向": ["AI", "Cursor"]},
            ),
            make_item(
                "SpaceX rises 4% to leapfrog Amazon in market cap, closes short of Microsoft",
                summary="SpaceX stock movement and market cap put its valuation close to Microsoft.",
                role="global_tech_business",
                link="https://example.com/final-spacex-market-cap",
                source="CNBC Technology",
                feed_name="CNBC Technology",
                matched_keywords={"财经股票": ["stock", "market"]},
            ),
        ],
        ReportConfig(report_type="digest", max_market_signals=2, max_quick_scan_items=10),
    )
    final_displayed_links = all_links(final_dedup_sections)
    assert section_for_link(final_dedup_sections, "https://example.com/final-spacex-cursor-techcrunch") == "market_signal"
    assert sum(1 for link in final_displayed_links if "final-spacex-cursor" in link) == 1
    assert section_for_link(final_dedup_sections, "https://example.com/final-spacex-market-cap") == "market_signal"

    v0411_sections = build_digest_sections(
        [
            make_item(
                "美官员：特朗普已亲自签署美伊谅解备忘录，协议现已生效",
                summary="美伊冲突相关协议已经生效，影响战争与地区局势。",
                role="breaking_news",
                link="https://example.com/trump-iran-memo-effective",
                source="中国新闻网-国际新闻",
                feed_name="中国新闻网-国际新闻",
            ),
            make_item(
                "美官员称特朗普亲自签署美伊谅解备忘录",
                summary="美伊冲突相关协议由特朗普签署，涉及战争与地区局势。",
                role="breaking_news",
                link="https://example.com/trump-iran-memo-signed",
                source="中国新闻网-国际新闻",
                feed_name="中国新闻网-国际新闻",
            ),
            make_item(
                "NEA’s Tiffany Luck on AI IPOs, personal agents, and the ROI reckoning",
                summary="A podcast conversation about AI IPO trends, personal agents and enterprise ROI.",
                role="ai_industry",
                link="https://techcrunch.com/podcast/nea-tiffany-luck-ai-ipos-roi/",
                source="TechCrunch AI",
                feed_name="TechCrunch AI",
                matched_keywords={"AI方向": ["AI", "agent"]},
            ),
            make_item(
                "NEA’s Tiffany Luck says enterprises are still figuring out their AI ROI",
                summary="A video interview discussing how enterprises think about AI ROI.",
                role="ai_industry",
                link="https://techcrunch.com/video/nea-tiffany-luck-enterprise-ai-roi/",
                source="TechCrunch AI",
                feed_name="TechCrunch AI",
                matched_keywords={"AI方向": ["AI", "agent"]},
            ),
            make_item(
                "World model maker Odyssey nabs $1.45B valuation backed by Amazon and other big names",
                summary="Odyssey reached a new valuation with strategic backing from Amazon.",
                role="ai_industry",
                link="https://example.com/odyssey-valuation-amazon",
                source="TechCrunch AI",
                feed_name="TechCrunch AI",
                matched_keywords={"AI方向": ["AI", "Amazon"]},
            ),
        ],
        ReportConfig(report_type="digest", max_core_events=5, max_market_signals=5, max_quick_scan_items=10),
    )
    v0411_core_titles = [item.title for item in v0411_sections.core]
    v0411_market_links = [item.link for item in v0411_sections.market]
    v0411_displayed_links = all_links(v0411_sections)
    assert len([title for title in v0411_core_titles if "特朗普" in title and "谅解备忘录" in title]) == 1
    assert "美官员：特朗普已亲自签署美伊谅解备忘录，协议现已生效" in v0411_core_titles
    assert not any("nea-tiffany-luck" in link for link in v0411_market_links)
    assert sum(1 for link in v0411_displayed_links if "nea-tiffany-luck" in link) == 1
    assert "https://example.com/odyssey-valuation-amazon" in v0411_market_links
    odyssey_item = next(item for item in v0411_sections.market if item.link == "https://example.com/odyssey-valuation-amazon")
    odyssey_reason = market_impact(odyssey_item)
    assert "估值" in odyssey_reason or "融资" in odyssey_reason or "战略背书" in odyssey_reason

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

    original_urlopen = main_module.urllib.request.urlopen
    captured_timeouts: list[int] = []

    class FakeResponse:
        headers = {"Content-Type": "application/rss+xml; charset=utf-8"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self) -> bytes:
            published = format_datetime(datetime.now(timezone.utc), usegmt=True)
            return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Tech</title>
    <item>
      <title>OpenAI launches enterprise payments integration</title>
      <link>https://example.com/cnbc-source-name</link>
      <description>OpenAI and Visa launch enterprise payments integration for merchants.</description>
      <pubDate>{published}</pubDate>
    </item>
  </channel>
</rss>
""".encode()

        def geturl(self) -> str:
            return "https://www.cnbc.com/id/19854910/device/rss/rss.html"

    try:
        def fake_urlopen(request, timeout):
            captured_timeouts.append(timeout)
            return FakeResponse()

        main_module.urllib.request.urlopen = fake_urlopen
        fetched = fetch_feed(
            {
                "name": "CNBC Technology",
                "url": "https://www.cnbc.com/id/19854910/device/rss/rss.html",
                "mode": "all",
                "role": "global_tech_business",
            },
            {},
            datetime.now(timezone.utc).date(),
            ReportConfig(report_type="digest"),
        )
        assert fetched[0].source == "CNBC Technology"
        assert captured_timeouts == [15]
    finally:
        main_module.urllib.request.urlopen = original_urlopen

    print("Visa/OpenAI sample section: market_signal")
    print(
        "Real title samples: weibo=quick_scan, zai=quick_scan, "
        "databricks=market_signal, spacex_market_cap=market_signal, spacex_cursor=market_signal"
    )
    print("Market dedup sample: spacex_cursor=1, pboc_policy=market_signal")
    print("v0.4.1.1 samples: trump_iran=core_deduped, nea=quick_scan_deduped, odyssey=market_signal")
    print(
        "False-positive samples: trade_meeting=quick_scan, "
        "weibo_benchmark=quick_scan, anthropic_fable=quick_scan, forum_attendance=not_watch"
    )
    print("Source name sample: CNBC Technology")
    print("offline digest smoke passed")


if __name__ == "__main__":
    main()
