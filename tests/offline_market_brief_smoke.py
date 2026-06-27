from __future__ import annotations

from datetime import date
from dataclasses import dataclass
from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from holdings import load_holdings  # noqa: E402
from market_analysis import build_market_brief_context  # noqa: E402
from market_brief_writer import (  # noqa: E402
    DIRECT_TRADING_ADVICE_TERMS,
    MARKET_BRIEF_SECTIONS,
    render_market_brief_markdown,
)
from market_data import load_offline_market_snapshot  # noqa: E402


@dataclass(frozen=True)
class ArticleFixture:
    title: str
    summary: str
    source: str
    feed_role: str
    link: str
    matched_keywords: dict[str, list[str]]


def article(title: str, summary: str, link: str) -> ArticleFixture:
    return ArticleFixture(
        title=title,
        summary=summary,
        source="离线测试源",
        feed_role="market",
        link=link,
        matched_keywords={},
    )


def write_holdings_fixture(path: Path, code: str, name: str) -> None:
    path.write_text(
        """{
  "holdings": [
    {
      "code": "%s",
      "name": "%s",
      "market": "A股",
      "sector": "电力设备",
      "watch_tags": ["特高压", "电网设备"],
      "notes": "观察是否跟随所属板块和市场主线"
    }
  ]
}
"""
        % (code, name),
        encoding="utf-8",
    )


def main() -> None:
    report_date = date(2026, 6, 26)
    fixture_dir = Path(tempfile.mkdtemp(prefix="automation-brief-market-"))
    fixture_dir.mkdir(parents=True, exist_ok=True)
    first_fixture = fixture_dir / "holdings-first.json"
    second_fixture = fixture_dir / "holdings-second.json"

    write_holdings_fixture(first_fixture, "601179", "中国西电")
    write_holdings_fixture(second_fixture, "002202", "金风科技")

    first_holdings = load_holdings(first_fixture, example_path=first_fixture)
    second_holdings = load_holdings(second_fixture, example_path=second_fixture)
    first_articles = [
        article(
            "国家电网启动特高压设备招标，中国西电所在电力设备链条受关注",
            "招标订单和电网投资节奏可能成为产业催化。",
            "https://example.com/grid-tender-first",
        ),
        article(
            "AI 圆桌访谈热议 IPO 和大模型 ROI",
            "泛圆桌和访谈内容没有具体融资、订单、监管或行情变量。",
            "https://example.com/ai-roundtable-first",
        ),
        article(
            "普通食品检验结果公布，消费维权案例持续发酵",
            "普通消费维权和食品检验不应进入市场投研核心段落。",
            "https://example.com/consumer-rights-first",
        ),
        article(
            "9点1氪｜苹果涨价引山姆代购潮；DeepSeek大规模招聘；黄金再度跌破4000美元",
            "综合快讯合集不应整体进入核心事件。",
            "https://example.com/kr-roundup-first",
        ),
    ]
    second_articles = [
        article(
            "海外风电项目披露新订单，金风科技所属方向关注度上升",
            "风电订单和海上风电政策节奏需要继续验证。",
            "https://example.com/wind-order-second",
        )
    ]
    first_context = build_market_brief_context(
        load_offline_market_snapshot(report_date),
        first_holdings,
        first_articles,
    )
    second_context = build_market_brief_context(
        load_offline_market_snapshot(report_date),
        second_holdings,
        second_articles,
    )
    first_markdown = render_market_brief_markdown(first_context)
    second_markdown = render_market_brief_markdown(second_context)

    assert first_markdown.startswith("# 每日市场投研晨报｜2026-06-26")
    assert "Mode: market_brief" in first_markdown
    for section in MARKET_BRIEF_SECTIONS:
        assert section in first_markdown

    assert "### 601179 中国西电" in first_markdown
    assert "国家电网启动特高压设备招标" in first_markdown
    assert "类型：产业催化" in first_markdown
    assert "相关度：" in first_markdown
    assert "观察理由：离线测试源 报道的" in first_markdown
    assert "产业主题和可验证催化" in first_markdown
    assert "AI 圆桌访谈热议 IPO 和大模型 ROI" not in first_markdown
    assert "普通食品检验结果公布" not in first_markdown
    assert "9点1氪" not in first_markdown
    industry_section = first_markdown.split("## 三、产业催化与主线线索", 1)[1].split("## 四、我的持仓新闻观察", 1)[0]
    assert "新闻线索指向：" not in industry_section or "暂无可展示内容" not in industry_section
    assert "### 002202 金风科技" not in first_markdown
    assert "### 002202 金风科技" in second_markdown
    assert "海外风电项目披露新订单" in second_markdown
    assert "### 601179 中国西电" not in second_markdown
    assert first_markdown != second_markdown
    assert "### 1日强势" not in first_markdown
    assert "### 5日持续强势" not in first_markdown
    assert "### 20日趋势主线" not in first_markdown
    assert first_markdown.count("未接真实行情") <= 2

    for term in DIRECT_TRADING_ADVICE_TERMS:
        assert term not in first_markdown
        assert term not in second_markdown

    assert "本报告仅用于个人市场观察和复盘，不构成投资建议。" in first_markdown

    business_files = [
        PROJECT_ROOT / "main.py",
        PROJECT_ROOT / "holdings.py",
        PROJECT_ROOT / "market_brief_writer.py",
        PROJECT_ROOT / "market_data.py",
        PROJECT_ROOT / "market_analysis.py",
        PROJECT_ROOT / "market_news.py",
    ]
    forbidden_terms = ("601179", "002202", "中国西电", "金风科技")
    for path in business_files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            assert term not in text, f"{term} should not be hard-coded in {path.name}"

    print("offline market brief smoke passed")


if __name__ == "__main__":
    main()
