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
    holding_relation: str = ""


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
NEWS_TYPE_COMPANY_OPERATING = "公司经营 / 财报"
NEWS_TYPE_BUSINESS = "普通商业新闻"
NEWS_TYPE_WEAK = "弱相关内容"
HOLDING_RELATION_CLEAR = "明确相关"
HOLDING_RELATION_WEAK = "弱相关变量"

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
    "上交所",
    "深交所",
    "北交所",
    "监管",
    "处罚",
    "监管函",
    "政策文件",
    "行政处罚",
    "立案调查",
    "问询函",
    "通报批评",
    "再融资",
    "定增",
    "储架发行",
    "减持",
    "退市",
    "并购重组",
    "征求意见",
    "文旅部",
    "立案",
    "查处",
    "整治",
    "执法",
    "专项行动",
)
STRONG_POLICY_TERMS = (
    "证监会",
    "交易所",
    "上交所",
    "深交所",
    "北交所",
    "监管部门",
    "征求意见",
    "规则",
    "制度",
    "办法",
    "通知",
    "处罚",
    "问询",
    "问询函",
    "退市",
    "减持",
    "再融资",
    "定增",
    "储架发行",
    "并购重组",
)
A_SHARE_POLICY_EVENT_TERMS = (
    "再融资",
    "定增",
    "储架发行",
)
A_SHARE_POLICY_CONTEXT_TERMS = (
    "证监会",
    "交易所",
    "上交所",
    "深交所",
    "北交所",
    "规则",
    "制度",
    "征求意见",
)
REGULATION_COMBO_TERMS = (
    "部门",
    "规则",
    "制度",
    "办法",
    "通知",
    "处罚",
    "问询",
    "证监会",
    "交易所",
    "上交所",
    "深交所",
    "北交所",
)
COMPANY_FINANCING_TERMS = (
    "IPO",
    "Pre-IPO",
    "pre-ipo",
    "pre ipo",
    "递表",
    "招股书",
    "募资",
    "融资轮",
    "A轮",
    "B轮",
    "C轮",
    "港股IPO",
    "美股IPO",
    "冲刺上市",
    "冲港股IPO",
    "港交所",
    "纳斯达克",
    "估值",
    "融资",
    "并购",
    "重组",
    "回购",
)
COMPANY_OPERATING_TERMS = (
    "财报",
    "业绩",
    "业绩预告",
    "预计",
    "营收",
    "利润",
    "净利润",
    "归母净利润",
    "经营数据",
    "收入",
    "毛利",
    "净利",
    "同比增长",
)
FINANCING_TITLE_ACTION_TERMS = (
    "完成融资", "获融资", "再获融资", "A轮", "B轮", "C轮", "Pre-A", "Pre-B", "Pre-IPO",
    "领投", "跟投", "募资", "IPO", "递表", "招股书", "冲港股", "港股 IPO", "美股上市", "纳斯达克",
)
OPERATING_TITLE_ACTION_TERMS = (
    "业绩预告", "预计净利润", "归母净利润", "净利润同比", "营收同比", "亏损", "扭亏", "财报", "年报", "半年报", "季报",
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
    "创新药",
    "医药",
    "出海",
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
    "创新药",
    "医药",
    "出海",
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
    "重押",
    "出海",
    "海外投资",
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
NEGATED_FINANCING_PATTERNS = (
    "不是 IPO",
    "不是IPO",
    "不属于 IPO",
    "不属于IPO",
    "不是融资",
    "不属于融资",
)
DIRECTORY_OR_RANKING_TERMS = (
    "名册",
    "榜单",
    "名单",
    "百强",
    "机构评选",
    "系列名册",
    "正式发布",
)
CONCRETE_CAPITAL_EVENT_TERMS = (
    "完成融资",
    "获融资",
    "再获融资",
    "领投",
    "A轮",
    "B轮",
    "C轮",
    "IPO",
    "递表",
    "招股书",
    "募资完成",
)
GOVERNMENT_REGULATOR_TERMS = (
    "文旅部",
    "证监会",
    "交易所",
    "上交所",
    "深交所",
    "北交所",
    "监管部门",
    "部委",
    "市场监管总局",
    "发改委",
    "财政部",
    "央行",
    "人民银行",
)
REGULATORY_ACTION_TERMS = (
    "立案",
    "查处",
    "处罚",
    "整治",
    "监管",
    "通报",
    "执法",
    "专项行动",
)
GENERIC_EXCHANGE_POLICY_TERMS = (
    "交易所",
    "上交所",
    "深交所",
    "北交所",
)
HOLDING_LOW_PRECISION_SECTORS = (
    "电力设备",
    "风电设备",
    "风电",
    "海上风电",
    "新能源",
    "科技",
    "AI",
)
THEME_ALIASES = (
    ("AI 应用 / 企业软件", ("AI 应用", "AI应用", "企业软件", "SaaS", "首席销售官")),
    ("电网设备 / 特高压", ("电网设备", "特高压", "电网")),
    ("风电", ("风电", "海上风电")),
    ("半导体 / 芯片", ("半导体", "芯片")),
    ("新能源 / 储能", ("新能源", "储能", "光伏")),
)
COMPUTE_DIRECT_TERMS = (
    "GPU", "芯片", "服务器", "算力中心", "训练集群", "推理集群", "AI 基础设施", "AI基础设施", "算力租赁", "算力基础设施",
)
DATA_CENTER_POWER_DIRECT_TERMS = (
    "数据中心", "IDC", "供配电", "变压器", "UPS", "柴油发电机", "液冷", "电力需求", "数据中心用电",
)
AI_APPLICATION_TERMS = ("AI 应用", "AI应用", "企业软件", "SaaS", "首席销售官")
OVERSEAS_IPO_TERMS = (
    "美股",
    "纳斯达克",
    "港股",
    "pre-ipo",
    "pre ipo",
    "investor meetings",
    "递表美股",
    "秘密递表",
)
A_SHARE_RELATED_IPO_TERMS = (
    "A股",
    "科创",
    "创业板",
    "北交所",
    "硬科技",
    "半导体",
    "芯片",
    "人工智能",
    "算力",
    "新能源",
    "储能",
    "风电",
    "电网",
    "特高压",
    "机器人",
)
MAX_COMPANY_FINANCING_EVENTS = 2
MAX_IMPORTANT_EVENTS_PER_SOURCE = 2
CONFIRMED_THEME_MIN_SCORE = 75
CONFIRMED_THEME_MIN_COUNT = 2


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
    holding_relation: str = "",
) -> NewsInsight:
    return NewsInsight(
        title=_clean(getattr(article, "title", "Untitled")) or "Untitled",
        source=_clean(getattr(article, "source", "")) or _clean(getattr(article, "feed_name", "")) or "Unknown",
        link=_clean(getattr(article, "link", "")),
        reason=reason,
        relevance_score=relevance_score,
        news_type=news_type,
        holding_relation=holding_relation,
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


def _dedupe_text_items(items: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return tuple(deduped)


def _with_reason(item: NewsInsight, reason: str, title: str | None = None, score: int | None = None) -> NewsInsight:
    return NewsInsight(
        title=title or item.title,
        source=item.source,
        link=item.link,
        reason=reason,
        relevance_score=score if score is not None else item.relevance_score,
        news_type=item.news_type,
        holding_relation=item.holding_relation,
    )


def _confirmed_theme_clues(theme_stats: dict[str, dict[str, int]], max_items: int) -> tuple[str, ...]:
    confirmed: list[tuple[str, int]] = []
    for theme, stats in theme_stats.items():
        if stats["count"] >= CONFIRMED_THEME_MIN_COUNT or stats["max_score"] >= CONFIRMED_THEME_MIN_SCORE:
            confirmed.append((theme, stats["max_score"]))
    return tuple(
        f"新闻线索指向：{theme}"
        for theme, _score in sorted(confirmed, key=lambda item: item[1], reverse=True)[:max_items]
    )


def _matched_terms(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    lowered = text.lower()
    matched: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if term.lower() not in lowered or term in seen:
            continue
        seen.add(term)
        matched.append(term)
    return tuple(matched)


def _dedupe_terms(*groups: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for group in groups:
        for term in group:
            if term in seen:
                continue
            seen.add(term)
            deduped.append(term)
    return tuple(deduped)


def _strong_policy_terms(policy_terms: tuple[str, ...]) -> tuple[str, ...]:
    if not policy_terms:
        return ()
    strong = tuple(term for term in policy_terms if term in STRONG_POLICY_TERMS)
    has_regulation_combo = "监管" in policy_terms and any(
        term in policy_terms for term in REGULATION_COMBO_TERMS if term != "监管"
    )
    if has_regulation_combo and "监管" not in strong:
        strong += ("监管",)
    return strong


def _is_a_share_policy_event(text: str) -> bool:
    return _contains_any(text, A_SHARE_POLICY_EVENT_TERMS) and _contains_any(text, A_SHARE_POLICY_CONTEXT_TERMS)


def _is_large_financial_earnings_preview(title: str, text: str) -> bool:
    if not _contains_any(text, ("归母净利润", "净利润", "利润")):
        return False
    if not _contains_any(text, ("预计", "上半年", "超", "亿元")):
        return False
    return _contains_any(title, ("国泰海通", "券商", "证券"))


def _is_directory_or_ranking_without_capital_event(title: str) -> bool:
    return _contains_any(title, DIRECTORY_OR_RANKING_TERMS) and not _contains_any(
        title, CONCRETE_CAPITAL_EVENT_TERMS
    )


def _is_government_regulatory_action(title: str) -> bool:
    return _contains_any(title, GOVERNMENT_REGULATOR_TERMS) and _contains_any(title, REGULATORY_ACTION_TERMS)


def _filter_negated_policy_terms(
    text: str,
    title_terms: tuple[str, ...],
    policy_terms: tuple[str, ...],
) -> tuple[str, ...]:
    if not ("没有" in text or "无" in text):
        return policy_terms
    negated_fragments: list[str] = []
    for marker in ("没有", "无"):
        start = text.find(marker)
        while start != -1:
            end_candidates = [
                text.find(separator, start)
                for separator in ("。", "；", ";", "\n")
                if text.find(separator, start) != -1
            ]
            end = min(end_candidates) if end_candidates else len(text)
            negated_fragments.append(text[start:end])
            start = text.find(marker, start + len(marker))
    return tuple(
        term
        for term in policy_terms
        if term in title_terms or not any(term in fragment for fragment in negated_fragments)
    )


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
        variables = "、".join(_dedupe_terms(macro_terms, risk_terms)[:4])
        return f"{source} 报道的「{title}」包含 {variables} 等宏观或资产价格变量，重点看它是否继续影响风险偏好、汇率利率预期或跨市场联动。"
    if news_type == NEWS_TYPE_POLICY_REGULATION:
        variables = "、".join(_dedupe_terms(policy_terms, risk_terms)[:4])
        return f"{source} 报道的「{title}」出现 {variables} 等正式政策或监管线索，可能改变相关板块合规风险和资金定价。"
    if news_type == NEWS_TYPE_INDUSTRY_CATALYST:
        variables = "、".join(_dedupe_terms(catalyst_terms, industry_terms)[:4])
        return f"{source} 报道的「{title}」同时具备 {variables} 等产业主题和可验证催化，后续看订单、投资节奏或产业链扩散。"
    if news_type == NEWS_TYPE_COMPANY_FINANCING:
        variables = "、".join(company_terms[:4])
        return f"{source} 报道的「{title}」属于 {variables} 等公司资本事件，适合观察可比公司估值、上市后交易热度或融资环境。"
    if news_type == NEWS_TYPE_COMPANY_OPERATING:
        variables = "、".join(company_terms[:4])
        return f"{source} 报道的「{title}」包含 {variables} 等经营或财报变量，适合观察公司基本面变化和同类公司预期。"
    if news_type == NEWS_TYPE_WEAK:
        return "内容形态或主题偏泛，缺少明确行情、政策、订单、监管或公司资本事件支撑。"
    variables = "、".join(_dedupe_terms(industry_terms, company_terms, macro_terms)[:4])
    return f"「{title}」包含 {variables or '商业动态'} 线索，但缺少更强市场验证变量，作为普通商业新闻低优先级观察。"


def _score_article(article: Any) -> tuple[int, str, str, bool]:
    title = _article_title(article)
    source = _clean(getattr(article, "source", "")) or _clean(getattr(article, "feed_name", "")) or "Unknown"
    text = _article_text(article)
    title_macro_terms = _matched_terms(title, MACRO_RISK_TERMS)
    title_policy_terms = _matched_terms(title, POLICY_REGULATION_TERMS)
    title_company_terms = _matched_terms(title, COMPANY_FINANCING_TERMS)
    title_operating_terms = _matched_terms(title, COMPANY_OPERATING_TERMS)
    title_industry_terms = _matched_terms(title, HIGH_VALUE_INDUSTRY_THEMES)
    title_catalyst_terms = _matched_terms(title, CONCRETE_CATALYST_TERMS)
    title_financing_action_terms = _matched_terms(title, FINANCING_TITLE_ACTION_TERMS)
    title_operating_action_terms = _matched_terms(title, OPERATING_TITLE_ACTION_TERMS)
    direct_compute_terms = _matched_terms(text, COMPUTE_DIRECT_TERMS)
    direct_data_center_power_terms = _matched_terms(text, DATA_CENTER_POWER_DIRECT_TERMS)
    is_ai_application = _contains_any(title, AI_APPLICATION_TERMS) and _contains_any(title, ("AI", "人工智能"))
    macro_terms = _matched_terms(text, MACRO_RISK_TERMS)
    policy_terms = _matched_terms(text, POLICY_REGULATION_TERMS)
    company_terms = _matched_terms(text, COMPANY_FINANCING_TERMS)
    operating_terms = _matched_terms(text, COMPANY_OPERATING_TERMS)
    industry_terms = _matched_terms(text, HIGH_VALUE_INDUSTRY_THEMES)
    catalyst_terms = _matched_terms(text, CONCRETE_CATALYST_TERMS)
    risk_terms = _matched_terms(text, RISK_TERMS)
    weak_terms = _matched_terms(text, WEAK_RELATED_PATTERNS)
    policy_terms = _filter_negated_policy_terms(text, title_policy_terms, policy_terms)
    strong_policy_terms = _strong_policy_terms(policy_terms)
    title_strong_policy_terms = _strong_policy_terms(title_policy_terms)
    is_a_share_policy_event = _is_a_share_policy_event(text)
    is_large_financial_earnings_preview = _is_large_financial_earnings_preview(title, text)
    is_directory_or_ranking = _is_directory_or_ranking_without_capital_event(title)
    is_government_regulatory_action = _is_government_regulatory_action(title)
    if _contains_any(text, NEGATED_FINANCING_PATTERNS):
        title_company_terms = ()
        company_terms = ()
    if is_directory_or_ranking:
        title_company_terms = ()
        company_terms = ()
    if is_government_regulatory_action:
        title_operating_terms = ()
        title_operating_action_terms = ()
    if company_terms and not title_policy_terms:
        policy_terms = tuple(term for term in policy_terms if term not in GENERIC_EXCHANGE_POLICY_TERMS)
        strong_policy_terms = _strong_policy_terms(policy_terms)
    title_specific_financing_terms = tuple(term for term in title_company_terms if term != "上市")
    specific_financing_terms = tuple(term for term in company_terms if term != "上市")

    score = 0
    if macro_terms:
        score += 30 + min(len(macro_terms) * 4, 16)
    if policy_terms:
        score += 50 + min(len(policy_terms) * 5, 25)
    if strong_policy_terms:
        score += 12 + min(len(strong_policy_terms) * 3, 18)
    if is_a_share_policy_event:
        score += 42
    if company_terms:
        score += 34 + min(len(company_terms) * 4, 16)
    if operating_terms:
        score += 30 + min(len(operating_terms) * 4, 16)
    if is_large_financial_earnings_preview:
        score += 104
    if direct_compute_terms or direct_data_center_power_terms:
        score += 60
    if is_ai_application:
        score += 48
    if industry_terms:
        score += 14 + min(len(industry_terms) * 3, 15)
    if catalyst_terms:
        score += 24 + min(len(catalyst_terms) * 4, 16)
    if risk_terms:
        score += 10
    if is_government_regulatory_action:
        score += 50
    if is_directory_or_ranking:
        score -= 100

    if title_company_terms:
        score += 18
    if title_operating_terms:
        score += 16
    if title_macro_terms:
        score += 10
    if title_policy_terms:
        score += 28
    if title_strong_policy_terms:
        score += 12
    if title_catalyst_terms and title_industry_terms:
        score += 14

    is_roundup = _contains_any(title, ROUNDUP_PATTERNS)
    has_hard_signal = bool(
        policy_terms or company_terms or operating_terms or title_macro_terms or title_policy_terms
    )
    has_negated_signal = _contains_any(text, NEGATED_SIGNAL_PATTERNS)
    weak_related = is_roundup or (bool(weak_terms) and (not has_hard_signal or has_negated_signal))
    if is_roundup:
        score -= 140
    if weak_terms:
        score -= 90 if weak_related else 18

    if weak_related:
        news_type = NEWS_TYPE_WEAK
    elif is_government_regulatory_action:
        news_type = NEWS_TYPE_POLICY_REGULATION
    elif title_strong_policy_terms or is_a_share_policy_event:
        news_type = NEWS_TYPE_POLICY_REGULATION
    elif title_financing_action_terms:
        news_type = NEWS_TYPE_COMPANY_FINANCING
    elif title_operating_action_terms:
        news_type = NEWS_TYPE_COMPANY_OPERATING
    elif (
        (title_catalyst_terms or direct_compute_terms or direct_data_center_power_terms or is_ai_application)
        and (title_industry_terms or direct_compute_terms or direct_data_center_power_terms or is_ai_application)
        and not title_specific_financing_terms
    ):
        news_type = NEWS_TYPE_INDUSTRY_CATALYST
    elif title_operating_terms or (operating_terms and not title_specific_financing_terms and not specific_financing_terms):
        news_type = NEWS_TYPE_COMPANY_OPERATING
    elif strong_policy_terms:
        news_type = NEWS_TYPE_POLICY_REGULATION
    elif title_company_terms or company_terms:
        news_type = NEWS_TYPE_COMPANY_FINANCING
    elif title_operating_terms or operating_terms:
        news_type = NEWS_TYPE_COMPANY_OPERATING
    elif title_macro_terms or (macro_terms and not company_terms):
        news_type = NEWS_TYPE_MACRO_RISK
    elif (title_catalyst_terms or catalyst_terms) and (title_industry_terms or industry_terms):
        news_type = NEWS_TYPE_INDUSTRY_CATALYST
    elif score < 40:
        news_type = NEWS_TYPE_WEAK
    else:
        news_type = NEWS_TYPE_BUSINESS

    reason_company_terms = company_terms + operating_terms
    if news_type == NEWS_TYPE_COMPANY_OPERATING:
        reason_company_terms = operating_terms

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
            company_terms=reason_company_terms,
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
    if _contains_any(text, DATA_CENTER_POWER_DIRECT_TERMS):
        return "数据中心电力"
    if _contains_any(text, COMPUTE_DIRECT_TERMS):
        return "算力"
    for label, terms in THEME_ALIASES:
        if _contains_any(text, terms):
            return label
    matched = _matched_terms(text, HIGH_VALUE_INDUSTRY_THEMES)
    return matched[0] if matched else None


def _policy_event_key(item: NewsInsight) -> str | None:
    if item.news_type != NEWS_TYPE_POLICY_REGULATION:
        return None
    text = f"{item.title} {item.reason}"
    if _contains_any(text, ("证监会",)) and _contains_any(text, ("再融资", "定增", "储架发行", "征求意见")):
        return "policy:csrc-refinancing-private-placement"
    if _contains_any(text, ("减持",)):
        return "policy:shareholding-reduction"
    if _contains_any(text, ("退市",)):
        return "policy:delisting"
    if _contains_any(text, ("并购重组",)):
        return "policy:ma-restructuring"
    if _contains_any(text, ("问询", "问询函")):
        return "policy:inquiry"
    if _contains_any(text, ("处罚", "行政处罚", "监管函")):
        return "policy:penalty"
    return None


def _policy_event_title(key: str, fallback: str) -> str:
    if key == "policy:csrc-refinancing-private-placement":
        return "证监会完善上市公司再融资规则，并拟建立定增储架发行制度"
    return fallback


def _consolidate_policy_events(items: list[NewsInsight]) -> list[NewsInsight]:
    consolidated: list[NewsInsight] = []
    key_to_index: dict[str, int] = {}
    for item in sorted(items, key=lambda candidate: candidate.relevance_score, reverse=True):
        key = _policy_event_key(item)
        if not key:
            consolidated.append(item)
            continue
        if key not in key_to_index:
            key_to_index[key] = len(consolidated)
            consolidated.append(_with_reason(item, item.reason, title=_policy_event_title(key, item.title)))
            continue
        index = key_to_index[key]
        existing = consolidated[index]
        merged_reason = f"{existing.reason} 同主题政策线索：{item.title}。"
        merged_score = max(existing.relevance_score, item.relevance_score) + 20
        consolidated[index] = _with_reason(
            existing,
            merged_reason,
            title=_policy_event_title(key, existing.title),
            score=merged_score,
        )
    return consolidated


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


def _is_unmapped_overseas_ipo(article: Any, news_type: str) -> bool:
    if news_type != NEWS_TYPE_COMPANY_FINANCING:
        return False
    text = _article_text(article)
    if not _contains_any(text, OVERSEAS_IPO_TERMS):
        return False
    return not _contains_any(text, A_SHARE_RELATED_IPO_TERMS)


def _select_important_events(items: list[NewsInsight], limit: int) -> tuple[NewsInsight, ...]:
    selected: list[NewsInsight] = []
    source_counts: dict[str, int] = {}
    financing_count = 0
    seen: set[tuple[str, str]] = set()
    for item in sorted(items, key=lambda candidate: candidate.relevance_score, reverse=True):
        key = (item.link, item.title)
        if key in seen:
            continue
        seen.add(key)
        if source_counts.get(item.source, 0) >= MAX_IMPORTANT_EVENTS_PER_SOURCE:
            continue
        if item.news_type == NEWS_TYPE_COMPANY_FINANCING and financing_count >= MAX_COMPANY_FINANCING_EVENTS:
            continue
        selected.append(item)
        source_counts[item.source] = source_counts.get(item.source, 0) + 1
        if item.news_type == NEWS_TYPE_COMPANY_FINANCING:
            financing_count += 1
        if len(selected) >= limit:
            break
    return tuple(selected)


def _holding_relation_for_match(holding: Any, term: str, precise_terms: tuple[str, ...], score: int) -> str:
    direct_terms = {
        _clean(getattr(holding, "code", "")),
        _clean(getattr(holding, "name", "")),
    }
    if term in direct_terms:
        return HOLDING_RELATION_CLEAR
    if term not in precise_terms and score >= 60:
        return ""
    if score < 60 or term not in precise_terms:
        return HOLDING_RELATION_WEAK
    return HOLDING_RELATION_CLEAR


def _holding_match_reason(
    holding: Any,
    base_reason: str,
    term: str,
    relation: str,
) -> str:
    if relation == HOLDING_RELATION_CLEAR:
        return f"{base_reason} 命中关注对象高精度线索：{term}。"
    holding_name = _clean(getattr(holding, "name", "")) or "该持仓"
    return (
        f"弱相关变量：仅命中 {term} 等行业或外部变量，"
        f"当前 RSS 候选未出现与{holding_name}直接相关的订单、业绩、公告或公司消息。"
    )


def _risk_variable(item: NewsInsight) -> str:
    if item.news_type == NEWS_TYPE_POLICY_REGULATION:
        if _contains_any(f"{item.title} {item.reason}", ("再融资", "定增", "储架发行")):
            return "政策变量：再融资和定增储架发行制度落地细则、适用范围和市场解读，可能影响上市公司融资节奏与资金偏好。"
        return "监管变量：后续是否出现正式处罚、问询范围扩大或同类公司合规风险重估。"
    if item.news_type == NEWS_TYPE_COMPANY_FINANCING:
        return "资本市场变量：IPO / 融资 / 估值新闻后续交易热度是否退潮，并影响同类公司预期。"
    if item.news_type == NEWS_TYPE_COMPANY_OPERATING:
        return "经营变量：财报、营收或利润变化是否能持续，并影响同类公司基本面预期。"
    if item.news_type == NEWS_TYPE_MACRO_RISK:
        return "宏观变量：价格、汇率、利率或流动性信号是否继续压制风险偏好。"
    return "反证变量：主题新闻是否缺少订单、公告或成交结构验证。"


def _watch_variable(item: NewsInsight) -> str:
    if item.news_type == NEWS_TYPE_COMPANY_FINANCING:
        return f"观察 {item.title} 的上市后成交热度、估值变化和可比公司反馈。"
    if item.news_type == NEWS_TYPE_COMPANY_OPERATING:
        return f"观察 {item.title} 的营收、利润或经营数据是否延续，并影响同类公司预期。"
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
    theme_stats: dict[str, dict[str, int]] = {}

    for article in articles:
        if _is_excluded_article(article):
            continue
        text = _article_text(article)
        score, news_type, reason, weak_related = _score_article(article)
        if not _is_investable_candidate(score, news_type, weak_related):
            continue
        if _is_unmapped_overseas_ipo(article, news_type):
            continue

        if news_type in {
            NEWS_TYPE_MACRO_RISK,
            NEWS_TYPE_POLICY_REGULATION,
            NEWS_TYPE_COMPANY_FINANCING,
            NEWS_TYPE_COMPANY_OPERATING,
        }:
            event_candidates.append(_insight(article, reason, score, news_type))
        if news_type == NEWS_TYPE_INDUSTRY_CATALYST and score >= 55:
            catalyst = _insight(article, reason, score, news_type)
            catalyst_candidates.append(catalyst)
            theme = _theme_key(text)
            if theme:
                stats = theme_stats.setdefault(theme, {"count": 0, "max_score": 0})
                stats["count"] += 1
                stats["max_score"] = max(stats["max_score"], score)
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
            if _is_unmapped_overseas_ipo(article, news_type):
                continue
            for term in terms:
                if term.lower() not in text.lower():
                    continue
                relation = _holding_relation_for_match(holding, term, precise_terms, score)
                if not relation:
                    continue
                match_reason = _holding_match_reason(holding, reason, term, relation)
                matches.append(_insight(article, match_reason, score, news_type, holding_relation=relation))
                break
        deduped_matches = _dedupe_insights(matches, max_items)
        if deduped_matches:
            holding_matches.append(
                HoldingNewsMatch(
                    holding_title=f"{holding.code} {holding.name}",
                    matches=deduped_matches,
                )
            )

    consolidated_events = _consolidate_policy_events(event_candidates)
    market_events = _select_important_events(consolidated_events, max_items)
    industry_catalysts = _dedupe_insights(catalyst_candidates, max_items)
    policy_risk_candidates = [item for item in market_events if item.news_type == NEWS_TYPE_POLICY_REGULATION]
    risk_points = _dedupe_insights(risk_candidates + policy_risk_candidates, max_items)
    watch_points = _dedupe_insights(watch_candidates, max_items)

    environment_points = (f"RSS 候选新闻 {len(articles)} 条；以下只基于新闻线索做观察。",)
    if risk_points:
        environment_points += tuple(
            f"风险/反证：{item}"
            for item in _dedupe_text_items(tuple(_risk_variable(item) for item in risk_points))[:2]
        )

    theme_clues = _confirmed_theme_clues(theme_stats, max_items)
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
