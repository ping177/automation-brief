from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from market_analysis import MarketBriefContext
from market_news import NewsInsight


MARKET_BRIEF_SECTIONS = (
    "## 一、市场温度",
    "## 二、今日主线",
    "## 三、我的持仓观察",
    "## 四、重要新闻与验证",
    "## 五、风险与反证",
    "## 六、今日继续观察",
)

DIRECT_TRADING_ADVICE_TERMS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "止损",
    "止盈",
    "清仓",
    "满仓",
    "梭哈",
    "抄底",
    "追涨买入",
)

DISCLAIMER = "本报告仅用于个人市场观察和复盘，不构成投资建议。"


def sanitize_report_text(value: str) -> str:
    cleaned = value
    for term in DIRECT_TRADING_ADVICE_TERMS:
        cleaned = cleaned.replace(term, "具体交易动作")
    return cleaned


def markdown_escape(value: str) -> str:
    return sanitize_report_text(value).replace("|", "\\|")


def append_bullets(lines: list[str], items: tuple[str, ...]) -> None:
    if not items:
        lines.extend(["- 暂无可展示内容。", ""])
        return
    for item in items:
        lines.append(f"- {markdown_escape(item)}")
    lines.append("")


def append_insights(lines: list[str], items: Iterable[NewsInsight], empty_text: str | None = "- 暂无可展示内容。") -> None:
    listed = tuple(items)
    if not listed:
        if empty_text:
            lines.extend([empty_text, ""])
        return
    for item in listed:
        lines.append(f"- {markdown_escape(item.title)}")
        lines.append(f"  - 来源：{markdown_escape(item.source)}")
        lines.append(f"  - 类型：{markdown_escape(item.news_type)}")
        lines.append(f"  - 相关度：{item.relevance_score}")
        if item.reason:
            lines.append(f"  - 观察理由：{markdown_escape(item.reason)}")
        if item.link:
            lines.append(f"  - 链接：{item.link}")
    lines.append("")


def format_pct_change(value: float | None) -> str:
    if value is None:
        return "涨跌幅 数据暂不可用"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.2f}%"


def format_amount(value: float | None) -> str:
    if value is None:
        return "成交额 数据暂不可用"
    return f"成交额 {value / 100_000_000:.1f} 亿"


def format_quote_meta(source: str, as_of: str) -> str:
    parts = []
    if source:
        parts.append(f"来源 {source}")
    if as_of:
        parts.append(f"截至 {as_of}")
    return f"，{'，'.join(parts)}" if parts else ""


def has_amount_data(context: MarketBriefContext) -> bool:
    return any(quote.amount is not None for quote in context.snapshot.indexes + context.snapshot.holdings)


def market_temperature_note(context: MarketBriefContext) -> str:
    pct_values = [quote.pct_change for quote in context.snapshot.indexes if quote.pct_change is not None]
    if not pct_values:
        return "主要指数行情数据不足，本次不判断市场强弱。"

    positive_count = sum(1 for value in pct_values if value > 0)
    negative_count = sum(1 for value in pct_values if value < 0)
    average_pct = sum(pct_values) / len(pct_values)
    if positive_count and negative_count:
        return "主要指数涨跌分化，新闻主线需要继续用后续行情和板块表现验证。"
    if average_pct >= 0.6:
        return "主要指数整体偏强，但仍需观察后续持续性。"
    if average_pct <= -0.6:
        return "主要指数整体偏弱，风险偏好仍需等待后续数据确认。"
    return "主要指数整体偏震荡，暂不把单日波动解读为趋势。"


def average_index_pct_change(context: MarketBriefContext) -> float | None:
    pct_values = [quote.pct_change for quote in context.snapshot.indexes if quote.pct_change is not None]
    if not pct_values:
        return None
    return sum(pct_values) / len(pct_values)


def relative_to_indexes_text(context: MarketBriefContext, pct_change: float | None) -> str:
    average_pct = average_index_pct_change(context)
    if pct_change is None or average_pct is None:
        return "相对观察：主要指数或个股涨跌数据不足。"
    diff = pct_change - average_pct
    if average_pct > 0.5 and pct_change < -2.0:
        return "相对观察：逆势走弱。"
    if average_pct < -0.5 and pct_change > 2.0:
        return "相对观察：逆势走强。"
    if diff >= 1.5:
        return "相对观察：明显强于主要指数均值。"
    if diff >= 0.5:
        return "相对观察：小幅强于主要指数均值。"
    if diff <= -1.5:
        return "相对观察：明显弱于主要指数均值。"
    if diff <= -0.5:
        return "相对观察：小幅弱于主要指数均值。"
    return "相对观察：接近主要指数均值。"


def holding_anomaly_text(context: MarketBriefContext, pct_change: float | None) -> str:
    relative_text = relative_to_indexes_text(context, pct_change)
    if relative_text == "相对观察：逆势走弱。":
        return "异常提示：主要指数整体偏强，但该持仓明显逆势走弱；RSS 候选新闻暂未解释该波动，后续需观察是否来自板块、公司消息或资金行为。"
    if relative_text == "相对观察：逆势走强。":
        return "异常提示：主要指数整体偏弱，但该持仓明显逆势走强；RSS 候选新闻暂未解释该波动，后续需观察是否来自板块、公司消息或资金行为。"
    return ""


def market_led_observation(context: MarketBriefContext) -> str:
    science_quote = next(
        (
            quote
            for quote in context.snapshot.indexes
            if quote.code == "000688" or "科创50" in quote.name
        ),
        None,
    )
    if science_quote is None or science_quote.pct_change is None:
        return ""
    other_values = [
        quote.pct_change
        for quote in context.snapshot.indexes
        if quote is not science_quote and quote.pct_change is not None
    ]
    if not other_values:
        return ""
    other_average = sum(other_values) / len(other_values)
    if science_quote.pct_change - other_average >= 2.0 and science_quote.pct_change >= 1.5:
        return (
            "行情层面观察：科创50明显强于其他主要指数，指数层面显示科创 / 硬科技方向风险偏好较强；"
            "该判断仅来自宽基指数表现，仍需后续新闻和板块数据验证。"
        )
    return ""


def market_watch_signals(context: MarketBriefContext) -> tuple[str, ...]:
    fallback = (
        "观察主要指数涨跌是否继续支持市场风险偏好；成交额字段稳定前，不判断放量 / 缩量。",
        "观察持仓所属板块是否跟随市场主线。",
        "观察外部风险偏好、汇率利率和政策变量是否变化。",
    )
    if not context.snapshot.watch_signals:
        return fallback
    if has_amount_data(context):
        return context.snapshot.watch_signals
    adjusted: list[str] = []
    for signal in context.snapshot.watch_signals:
        if "成交额" in signal:
            adjusted.append(fallback[0])
        else:
            adjusted.append(signal)
    return tuple(dict.fromkeys(adjusted))


def append_market_temperature(lines: list[str], context: MarketBriefContext) -> None:
    snapshot = context.snapshot
    lines.append(f"- 报告日期：{snapshot.data_date.isoformat()}")
    lines.append(f"- 行情交易日：{snapshot.market_data_date.isoformat()}")
    if snapshot.indexes:
        for quote in snapshot.indexes:
            lines.append(
                f"- {markdown_escape(quote.name)}（{markdown_escape(quote.code)}）："
                f"{format_pct_change(quote.pct_change)}，{format_amount(quote.amount)}"
                f"{markdown_escape(format_quote_meta(quote.source, quote.as_of))}"
            )
    else:
        lines.append("- 指数行情：数据暂不可用。")
    lines.append(f"- 市场判断：{markdown_escape(market_temperature_note(context))}")
    for failure in snapshot.failures:
        if failure.scope == "amount":
            lines.append("- 成交额口径：当前轻量行情源未稳定返回成交额字段，本次不判断放量 / 缩量。")
        else:
            lines.append(
                f"- {markdown_escape(failure.scope)}：行情数据源未返回该字段或请求失败，本次不做该项判断。"
            )
    lines.append("")


def append_today_theme(lines: list[str], context: MarketBriefContext) -> None:
    news = context.news_analysis
    if news.theme_clues:
        append_bullets(lines, news.theme_clues)
    elif news.industry_catalysts:
        lines.extend(["- RSS 候选新闻中暂未提取到足够明确的产业主线。", ""])
    else:
        lines.extend(["- RSS 候选新闻中暂未提取到足够明确的产业主线。", ""])

    market_observation = market_led_observation(context)
    if market_observation:
        lines.append(f"- {markdown_escape(market_observation)}")
        lines.append("")

    if context.snapshot.indexes:
        lines.append(f"- 行情验证：{markdown_escape(market_temperature_note(context))}")
    else:
        lines.append("- 行情验证：指数行情数据暂不可用，本次仅保留新闻驱动观察。")
    lines.append("")


def render_holding_observations(context: MarketBriefContext) -> list[str]:
    lines: list[str] = []
    news = context.news_analysis
    if context.holding_observations:
        for observation in context.holding_observations:
            tags = "、".join(observation.watch_tags) if observation.watch_tags else "暂无标签"
            quote = observation.quote
            lines.extend(
                [
                    f"### {markdown_escape(observation.title)}",
                    "",
                    f"- 行业/板块：{markdown_escape(observation.sector or '数据暂不可用')}",
                    (
                        f"- 行情：{format_pct_change(quote.pct_change)}，{format_amount(quote.amount)}"
                        f"{markdown_escape(format_quote_meta(quote.source, quote.as_of))}"
                        if quote
                        else "- 行情：数据暂不可用"
                    ),
                    (
                        f"- {markdown_escape(relative_to_indexes_text(context, quote.pct_change))}"
                        if quote
                        else "- 相对观察：行情数据暂不可用。"
                    ),
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
                    lines.append(f"    - 类型：{markdown_escape(item.news_type)}")
                    lines.append(f"    - 相关度：{item.relevance_score}")
                    if item.reason:
                        lines.append(f"    - 观察理由：{markdown_escape(item.reason)}")
                    if item.link:
                        lines.append(f"    - 链接：{item.link}")
            else:
                lines.append("- 相关新闻：暂无从 RSS 候选中匹配到的明确线索。")
                anomaly = holding_anomaly_text(context, quote.pct_change if quote else None)
                if anomaly:
                    lines.append(f"- {markdown_escape(anomaly)}")
            lines.append("")
        return lines

    if news.holding_related_news:
        for match in news.holding_related_news:
            lines.extend([f"### {markdown_escape(match.holding_title)}", ""])
            append_insights(lines, match.matches)
        return lines

    return ["- 暂无持仓配置，请创建 config/holdings.json。", ""]


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
        f"Report date: {snapshot.data_date.isoformat()}",
        f"Market data date: {snapshot.market_data_date.isoformat()}",
        "Mode: market_brief",
        "",
        "## 一、市场温度",
        "",
        markdown_escape(snapshot.environment_note),
        "",
    ]
    append_market_temperature(lines, context)

    lines.extend(["## 二、今日主线", ""])
    append_today_theme(lines, context)
    append_insights(lines, news.industry_catalysts, empty_text=None)

    lines.extend(["## 三、我的持仓观察", ""])
    lines.extend(render_holding_observations(context))

    lines.extend(["## 四、重要新闻与验证", ""])
    append_insights(lines, news.market_events)

    lines.extend(["## 五、风险与反证", ""])
    if risk_points:
        append_bullets(lines, risk_points)
    else:
        lines.extend(["- 暂未从 RSS 候选中提取到明确风险或反证线索。", ""])

    lines.extend(["## 六、今日继续观察", ""])
    append_bullets(lines, news.watch_points or market_watch_signals(context))

    lines.extend(["- 数据限制：成交额、行业或行情字段缺失时均标记为数据暂不可用，不做推断。"])
    lines.append(f"- {DISCLAIMER}")
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
