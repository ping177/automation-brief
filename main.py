from __future__ import annotations

import argparse
import json
import logging
import re
import time as time_module
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any, Optional

import feedparser


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_FEEDS_FILE = BASE_DIR / "feeds.json"
DEFAULT_KEYWORDS_FILE = BASE_DIR / "keywords.json"
DEFAULT_CONFIG_FILE = BASE_DIR / "config.json"
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"
LOG_FILE = BASE_DIR / "daily-news.log"
FEED_FETCH_ATTEMPTS = 2
FEED_FETCH_RETRY_DELAY_SECONDS = 3


@dataclass(frozen=True)
class ReportConfig:
    output_dir: str = "output"
    report_type: str = "list"
    max_items_per_category: int = 8
    max_items_per_feed: int = 3
    summary_max_chars: int = 180
    category_order: tuple[str, ...] = ("财经股票", "AI方向")
    days_back: int = 2
    lookback_hours: int = 24
    filter_stale_by_url_date: bool = True
    stale_url_date_tolerance_days: int = 2
    max_core_events: int = 8
    max_market_signals: int = 6
    max_market_signals_per_source: int = 3
    max_watch_items: int = 5
    output_title: str = "每日早间回顾"
    include_quick_scan: bool = True
    max_quick_scan_items: int = 10
    max_quick_scan_items_per_source: int = 3
    allow_tech_industry_in_market: bool = False
    core_event_roles: tuple[str, ...] = (
        "breaking_news",
        "general",
        "global_tech_business",
        "ai_industry",
    )
    market_signal_roles: tuple[str, ...] = ("market", "global_tech_business", "ai_industry")
    watch_item_roles: tuple[str, ...] = (
        "market",
        "breaking_news",
        "general",
        "global_tech_business",
        "ai_industry",
    )
    quick_scan_roles: tuple[str, ...] = (
        "breaking_news",
        "market",
        "tech_industry",
        "global_tech_business",
        "ai_industry",
        "general",
    )
    quick_scan_exclude_roles: tuple[str, ...] = ("ai_tools",)
    quick_scan_low_value_patterns: tuple[str, ...] = (
        "体育",
        "球员",
        "赛季最佳",
        "赛事",
        "德甲",
        "抢劫",
        "受伤",
        "游客",
        "个案",
        "开幕式",
        "推介会",
        "座谈会",
        "宣传",
        "畅谈",
        "融合发展",
    )
    core_event_negative_patterns: tuple[str, ...] = (
        "鹅腿",
        "鸭腿",
        "阿姨",
        "摊贩",
        "摊主",
        "网红",
        "地方通报",
        "正核查",
        "依法依规处置",
        "个案",
        "游客",
        "男子",
        "女子",
        "老人",
        "食品经营",
        "消费纠纷",
    )
    low_value_patterns: tuple[str, ...] = (
        "游戏风向标",
        "IPO定价",
        "持股比例",
        "评级汇总",
        "目标价",
        "超豪华",
        "香氛",
        "彩电",
        "大沙发",
    )
    digest_exclude_roles: tuple[str, ...] = ("ai_tools",)


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    feed_name: str
    feed_role: str
    published: str
    published_at: Optional[datetime]
    link: str
    summary: str
    matched_keywords: dict[str, list[str]]


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_optional_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return load_json(path)


def positive_int(value: Any, default: int, field_name: str) -> int:
    if value is None:
        return default
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"config.{field_name} must be an integer") from exc
    if number < 1:
        raise ValueError(f"config.{field_name} must be greater than 0")
    return number


def normalize_string_tuple(value: Any, default: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if value is None:
        return default
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"config.{field_name} must be a list")

    cleaned = tuple(str(item).strip() for item in value if str(item).strip())
    return cleaned or default


def bool_value(value: Any, default: bool, field_name: str) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    raise ValueError(f"config.{field_name} must be a boolean")


def normalize_config(raw_config: Any) -> ReportConfig:
    if raw_config is None:
        raw_config = {}
    if not isinstance(raw_config, dict):
        raise ValueError("config.json must be an object")

    defaults = ReportConfig()
    cleaned_category_order = normalize_string_tuple(
        raw_config.get("category_order"), defaults.category_order, "category_order"
    )
    report_type = str(raw_config.get("report_type", defaults.report_type)).strip().lower()
    if report_type not in {"list", "digest"}:
        raise ValueError("config.report_type must be either 'list' or 'digest'")

    return ReportConfig(
        output_dir=str(raw_config.get("output_dir", defaults.output_dir)).strip() or defaults.output_dir,
        report_type=report_type,
        max_items_per_category=positive_int(
            raw_config.get("max_items_per_category"), defaults.max_items_per_category, "max_items_per_category"
        ),
        max_items_per_feed=positive_int(
            raw_config.get("max_items_per_feed"), defaults.max_items_per_feed, "max_items_per_feed"
        ),
        summary_max_chars=positive_int(
            raw_config.get("summary_max_chars"), defaults.summary_max_chars, "summary_max_chars"
        ),
        category_order=cleaned_category_order or defaults.category_order,
        days_back=positive_int(raw_config.get("days_back"), defaults.days_back, "days_back"),
        lookback_hours=positive_int(
            raw_config.get("lookback_hours"), defaults.lookback_hours, "lookback_hours"
        ),
        filter_stale_by_url_date=bool_value(
            raw_config.get("filter_stale_by_url_date"),
            defaults.filter_stale_by_url_date,
            "filter_stale_by_url_date",
        ),
        stale_url_date_tolerance_days=positive_int(
            raw_config.get("stale_url_date_tolerance_days"),
            defaults.stale_url_date_tolerance_days,
            "stale_url_date_tolerance_days",
        ),
        max_core_events=positive_int(
            raw_config.get("max_core_events"), defaults.max_core_events, "max_core_events"
        ),
        max_market_signals=positive_int(
            raw_config.get("max_market_signals"), defaults.max_market_signals, "max_market_signals"
        ),
        max_market_signals_per_source=positive_int(
            raw_config.get("max_market_signals_per_source"),
            defaults.max_market_signals_per_source,
            "max_market_signals_per_source",
        ),
        max_watch_items=positive_int(
            raw_config.get("max_watch_items"), defaults.max_watch_items, "max_watch_items"
        ),
        output_title=str(raw_config.get("output_title", defaults.output_title)).strip()
        or defaults.output_title,
        include_quick_scan=bool_value(
            raw_config.get("include_quick_scan"), defaults.include_quick_scan, "include_quick_scan"
        ),
        max_quick_scan_items=positive_int(
            raw_config.get("max_quick_scan_items"), defaults.max_quick_scan_items, "max_quick_scan_items"
        ),
        max_quick_scan_items_per_source=positive_int(
            raw_config.get("max_quick_scan_items_per_source"),
            defaults.max_quick_scan_items_per_source,
            "max_quick_scan_items_per_source",
        ),
        allow_tech_industry_in_market=bool_value(
            raw_config.get("allow_tech_industry_in_market"),
            defaults.allow_tech_industry_in_market,
            "allow_tech_industry_in_market",
        ),
        core_event_roles=normalize_string_tuple(
            raw_config.get("core_event_roles"), defaults.core_event_roles, "core_event_roles"
        ),
        market_signal_roles=normalize_string_tuple(
            raw_config.get("market_signal_roles"), defaults.market_signal_roles, "market_signal_roles"
        ),
        watch_item_roles=normalize_string_tuple(
            raw_config.get("watch_item_roles"), defaults.watch_item_roles, "watch_item_roles"
        ),
        quick_scan_roles=normalize_string_tuple(
            raw_config.get("quick_scan_roles"), defaults.quick_scan_roles, "quick_scan_roles"
        ),
        quick_scan_exclude_roles=normalize_string_tuple(
            raw_config.get("quick_scan_exclude_roles"),
            defaults.quick_scan_exclude_roles,
            "quick_scan_exclude_roles",
        ),
        quick_scan_low_value_patterns=normalize_string_tuple(
            raw_config.get("quick_scan_low_value_patterns"),
            defaults.quick_scan_low_value_patterns,
            "quick_scan_low_value_patterns",
        ),
        core_event_negative_patterns=normalize_string_tuple(
            raw_config.get("core_event_negative_patterns"),
            defaults.core_event_negative_patterns,
            "core_event_negative_patterns",
        ),
        low_value_patterns=normalize_string_tuple(
            raw_config.get("low_value_patterns"), defaults.low_value_patterns, "low_value_patterns"
        ),
        digest_exclude_roles=normalize_string_tuple(
            raw_config.get("digest_exclude_roles"),
            defaults.digest_exclude_roles,
            "digest_exclude_roles",
        ),
    )


def normalize_feeds(raw_feeds: Any) -> list[dict[str, str]]:
    if not isinstance(raw_feeds, list):
        raise ValueError("feeds.json must be a list of feed objects")

    feeds: list[dict[str, str]] = []
    for index, feed in enumerate(raw_feeds, start=1):
        if not isinstance(feed, dict):
            raise ValueError(f"Feed #{index} must be an object")

        name = str(feed.get("name", "")).strip()
        url = str(feed.get("url", "")).strip()
        mode = str(feed.get("mode", "keyword")).strip().lower() or "keyword"
        role = str(feed.get("role", "general")).strip().lower() or "general"
        if not name or not url:
            raise ValueError(f"Feed #{index} must include non-empty name and url")
        if mode not in {"keyword", "all"}:
            raise ValueError(f"Feed #{index} mode must be either 'keyword' or 'all'")
        valid_roles = {
            "breaking_news",
            "market",
            "tech_industry",
            "global_tech_business",
            "ai_industry",
            "ai_tools",
            "general",
        }
        if role not in valid_roles:
            raise ValueError(
                f"Feed #{index} role must be one of {', '.join(sorted(valid_roles))}"
            )

        feeds.append({"name": name, "url": url, "mode": mode, "role": role})
    return feeds


def normalize_keywords(raw_keywords: Any) -> dict[str, list[str]]:
    if not isinstance(raw_keywords, dict):
        raise ValueError("keywords.json must be an object grouped by category")

    keywords: dict[str, list[str]] = {}
    for category, values in raw_keywords.items():
        if not isinstance(values, list):
            raise ValueError(f"Keywords for category {category!r} must be a list")

        cleaned = [str(value).strip() for value in values if str(value).strip()]
        if cleaned:
            keywords[str(category)] = cleaned
    return keywords


def clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|")


def normalize_link(link: str) -> str:
    return link.strip()


def get_entry_datetime(entry: Any) -> Optional[datetime]:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc)

    for attr in ("published", "updated"):
        value = getattr(entry, attr, None)
        if not value:
            continue
        try:
            parsed_datetime = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            continue
        if parsed_datetime.tzinfo is None:
            return parsed_datetime.replace(tzinfo=timezone.utc)
        return parsed_datetime
    return None


def format_published(entry: Any, published_at: Optional[datetime]) -> str:
    if getattr(entry, "published", None):
        return clean_text(entry.published)
    if getattr(entry, "updated", None):
        return clean_text(entry.updated)

    if published_at:
        return published_at.isoformat()
    return "Unknown"


def entry_text(entry: Any) -> str:
    parts = [
        getattr(entry, "title", ""),
        getattr(entry, "summary", ""),
        getattr(entry, "description", ""),
    ]
    return clean_text(" ".join(parts)).lower()


def match_keywords(text: str, keywords_by_category: dict[str, list[str]]) -> dict[str, list[str]]:
    matches: dict[str, list[str]] = {}
    for category, keywords in keywords_by_category.items():
        hits = [keyword for keyword in keywords if keyword.lower() in text]
        if hits:
            matches[category] = hits
    return matches


def within_days_back(published_at: Optional[datetime], report_date: date, days_back: int) -> bool:
    if not published_at:
        return True

    end_at = datetime.combine(report_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    start_at = end_at - timedelta(days=days_back)
    return start_at <= published_at.astimezone(timezone.utc) < end_at


def within_lookback_hours(published_at: Optional[datetime], lookback_hours: int) -> bool:
    if not published_at:
        return True

    end_at = datetime.now(timezone.utc)
    start_at = end_at - timedelta(hours=lookback_hours)
    return start_at <= published_at.astimezone(timezone.utc) <= end_at


def extract_url_date(url: str) -> Optional[date]:
    patterns = (
        r"/(?P<year>\d{4})-(?P<month>\d{2})/(?P<day>\d{2})(?:/|$)",
        r"/(?P<year>\d{4})/(?P<month>\d{2})-(?P<day>\d{2})(?:/|$)",
        r"/(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})(?:/|$)",
        r"/(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})(?:/|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, url)
        if not match:
            continue
        try:
            return date(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
            )
        except ValueError:
            return None
    return None


def stale_by_url_date(url: str, config: ReportConfig) -> bool:
    if not config.filter_stale_by_url_date:
        return False

    url_date = extract_url_date(url)
    if not url_date:
        return False

    start_at = datetime.now(timezone.utc) - timedelta(hours=config.lookback_hours)
    threshold = start_at.date() - timedelta(days=config.stale_url_date_tolerance_days)
    return url_date < threshold


def fetch_feed(
    feed: dict[str, str],
    keywords_by_category: dict[str, list[str]],
    report_date: date,
    config: ReportConfig,
) -> list[NewsItem]:
    parsed_feed = parse_feed_with_retry(feed)
    if parsed_feed.bozo:
        reason = getattr(parsed_feed, "bozo_exception", "Unknown feed parse error")
        if len(parsed_feed.entries) == 0:
            raise RuntimeError(str(reason))
        logging.warning(
            "RSS parse warning but entries are available: %s (%s): %s",
            feed["name"],
            feed["url"],
            reason,
        )

    items: list[NewsItem] = []
    stale_count = 0
    source = feed["name"]
    for entry in parsed_feed.entries:
        title = clean_text(getattr(entry, "title", "Untitled"))
        link = normalize_link(getattr(entry, "link", ""))
        if not link:
            continue
        if stale_by_url_date(link, config):
            stale_count += 1
            continue

        published_at = get_entry_datetime(entry)
        if config.report_type == "digest":
            in_time_range = within_lookback_hours(published_at, config.lookback_hours)
        else:
            in_time_range = within_days_back(published_at, report_date, config.days_back)
        if not in_time_range:
            continue

        summary = clean_text(getattr(entry, "summary", "") or getattr(entry, "description", ""))
        matched = match_keywords(entry_text(entry), keywords_by_category)
        if feed["mode"] == "keyword" and not matched:
            continue

        items.append(
            NewsItem(
                title=title,
                source=source,
                feed_name=feed["name"],
                feed_role=feed["role"],
                published=format_published(entry, published_at),
                published_at=published_at,
                link=link,
                summary=summary,
                matched_keywords=matched,
            )
        )
    if stale_count:
        logging.info("Filtered stale RSS items by URL date: %s (%s): %s", feed["name"], feed["url"], stale_count)
    return items


def parse_feed_with_retry(feed: dict[str, str]) -> Any:
    last_error: Optional[BaseException] = None
    for attempt in range(1, FEED_FETCH_ATTEMPTS + 1):
        try:
            parsed_feed = feedparser.parse(feed["url"])
        except Exception as exc:
            last_error = exc
        else:
            if not parsed_feed.bozo or len(parsed_feed.entries) > 0:
                return parsed_feed
            last_error = getattr(parsed_feed, "bozo_exception", RuntimeError("Unknown feed parse error"))

        if attempt < FEED_FETCH_ATTEMPTS:
            logging.warning(
                "RSS fetch attempt %s/%s failed: %s (%s): %s; retrying in %ss",
                attempt,
                FEED_FETCH_ATTEMPTS,
                feed["name"],
                feed["url"],
                last_error,
                FEED_FETCH_RETRY_DELAY_SECONDS,
            )
            time_module.sleep(FEED_FETCH_RETRY_DELAY_SECONDS)

    if last_error:
        raise RuntimeError(str(last_error))
    raise RuntimeError("Unknown feed parse error")


def collect_news(
    feeds: list[dict[str, str]],
    keywords_by_category: dict[str, list[str]],
    config: ReportConfig,
    report_date: date,
) -> tuple[list[NewsItem], list[tuple[str, str]]]:
    seen_links: set[str] = set()
    collected: list[NewsItem] = []
    failures: list[tuple[str, str]] = []

    for feed in feeds:
        try:
            logging.info("Fetching RSS: %s (%s)", feed["name"], feed["url"])
            items = fetch_feed(feed, keywords_by_category, report_date, config)
        except Exception as exc:
            logging.warning("Failed to fetch RSS %s (%s): %s", feed["name"], feed["url"], exc)
            failures.append((feed["name"], str(exc)))
            continue

        added_from_feed = 0
        for item in items:
            if item.link in seen_links:
                continue
            seen_links.add(item.link)
            collected.append(item)
            added_from_feed += 1
            if added_from_feed >= config.max_items_per_feed:
                break

    return collected, failures


def group_by_category(
    items: list[NewsItem], keywords_by_category: dict[str, list[str]]
) -> dict[str, list[NewsItem]]:
    grouped = {category: [] for category in keywords_by_category}
    for item in items:
        for category in keywords_by_category:
            if category in item.matched_keywords:
                grouped.setdefault(category, []).append(item)
                break
    return grouped


def ordered_categories(keywords_by_category: dict[str, list[str]], config: ReportConfig) -> list[str]:
    categories = []
    for category in config.category_order:
        if category in keywords_by_category and category not in categories:
            categories.append(category)

    for category in keywords_by_category:
        if category not in categories:
            categories.append(category)
    return categories


def format_matched_keywords(matched_keywords: dict[str, list[str]]) -> str:
    parts = []
    for category, keywords in matched_keywords.items():
        parts.append(f"{category}: {', '.join(keywords)}")
    return "; ".join(parts)


def truncate_summary(summary: str, max_chars: int) -> str:
    cleaned = clean_text(summary)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip() + "……"


MARKET_SIGNAL_TERMS = (
    "A股",
    "沪指",
    "深成指",
    "创业板",
    "科创板",
    "港股",
    "美股",
    "纳斯达克",
    "标普500",
    "道琼斯",
    "美联储",
    "央行",
    "利率",
    "降息",
    "加息",
    "汇率",
    "人民币",
    "美元指数",
    "美债",
    "黄金",
    "原油",
    "铜",
    "大宗商品",
    "风险偏好",
    "关税",
    "贸易",
    "政策",
    "财政",
    "国债",
    "北向资金",
    "成交量",
    "新能源",
    "风电",
    "电力设备",
    "特高压",
    "电网",
    "储能",
    "光伏",
    "半导体",
    "AI",
    "机器人",
    "金风科技",
    "中国西电",
)
MARKET_GENERIC_TERMS = ("资金", "资本", "财政", "金融")
MARKET_STRONG_TERMS = (
    "财政部",
    "央行",
    "人民银行",
    "货币政策",
    "财政政策",
    "政策措施",
    "专项债",
    "国债",
    "地方债",
    "赤字",
    "预算",
    "税收",
    "降准",
    "降息",
    "利率",
    "汇率",
    "A股",
    "港股",
    "美股",
    "债市",
    "商品",
    "黄金",
    "原油",
    "上市公司",
    "财报",
    "业绩",
    "监管",
    "证监会",
    "交易所",
    "停牌",
    "复牌",
    "并购",
    "重组",
    "减持",
    "增持",
    "科创板",
    "创业板",
    "IPO",
    "退市",
    "ST",
    "股价",
    "涨停",
    "跌停",
    "大涨",
    "大跌",
    "道指",
    "标普",
    "融资",
    "估值",
    "回购",
    "处罚",
    "芯片出口管制",
    "出口管制",
    "制裁",
    "芯片禁令",
    "美元",
    "订单",
    "营收",
    "利润",
)
AI_TECH_CONTEXT_TERMS = (
    "AI",
    "人工智能",
    "大模型",
    "Claude",
    "Anthropic",
    "OpenAI",
    "ChatGPT",
    "SpaceX",
    "Microsoft",
    "Google",
    "Nvidia",
    "科技",
    "创新",
    "产业",
    "模型",
    "LLM",
    "agent",
)
CAPITAL_MARKET_TERMS = (
    "估值",
    "融资",
    "IPO",
    "股价",
    "财报",
    "业绩",
    "营收",
    "利润",
    "订单",
    "上市公司",
    "并购",
    "重组",
    "回购",
    "减持",
    "增持",
    "revenue",
    "sales",
    "margin",
    "valuation",
    "market cap",
    "stock",
    "shares",
    "rises",
    "rise",
    "funding",
)
LOCAL_PROMO_TERMS = (
    "地方",
    "乡村振兴",
    "案例",
    "文旅",
    "推介",
    "产业故事",
    "活水",
    "动能",
    "鹤岗",
)
POLICY_BACKGROUND_TERMS = (
    "助力",
    "共同发展",
    "座谈会",
    "召开",
    "国产化",
    "实现",
)
CORE_EVENT_TERMS = (
    "国家级",
    "中央",
    "国务院",
    "央行",
    "财政部",
    "发改委",
    "商务部",
    "证监会",
    "战争",
    "冲突",
    "外交",
    "制裁",
    "关税",
    "选举",
    "投票",
    "峰会",
    "灾害",
    "极端天气",
    "地震",
    "洪水",
    "疫情",
    "重大事故",
    "卫星发射",
    "发射",
    "重大工程",
    "能源供应",
    "宏观经济",
    "就业",
    "通胀",
    "贸易",
    "支付",
    "商业化",
    "支付网络",
    "Visa",
    "Mastercard",
    "Stripe",
    "PayPal",
    "payment",
    "payments",
    "checkout",
    "commerce",
    "agentic commerce",
    "merchant",
    "partnership",
    "commercialization",
    "OpenAI",
    "ChatGPT",
    "Anthropic",
    "Microsoft",
    "Google",
    "Nvidia",
    "进出口",
    "GDP",
    "CPI",
    "PPI",
    "PMI",
    "监管",
    "上市公司",
    "行业",
)
CORE_LOW_IMPORTANCE_TERMS = (
    "个人",
    "游客",
    "遇害",
    "抢劫",
    "受伤",
    "青年交流",
    "青年",
    "论坛",
    "活动",
    "展会",
    "参访",
    "开幕式",
    "推介会",
    "畅谈",
    "融合发展",
    "地方",
    "乡村振兴",
    "案例",
    "文旅",
    "研究发现",
    "科普",
    "娱乐",
    "体育",
    "助力",
    "共同发展",
    "座谈会",
    "召开",
    "国产化",
)
CORE_LOW_IMPORTANCE_OVERRIDES = (
    "公共安全",
    "外交",
    "战争",
    "冲突",
    "制裁",
    "重大事故",
    "地震",
    "洪水",
    "疫情",
    "极端天气",
    "政策",
)
CORE_NEGATIVE_OVERRIDES = (
    "国家",
    "国务院",
    "部委",
    "央行",
    "财政部",
    "发改委",
    "商务部",
    "证监会",
    "交易所",
    "市场监管总局",
    "全国",
    "上市公司",
    "资本市场",
    "财务造假",
    "立案调查",
    "处罚",
    "食品安全",
    "专项整治",
    "公共安全",
    "外交",
    "战争",
    "冲突",
    "制裁",
    "重大",
    "灾害",
    "地震",
    "洪水",
    "疫情",
    "极端天气",
    "宏观经济",
    "政策",
)

WATCH_TERMS = (
    "今日公布",
    "今晚公布",
    "明日公布",
    "将公布",
    "将召开",
    "将举行",
    "将生效",
    "将落地",
    "将披露",
    "今日开盘",
    "今晚",
    "明天",
    "本周公布",
    "本周召开",
    "截至",
    "到期",
    "投票",
    "议息",
    "财报发布",
    "数据发布",
    "利率决议",
    "政策落地",
    "监管决定",
)
WATCH_VARIABLE_TERMS = (
    "政策",
    "会议",
    "议息",
    "利率",
    "汇率",
    "CPI",
    "PPI",
    "PMI",
    "非农",
    "财报",
    "业绩",
    "监管",
    "制裁",
    "关税",
    "选举",
    "投票",
    "数据",
    "发布会",
    "开盘",
    "停牌",
    "复牌",
    "解禁",
    "分红",
    "招标",
    "限售",
    "油价",
    "黄金",
    "美元",
    "美股",
    "A股",
    "港股",
    "债市",
    "商品",
    "央行",
    "美联储",
    "国常会",
    "发改委",
    "证监会",
    "交易所",
    "OpenAI",
    "ChatGPT",
    "Visa",
    "Mastercard",
    "Stripe",
    "PayPal",
    "payment",
    "payments",
    "checkout",
    "commerce",
    "agentic commerce",
    "merchant",
    "partnership",
    "commercialization",
)
WATCH_TIME_PATTERNS = (
    r"\d{1,2}月\d{1,2}日(?:公布|召开|举行|生效|落地|披露|开盘|到期)",
    r"\d{4}年\d{1,2}月\d{1,2}日(?:公布|召开|举行|生效|落地|披露|开盘|到期)",
)
WATCH_PAST_ACTIVITY_TERMS = (
    "参加",
    "出席",
    "举行活动",
    "举办活动",
    "召开论坛",
    "参加论坛",
    "交流会",
    "对接会",
    "开幕式",
    "吸引",
    "参会",
    "与会",
)
WATCH_STRONG_FUTURE_TERMS = (
    "今日公布",
    "今晚公布",
    "明日公布",
    "将公布",
    "将召开",
    "将举行",
    "将生效",
    "将落地",
    "将披露",
    "本周公布",
    "本周召开",
    "到期",
    "投票",
    "议息",
    "财报发布",
    "数据发布",
    "利率决议",
    "政策落地",
    "监管决定",
)
PRODUCT_OR_CONSUMER_TERMS = (
    "新品",
    "手机",
    "汽车内饰",
    "导购",
    "体验",
    "游戏",
    "业务调整",
    "无法使用",
    "产品",
    "工具",
    "消费科技",
    "水上飞行器",
)
AI_IMPACT_TERMS = (
    "AI",
    "人工智能",
    "大模型",
    "LLM",
    "Agent",
    "OpenAI",
    "Claude",
    "Gemini",
    "DeepSeek",
    "Anthropic",
    "Microsoft",
    "Google",
    "Nvidia",
    "ChatGPT",
    "agent",
    "模型",
    "推理",
    "训练",
    "算力",
    "芯片",
    "GPU",
)

OVERSEAS_RATE_TERMS = (
    "美股",
    "纳斯达克",
    "标普500",
    "道琼斯",
    "美联储",
    "利率",
    "降息",
    "加息",
    "汇率",
    "人民币",
    "美元指数",
    "美债",
    "黄金",
    "原油",
)
POLICY_TERMS = ("政策", "财政", "央行", "监管", "关税", "贸易", "会议", "决议", "落地")
GLOBAL_TECH_DOMAIN_TERMS = (
    "Visa",
    "Mastercard",
    "Stripe",
    "PayPal",
    "payment",
    "payments",
    "checkout",
    "commerce",
    "agentic commerce",
    "shopping",
    "merchant",
    "commercialization",
    "OpenAI",
    "ChatGPT",
    "Anthropic",
    "Microsoft",
    "Google",
    "Nvidia",
    "AI agent",
    "agent",
    "支付",
    "支付网络",
    "商业化",
    "商户",
)
GLOBAL_TECH_ACTION_TERMS = (
    "partnership",
    "launch",
    "launched",
    "integration",
    "integrates",
    "revenue",
    "valuation",
    "funding",
    "IPO",
    "regulation",
    "regulatory",
    "antitrust",
    "enterprise",
    "cloud",
    "chip",
    "payment network",
    "commerce",
    "merchant",
    "customer",
    "customers",
    "deal",
    "distribution",
    "platform",
    "payments",
    "checkout",
    "commercialization",
    "合作伙伴",
    "发布",
    "集成",
    "整合",
    "营收",
    "估值",
    "融资",
    "监管",
    "反垄断",
    "企业客户",
    "云",
    "芯片",
    "支付网络",
    "商户",
    "交易",
    "收购",
    "关闭",
    "平台",
    "分发",
    "算力采购",
    "商业化",
)
GLOBAL_TECH_BUSINESS_TERMS = GLOBAL_TECH_DOMAIN_TERMS + GLOBAL_TECH_ACTION_TERMS
GLOBAL_TECH_CAPITAL_TERMS = (
    "funding",
    "raises",
    "raised",
    "valuation",
    "IPO",
    "revenue",
    "sales",
    "margin",
    "market cap",
    "融资",
    "估值",
    "上市",
    "营收",
    "销售额",
    "利润率",
    "市值",
)
GLOBAL_TECH_PAYMENT_TERMS = (
    "Visa",
    "Mastercard",
    "Stripe",
    "PayPal",
    "payment",
    "payments",
    "checkout",
    "commerce",
    "merchant",
    "payment network",
    "支付",
    "支付网络",
    "商户",
)
GLOBAL_TECH_REGULATORY_TERMS = (
    "regulation",
    "regulatory",
    "antitrust",
    "lawsuit",
    "ban",
    "compliance",
    "监管",
    "反垄断",
    "诉讼",
    "禁令",
    "合规",
)
GLOBAL_TECH_ENTERPRISE_TERMS = (
    "enterprise",
    "enterprise customers",
    "cloud deal",
    "chip order",
    "compute deal",
    "customer",
    "customers",
    "order",
    "deal",
    "cloud",
    "chip",
    "企业客户",
    "云",
    "芯片订单",
    "算力采购",
    "订单",
)
GLOBAL_TECH_PLATFORM_TERMS = (
    "major platform integration",
    "distribution channel",
    "official commercial launch",
    "commercial launch",
    "platform integration",
    "integration",
    "distribution",
    "platform",
    "launch",
    "launched",
    "集成",
    "分发",
    "平台",
    "商业发布",
    "正式商业化发布",
)
GLOBAL_TECH_BUSINESS_IMPACT_TERMS = (
    "business impact",
    "enterprise",
    "customers",
    "revenue",
    "sales",
    "paid",
    "commercial",
    "product discontinuation",
    "service shutdown",
    "platform",
    "业务影响",
    "企业客户",
    "客户",
    "营收",
    "付费",
    "商业产品",
    "产品停运",
    "服务关闭",
)
GLOBAL_TECH_DEAL_TERMS = (
    "acquire",
    "acquisition",
    "buy",
    "buyout",
    "merger",
    "deal",
    "收购",
    "并购",
    "合并",
    "交易",
)
GLOBAL_TECH_DEAL_MARKET_TERMS = (
    "stock deal",
    "stock",
    "shares",
    "IPO",
    "post-IPO",
    "days after IPO",
    "market cap",
    "valuation",
    "市值",
    "估值",
    "股权交易",
    "上市",
)
GLOBAL_TECH_SHUTDOWN_TERMS = ("shutdown", "closed", "acquisition", "acquire", "关闭", "收购")
AI_TECH_DISCUSSION_TERMS = (
    "benchmark",
    "benchmarks",
    "coding benchmark",
    "performance",
    "small model",
    "tiny",
    "open-weights",
    "open-source",
    "open source",
    "beats GPT",
    "long-horizon",
    "paper",
    "research",
    "technical",
    "arguing",
    "controversy",
    "leaderboard",
    "model comparison",
    "VibeThinker",
    "GLM",
    "模型性能",
    "小模型",
    "开源",
    "论文",
    "技术路线",
    "基准",
    "争议",
    "对比",
)
MARKET_EVENT_NOISE_TERMS = (
    "交流会",
    "对接会",
    "合作会",
    "论坛",
    "活动",
    "开幕式",
    "推介会",
    "洽谈会",
    "参加",
    "出席",
)
MARKET_HARD_TERMS = (
    "投资额",
    "签约金额",
    "政策落地",
    "上市公司",
    "价格",
    "融资",
    "产业链冲击",
    "贸易限制",
    "出口管制",
    "关税",
    "宏观",
    "GDP",
    "CPI",
    "PPI",
    "PMI",
) + MARKET_STRONG_TERMS + CAPITAL_MARKET_TERMS + OVERSEAS_RATE_TERMS
INDUSTRY_TERMS = (
    "新能源",
    "风电",
    "电力设备",
    "特高压",
    "电网",
    "储能",
    "光伏",
    "半导体",
    "AI",
    "人工智能",
    "机器人",
    "芯片",
    "金风科技",
    "中国西电",
    "OpenAI",
    "ChatGPT",
    "Anthropic",
    "Microsoft",
    "Google",
    "Nvidia",
    "agent",
)
MARKET_PRICE_TERMS = (
    "A股",
    "沪指",
    "深成指",
    "创业板",
    "科创板",
    "港股",
    "美股",
    "纳斯达克",
    "标普500",
    "道琼斯",
    "北向资金",
    "成交量",
    "风险偏好",
)


@dataclass(frozen=True)
class DigestSections:
    core: list[NewsItem]
    market: list[NewsItem]
    watch: list[NewsItem]
    quick_scan: list[NewsItem]


def item_text(item: NewsItem) -> str:
    keywords = " ".join(keyword for values in item.matched_keywords.values() for keyword in values)
    return clean_text(f"{item.title} {item.summary} {item.source} {item.feed_name} {keywords}")


def digest_match_text(item: NewsItem) -> str:
    return clean_text(f"{item.title} {item.summary}")


def digest_title_text(item: NewsItem) -> str:
    return clean_text(item.title)


def digest_context_text(item: NewsItem) -> str:
    return clean_text(f"{item.title} {item.summary} {item.source} {item.feed_name}")


def count_terms(text: str, terms: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(1 for term in terms if term.lower() in lowered)


def matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def has_billion_scale_amount(text: str) -> bool:
    return bool(
        re.search(r"\$\s?\d+(?:\.\d+)?\s?(?:b|bn|billion)\b", text, re.IGNORECASE)
        or re.search(r"\b\d+(?:\.\d+)?\s?billion\b", text, re.IGNORECASE)
    )


def has_strong_global_tech_deal_signal(item: NewsItem) -> bool:
    title = digest_title_text(item)
    if count_terms(title, GLOBAL_TECH_DEAL_TERMS) == 0:
        return False
    return count_terms(title, GLOBAL_TECH_DEAL_MARKET_TERMS) > 0 or has_billion_scale_amount(title)


def normalized_title_text(title: str) -> str:
    text = title.lower()
    text = re.sub(r"\$\s?(\d+(?:\.\d+)?)\s?(?:b|bn|billion)\b", r"\1b", text)
    text = re.sub(r"\b(\d+(?:\.\d+)?)\s?billion\b", r"\1b", text)
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def market_event_key(item: NewsItem) -> str:
    if not has_strong_global_tech_deal_signal(item):
        return ""
    title = digest_title_text(item)
    normalized = normalized_title_text(title)
    amount_match = re.search(r"\b\d+(?:\.\d+)?b\b", normalized)
    amount = amount_match.group(0) if amount_match else ""
    entity_stopwords = {"AI", "IPO", "GPT", "LLM"}
    entities = [
        match.group(0).lower()
        for match in re.finditer(r"\b[A-Z][A-Za-z0-9.]{1,}\b", title)
        if match.group(0) not in entity_stopwords
    ]
    seen_entities: list[str] = []
    for entity in entities:
        if entity not in seen_entities:
            seen_entities.append(entity)
    if amount and len(seen_entities) >= 2:
        return "deal:" + ":".join([amount] + sorted(seen_entities[:3]))
    return "deal:" + normalized


def category_label(item: NewsItem) -> str:
    if item.matched_keywords:
        return next(iter(item.matched_keywords))
    return item.feed_name or item.source


def importance_score(item: NewsItem) -> tuple[int, datetime]:
    text = digest_match_text(item)
    title = digest_title_text(item)
    score = len(item.matched_keywords) * 2
    score += count_terms(text, MARKET_SIGNAL_TERMS)
    score += count_terms(text, WATCH_TERMS)
    score += count_terms(title, MARKET_STRONG_TERMS) * 4
    score += count_terms(title, MARKET_PRICE_TERMS) * 3
    score += count_terms(title, CAPITAL_MARKET_TERMS) * 4
    if item.feed_role in {"global_tech_business", "ai_industry"}:
        score += count_terms(title, GLOBAL_TECH_PAYMENT_TERMS) * 5
        score += count_terms(title, GLOBAL_TECH_CAPITAL_TERMS) * 4
        score += count_terms(title, GLOBAL_TECH_DEAL_TERMS) * 4
        score += count_terms(title, GLOBAL_TECH_DEAL_MARKET_TERMS) * 4
        if has_billion_scale_amount(title):
            score += 4
        score += count_terms(title, GLOBAL_TECH_REGULATORY_TERMS) * 4
        score += count_terms(title, GLOBAL_TECH_ENTERPRISE_TERMS) * 3
        score += count_terms(title, GLOBAL_TECH_PLATFORM_TERMS) * 3
        if count_terms(title, AI_TECH_DISCUSSION_TERMS) > 0 and not has_global_tech_market_signal(item):
            score -= 8
    published_at = item.published_at or datetime.min.replace(tzinfo=timezone.utc)
    return score, published_at


def sort_by_score(items: list[NewsItem]) -> list[NewsItem]:
    return sorted(items, key=importance_score, reverse=True)


def has_watch_signal(item: NewsItem) -> bool:
    text = digest_match_text(item)
    if count_terms(text, POLICY_BACKGROUND_TERMS) > 0:
        return False
    if count_terms(text, WATCH_PAST_ACTIVITY_TERMS) > 0 and count_terms(text, WATCH_STRONG_FUTURE_TERMS) == 0:
        return False
    has_time_signal = count_terms(text, WATCH_TERMS) > 0 or any(
        re.search(pattern, text) for pattern in WATCH_TIME_PATTERNS
    )
    if not has_time_signal:
        return False
    if count_terms(text, WATCH_VARIABLE_TERMS) == 0:
        return False
    if count_terms(text, PRODUCT_OR_CONSUMER_TERMS) > 0 and count_terms(text, MARKET_SIGNAL_TERMS) == 0:
        return False
    return True


def has_global_tech_market_signal(item: NewsItem) -> bool:
    text = digest_match_text(item)
    title = digest_title_text(item)
    if has_strong_global_tech_deal_signal(item):
        return True
    domain_hits = count_terms(text, GLOBAL_TECH_DOMAIN_TERMS)
    if domain_hits == 0:
        return False
    title_hard_hits = (
        count_terms(title, GLOBAL_TECH_CAPITAL_TERMS)
        + count_terms(title, GLOBAL_TECH_PAYMENT_TERMS)
        + count_terms(title, GLOBAL_TECH_REGULATORY_TERMS)
        + count_terms(title, GLOBAL_TECH_ENTERPRISE_TERMS)
        + count_terms(title, GLOBAL_TECH_PLATFORM_TERMS)
        + count_terms(title, GLOBAL_TECH_BUSINESS_IMPACT_TERMS)
        + count_terms(title, GLOBAL_TECH_DEAL_TERMS)
        + count_terms(title, GLOBAL_TECH_DEAL_MARKET_TERMS)
    )
    if count_terms(title, AI_TECH_DISCUSSION_TERMS) > 0 and title_hard_hits == 0:
        return False
    hard_hits = (
        count_terms(text, GLOBAL_TECH_CAPITAL_TERMS)
        + count_terms(text, GLOBAL_TECH_PAYMENT_TERMS)
        + count_terms(text, GLOBAL_TECH_REGULATORY_TERMS)
        + count_terms(text, GLOBAL_TECH_ENTERPRISE_TERMS)
        + count_terms(text, GLOBAL_TECH_PLATFORM_TERMS)
        + count_terms(text, GLOBAL_TECH_BUSINESS_IMPACT_TERMS)
    )
    if count_terms(text, AI_TECH_DISCUSSION_TERMS) > 0 and hard_hits == 0:
        return False
    if count_terms(text, GLOBAL_TECH_PAYMENT_TERMS) > 0 and count_terms(text, GLOBAL_TECH_ACTION_TERMS) > 0:
        return True
    if count_terms(text, GLOBAL_TECH_CAPITAL_TERMS) > 0:
        return True
    if count_terms(text, GLOBAL_TECH_REGULATORY_TERMS) > 0:
        return True
    if count_terms(text, GLOBAL_TECH_ENTERPRISE_TERMS) >= 2:
        return True
    if count_terms(text, GLOBAL_TECH_PLATFORM_TERMS) > 0 and count_terms(text, ("commercial", "official", "enterprise", "商业化", "正式", "企业")) > 0:
        return True
    if count_terms(text, GLOBAL_TECH_SHUTDOWN_TERMS) > 0 and count_terms(text, GLOBAL_TECH_BUSINESS_IMPACT_TERMS) > 0:
        return True
    return False


def has_market_signal(item: NewsItem) -> bool:
    text = digest_match_text(item)
    strong_hits = count_terms(text, MARKET_STRONG_TERMS)
    ai_tech_hits = count_terms(text, AI_TECH_CONTEXT_TERMS)
    if count_terms(text, LOCAL_PROMO_TERMS) > 0 and count_terms(text, MARKET_STRONG_TERMS) == 0:
        return False
    if count_terms(text, POLICY_BACKGROUND_TERMS) > 0 and count_terms(text, MARKET_STRONG_TERMS) == 0:
        return False
    if count_terms(text, MARKET_EVENT_NOISE_TERMS) > 0 and count_terms(text, MARKET_HARD_TERMS) == 0:
        return False
    if item.feed_role in {"global_tech_business", "ai_industry"}:
        return has_global_tech_market_signal(item)
    if item.feed_role == "tech_industry":
        return strong_hits > 0
    if strong_hits > 0:
        return True
    if ai_tech_hits > 0:
        return False
    if count_terms(text, MARKET_GENERIC_TERMS) > 0:
        return False
    if count_terms(text, INDUSTRY_TERMS) > 0 and count_terms(text, MARKET_HARD_TERMS) == 0:
        return False
    return count_terms(text, MARKET_SIGNAL_TERMS) > 0


def has_core_event_signal(item: NewsItem, config: ReportConfig) -> bool:
    text = digest_match_text(item)
    has_negative_signal = count_terms(text, config.core_event_negative_patterns) > 0
    has_major_override = count_terms(text, CORE_NEGATIVE_OVERRIDES) > 0
    if has_negative_signal and not has_major_override:
        return False
    if count_terms(text, CORE_LOW_IMPORTANCE_TERMS) > 0 and count_terms(text, CORE_LOW_IMPORTANCE_OVERRIDES) == 0:
        return False
    if item.feed_role in {"global_tech_business", "ai_industry"} and not has_global_tech_market_signal(item):
        return False
    return count_terms(text, CORE_EVENT_TERMS) > 0


def has_industry_signal(item: NewsItem) -> bool:
    text = digest_match_text(item)
    return (
        count_terms(text, POLICY_TERMS) > 0
        or count_terms(text, INDUSTRY_TERMS) > 0
        or count_terms(text, GLOBAL_TECH_BUSINESS_TERMS) > 0
    )


def is_low_value(item: NewsItem, config: ReportConfig) -> bool:
    return count_terms(digest_context_text(item), config.low_value_patterns) > 0


def is_quick_scan_low_value(item: NewsItem, config: ReportConfig) -> bool:
    return count_terms(digest_context_text(item), config.quick_scan_low_value_patterns) > 0


def can_enter_digest(item: NewsItem, config: ReportConfig) -> bool:
    if is_low_value(item, config):
        return False
    if item.feed_role in config.digest_exclude_roles:
        return False
    if item.feed_role in {"tech_industry", "global_tech_business", "ai_industry"}:
        return has_industry_signal(item) or has_market_signal(item)
    return True


def classify_digest_item(item: NewsItem, config: ReportConfig) -> Optional[str]:
    if not can_enter_digest(item, config):
        return None
    if item.feed_role in config.watch_item_roles and has_watch_signal(item):
        return "watch"
    market_allowed = item.feed_role in config.market_signal_roles or (
        config.allow_tech_industry_in_market and item.feed_role == "tech_industry"
    )
    if market_allowed and has_market_signal(item):
        return "market"
    if item.feed_role in config.core_event_roles and has_core_event_signal(item, config):
        return "core"
    return None


def quick_scan_type(item: NewsItem) -> str:
    text = digest_match_text(item)
    if item.feed_role == "ai_industry":
        return "AI 产业"
    if item.feed_role == "global_tech_business":
        return "全球科技商业"
    if item.feed_role == "tech_industry":
        return "科技产业"
    if item.feed_role == "market":
        return "市场边缘信号" if count_terms(text, MARKET_SIGNAL_TERMS + MARKET_GENERIC_TERMS) > 0 else "公司动态"
    if count_terms(text, ("商务部", "政策", "关税", "监管", "国务院", "发改委", "央行", "财政部")) > 0:
        return "政策背景"
    if count_terms(text, ("国际", "外交", "海外", "中非", "美国", "欧洲", "日本", "韩国")) > 0:
        return "国际观察"
    if count_terms(text, ("公司", "企业", "上市公司", "业务", "营收", "利润")) > 0:
        return "公司动态"
    if item.feed_role == "breaking_news":
        return "综合新闻"
    return "其他观察"


def can_enter_quick_scan(
    item: NewsItem,
    config: ReportConfig,
    used_links: set[str],
    used_event_keys: set[str],
) -> bool:
    if item.link in used_links:
        return False
    event_key = market_event_key(item)
    if event_key and event_key in used_event_keys:
        return False
    if item.feed_role not in config.quick_scan_roles:
        return False
    if item.feed_role in config.digest_exclude_roles or item.feed_role in config.quick_scan_exclude_roles:
        return False
    return not is_low_value(item, config) and not is_quick_scan_low_value(item, config)


def quick_scan_items(
    items: list[NewsItem],
    config: ReportConfig,
    used_links: set[str],
    used_event_keys: set[str],
) -> list[NewsItem]:
    if not config.include_quick_scan:
        return []
    selected: list[NewsItem] = []
    source_counts: dict[str, int] = {}
    for item in sort_by_score(items):
        if not can_enter_quick_scan(item, config, used_links, used_event_keys):
            continue
        source_key = item.source or item.feed_name
        if source_counts.get(source_key, 0) >= config.max_quick_scan_items_per_source:
            continue
        selected.append(item)
        event_key = market_event_key(item)
        if event_key:
            used_event_keys.add(event_key)
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        if len(selected) >= config.max_quick_scan_items:
            break
    return selected


def source_key(item: NewsItem) -> str:
    return item.source or item.feed_name


def build_digest_sections(items: list[NewsItem], config: ReportConfig) -> DigestSections:
    core: list[NewsItem] = []
    market: list[NewsItem] = []
    watch: list[NewsItem] = []
    market_source_counts: dict[str, int] = {}
    market_event_keys: set[str] = set()

    for item in sort_by_score(items):
        section = classify_digest_item(item, config)
        if section == "watch" and len(watch) < config.max_watch_items:
            watch.append(item)
        elif section == "market" and len(market) < config.max_market_signals:
            event_key = market_event_key(item)
            if event_key and event_key in market_event_keys:
                continue
            key = source_key(item)
            if market_source_counts.get(key, 0) >= config.max_market_signals_per_source:
                continue
            market.append(item)
            if event_key:
                market_event_keys.add(event_key)
            market_source_counts[key] = market_source_counts.get(key, 0) + 1
        elif section == "core" and len(core) < config.max_core_events:
            core.append(item)

    selected_items = core + market + watch
    used_links = {item.link for item in selected_items}
    used_event_keys = {key for key in (market_event_key(item) for item in selected_items) if key}
    quick_scan = quick_scan_items(items, config, used_links, used_event_keys)
    return DigestSections(core=core, market=market, watch=watch, quick_scan=quick_scan)


def rule_reason(item: NewsItem) -> str:
    text = digest_match_text(item)
    policy_hits = matched_terms(text, POLICY_TERMS)
    business_hits = matched_terms(text, GLOBAL_TECH_DOMAIN_TERMS)
    core_hits = matched_terms(text, CORE_EVENT_TERMS)
    industry_hits = matched_terms(text, INDUSTRY_TERMS)
    if policy_hits:
        return f"涉及{policy_hits[0]}相关信息，适合作为今日宏观和产业背景观察。"
    if business_hits and has_global_tech_market_signal(item):
        return f"涉及{business_hits[0]}相关全球科技商业进展，可能影响 AI 商业化或基础设施生态。"
    if core_hits:
        return f"涉及{core_hits[0]}，属于需要优先关注的高影响事件。"
    if industry_hits:
        return f"涉及{industry_hits[0]}方向，可能影响相关产业关注度。"
    return "作为背景信息观察，暂不强行外推为市场影响。"


def market_impact(item: NewsItem) -> str:
    text = digest_match_text(item)
    title = digest_title_text(item)
    overseas_hits = matched_terms(text, OVERSEAS_RATE_TERMS)
    market_hits = matched_terms(text, MARKET_PRICE_TERMS)
    capital_hits = matched_terms(text, CAPITAL_MARKET_TERMS)
    policy_hits = matched_terms(text, POLICY_TERMS)
    business_hits = matched_terms(text, GLOBAL_TECH_DOMAIN_TERMS)
    industry_hits = matched_terms(text, INDUSTRY_TERMS)
    global_capital_hits = matched_terms(text, GLOBAL_TECH_CAPITAL_TERMS)
    global_payment_hits = matched_terms(text, GLOBAL_TECH_PAYMENT_TERMS)
    global_regulatory_hits = matched_terms(text, GLOBAL_TECH_REGULATORY_TERMS)
    global_enterprise_hits = matched_terms(text, GLOBAL_TECH_ENTERPRISE_TERMS)
    global_platform_hits = matched_terms(text, GLOBAL_TECH_PLATFORM_TERMS)
    title_deal_hits = matched_terms(title, GLOBAL_TECH_DEAL_TERMS)
    title_deal_market_hits = matched_terms(title, GLOBAL_TECH_DEAL_MARKET_TERMS)
    title_market_hits = matched_terms(title, MARKET_PRICE_TERMS)
    title_capital_hits = matched_terms(title, CAPITAL_MARKET_TERMS)
    title_global_capital_hits = matched_terms(title, GLOBAL_TECH_CAPITAL_TERMS)
    title_global_payment_hits = matched_terms(title, GLOBAL_TECH_PAYMENT_TERMS)
    title_global_regulatory_hits = matched_terms(title, GLOBAL_TECH_REGULATORY_TERMS)
    title_global_enterprise_hits = matched_terms(title, GLOBAL_TECH_ENTERPRISE_TERMS)
    title_global_platform_hits = matched_terms(title, GLOBAL_TECH_PLATFORM_TERMS)
    if overseas_hits:
        return f"涉及{overseas_hits[0]}，可能影响风险偏好、汇率利率预期或 A 股情绪。"
    if title_deal_hits and has_strong_global_tech_deal_signal(item):
        deal_parts = title_deal_hits[:1] + title_deal_market_hits[:1]
        if has_billion_scale_amount(title):
            deal_parts.append("billion-scale amount")
        return f"涉及{' / '.join(deal_parts)}，可作为并购、交易规模、IPO 或估值信号观察。"
    if title_market_hits:
        return f"涉及{title_market_hits[0]}，可观察其对市场交易情绪的影响。"
    if title_global_capital_hits:
        return f"涉及{title_global_capital_hits[0]}，可作为营收、利润率、估值或资本市场信号观察。"
    if title_capital_hits:
        return f"涉及{title_capital_hits[0]}，可作为资本市场或公司估值信号观察。"
    if title_global_payment_hits and has_global_tech_market_signal(item):
        return f"涉及{title_global_payment_hits[0]}，可作为 AI 支付、agent commerce 或支付基础设施信号观察。"
    if title_global_regulatory_hits:
        return f"涉及{title_global_regulatory_hits[0]}，可作为监管、合规或反垄断风险信号观察。"
    if title_global_enterprise_hits:
        return f"涉及{title_global_enterprise_hits[0]}，可作为企业客户、云、芯片或算力订单信号观察。"
    if title_global_platform_hits:
        return f"涉及{title_global_platform_hits[0]}，可作为平台集成、分发渠道或商业发布信号观察。"
    if market_hits:
        return f"涉及{market_hits[0]}，可观察其对市场交易情绪的影响。"
    if global_capital_hits:
        return f"涉及{global_capital_hits[0]}，可作为营收、利润率、估值或资本市场信号观察。"
    if capital_hits:
        return f"涉及{capital_hits[0]}，可作为资本市场或公司估值信号观察。"
    if global_payment_hits and has_global_tech_market_signal(item):
        return f"涉及{global_payment_hits[0]}，可作为支付基础设施或 commerce 生态信号观察。"
    if global_regulatory_hits:
        return f"涉及{global_regulatory_hits[0]}，可作为监管、合规或反垄断风险信号观察。"
    if global_enterprise_hits:
        return f"涉及{global_enterprise_hits[0]}，可作为企业客户、云、芯片或算力订单信号观察。"
    if global_platform_hits:
        return f"涉及{global_platform_hits[0]}，可作为平台集成、分发渠道或商业发布信号观察。"
    if policy_hits:
        return f"涉及{policy_hits[0]}，可能影响政策预期和相关板块关注度。"
    if business_hits and has_global_tech_market_signal(item):
        return f"涉及{business_hits[0]}，可作为 AI 商业化、支付基础设施或平台生态信号观察。"
    if industry_hits:
        return "作为产业动态观察，短期市场影响可能有限。"
    return "作为市场边缘信号观察。"


def watch_impact(item: NewsItem) -> str:
    text = digest_match_text(item)
    watch_hits = matched_terms(text, WATCH_TERMS)
    overseas_hits = matched_terms(text, OVERSEAS_RATE_TERMS)
    policy_hits = matched_terms(text, POLICY_TERMS)
    industry_hits = matched_terms(text, INDUSTRY_TERMS)
    ai_hits = matched_terms(text, AI_IMPACT_TERMS)
    prefix = f"{watch_hits[0]}相关进展" if watch_hits else "后续进展"
    if overseas_hits:
        return f"需观察{prefix}是否影响风险偏好、汇率利率预期或 A 股情绪。"
    if policy_hits:
        return f"需观察{prefix}是否改变政策预期和相关板块关注度。"
    if ai_hits:
        return f"需观察{prefix}是否带动 AI 产业关注度。"
    if industry_hits:
        return "作为产业动态观察，短期市场影响可能有限。"
    return "作为背景信息观察。"


def count_items_with_terms(items: list[NewsItem], terms: tuple[str, ...]) -> int:
    return sum(1 for item in items if count_terms(digest_match_text(item), terms) > 0)


def one_line_theme(sections: DigestSections) -> str:
    main_items = sections.core + sections.market + sections.watch
    if len(main_items) <= 1 and sections.quick_scan:
        return "主栏目有效信号偏少，可通过快速扫读补充了解政策、科技产业与外围市场动态。"
    if len(main_items) <= 1:
        return "主线信号仍不够集中，建议重点扫读政策、市场与科技产业动态的后续变化。"

    overseas_count = count_items_with_terms(main_items, OVERSEAS_RATE_TERMS)
    policy_count = count_items_with_terms(main_items, POLICY_TERMS)
    if overseas_count >= 3:
        return "今天重点关注海外风险偏好和汇率利率变化对 A 股情绪的影响。"
    if policy_count >= 3:
        return "前三个主栏目中政策相关信息较多，建议继续观察后续落地和市场反馈。"
    if len(sections.market) >= 3:
        return "市场信号较多但主线分散，建议重点观察股价、估值、业绩与政策相关线索。"
    return "主线信号仍不够集中，建议重点扫读政策、市场与科技产业动态的后续变化。"


def append_failures(lines: list[str], failures: list[tuple[str, str]]) -> None:
    lines.extend(["## 抓取失败", ""])
    if failures:
        for source, reason in failures:
            lines.append(f"- {markdown_escape(source)}：{markdown_escape(reason)}")
        lines.append("")
    else:
        lines.extend(["无。", ""])


def write_list_markdown(
    items: list[NewsItem],
    keywords_by_category: dict[str, list[str]],
    output_dir: Path,
    report_date: date,
    config: ReportConfig,
    failures: list[tuple[str, str]],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"daily-news-{report_date.isoformat()}.md"
    grouped = group_by_category(items, keywords_by_category)
    categories = ordered_categories(keywords_by_category, config)
    displayed_count = sum(
        min(len(grouped.get(category, [])), config.max_items_per_category) for category in categories
    )

    lines = [
        f"# Daily News - {report_date.isoformat()}",
        "",
        f"Generated at: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Total displayed articles: {displayed_count}",
        "",
    ]

    for category in categories:
        category_items = grouped.get(category, [])[: config.max_items_per_category]
        lines.extend([f"## {category}", ""])
        if not category_items:
            lines.extend(["今日暂无匹配内容。", ""])
            continue

        for item in category_items:
            matched = format_matched_keywords(item.matched_keywords)
            summary = truncate_summary(item.summary or "No summary", config.summary_max_chars)
            lines.extend(
                [
                    f"### {markdown_escape(item.title)}",
                    "",
                    f"- Source: {markdown_escape(item.source)}",
                    f"- Published: {markdown_escape(item.published)}",
                    f"- Link: {item.link}",
                    f"- Matched keywords: {markdown_escape(matched)}",
                    f"- Original summary: {markdown_escape(summary)}",
                    "",
                ]
            )

    append_failures(lines, failures)

    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def write_digest_markdown(
    items: list[NewsItem],
    output_dir: Path,
    report_date: date,
    config: ReportConfig,
    failures: list[tuple[str, str]],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"daily-news-{report_date.isoformat()}.md"

    sections = build_digest_sections(items, config)
    displayed_count = len(sections.core) + len(sections.market) + len(sections.watch) + len(sections.quick_scan)

    lines = [
        f"# {markdown_escape(config.output_title)}｜{report_date.isoformat()}",
        "",
        f"Generated at: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Lookback: past {config.lookback_hours} hours",
        f"Total source articles: {len(items)}",
        f"Displayed items: {displayed_count}",
        "",
        "## 一、昨日最重要的事",
        "",
    ]

    if sections.core:
        for index, item in enumerate(sections.core, start=1):
            lines.extend(
                [
                    f"### {index}. {markdown_escape(item.title)}",
                    f"- 来源：{markdown_escape(item.source)}",
                    f"- 时间：{markdown_escape(item.published)}",
                    f"- 为什么重要：{markdown_escape(rule_reason(item))}",
                    f"- 链接：{item.link}",
                    "",
                ]
            )
    else:
        lines.extend(["过去时间窗口内暂无匹配内容。", ""])

    lines.extend(["## 二、昨日市场信号", ""])
    if sections.market:
        for index, item in enumerate(sections.market, start=1):
            lines.extend(
                [
                    f"### {index}. {markdown_escape(item.title)}",
                    f"- 来源：{markdown_escape(item.source)}",
                    f"- 可能影响：{markdown_escape(market_impact(item))}",
                    f"- 链接：{item.link}",
                    "",
                ]
            )
    else:
        lines.extend(["过去时间窗口内暂无明显市场信号。", ""])

    lines.extend(["## 三、今天值得关注的变量", ""])
    if sections.watch:
        for index, item in enumerate(sections.watch, start=1):
            lines.extend(
                [
                    f"### {index}. {markdown_escape(item.title)}",
                    f"- 可能影响：{markdown_escape(watch_impact(item))}",
                    "",
                ]
            )
    else:
        lines.extend(["暂无从昨日新闻中提取出的明确延续变量。", ""])

    lines.extend(["## 四、快速扫读", ""])
    if sections.quick_scan:
        for index, item in enumerate(sections.quick_scan, start=1):
            lines.extend(
                [
                    f"### {index}. {markdown_escape(item.title)}",
                    f"- 来源：{markdown_escape(item.source)}",
                    f"- 类型：{markdown_escape(quick_scan_type(item))}",
                    f"- 链接：{item.link}",
                    "",
                ]
            )
    else:
        lines.extend(["暂无可补充的快速扫读内容。", ""])

    lines.extend(["## 五、一句话主线", "", one_line_theme(sections), ""])
    append_failures(lines, failures)

    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def write_markdown(
    items: list[NewsItem],
    keywords_by_category: dict[str, list[str]],
    output_dir: Path,
    report_date: date,
    config: ReportConfig,
    failures: list[tuple[str, str]],
) -> Path:
    if config.report_type == "digest":
        return write_digest_markdown(items, output_dir, report_date, config, failures)
    return write_list_markdown(items, keywords_by_category, output_dir, report_date, config, failures)


def parse_report_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError):
        return date.fromisoformat(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a keyword-filtered RSS daily news report.")
    parser.add_argument("--feeds", type=Path, default=DEFAULT_FEEDS_FILE, help="Path to feeds.json")
    parser.add_argument(
        "--keywords", type=Path, default=DEFAULT_KEYWORDS_FILE, help="Path to keywords.json"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_FILE, help="Path to config.json")
    parser.add_argument("--output", type=Path, help="Override output directory")
    parser.add_argument("--date", help="Report date, defaults to today. Example: 2026-06-11")
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()

    feeds = normalize_feeds(load_json(args.feeds))
    keywords = normalize_keywords(load_json(args.keywords))
    config = normalize_config(load_optional_json(args.config))
    report_date = parse_report_date(args.date)
    output_dir = args.output if args.output else BASE_DIR / config.output_dir

    items, failures = collect_news(feeds, keywords, config, report_date)
    output_file = write_markdown(items, keywords, output_dir, report_date, config, failures)
    logging.info("Generated report: %s", output_file)


if __name__ == "__main__":
    main()
