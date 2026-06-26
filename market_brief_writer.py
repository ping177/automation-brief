from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from market_analysis import MarketBriefContext
from market_news import NewsInsight


MARKET_BRIEF_SECTIONS = (
    "## 一、市场环境观察",
    "## 二、重要市场事件",
    "## 三、产业催化与主线线索",
    "## 四、我的持仓新闻观察",
    "## 五、风险与反证",
    "## 六、今日观察清单",
    "## 七、建议交给 AI 投研小组深挖",
    "## 八、数据与限制说明",
)

DIRECT_TRADING_ADVICE_TERMS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "清仓",
    "满仓",
    "梭哈",
    "抄底",
    "追涨买入",
)

DISCLAIMER = "本报告仅用于个人市场观察和复盘，不构成投资建议。"


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|")


def append_bullets(lines: list[str], items: tuple[str, ...]) -> None:
    if not items:
        lines.extend(["- 暂无可展示内容。", ""])
        return
    for item in items:
        lines.append(f"- {markdown_escape(item)}")
    lines.append("")


def append_insights(lines: list[str], items: Iterable[NewsInsight]) -> None:
    listed = tuple(items)
    if not listed:
        lines.extend(["- 暂无可展示内容。", ""])
        return
    for item in listed:
        lines.append(f"- {markdown_escape(item.title)}")
        lines.append(f"  - 来源：{markdown_escape(item.source)}")
        if item.reason:
            lines.append(f"  - 观察理由：{markdown_escape(item.reason)}")
        if item.link:
            lines.append(f"  - 链接：{item.link}")
    lines.append("")


def render_holding_observations(context: MarketBriefContext) -> list[str]:
    lines: list[str] = []
    news = context.news_analysis
    if context.holding_observations:
        for observation in context.holding_observations:
            tags = "、".join(observation.watch_tags) if observation.watch_tags else "暂无标签"
            lines.extend(
                [
                    f"### {markdown_escape(observation.title)}",
                    "",
                    f"- 市场/行业：{markdown_escape(observation.sector)}",
                    f"- 关注标签：{markdown_escape(tags)}",
                    f"- 观察备注：{markdown_escape(observation.notes or '暂无备注。')}",
                    f"- 当前状态：{markdown_escape(observation.observation)}",
                ]
            )
            related = next(
                (
                    match
                    for match in news.holding_related_news
                    if match.holding_title == observation.title
                ),
                None,
            )
            if related:
                lines.append("- 相关新闻：")
                for item in related.matches:
                    lines.append(f"  - {markdown_escape(item.title)}（{markdown_escape(item.source)}）")
                    if item.link:
                        lines.append(f"    - 链接：{item.link}")
            else:
                lines.append("- 相关新闻：暂无从 RSS 候选中匹配到的明确线索。")
            lines.append("")
        return lines

    if news.holding_related_news:
        for match in news.holding_related_news:
            lines.extend([f"### {markdown_escape(match.holding_title)}", ""])
            append_insights(lines, match.matches)
        return lines

    return ["暂无持仓配置，请创建 config/holdings.json。", ""]


def render_market_brief_markdown(context: MarketBriefContext, generated_at: datetime | None = None) -> str:
    generated_time = generated_at or datetime.now().astimezone()
    snapshot = context.snapshot
    news = context.news_analysis
    risk_points = tuple(
        point.replace("风险/反证：", "", 1)
        for point in news.environment_points
        if point.startswith("风险/反证：")
    )

    lines = [
        f"# 每日市场投研晨报｜{snapshot.data_date.isoformat()}",
        "",
        f"Generated at: {generated_time.isoformat(timespec='seconds')}",
        f"Data date: {snapshot.data_date.isoformat()}",
        "Mode: market_brief",
        "",
        "## 一、市场环境观察",
        "",
        markdown_escape(snapshot.environment_note),
        "",
    ]
    append_bullets(lines, news.environment_points)

    lines.extend(["## 二、重要市场事件", ""])
    append_insights(lines, news.market_events)

    lines.extend(["## 三、产业催化与主线线索", ""])
    if news.theme_clues:
        append_bullets(lines, news.theme_clues)
    append_insights(lines, news.industry_catalysts)

    lines.extend(["## 四、我的持仓新闻观察", ""])
    lines.extend(render_holding_observations(context))

    lines.extend(["## 五、风险与反证", ""])
    if risk_points:
        append_bullets(lines, risk_points)
    else:
        lines.extend(["- 暂未从 RSS 候选中提取到明确风险或反证线索。", ""])

    lines.extend(["## 六、今日观察清单", ""])
    append_bullets(lines, news.watch_points or snapshot.watch_signals)

    lines.extend(["## 七、建议交给 AI 投研小组深挖", ""])
    append_bullets(
        lines,
        news.deep_dive_questions
        or (
            "持仓所属行业是否正在接近或偏离新闻线索中的市场主线。",
            "产业催化是否能被后续真实行情和成交结构验证。",
            "风险事件是否会改变板块预期或资金偏好。",
        ),
    )

    lines.extend(
        [
            "## 八、数据与限制说明",
            "",
            f"- {DISCLAIMER}",
            "- 当前仍未接真实行情，不计算相对强弱、板块强度或个股强弱。",
            "- 输出仅基于 RSS 候选新闻、离线行情占位和本地 holdings 配置做观察。",
            "- 当前不输出交易动作。",
        ]
    )
    if context.holdings_config.used_example:
        lines.append("- 当前使用 config/holdings.example.json 示例持仓；真实关注列表请创建 config/holdings.json。")
    elif context.holdings_config.source_path:
        lines.append(f"- 持仓观察来自 {context.holdings_config.source_path.name}。")
    else:
        lines.append("- 未发现持仓配置文件。")
    if context.feed_failures:
        lines.append("- RSS 抓取失败源：")
        for source, reason in context.feed_failures:
            lines.append(f"  - {markdown_escape(source)}：{markdown_escape(reason)}")
    lines.append("")
    return "\n".join(lines)


def write_market_brief_markdown(context: MarketBriefContext, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"market-brief-{context.snapshot.data_date.isoformat()}.md"
    output_file.write_text(render_market_brief_markdown(context), encoding="utf-8")
    return output_file
