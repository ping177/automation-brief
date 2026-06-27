# Daily News Automation

一个低成本的每日资讯自动化工具：从 `feeds.json` 配置的 RSS 源抓取文章，根据 `keywords.json` 中的关键词分类过滤，去重后生成 Markdown 简报。

v0.2-alpha 新增“每日早间回顾简报”模式，用规则把过去 24 小时的重要事件、市场信号和今日关注变量整理成结构化输出。v0.2.1 收紧了 digest 分流规则，避免泛科技内容和 AI 工具内容混入每日市场简报。v0.2.2 继续收紧“今天值得关注的变量”，避免普通产品发布、游戏、消费科技和业务调整误入。v0.5-alpha 新增 `market_brief` 市场投研晨报骨架，用离线 mock/sample 数据和可配置 holdings 文件生成“每日市场雷达 + 持仓观察 + 主线发现 + 风险提醒”的基础 Markdown 结构。v0.5.1-alpha 完善 holdings 本地初始化、校验和手动生成体验。v0.5.2-alpha 让显式 `market_brief` 复用 RSS 候选新闻做新闻驱动观察和 holdings 相关新闻匹配。v0.5-beta 第一阶段为显式 `market_brief` 增加轻量 A 股行情验证。当前版本仍不调用 AI。

当前版本不接 DeepSeek，不接 Tavily，也不依赖任何付费搜索 API。
`market_brief` 当前只做新闻 + 最小行情验证，不做买卖建议，也不替用户做投资决策。

## 项目文档

- `docs/PROJECT_STATE.md`：当前人工状态，供 project-command-center 展示。
- `docs/BACKLOG.md`：后续任务和优先级。
- `docs/DEVLOG.md`：开发过程记录和重要验证记录。
- `docs/TESTING.md`：测试命令、smoke checklist 和验收记录。
- `docs/DECISIONS.md`：长期产品、架构和工作流决策。
- `docs/MISSED_CASES.md`：missed coverage、漏报案例和质量追踪。

## 功能

- 从多个 RSS 源抓取文章
- 按关键词分类过滤新闻
- 支持 RSS 源按 `mode` 控制收录方式：`keyword` 需要命中关键词，`all` 在时间范围内直接收录
- 支持 RSS 源按 `role` 控制 digest 分流：快讯、市场、科技产业、全球科技商业、AI 产业、AI 工具和通用源分开处理
- 同一链接只保留一次
- 支持三种输出模式：`list` 分类新闻列表，`digest` 早间回顾简报，`market_brief` 市场投研晨报骨架
- 支持每个分类、每个 RSS 源的输出数量控制
- 支持摘要长度截断
- 支持按配置控制分类输出顺序
- 单个 RSS 抓取失败不会中断整体流程，会记录到日志，并在文末统一展示
- 输出到 `output/daily-news-YYYY-MM-DD.md`

`list` 模式每条新闻包含：

- 标题
- 来源
- 发布时间
- 链接
- 命中的关键词
- 原始摘要

`digest` 模式输出结构：

- 昨日最重要的事
- 昨日市场信号
- 今天值得关注的变量
- 快速扫读
- 一句话主线
- 抓取失败

前三个主栏目采用严格筛选，尽量避免普通社会新闻、活动新闻和泛产业动态误入。`快速扫读` 用于增加信息覆盖，收录没有进入前三个主栏目但仍可扫一眼的新闻；它不等于重要新闻，也不代表市场信号。快速扫读仍会用 `quick_scan_low_value_patterns` 过滤低优先级体育、个案社会新闻和宣传活动，并用 `max_quick_scan_items_per_source` 限制同一来源展示数量，避免 36氪或其他单一源刷屏。

digest 使用栏目角色硬隔离：

- `breaking_news` 和 `general` 才能进入“昨日最重要的事”，并且还必须命中重大事件信号
- `market` 是“昨日市场信号”的默认主来源
- `tech_industry` 默认只进入“快速扫读”，不会进入核心事件、市场信号或今日变量
- `global_tech_business` 和 `ai_industry` 可以进入核心事件、市场信号、今日变量和快速扫读，用于补充全球科技商业、AI 商业化、支付基础设施和平台生态新闻
- `ai_tools` 默认排除 daily digest，也不会进入“快速扫读”，保留给未来 weekly AI tools radar

`digest` 模式下每条文章最多进入一个 section。分流优先级是：

0. 先执行 `low_value_patterns` 过滤，命中后不进入 digest 主体
1. 同时命中时间指向和变量类型，进入“今天值得关注的变量”
2. 否则命中市场信号规则，进入“昨日市场信号”
3. 否则来自 `breaking_news` 源且命中重大事件信号，进入“昨日最重要的事”
4. 其他文章不进入 digest 主体

`breaking_news` 不等于自动进入核心事件。“昨日最重要的事”还需要命中国家级政策、中央部门、国际冲突、外交制裁、选举投票、重大灾害、重大事故、航天能源基础设施、宏观经济、资本市场监管等重大事件信号。个人案件、普通活动论坛、地方宣传稿、乡村振兴案例、文旅活动、普通社会新闻和娱乐体育内容默认不进入核心事件。

核心事件会过滤地方民生个案、普通舆情处置和普通消费纠纷，例如地方通报、个案核查、食品摊贩/商户经营问题、网红个案等。`监管`、`通报`、`核查`、`处置` 不是进入核心事件的充分条件，必须同时看监管层级和影响范围；证监会立案、交易所处罚、上市公司财务造假、部委级监管政策、全国性食品安全事件和重大公共安全事件仍可进入核心事件或市场信号。

“昨日市场信号”会避免被 `资金`、`资本`、`财政`、`金融` 这类泛词单独触发。它们需要和更明确的宏观或资本市场词同现，例如 `财政部`、`央行`、`货币政策`、`专项债`、`国债`、`降息`、`利率`、`汇率`、`A股`、`港股`、`美股`、`债市`、`上市公司`、`财报`、`监管`、`证监会`、`交易所`、`停牌`、`并购`、`重组`、`IPO`、`退市`、`ST` 等。地方政务、乡村振兴和案例宣传类文章即使命中泛词，也不会自动进入市场信号。

AI 和科技产业词也不再单独触发“昨日市场信号”。标题或摘要只出现 `AI`、`人工智能`、`大模型`、`OpenAI`、`SpaceX`、`科技`、`创新`、`产业` 等词时，默认更适合进入“快速扫读”。只有同时出现股价、涨跌、A股/港股/美股、财报、业绩、营收、利润、订单、融资、IPO、估值、并购、回购、监管、处罚、出口管制、制裁、关税、汇率、利率、美元、黄金、原油、债市等明确市场词时，才可能进入市场信号。

“昨日市场信号”支持 `max_market_signals_per_source` 控制同一来源展示上限，避免单个市场源一次占满整个栏目。这个限制只影响“昨日市场信号”，不影响“快速扫读”。

`tech_industry` 默认不进入“昨日市场信号”。只有在 `config.json` 显式设置 `allow_tech_industry_in_market: true` 后，且标题或摘要明确出现股价、涨跌停、A股/港股/美股、上市公司、财报、业绩、融资、IPO、并购、重组、监管、处罚、退市、科创板、创业板、芯片出口管制、关税、制裁、订单、营收、利润等强市场词时，才可能进入市场信号。普通产品发布、展区、首飞、生态、场景、前沿动态更适合进入“快速扫读”。

“今天值得关注的变量”需要同时满足明确后续观察节点和变量类型，不能只因为包含政策部门、商务部、关税、发展、助力等词进入：

- 后续观察节点：如 `今日公布`、`今晚公布`、`明日公布`、`将公布`、`将召开`、`将举行`、`将生效`、`将落地`、`将披露`、`今日开盘`、`今晚`、`明天`、`本周公布`、`本周召开`、`截至`、`到期`、`投票`、`议息`、`财报发布`、`数据发布` 等
- 变量类型：如 `政策`、`会议`、`议息`、`利率`、`汇率`、`CPI`、`PPI`、`PMI`、`非农`、`财报`、`业绩`、`监管`、`关税`、`数据`、`开盘`、`停牌`、`复牌`、`油价`、`黄金`、`美元`、`美股`、`A股`、`港股`、`债市`、`央行`、`美联储`、`证监会`、`交易所` 等

单独出现“将”不再作为今日变量触发词；普通产品发布、业务调整、消费科技、游戏、导购、体验类文章没有明确市场/政策/宏观/财报/监管/资产价格变量时，不进入今日变量。

“一句话主线”采用保守策略，只根据前三个主栏目实际展示的新闻判断，不读取“快速扫读”或未展示关键词。除非前三个主栏目中至少有多条新闻指向同一主题，否则使用克制兜底，避免硬凑“科技成长方向”“政策预期发酵”或“新能源、电力设备、风电”等行业主线。

`market_brief` 模式是显式触发的市场投研晨报，不改变每日自动运行的默认 digest 链路。输出文件为：

```text
output/market-brief-YYYY-MM-DD.md
```

显式 `market_brief` 会复用 `feeds.json` / `keywords.json` 抓取到的 RSS 候选新闻，提取重要市场事件、产业催化、风险/反证、今日观察点，并用 `config/holdings.json` 中的 `code`、`name`、`sector`、`watch_tags` 做相关新闻匹配。v0.5-beta 第一阶段会尝试用轻量公开行情接口获取主要指数和 holdings 个股涨跌；行情源失败或字段缺失时显示“数据暂不可用”，不编造。当前不接 AKShare、TuShare，不计算复杂相对强弱、板块强度或产业催化强度，不输出交易动作。持仓观察来自 `config/holdings.json`；如果真实文件不存在，会回退读取 `config/holdings.example.json`。真实 `config/holdings.json` 已加入 `.gitignore`，不要提交成本、仓位、市值、亏损金额或其他敏感持仓信息。

`market_brief` 输出结构：

- 市场温度
- 今日主线
- 我的持仓观察
- 重要新闻与验证
- 风险与反证
- 今日继续观察

免责声明固定保留：本报告仅用于个人市场观察和复盘，不构成投资建议。

### holdings 本地配置

初始化本地 holdings 配置：

```bash
python3 scripts/init_holdings_config.py
```

脚本会从 `config/holdings.example.json` 创建本地 `config/holdings.json`。如果文件已经存在，脚本不会覆盖。`config/holdings.json` 已被 `.gitignore` 忽略，应只保留在本机。

编辑 `config/holdings.json` 时，每个条目只建议填写这些字段：

```json
{
  "code": "示例代码",
  "name": "示例名称",
  "market": "A股",
  "sector": "示例行业",
  "watch_tags": ["关注标签"],
  "notes": "只写观察备注"
}
```

不要在 `config/holdings.json` 保存成本、仓位、持股数量、市值、盈亏金额、账户金额等真实敏感信息。调仓或调整关注对象后，直接编辑本地 `config/holdings.json`，然后运行校验：

```bash
python3 scripts/validate_holdings_config.py
```

校验脚本只输出字段级错误或 warning，不输出成本、仓位、市值、盈亏金额等具体值。

## 本地运行

创建虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

创建配置文件：

```bash
cp feeds.example.json feeds.json
cp keywords.example.json keywords.json
cp config.example.json config.json
```

编辑 `feeds.json`、`keywords.json` 和 `config.json` 后运行：

```bash
python main.py
```

生成结果会保存到：

```text
output/daily-news-YYYY-MM-DD.md
```

日志文件：

```text
daily-news.log
```

也可以指定配置、输出目录和日期：

```bash
python main.py --feeds feeds.json --keywords keywords.json --config config.json --output output --date 2026-06-11
```

如需手动生成 v0.5-beta 市场投研晨报，先确认 holdings 配置有效：

```bash
python3 scripts/validate_holdings_config.py
```

再运行独立脚本：

```bash
scripts/run_market_brief.sh
```

也可以直接使用显式 CLI 覆盖：

```bash
python3 main.py --report-type market_brief --output output --date 2026-06-11
```

`python3 main.py` 使用当前 `config.json`，仍按现有配置生成普通每日早间回顾，不会默认切换到 `market_brief`。`scripts/run_daily_digest.sh` 也不受影响，仍服务每天 08:00 的普通 digest、Obsidian 同步和 Bark 推送链路。

## RSS 源健康检查

可以用 `check_feeds.py` 检查 `feeds.json` 中每个 RSS 源是否可访问、是否能被 `feedparser` 解析，以及解析出的条目数量：

```bash
python3 check_feeds.py
```

输出字段包括：

- `name`
- `role`
- `mode`
- `status`
- `entries_count`
- `error_message`

输出会按 `status` 排序：`ok` 在前，`ok_with_warning` 次之，`empty` 和 `failed` 在后。表格前会显示 `total`、`ok`、`ok_with_warning`、`empty`、`failed` 统计。

`status` 规则：

- `ok`：能解析，且 `entries_count > 0`
- `ok_with_warning`：RSS 有格式、编码等警告，但 `entries_count > 0`，内容仍可用于日报
- `empty`：没有严重异常，但 `entries_count = 0`
- `failed`：请求异常、完全无法解析，或 `entries_count = 0` 且存在严重解析异常

健康检查时不要只看 `failed` 文案，也要结合 `entries_count` 判断。比如部分 RSS 会有编码声明警告，但只要 `entries_count > 0`，程序会继续处理。若源返回 `text/html` 而不是 RSS/XML media type，通常说明不是可用 RSS 地址，应删除或替换。

## 如何人工添加 RSS 源

新增 RSS 源建议先人工确认来源质量，再编辑 `feeds.json`。不要一次性大量加入未经确认的源，先少量添加、运行健康检查，再观察 digest 输出质量。

每个源建议包含：

```json
{
  "name": "源名称",
  "url": "https://example.com/feed.xml",
  "category": "可选分类",
  "mode": "keyword",
  "role": "general"
}
```

字段选择建议：

- `mode: "keyword"`：默认选择。只有命中 `keywords.json` 才收录，适合泛资讯、科技产业、博客和工具类源。
- `mode: "all"`：只要在时间范围内就收录，适合你已经确认质量较高的快讯、电报或市场源。
- `role: "breaking_news"`：快讯/电报源，可进入 digest 的“昨日最重要的事”。
- `role: "market"`：市场源，可进入“昨日市场信号”。
- `role: "tech_industry"`：科技产业源，只有命中政策、产业、AI、半导体、机器人、新能源等信号时进入 digest。
- `role: "global_tech_business"`：全球科技商业源，可进入核心事件、市场信号、今日变量和快速扫读，适合大型科技公司、支付、云、芯片、平台生态和商业化新闻。
- `role: "ai_industry"`：AI 产业源，可进入核心事件、市场信号、今日变量和快速扫读，适合 AI 公司、模型、agent、算力、企业化和商业化新闻。
- `role: "ai_tools"`：AI 工具源，默认会被 `digest_exclude_roles` 排除在每日 digest 主体之外，后续用于 weekly AI tools radar。
- `role: "general"`：通用源，不命中明确规则时不进入 digest 主体。

添加后先运行：

```bash
python3 check_feeds.py
```

如果状态是 `ok`，再运行：

```bash
python main.py
```

## 配置格式

`config.json` 是可选的。如果不存在，程序会使用默认配置：

```json
{
  "output_dir": "output",
  "report_type": "list",
  "max_items_per_category": 8,
  "max_items_per_feed": 3,
  "summary_max_chars": 180,
  "category_order": ["财经股票", "AI方向"],
  "days_back": 2,
  "lookback_hours": 24,
  "filter_stale_by_url_date": true,
  "stale_url_date_tolerance_days": 2,
  "max_core_events": 8,
  "max_market_signals": 6,
  "max_market_signals_per_source": 3,
  "max_watch_items": 5,
  "output_title": "每日早间回顾",
  "include_quick_scan": true,
  "max_quick_scan_items": 10,
  "max_quick_scan_items_per_source": 3,
  "allow_tech_industry_in_market": false,
  "core_event_roles": [
    "breaking_news",
    "general",
    "global_tech_business",
    "ai_industry"
  ],
  "market_signal_roles": [
    "market",
    "global_tech_business",
    "ai_industry"
  ],
  "watch_item_roles": [
    "market",
    "breaking_news",
    "general",
    "global_tech_business",
    "ai_industry"
  ],
  "quick_scan_roles": [
    "breaking_news",
    "market",
    "tech_industry",
    "global_tech_business",
    "ai_industry",
    "general"
  ],
  "quick_scan_exclude_roles": ["ai_tools"],
  "quick_scan_low_value_patterns": [
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
    "融合发展"
  ],
  "core_event_negative_patterns": [
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
    "消费纠纷"
  ],
  "low_value_patterns": [
    "游戏风向标",
    "IPO定价",
    "持股比例",
    "评级汇总",
    "目标价",
    "超豪华",
    "香氛",
    "彩电",
    "大沙发"
  ],
  "digest_exclude_roles": ["ai_tools"]
}
```

字段说明：

- `output_dir`：日报输出目录，默认 `"output"`
- `report_type`：输出类型，默认 `"list"`；可选 `"list"`、`"digest"` 或 `"market_brief"`
- `max_items_per_category`：每个分类最多输出多少条，默认 `8`
- `max_items_per_feed`：每个 RSS 源最多输出多少条，默认 `3`
- `summary_max_chars`：每条新闻摘要最多保留多少字符，默认 `180`
- `category_order`：分类输出顺序，未列出的分类会排在后面
- `days_back`：`list` 模式只保留最近多少天的 RSS 内容，默认 `2`
- `lookback_hours`：`digest` 模式回看最近多少小时的 RSS 内容，默认 `24`
- `filter_stale_by_url_date`：是否根据文章 URL 中的日期过滤旧新闻，默认 `true`
- `stale_url_date_tolerance_days`：URL 日期过滤的容忍天数，默认 `2`
- `max_core_events`：`digest` 模式“昨日最重要的事”最多输出多少条，默认 `8`
- `max_market_signals`：`digest` 模式“昨日市场信号”最多输出多少条，默认 `6`
- `max_market_signals_per_source`：“昨日市场信号”中同一来源最多输出多少条，默认 `3`
- `max_watch_items`：`digest` 模式“今天值得关注的变量”最多输出多少条，默认 `5`
- `output_title`：`digest` 模式标题，默认 `"每日早间回顾"`
- `include_quick_scan`：是否在 `digest` 中输出“快速扫读”，默认 `true`
- `max_quick_scan_items`：“快速扫读”最多输出多少条，默认 `10`
- `max_quick_scan_items_per_source`：“快速扫读”中同一来源最多输出多少条，默认 `3`
- `allow_tech_industry_in_market`：是否允许 `tech_industry` 进入“昨日市场信号”，默认 `false`
- `core_event_roles`：允许进入“昨日最重要的事”的 role，默认 `["breaking_news", "general", "global_tech_business", "ai_industry"]`
- `market_signal_roles`：允许进入“昨日市场信号”的 role，默认 `["market", "global_tech_business", "ai_industry"]`
- `watch_item_roles`：允许进入“今天值得关注的变量”的 role，默认 `["market", "breaking_news", "general", "global_tech_business", "ai_industry"]`
- `quick_scan_roles`：允许进入“快速扫读”的 feed role，默认 `["breaking_news", "market", "tech_industry", "global_tech_business", "ai_industry", "general"]`
- `quick_scan_exclude_roles`：“快速扫读”排除的 feed role，默认 `["ai_tools"]`
- `quick_scan_low_value_patterns`：只作用于“快速扫读”的降噪词，默认过滤体育、个案社会新闻和宣传活动
- `core_event_negative_patterns`：只作用于“昨日最重要的事”的降噪词，默认过滤地方民生个案、普通舆情处置、摊贩/商户经营问题和消费纠纷
- `low_value_patterns`：低价值内容过滤词，在 digest 分流前先执行；标题、摘要、来源和 feed 名命中后不进入 digest 主体
- `digest_exclude_roles`：`digest` 模式默认排除的 feed role，默认 `["ai_tools"]`

部分 RSS 源可能返回旧文章，或给旧文章附上新的 `published` / `updated` 时间。开启 `filter_stale_by_url_date` 后，程序会尝试从文章 URL 中识别日期，例如 `/2022-12/14/`、`/2026/06-11/`、`/2026/06/11/`、`/2026-06-11/`。如果 URL 日期明显早于当前 `lookback_hours` 窗口，并超过 `stale_url_date_tolerance_days` 容忍范围，该文章会被过滤，避免旧新闻混入“过去 24 小时”的日报。被过滤的旧新闻只写入日志，不算抓取失败。

`feeds.json`：

```json
[
  {
    "name": "财经快讯",
    "url": "https://example.com/breaking-news.rss",
    "mode": "all",
    "role": "breaking_news"
  },
  {
    "name": "市场源",
    "url": "https://example.com/market.rss",
    "mode": "all",
    "role": "market"
  },
  {
    "name": "科技产业",
    "url": "https://example.com/tech-industry.rss",
    "mode": "keyword",
    "role": "tech_industry"
  },
  {
    "name": "GitHub Trending Python Daily",
    "url": "https://mshibanami.github.io/GitHubTrendingRSS/daily/python.xml",
    "mode": "keyword",
    "role": "ai_tools"
  },
  {
    "name": "OpenAI News",
    "url": "https://openai.com/news/rss.xml",
    "mode": "all",
    "role": "ai_industry"
  },
  {
    "name": "CNBC Technology",
    "url": "https://www.cnbc.com/id/19854910/device/rss/rss.html",
    "mode": "keyword",
    "role": "global_tech_business"
  }
]
```

`mode` 是可选字段：

- `keyword`：默认值，必须命中 `keywords.json` 才收录
- `all`：只要在时间范围内就收录，不要求命中关键词，适合财经快讯类 RSS 源

`role` 是可选字段，默认 `"general"`：

- `breaking_news`：快讯/电报源，可进入“昨日最重要的事”
- `market`：市场信号源，可进入“昨日市场信号”
- `tech_industry`：科技产业源，只在命中政策、产业、AI、半导体、机器人、新能源等信号时进入
- `global_tech_business`：全球科技商业源，可进入核心事件、市场信号、今日变量和快速扫读
- `ai_industry`：AI 产业源，可进入核心事件、市场信号、今日变量和快速扫读
- `ai_tools`：AI 工具源，默认不进入每日早间回顾主体，后续用于“每周 AI 工具雷达”
- `general`：通用源，不命中明确规则时不进入 digest 主体

`mode` 和 `role` 是两件事：`mode` 决定 RSS 抓取后是否需要关键词命中才收录，`role` 决定文章适合进入 digest 的哪个 section。

`keywords.json`：

```json
{
  "财经股票": ["market", "stock", "economy", "财经", "股票"],
  "AI方向": ["AI", "OpenAI", "LLM", "模型"]
}
```

`feeds.json` 只配置 RSS 源，`keywords.json` 只配置分类和关键词。版面、数量、摘要长度等输出控制都放在 `config.json`。

## v0.3.1 本地定时运行

v0.3.1 只做本地定时自动运行：每天早上调用 `main.py` 生成 `output/daily-news-YYYY-MM-DD.md`。这一版不接推送、不接 AI，也不改变日报筛选规则。

当前验证状态：LaunchAgent 已验证可在 08:00 自动触发，并成功生成当日 Markdown 简报。

v0.3.2 在日报生成成功后增加 Bark 简短通知。推送只包含“日报已生成”和输出文件路径，不发送完整 Markdown 正文。

v0.3.3-alpha 在日报生成成功后额外复制一份 Markdown 到本地 Obsidian iCloud vault，方便 iPhone 上打开 Obsidian 阅读完整日报。这一版还不保证 Bark 点击直达，点击打开留到 v0.3.3-beta。

v0.3.3-beta 在 Bark 通知中增加 Obsidian URI，配置完成后点击通知可直接打开当天日报。

假设项目路径是：

```text
/Users/wp/Projects/自动化简报
```

### 手动测试脚本

先确认虚拟环境和配置文件已经准备好，然后直接运行脚本：

```bash
cd /Users/wp/Projects/自动化简报
chmod +x scripts/run_daily_digest.sh
scripts/run_daily_digest.sh
```

生成结果会写入：

```text
output/daily-news-YYYY-MM-DD.md
```

程序日志仍写入：

```text
daily-news.log
```

### 配置 Bark 推送

在 iPhone 安装 Bark，允许通知，然后复制 Bark 提供的推送地址。可以先用 curl 测试手机是否能收到通知：

```bash
curl "https://api.day.app/你的key/test"
```

复制示例环境文件：

```bash
cp .env.example .env
```

把 Bark 地址写入本地 `.env`：

```text
BARK_URL=https://api.day.app/你的key
```

`.env` 已在 `.gitignore` 中，不要提交，也不要把真实 Bark key 写入 README、示例配置或其他会提交的文件。

如果 `.env` 不存在或 `BARK_URL` 为空，程序会跳过推送，不影响日报生成。Bark 推送失败时也不会让已生成的日报失效，错误会写到 stderr，方便在 launchd err log 中查看。

Bark 推送依赖网络。如果 Mac 早上刚唤醒时网络或 SSL 连接短暂不稳定，脚本会自动重试最多 3 次。若重试后仍失败，可以在网络恢复后手动补发：

```bash
.venv/bin/python scripts/send_bark_notification.py
```

### 配置 Obsidian iCloud 同步

在 `.env` 中配置手机可同步的 Obsidian iCloud 目录：

```text
MOBILE_DIGEST_DIR="~/Library/Mobile Documents/iCloud~md~obsidian/Documents/MindPalace/10 Atlas/Sources/每日早间回顾"
```

路径包含空格或中文时，建议用双引号包裹。真实路径只写在本地 `.env`，不要提交。

同步脚本会在 `main.py` 成功生成日报后，把当天文件复制到该目录，文件名保持：

```text
daily-news-YYYY-MM-DD.md
```

如果 `MOBILE_DIGEST_DIR` 为空，程序会跳过同步，不影响日报生成，也不影响 Bark 推送。同步失败会写到 stderr，方便在 launchd err log 中查看。

手机端需要打开 Obsidian，并等待 iCloud 同步完成后，才能看到完整日报。v0.3.3-alpha 只保证文件会复制到 iCloud 目录，不保证 Bark 通知点击后直接打开 Obsidian 文件。

### 配置 Bark 点击直达 Obsidian

v0.3.3-beta 使用 Obsidian URI 打开当天日报。iPhone 上需要已安装 Obsidian，并且已经打开或登录过 `MindPalace` vault。

在 `.env` 中增加 vault 名称和日报在 vault 内的相对目录：

```text
OBSIDIAN_VAULT_NAME=MindPalace
MOBILE_DIGEST_RELATIVE_PATH="10 Atlas/Sources/每日早间回顾"
```

脚本会根据当天日期生成 Obsidian URI，例如：

```text
obsidian://open?vault=MindPalace&file=10%20Atlas%2FSources%2F%E6%AF%8F%E6%97%A5%E6%97%A9%E9%97%B4%E5%9B%9E%E9%A1%BE%2Fdaily-news-YYYY-MM-DD.md
```

如果 `OBSIDIAN_VAULT_NAME` 或 `MOBILE_DIGEST_RELATIVE_PATH` 没有配置，Bark 仍会发送普通通知，只是不带点击跳转。推送仍只发送简短通知，不发送完整 Markdown。

如果点击通知没有跳转，先确认 iPhone 能正常打开 Obsidian 和 `MindPalace` vault，再确认当天 `daily-news-YYYY-MM-DD.md` 已经通过 iCloud 同步到 `10 Atlas/Sources/每日早间回顾/`。

### 安装 launchd 定时任务

项目提供了示例 plist：

```text
scripts/com.ping.automation-brief.daily.plist.example
```

复制到 `~/Library/LaunchAgents/`：

```bash
mkdir -p ~/Library/LaunchAgents
cp scripts/com.ping.automation-brief.daily.plist.example ~/Library/LaunchAgents/com.ping.automation-brief.daily.plist
```

如果你的项目路径不是 `/Users/wp/Projects/自动化简报`，需要编辑 plist 中的 `ProgramArguments`、`WorkingDirectory`、`StandardOutPath` 和 `StandardErrorPath`。

示例配置为每天早上 08:00 运行：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.ping.automation-brief.daily</string>

  <key>ProgramArguments</key>
  <array>
    <string>/Users/wp/Projects/自动化简报/scripts/run_daily_digest.sh</string>
  </array>

  <key>WorkingDirectory</key>
  <string>/Users/wp/Projects/自动化简报</string>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>/Users/wp/Projects/自动化简报/daily-digest.launchd.out.log</string>

  <key>StandardErrorPath</key>
  <string>/Users/wp/Projects/自动化简报/daily-digest.launchd.err.log</string>
</dict>
</plist>
```

加载任务：

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ping.automation-brief.daily.plist
```

验证是否加载成功：

```bash
launchctl print gui/$(id -u)/com.ping.automation-brief.daily
launchctl list | grep automation-brief
launchctl print gui/$(id -u)/com.ping.automation-brief.daily | grep -E "runs|last exit code|state"
```

立即手动触发 launchd 运行一次：

```bash
launchctl kickstart -k gui/$(id -u)/com.ping.automation-brief.daily
```

### 查看日志

查看程序日志和 launchd 的 stdout/stderr：

```bash
ls output
tail -n 50 daily-news.log
tail -n 50 daily-digest.launchd.out.log
tail -n 50 daily-digest.launchd.err.log
```

查看 launchd 运行状态：

```bash
launchctl print gui/$(id -u)/com.ping.automation-brief.daily | grep -E "runs|last exit code|state"
```

### 睡眠和自动唤醒

v0.3.5 已验证 `pmset` 自动唤醒配合 launchd 可以完成无人值守运行：

```text
Mac 睡眠
→ 07:58 pmset 自动唤醒
→ 08:00 launchd 自动运行
→ scripts/run_daily_digest.sh
→ main.py 生成每日早间回顾 Markdown
→ publish_mobile_digest.py 同步到 Obsidian iCloud
→ send_bark_notification.py 发送 Bark 推送
→ 点击 Bark 通知直达 iPhone Obsidian 当天日报
```

已验证在不合盖、睡眠状态下，Mac 可以自动唤醒并在 08:00 由 launchd 成功运行。该链路不需要 Codex、浏览器或终端保持打开。

v0.4.1.2 增加运行时稳定性保护：`scripts/run_daily_digest.sh` 会在任务启动后自动使用 `caffeinate -dimsu` 持有防睡眠 assertion，直到 `main.py`、Obsidian iCloud 同步和 Bark 推送全部执行完毕。任务结束后 `caffeinate` 会随脚本自动退出，不会常驻。

该修复针对“07:58 已成功唤醒、08:00 launchd 已启动任务，但 Mac 在 RSS 请求期间再次睡眠，导致日报接近 09:00 才完成”的情况。RSS 请求同时增加单次 15 秒超时，保留最多 2 次尝试和失败后等待 3 秒的既有重试策略，避免单个源阻塞几十分钟。

脚本会把 `task`、`main.py`、`publish_mobile_digest.py` 和 `send_bark_notification.py` 的 start/end、exit code 与耗时写入 launchd 现有 stdout/stderr 日志，便于区分任务晚启动、网络请求变慢和 Bark 单独失败。

需要保持：

- Mac 不关机
- 用户账号已登录过
- launchd 任务仍加载
- `pmset` 自动唤醒计划仍存在
- 网络可用
- 项目目录和 `.env` 未移动或删除

可以关闭：

- Codex
- 浏览器
- 终端

Mac 睡眠时若没有配置自动唤醒，不保证 08:00 准点运行。唤醒后 launchd 可能补跑，但不能保证在你打开电脑前已经生成日报。

不建议仅把 `pmset` 唤醒时间提前到 07:45 或 07:30 来处理运行中延迟。2026-06-19 的诊断确认 07:58 已准时唤醒、08:00 已启动任务，核心问题是任务运行期间重新睡眠；应优先依赖脚本的 `caffeinate` 防睡眠保护和 RSS 网络超时。

测试定时任务时，建议在计划时间前唤醒电脑并保持联网。也可以临时保持唤醒 1 小时：

```bash
caffeinate -dimsu -t 3600
```

如果想长期稳定地在早上生成，可以配合 `pmset` 设置自动唤醒。查看现有计划：

```bash
pmset -g sched
```

每天 07:58 唤醒：

```bash
sudo pmset repeat wakeorpoweron MTWRFSU 07:58:00
```

`pmset -g sched` 中看到类似下面的输出，表示每天 07:58 会自动唤醒或开机：

```text
Repeating power events:
  wakepoweron at 7:58AM every day
```

取消自动唤醒：

```bash
sudo pmset repeat cancel
```

### 停用定时任务

停用并移除 plist：

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.ping.automation-brief.daily.plist
rm ~/Library/LaunchAgents/com.ping.automation-brief.daily.plist
```

如果只是修改 plist，需要先 `bootout` 再重新 `bootstrap`。
