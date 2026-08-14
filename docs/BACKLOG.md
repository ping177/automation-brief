# Backlog

本文记录 automation-brief 的后续任务和优先级。这里只描述未来方向，不替代 `docs/PROJECT_STATE.md` 的当前状态，也不记录 Git 快照。

## Numeric version route

新的正式 machine version token 统一使用 numeric 形式：

```text
v0.6.1 — Product Reset + Language Boundary
v0.6.2 — AI Curator Shadow Evaluation
v0.7 — Morning Brief
v0.7.1 — Morning Brief MVP（CLOSED）
v0.7.2 — Production Cutover
v0.7.3 — Morning Brief Long-term Usage Validation（planned）
```

历史条目中的既有 `-alpha` / `-beta` token 是 legacy 事实，保留原样，不回写历史。

## P0 / Next

当前无已知 P0 阻塞。

P0 只用于影响每日 08:00 自动生成、Obsidian iCloud 同步、Bark 推送或 Mac 自动唤醒链路的紧急问题。

### Canonical runtime data migration follow-up

- canonical runtime data 已迁移到 `~/Projects/_project-data/automation-brief/`；`reports/`、`runs/`、`manual-inputs/` 和 metadata-only `migration-records/` 已完成离线校验。
- 迁移前的 `output/`、仓库根 `daily-news.log` 和 `config/holdings.json` 保留且不再是默认来源。不要在本任务之外删除、覆盖或暂存这些 legacy 文件。
- 单独观察一段时间后，评估 legacy 文件清理、下游引用确认和审计 worktree 清理；清理必须是另一个明确任务，并先完成可回滚性检查。

### v0.6.1 Product Reset + Language Boundary

- Phase 1（本轮已完成）落地 Morning Brief 产品合同、未来统一输出结构、多语言输入 / 简体中文 reader-facing 输出边界、AI Curator 职责边界和 legacy / candidate 隔离合同；不修改业务代码、feed 配置、测试或生产入口。
- Phase 2（本轮已完成）实现可选顶层 feed `language` metadata：正式语义为 `zh-CN`、`en`、`und`，缺失、空值或非法值归一化为 `und`；旧配置继续可加载。
- v0.6.1 已正式完成；下一阶段是 v0.6.2 AI Curator Shadow Evaluation，仍只做 real-provider shadow evaluation，不替换生产输出。
- candidate path 读取 `language` 并写入现有 `CandidateArticle.language`；`CuratorRequest.target_language` 固定为 `zh-CN`。语言不进入 `stable_article_id()`、canonical URL、dedup identity 或 legacy keyword gate。
- 当前 16 个 active feed 全部保持启用，不删除、不改变 `mode` / `role`、不新增 `priority`，也不实现 `candidate_only` 配置。英文来源不因语言被删除。
- `keep`、`keep_but_lower_priority`、`candidate_only`、`needs_review` 仅作为未来 source policy 的设计建议，不是本版本 runtime config；当前没有真实 feed health / 重复率验证，因此不改变运行行为。
- v0.6.1 不接真实 AI provider、不切换 daily digest 或 `market_brief` 生产输出、不正式生成 Morning Brief 输出，不删除 legacy runtime data，也不修改 launchd / pmset / Bark / Obsidian 路径。

### v0.6.0-alpha AI Curator shadow foundation — retained constraints

- 使用 `scripts/run_ai_curator_shadow.py --candidate-fixture ... --fixture-response ...` 进行完全离线 shadow preview，不接 Bark / Obsidian / launchd / pmset；真实 RSS shadow 路径仍只能手动显式运行。
- 继续确认 `CuratorRequest` 只包含关键词前 RSS 候选池，不包含 holdings、matched keywords、legacy score、legacy category、行情或持仓涨跌。
- 用 candidate trace 区分 source miss、selection miss、classification miss 和 deduplication miss。
- 真实 provider 的 shadow evaluation 顺延至 v0.6.2，必须先复用现有 contract 和 trace，不替换普通 daily digest 或显式 `market_brief`。

### Legacy v0.5-beta market data verification（不属于 v0.6.1）

- 用显式 `market_brief` 样例验证轻量公开行情源是否稳定返回主要指数和 holdings 个股涨跌。
- 检查成交额字段口径是否稳定；在口径确认前必须显示“数据暂不可用”，不能硬凑。
- 检查 holdings 行业 / 板块只来自 canonical `manual-inputs/holdings.json` 的 `sector` 字段或仓库示例配置，不引入硬编码真实持仓。
- 检查周末或非交易日生成时，报告日期和行情交易日是否分开显示。
- 检查 v0.5-beta.5 后重要新闻的来源限额和融资类型限额是否仍保留足够的高相关政策、业绩与产业事件。
- 检查 v0.5-beta.5 后投资机构名册、榜单、名单等行业资料是否持续降权，政府部门立案 / 查处 / 整治 / 通报等统计是否持续优先归为政策监管。
- 检查 v0.5-beta.5 后 AI 应用新闻不会扩展为算力或数据中心电力，且直接基础设施证据仍能形成对应主题。
- 检查市场或持仓异常是否持续优先于单条创业融资新闻进入风险与今日继续观察，且不出现交易动作建议。
- 继续确认默认 `python3 main.py` 和 `scripts/run_daily_digest.sh` 仍生成普通 digest，不自动推送 market brief。

## P1

### 观察 v0.4.1.2 自动运行稳定性

- 连续观察真实早报运行时间，确认 `pmset` 唤醒、launchd 触发、`caffeinate` 持有防睡眠 assertion、RSS 抓取、Obsidian iCloud 同步和 Bark 推送都稳定。
- 若再次出现延迟，优先查看 launchd stdout/stderr、`daily-news.log`、`pmset -g log` 和输出文件时间。
- 不优先通过单纯提前 `pmset` 唤醒时间解决运行中睡眠问题。

### Legacy `market_brief` 能力（保留、不扩展）

- v0.5-alpha 已完成最小骨架：显式 `market_brief` report type、稳定 Markdown section、可配置 holdings 读取、离线 sample 数据和 smoke test。
- v0.5.1-alpha 已补齐 holdings 本地配置体验：初始化本地 `config/holdings.json`、字段校验、敏感字段 warning 和手动 market brief 生成入口。
- v0.5.2-alpha 已让显式 `market_brief` 复用 RSS 候选新闻，生成重要市场事件、产业催化、风险/反证、今日观察点和 holdings 相关新闻匹配。
- v0.5.3-alpha 已完成新闻质量调优：候选新闻相关度评分、新闻类型分类、弱相关过滤、AI / 算力 / 数据中心电力主题聚合、具体观察理由和高精度 holdings 匹配。
- v0.5.3-alpha quality fix 已继续修正真实样例问题：综合快讯合集降权，IPO/上市不误判宏观或政策，风险/反证和今日观察清单输出可观察变量，主题线索必须带代表新闻，holdings 泛行业词不能单独触发强相关新闻。
- v0.5-beta first stage 已接入轻量公开 A 股行情：显式 `market_brief` 尝试展示主要指数、成交额和 holdings 个股涨跌；行情失败只降级提示，不阻断报告生成。
- v0.5-beta.1 已完成小修：报告日期 / 行情交易日分离，成交额口径未确认时保守显示不可用，今日主线不输出空模板，风险变量去重，IPO / 融资展示限量并过滤弱映射海外 IPO，holdings 增加相对主要指数的轻量观察。
- v0.5-beta.2 已完成行情与新闻融合 polish：新闻主线增加置信度门槛，科创50显著强于其他指数时输出行情层面观察，持仓相对观察细分小幅 / 明显 / 逆势，持仓异常且 RSS 无解释时输出后续观察变量，财报 / 营收 / 利润类新闻归为公司经营 / 财报。
- v0.5-beta.3 已完成新闻事件排序和合并 polish：政策监管新闻优先级提高，同主题证监会再融资 / 定增政策合并展示，IPO / 融资分类更严格，holdings 相关新闻区分明确相关新闻 / 弱相关变量，风险与反证优先覆盖政策监管变量。
- v0.5-beta.3.1 已完成真实样例 hotfix：A 股再融资 / 定增制度变量继续提权，泛“监管”分类收紧，观察理由关键词去重，今日主线增加 `relevance >= 70` 渲染阈值，券商业绩预告排序提高，风险与反证明确覆盖再融资和定增储架发行变量。
- v0.5-beta.5 已完成重要新闻相关度和分类 polish：重要新闻增加同源与融资类型限额，融资/财报按标题主动作处理，投资机构名册 / 榜单降权，政府监管统计优先归政策监管，算力/数据中心电力需要直接证据，风险与今日继续观察优先使用市场和持仓异常。
- 以上 v0.5 系列条目是已完成的显式 `market_brief` 历史能力；它继续作为独立、手动或显式触发的旧入口保留，不代表 Morning Brief 的最终产品定位，也不在 v0.6.1 中继续优化。
- 保持规则输出克制，不把普通科技动态、泛访谈、benchmark 争议和活动宣传误升格为市场信号。
- 持仓观察必须来自 canonical `manual-inputs/holdings.json` 或仓库示例文件，不能把具体持仓硬编码进业务代码。

### Later: deeper market data validation

- 后续再评估更稳定的数据源、行业 / 板块行情、相对强弱和成交结构。
- 继续避免复杂策略、交易动作、真实持仓敏感字段和重依赖。

### RSS 覆盖质量复盘

- 继续观察 v0.4.1 新增的 `global_tech_business` 和 `ai_industry` RSS 源是否提升覆盖而不过度增加噪音。
- 对漏报和误升格使用 `docs/MISSED_CASES.md` 记录，再决定是否调整源、关键词、role 或规则。
- 避免一次性新增大量未经验证的 RSS 源。

## P2

### v0.6.2 AI Curator Shadow Evaluation

- v0.6.0-alpha 已完成 shadow foundation。后续真实 provider 必须实现 `CuratorProvider` 接口，并复用同一 `CuratorRequest` / `CuratorResponse` contract。
- Global Event Curator 只做全球重大事件选择，不接 holdings、行情、legacy score、legacy category 或 matched keywords。
- 真实 provider 不可直接替换 daily digest 或 `market_brief`；必须先输出 shadow preview 和 candidate trace，并保留 legacy fallback。
- AI 不做全网生成、不编造事实、不替代来源链接。
- Phase 4B 已冻结显式 `phase4_live` provider-facing projection：summary cap=`500`、candidate limit=`200`、provider body limit=`200000`；selected-only 真实 DeepSeek shadow 已完成输入/transport 验证，但 output validation 先因 duplicate rejected article ID、随后因 duplicate evidence ID 被拒绝。现在 live 模式采用 selected-only semantics：rejection enumeration 不再收集，provider boundary 将 rejection 字段 canonicalize 为 `[]`，并仅对同一 event 内完全相同的 evidence ID 做保序 exact-dedupe；selected events 的其他 contract 仍严格验证，后续 real shadow 仍需单独授权，不能自动切换生产路径。
- v0.6.2 Phase 4 已关闭：simple single-pass technical shadow boundary、GitHub-only cleanup 与 production isolation 已验证；same-snapshot 内容实验显示 major-event recall / ranking 仍不稳定。不要在 v0.6.2 继续 prompt、模型、source filter、validator 或多阶段实验；下一正式工作是 v0.7 Morning Brief 的独立产品设计，仍不得自动切换生产路径。

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
