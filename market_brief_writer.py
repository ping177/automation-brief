from __future__ import annotations

from datetime import datetime
from pathlib import Path

from market_analysis import MarketBriefContext


MARKET_BRIEF_SECTIONS = (
    "## 一、昨日市场环境",
    "## 二、市场主线",
    "### 1日强势",
    "### 5日持续强势",
    "### 20日趋势主线",
    "## 三、产业催化",
    "## 四、我的持仓观察",
    "## 五、明日观察信号",
    "## 六、纪律提醒",
    "## 七、建议交给 AI 投研小组深挖",
    "## 数据与限制说明",
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


def render_market_brief_markdown(context: MarketBriefContext, generated_at: datetime | None = None) -> str:
    generated_time = generated_at or datetime.now().astimezone()
    snapshot = context.snapshot
    lines = [
        f"# 每日市场投研晨报｜{snapshot.data_date.isoformat()}",
        "",
        f"Generated at: {generated_time.isoformat(timespec='seconds')}",
        f"Data date: {snapshot.data_date.isoformat()}",
        "Mode: market_brief",
        "",
        "## 一、昨日市场环境",
        "",
        markdown_escape(snapshot.environment_note),
        "",
        "## 二、市场主线",
        "",
        "### 1日强势",
        "",
    ]
    append_bullets(lines, snapshot.strong_1d)
    lines.extend(["### 5日持续强势", ""])
    append_bullets(lines, snapshot.strong_5d)
    lines.extend(["### 20日趋势主线", ""])
    append_bullets(lines, snapshot.trend_20d)

    lines.extend(["## 三、产业催化", ""])
    append_bullets(lines, snapshot.catalysts)

    lines.extend(["## 四、我的持仓观察", ""])
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
                    "",
                ]
            )
    else:
        lines.extend(["暂无持仓配置，请创建 config/holdings.json。", ""])

    lines.extend(["## 五、明日观察信号", ""])
    append_bullets(lines, snapshot.watch_signals)

    lines.extend(
        [
            "## 六、纪律提醒",
            "",
            "- 当前仅做市场观察，不构成投资建议。",
            "- 纪律提醒：连续加速后不要情绪追涨。",
            "- 纪律提醒：弱势股不要盲目补仓摊平。",
            "",
            "## 七、建议交给 AI 投研小组深挖",
            "",
            "- 持仓所属行业是否正在接近或偏离市场主线。",
            "- 产业催化是否能被后续真实行情和成交结构验证。",
            "- 风险事件是否会改变板块预期或资金偏好。",
            "",
            "## 数据与限制说明",
            "",
            f"- {DISCLAIMER}",
            "- v0.5-alpha 只使用离线 mock/sample 数据，不接真实行情。",
            "- 当前不计算相对强弱，不输出交易动作。",
        ]
    )
    if context.holdings_config.used_example:
        lines.append("- 当前使用 config/holdings.example.json 示例持仓；真实关注列表请创建 config/holdings.json。")
    elif context.holdings_config.source_path:
        lines.append(f"- 持仓观察来自 {context.holdings_config.source_path.name}。")
    else:
        lines.append("- 未发现持仓配置文件。")
    lines.append("")
    return "\n".join(lines)


def write_market_brief_markdown(context: MarketBriefContext, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"market-brief-{context.snapshot.data_date.isoformat()}.md"
    output_file.write_text(render_market_brief_markdown(context), encoding="utf-8")
    return output_file
