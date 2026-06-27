# Backlog

本文记录 automation-brief 的后续任务和优先级。这里只描述未来方向，不替代 `docs/PROJECT_STATE.md` 的当前状态，也不记录 Git 快照。

## P0 / Next

当前无已知 P0 阻塞。

P0 只用于影响每日 08:00 自动生成、Obsidian iCloud 同步、Bark 推送或 Mac 自动唤醒链路的紧急问题。

### v0.5.3-alpha sample review

- 用 `scripts/run_market_brief.sh` 或 `python3 main.py --report-type market_brief --output output` 生成一份真实 RSS 样例。
- 检查 relevance score、新闻类型、AI / 算力 / 数据中心电力主题聚合、弱相关过滤和 holdings 精确匹配是否符合预期。
- 若样例仍出现误升格或漏报，先记录到 `docs/MISSED_CASES.md`，再补离线 fixture 回归。

### v0.5-beta real A-share market data first stage verification

- 用显式 `market_brief` 样例验证轻量公开行情源是否稳定返回主要指数和 holdings 个股涨跌。
- 检查成交额字段是否稳定；缺失时必须显示“数据暂不可用”，不能硬凑。
- 检查 holdings 行业 / 板块只来自 `config/holdings.json` 的 `sector` 字段或示例配置，不引入硬编码真实持仓。
- 继续确认默认 `python3 main.py` 和 `scripts/run_daily_digest.sh` 仍生成普通 digest，不自动推送 market brief。

## P1

### 观察 v0.4.1.2 自动运行稳定性

- 连续观察真实早报运行时间，确认 `pmset` 唤醒、launchd 触发、`caffeinate` 持有防睡眠 assertion、RSS 抓取、Obsidian iCloud 同步和 Bark 推送都稳定。
- 若再次出现延迟，优先查看 launchd stdout/stderr、`daily-news.log`、`pmset -g log` 和输出文件时间。
- 不优先通过单纯提前 `pmset` 唤醒时间解决运行中睡眠问题。

### 市场投研晨报方向

- v0.5-alpha 已完成最小骨架：显式 `market_brief` report type、稳定 Markdown section、可配置 holdings 读取、离线 sample 数据和 smoke test。
- v0.5.1-alpha 已补齐 holdings 本地配置体验：初始化本地 `config/holdings.json`、字段校验、敏感字段 warning 和手动 market brief 生成入口。
- v0.5.2-alpha 已让显式 `market_brief` 复用 RSS 候选新闻，生成重要市场事件、产业催化、风险/反证、今日观察点和 holdings 相关新闻匹配。
- v0.5.3-alpha 已完成新闻质量调优：候选新闻相关度评分、新闻类型分类、弱相关过滤、AI / 算力 / 数据中心电力主题聚合、具体观察理由和高精度 holdings 匹配。
- v0.5.3-alpha quality fix 已继续修正真实样例问题：综合快讯合集降权，IPO/上市不误判宏观或政策，风险/反证和今日观察清单输出可观察变量，主题线索必须带代表新闻，holdings 泛行业词不能单独触发强相关新闻。
- v0.5-beta first stage 已接入轻量公开 A 股行情：显式 `market_brief` 尝试展示主要指数、成交额和 holdings 个股涨跌；行情失败只降级提示，不阻断报告生成。
- 明确早报的投研定位：先服务每日宏观、市场信号、AI 商业化、支付基础设施、全球科技商业和持仓相关观察。
- 保持规则输出克制，不把普通科技动态、泛访谈、benchmark 争议和活动宣传误升格为市场信号。
- 持仓观察必须来自 `config/holdings.json` 或示例文件，不能把具体持仓硬编码进业务代码。

### Later: deeper market data validation

- 后续再评估更稳定的数据源、行业 / 板块行情、相对强弱和成交结构。
- 继续避免复杂策略、交易动作、真实持仓敏感字段和重依赖。

### RSS 覆盖质量复盘

- 继续观察 v0.4.1 新增的 `global_tech_business` 和 `ai_industry` RSS 源是否提升覆盖而不过度增加噪音。
- 对漏报和误升格使用 `docs/MISSED_CASES.md` 记录，再决定是否调整源、关键词、role 或规则。
- 避免一次性新增大量未经验证的 RSS 源。

## P2

### AI 筛选 / rerank 方案评估

- 可评估轻量架构：RSS 候选新闻先由现有规则收集，再由 AI rerank 辅助排序和解释。
- AI 只应做候选新闻重要性判断、section 建议和 reason 草稿，不做全网生成、不编造事实、不替代来源链接。
- DeepSeek 或其他 AI 服务不可用时，应 fallback 到现有规则版日报。

### missed coverage 闭环

- 将漏报、重复、误升格、误降级案例稳定记录到 `docs/MISSED_CASES.md`。
- 每次规则调整都尽量补一个离线 smoke 样本或 section 组装级样本。
- 定期复盘 missed case 是否指向 source gap、keyword gap、role gap、rule gap 或未来 AI rerank gap。

### Bark / Obsidian 体验优化

- 继续保持 Bark 只推送简短通知，不推送完整 Markdown。
- 优化失败诊断文案和手动补发说明。
- 观察 iCloud 同步延迟，必要时补充排查 checklist，而不是把本机绝对路径写进代码。

## P3

### weekly AI tools radar

- `ai_tools` 继续默认排除 daily digest。
- GitHub Trending 不适合直接进入每日重点内容，可作为低频 AI/tool 观察源。
- 后续如做 weekly AI tools radar，应单独设计输出结构和筛选规则。

### launchd / pmset 可观测性增强

- 如真实运行仍偶发异常，可考虑补充更明确的 launchd 日志说明或诊断命令。
- 不优先修改 plist；需要修改时应先说明原因和影响范围。

### 配置文档整理

- 后续可把 `feeds.json`、`keywords.json`、`config.json` 的字段说明从 README 拆到独立配置文档。
- README 保持入口和常用运行说明，避免继续膨胀。
