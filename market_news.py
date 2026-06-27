from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from holdings import HoldingsConfig


@dataclass(frozen=True)
class NewsInsight:
    title: str
    source: str
    link: str
    reason: str
    relevance_score: int = 0
    news_type: str = "普通商业新闻"


@dataclass(frozen=True)
class HoldingNewsMatch:
    holding_title: str
    matches: tuple[NewsInsight, ...]


@dataclass(frozen=True)
class MarketNewsAnalysis:
    market_events: tuple[NewsInsight, ...]
    industry_catalysts: tuple[NewsInsight, ...]
    environment_points: tuple[str, ...]
    theme_clues: tuple[str, ...]
    watch_points: tuple[str, ...]
    deep_dive_questions: tuple[str, ...]
    holding_related_news: tuple[HoldingNewsMatch, ...]


NEWS_TYPE_MACRO_RISK = "宏观风险"
NEWS_TYPE_POLICY_REGULATION = "政策监管"
NEWS_TYPE_INDUSTRY_CATALYST = "产业催化"
NEWS_TYPE_COMPANY_FINANCING = "公司融资 / IPO"
NEWS_TYPE_BUSINESS = "普通商业新闻"
NEWS_TYPE_WEAK = "弱相关内容"

MARKET_EVENT_TERMS = (
    "A股",
    "港股",
    "美股",
    "债市",
    "汇率",
    "利率",
    "央行",
    "美联储",
    "财政部",
    "证监会",
    "交易所",
    "关税",
    "制裁",
    "财报",
    "业绩",
    "上市公司",
    "IPO",
    "并购",
    "重组",
    "回购",
    "估值",
    "融资",
)
MACRO_RISK_TERMS = (
    "A股",
    "港股",
    "美股",
    "债市",
    "汇率",
    "利率",
    "央行",
    "美联储",
    "财政部",
    "流动性",
    "成交量",
    "风险偏好",
)
POLICY_REGULATION_TERMS = (
    "证监会",
    "交易所",
    "监管",
    "处罚",
    "监管函",
    "政策文件",
    "行政处罚",
    "立案调查",
    "问询函",
    "通报批评",
)
COMPANY_FINANCING_TERMS = (
    "融资",
    "IPO",
    "上市",
    "估值",
    "并购",
    "重组",
    "回购",
    "财报",
    "业绩",
    "营收",
    "利润",
)
INDUSTRY_CATALYST_TERMS = (
    "订单",
    "中标",
    "招标",
    "政策",
    "补贴",
    "出口管制",
    "商业化",
    "支付",
    "AI",
    "人工智能",
    "算力",
    "芯片",
    "半导体",
    "机器人",
    "新能源",
    "风电",
    "光伏",
    "储能",
    "电网",
    "特高压",
)
HIGH_VALUE_INDUSTRY_THEMES = (
    "AI",
    "人工智能",
    "大模型",
    "算力",
    "数据中心",
    "数据中心电力",
    "电力",
    "芯片",
    "半导体",
    "机器人",
    "新能源",
    "风电",
    "光伏",
    "储能",
    "电网",
    "电网设备",
    "特高压",
)
CONCRETE_CATALYST_TERMS = (
    "订单",
    "中标",
    "招标",
    "投资",
    "建设",
    "扩产",
    "商业化",
    "支付",
    "出口管制",
    "补贴",
)
RISK_TERMS = (
    "风险",
    "下滑",
    "亏损",
    "处罚",
    "调查",
    "监管",
    "退市",
    "违约",
    "制裁",
    "关税",
    "出口管制",
)
WATCH_TERMS = (
    "今日",
    "明日",
    "今晚",
    "本周",
    "将公布",
    "将召开",
    "将披露",
    "将生效",
    "到期",
    "议息",
    "财报发布",
)
BROAD_HOLDING_WATCH_TAGS = (
    "出海",
    "央企",
    "国企",
    "新能源",
    "科技",
    "AI",
)
WEAK_RELATED_PATTERNS = (
    "圆桌",
    "访谈",
    "专访",
    "对话",
    "podcast",
    "播客",
    "视频",
    "活动",
    "论坛",
    "峰会",
    "体验",
    "消费维权",
    "维权",
    "食品检验",
    "食品抽检",
    "普通消费",
    "ai_tools",
)
ROUNDUP_PATTERNS = (
    "9点1氪",
    "8点1氪",
    "氪星晚报",
    "晚报",
    "早报",
    "日报",
    "周报",
    "一周",
)
NEGATED_SIGNAL_PATTERNS = (
    "没有具体",
    "缺少明确",
    "不涉及",
)
HOLDING_LOW_PRECISION_SECTORS = (
    "电力设备",
    "风电设备",
    "新能源",
    "科技",
    "AI",
)
THEME_ALIASES = (
    (
        "AI / 算力 / 数据中心电力",
        ("AI", "人工智能", "大模型", "算力", "数据中心", "数据中心电力"),
    ),
    ("电网设备 / 特高压", ("电网设备", "特高压", "电网")),
    ("风电", ("风电", "海上风电")),
    ("半导体 / 芯片", ("半导体", "芯片")),
    ("新能源 / 储能", ("新能源", "储能", "光伏")),
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _article_text(article: Any) -> str:
    matched_keywords = getattr(article, "matched_keywords", {}) or {}
    keyword_text = ""
    if isinstance(matched_keywords, dict):
        keyword_text = " ".join(
            str(keyword)
            for keywords in matched_keywords.values()
            for keyword in (keywords if isinstance(keywords, list) else [])
        )
    return " ".join(
        (
            _clean(getattr(article, "title", "")),
            _clean(getattr(article, "summary", "")),
            _clean(getattr(article, "source", "")),
            _clean(getattr(article, "feed_role", "")),
            keyword_text,
        )
    )


def _article_title(article: Any) -> str:
    return _clean(getattr(article, "title", ""))


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _insight(
    article: Any,
    reason: str,
    relevance_score: int = 0,
    news_type: str = "普通商业新闻",
) -> NewsInsight:
    return NewsInsight(
        title=_clean(getattr(article, "title", "Untitled")) or "Untitled",
        source=_clean(getattr(article, "source", "")) or _clean(getattr(article, "feed_name", "")) or "Unknown",
        link=_clean(getattr(article, "link", "")),
        reason=reason,
        relevance_score=relevance_score,
        news_type=news_type,
    )


def _dedupe_insights(items: list[NewsInsight], limit: int) -> tuple[NewsInsight, ...]:
    seen: set[tuple[str, str]] = set()
    deduped: list[NewsInsight] = []
    for item in sorted(items, key=lambda candidate: candidate.relevance_score, reverse=True):
        key = (item.link, item.title)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return tuple(deduped)


def _matched_terms(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    lowered = text.lower()
    return tuple(term for term in terms if term.lower() in lowered)


def _reason_for_type(
    title: str,
    source: str,
    news_type: str,
    macro_terms: tuple[str, ...],
    policy_terms: tuple[str, ...],
    company_terms: tuple[str, ...],
    industry_terms: tuple[str, ...],
    catalyst_terms: tuple[str, ...],
    risk_terms: tuple[str, ...],
) -> str:
    if news_type == NEWS_TYPE_MACRO_RISK:
        variables = "、".join((macro_terms + risk_terms)[:4])
        return f"{source} 报道的「{title}」包含 {variables} 等宏观或资产价格变量，重点看它是否继续影响风险偏好、汇率利率预期或跨市场联动。"
    if news_type == NEWS_TYPE_POLICY_REGULATION:
        variables = "、".join((policy_terms + risk_terms)[:4])
        return f"{source} 报道的「{title}」出现 {variables} 等正式政策或监管线索，可能改变相关板块合规风险和资金定价。"
    if news_type == NEWS_TYPE_INDUSTRY_CATALYST:
        variables = "、".join((catalyst_terms + industry_terms)[:4])
        return f"{source} 报道的「{title}」同时具备 {variables} 等产业主题和可验证催化，后续看订单、投资节奏或产业链扩散。"
    if news_type == NEWS_TYPE_COMPANY_FINANCING:
        variables = "、".join(company_terms[:4])
        return f"{source} 报道的「{title}」属于 {variables} 等公司资本事件，适合观察可比公司估值、上市后交易热度或融资环境。"
    if news_type == NEWS_TYPE_WEAK:
        return "内容形态或主题偏泛，缺少明确行情、政策、订单、监管或公司资本事件支撑。"
    variables = "、".join((industry_terms + company_terms + macro_terms)[:4])
    return f"「{title}」包含 {variables or '商业动态'} 线索，但缺少更强市场验证变量，作为普通商业新闻低优先级观察。"


def _score_article(article: Any) -> tuple[int, str, str, bool]:
    title = _article_title(article)
    source = _clean(getattr(article, "source", "")) or _clean(getattr(article, "feed_name", "")) or "Unknown"
    text = _article_text(article)
    title_macro_terms = _matched_terms(title, MACRO_RISK_TERMS)
    title_policy_terms = _matched_terms(title, POLICY_REGULATION_TERMS)
    title_company_terms = _matched_terms(title, COMPANY_FINANCING_TERMS)
    title_industry_terms = _matched_terms(title, HIGH_VALUE_INDUSTRY_THEMES)
    title_catalyst_terms = _matched_terms(title, CONCRETE_CATALYST_TERMS)
    macro_terms = _matched_terms(text, MACRO_RISK_TERMS)
    policy_terms = _matched_terms(text, POLICY_REGULATION_TERMS)
    company_terms = _matched_terms(text, COMPANY_FINANCING_TERMS)
    industry_terms = _matched_terms(text, HIGH_VALUE_INDUSTRY_THEMES)
    catalyst_terms = _matched_terms(text, CONCRETE_CATALYST_TERMS)
    risk_terms = _matched_terms(text, RISK_TERMS)
    weak_terms = _matched_terms(text, WEAK_RELATED_PATTERNS)

    score = 0
    if macro_terms:
        score += 30 + min(len(macro_terms) * 4, 16)
    if policy_terms:
        score += 34 + min(len(policy_terms) * 4, 16)
    if company_terms:
        score += 34 + min(len(company_terms) * 4, 16)
    if industry_terms:
        score += 14 + min(len(industry_terms) * 3, 15)
    if catalyst_terms:
        score += 24 + min(len(catalyst_terms) * 4, 16)
    if risk_terms:
        score += 10

    if title_company_terms:
        score += 18
    if title_macro_terms:
        score += 10
    if title_policy_terms:
        score += 18
    if title_catalyst_terms and title_industry_terms:
        score += 14

    is_roundup = _contains_any(title, ROUNDUP_PATTERNS)
    has_hard_signal = bool(policy_terms or company_terms or title_macro_terms or title_policy_terms)
    has_negated_signal = _contains_any(text, NEGATED_SIGNAL_PATTERNS)
    weak_related = is_roundup or (bool(weak_terms) and (not has_hard_signal or has_negated_signal))
    if is_roundup:
        score -= 140
    if weak_terms:
        score -= 90 if weak_related else 18

    if weak_related:
        news_type = NEWS_TYPE_WEAK
    elif title_policy_terms:
        news_type = NEWS_TYPE_POLICY_REGULATION
    elif title_company_terms or company_terms:
        news_type = NEWS_TYPE_COMPANY_FINANCING
    elif policy_terms:
        news_type = NEWS_TYPE_POLICY_REGULATION
    elif title_macro_terms or (macro_terms and not company_terms):
        news_type = NEWS_TYPE_MACRO_RISK
    elif (title_catalyst_terms or catalyst_terms) and (title_industry_terms or industry_terms):
        news_type = NEWS_TYPE_INDUSTRY_CATALYST
    elif score < 40:
        news_type = NEWS_TYPE_WEAK
    else:
        news_type = NEWS_TYPE_BUSINESS

    score = max(score, 0)
    return (
        score,
        news_type,
        _reason_for_type(
            title=title,
            source=source,
            news_type=news_type,
            macro_terms=macro_terms,
            policy_terms=policy_terms,
            company_terms=company_terms,
            industry_terms=industry_terms,
            catalyst_terms=catalyst_terms,
            risk_terms=risk_terms,
        ),
        weak_related,
    )


def _holding_match_terms(holding: Any) -> tuple[str, ...]:
    terms = [
        _clean(getattr(holding, "code", "")),
        _clean(getattr(holding, "name", "")),
        _clean(getattr(holding, "sector", "")),
    ]
    terms.extend(
        tag
        for tag in (_clean(item) for item in getattr(holding, "watch_tags", ()) or ())
        if tag and tag not in BROAD_HOLDING_WATCH_TAGS
    )
    return tuple(term for term in terms if term)


def _holding_precise_terms(holding: Any) -> tuple[str, ...]:
    return tuple(
        term
        for term in _holding_match_terms(holding)
        if len(term) >= 2 and term not in HOLDING_LOW_PRECISION_SECTORS
    )


def _theme_key(text: str) -> str | None:
    for label, terms in THEME_ALIASES:
        if _contains_any(text, terms):
            return label
    matched = _matched_terms(text, HIGH_VALUE_INDUSTRY_THEMES)
    return matched[0] if matched else None


def _is_investable_candidate(score: int, news_type: str, weak_related: bool) -> bool:
    return not weak_related and news_type != "弱相关内容" and score >= 45


def _is_excluded_article(article: Any) -> bool:
    title = _clean(getattr(article, "title", ""))
    source = _clean(getattr(article, "source", "")) or _clean(getattr(article, "feed_name", ""))
    role = _clean(getattr(article, "feed_role", ""))
    if role == "ai_tools" or "github trending" in source.lower():
        return True
    title_hard_terms = (
        "IPO",
        "融资",
        "估值",
        "中标",
        "招标",
        "监管函",
        "财报",
        "业绩",
        "并购",
        "重组",
        "回购",
        "订单",
    )
    return _contains_any(title, WEAK_RELATED_PATTERNS) and not _contains_any(title, title_hard_terms)


def _risk_variable(item: NewsInsight) -> str:
    if item.news_type == NEWS_TYPE_POLICY_REGULATION:
        return "监管变量：后续是否出现正式处罚、问询范围扩大或同类公司合规风险重估。"
    if item.news_type == NEWS_TYPE_COMPANY_FINANCING:
        return "资本市场变量：IPO / 融资 / 估值新闻后续交易热度是否退潮，并影响同类公司预期。"
    if item.news_type == NEWS_TYPE_MACRO_RISK:
        return "宏观变量：价格、汇率、利率或流动性信号是否继续压制风险偏好。"
    return "反证变量：主题新闻是否缺少订单、公告或成交结构验证。"


def _watch_variable(item: NewsInsight) -> str:
    if item.news_type == NEWS_TYPE_COMPANY_FINANCING:
        return f"观察 {item.title} 的上市后成交热度、估值变化和可比公司反馈。"
    if item.news_type == NEWS_TYPE_POLICY_REGULATION:
        return f"观察 {item.title} 是否出现正式文件、处罚范围或交易所后续问询。"
    if item.news_type == NEWS_TYPE_INDUSTRY_CATALYST:
        return f"观察 {item.title} 是否落到订单、招标、中标、扩产或商业化数据。"
    if item.news_type == NEWS_TYPE_MACRO_RISK:
        return f"观察 {item.title} 对汇率、利率、黄金、股指或成交量的延续影响。"
    return f"观察 {item.title} 是否被公告、成交结构或后续新闻验证。"


def analyze_market_news(
    articles: list[Any],
    holdings_config: HoldingsConfig,
    max_items: int = 5,
) -> MarketNewsAnalysis:
    event_candidates: list[NewsInsight] = []
    catalyst_candidates: list[NewsInsight] = []
    risk_candidates: list[NewsInsight] = []
    watch_candidates: list[NewsInsight] = []
    theme_scores: dict[str, int] = {}

    for article in articles:
        if _is_excluded_article(article):
            continue
        text = _article_text(article)
        score, news_type, reason, weak_related = _score_article(article)
        if not _is_investable_candidate(score, news_type, weak_related):
            continue

        if news_type in {NEWS_TYPE_MACRO_RISK, NEWS_TYPE_POLICY_REGULATION, NEWS_TYPE_COMPANY_FINANCING}:
            event_candidates.append(_insight(article, reason, score, news_type))
        if news_type == NEWS_TYPE_INDUSTRY_CATALYST and score >= 55:
            catalyst = _insight(article, reason, score, news_type)
            catalyst_candidates.append(catalyst)
            theme = _theme_key(text)
            if theme:
                theme_scores[theme] = max(theme_scores.get(theme, 0), score)
        if _contains_any(text, RISK_TERMS) and score >= 50:
            risk_candidates.append(_insight(article, reason, score, news_type))
        if _contains_any(text, WATCH_TERMS) and score >= 45:
            watch_candidates.append(_insight(article, reason, score, news_type))

    holding_matches: list[HoldingNewsMatch] = []
    for holding in holdings_config.holdings:
        terms = _holding_match_terms(holding)
        precise_terms = _holding_precise_terms(holding)
        matches: list[NewsInsight] = []
        for article in articles:
            if _is_excluded_article(article):
                continue
            text = _article_text(article)
            score, news_type, reason, weak_related = _score_article(article)
            if not _is_investable_candidate(score, news_type, weak_related):
                continue
            for term in terms:
                if term not in precise_terms:
                    continue
                if term.lower() not in text.lower():
                    continue
                match_reason = f"{reason} 命中关注对象高精度线索：{term}。"
                matches.append(_insight(article, match_reason, score, news_type))
        deduped_matches = _dedupe_insights(matches, max_items)
        if deduped_matches:
            holding_matches.append(
                HoldingNewsMatch(
                    holding_title=f"{holding.code} {holding.name}",
                    matches=deduped_matches,
                )
            )

    market_events = _dedupe_insights(event_candidates, max_items)
    industry_catalysts = _dedupe_insights(catalyst_candidates, max_items)
    risk_points = _dedupe_insights(risk_candidates, max_items)
    watch_points = _dedupe_insights(watch_candidates, max_items)

    environment_points = (f"RSS 候选新闻 {len(articles)} 条；以下只基于新闻线索做观察。",)
    if risk_points:
        environment_points += tuple(f"风险/反证：{_risk_variable(item)}" for item in risk_points[:2])

    theme_clues = tuple(
        f"新闻线索指向：{theme}"
        for theme, _score in sorted(theme_scores.items(), key=lambda item: item[1], reverse=True)[
            :max_items
        ]
    )
    deep_dive_questions = tuple(
        f"{item.title}：后续是否能被真实行情、成交结构或公司公告验证？"
        for item in (market_events + industry_catalysts)[:max_items]
    )

    return MarketNewsAnalysis(
        market_events=market_events,
        industry_catalysts=industry_catalysts,
        environment_points=environment_points,
        theme_clues=theme_clues,
        watch_points=tuple(_watch_variable(item) for item in watch_points),
        deep_dive_questions=deep_dive_questions,
        holding_related_news=tuple(holding_matches),
    )
