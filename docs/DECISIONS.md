# Decisions

本文记录 automation-brief 的长期产品、架构和工作流决策。只记录相对稳定的判断；短期任务放在 `docs/BACKLOG.md`，过程记录放在 `docs/DEVLOG.md`。

## Generation 1 Morning Brief 产品合同（legacy production）

本节保留当前 Generation 1 production 的历史产品合同。v1.0 不携带 Holdings，Market 仅是未来 optional capability；v1.0 以本文后部的 `v1.0 Event-driven Morning Brief` 决策和三份 canonical contract 文档为准。

### 个人早间简报定位

- 决策：automation-brief 的最终 reader-facing 产品定位是个人早间简报（Morning Brief）。目标是让读者每天早上约 5 分钟了解昨晚世界发生了什么、全球市场发生了什么、今天哪些变量值得继续关注。
- 不定位为 AI 投研助手、A 股机会发现系统、股票推荐工具、新闻到股票机会映射器或每日投资观点生成器。
- 未来统一结构为“昨夜最重要的事 / 隔夜市场 / 今日值得关注 / 持仓异常（仅异常时出现）”。“今日值得关注”最多 3 条，不是市场预测；“持仓异常”不得输出成本、仓位、盈亏或买卖建议。
- 影响：v0.6.1 冻结产品与语言合同并完成最小 candidate wiring，不正式生成 Morning Brief 输出，不删除 daily digest 或 `market_brief`，不切换生产输出。

### Numeric version route

- 决策：从本轮起新的正式 machine version token 使用 numeric 形式：`v0.6.1` Product Reset + Language Boundary、`v0.6.2` AI Curator Shadow Evaluation，以及 `v0.7` Morning Brief 总里程碑下的 `v0.7.1` Morning Brief MVP（CLOSED）、`v0.7.2` Production Cutover（CLOSED）、`v0.7.3` Morning Brief Long-term Usage Validation（CLOSED）、历史记录中的 `v0.7.4` Legacy Product Retirement & Capability Consolidation（SUPERSEDED / replaced by v1.0 plan）和下一代 `v1.0` Event-driven Morning Brief（Architecture + Core Data + Runtime / Failure Contract Freeze COMPLETE；v1.x implementation roadmap FROZEN；next task `v1.1`）；后续不再新增字母阶段标签作为正式阶段命名。
- 影响：既有 `v0.6.0-alpha`、`v0.5-beta` 等历史 token 保留为事实，不重写历史 Version Index；未来文档只使用 numeric route，不再新增带 alpha 后缀的同名路线 token 或字母阶段标签。

### 多语言输入与简体中文输出

- 决策：RSS 输入允许多语言，最终 reader-facing Curator 文本统一使用简体中文。
- feed 对象可有可选顶层 `language`：`zh-CN` 表示简体中文，`en` 表示英文，`und` 表示未知或未声明；缺失、空值或非法值归一化为 `und`。
- `CandidateArticle.language` 表示 source language snapshot；`CuratorRequest.target_language` 表示最终读者语言，产品合同固定为 `zh-CN`。不新增重复的 `source_language` 或 `output_language` 字段。
- 语言只属于候选元数据，不进入 `stable_article_id()`、canonical URL、dedup identity，也不改变 legacy keyword gate。

### Legacy / Candidate 隔离

- 决策：RSS 先进入共享的字段标准化、时间窗口和去重边界，再分流为 legacy pipeline 与 candidate pipeline。
- 语言 metadata 只沿 `feed -> normalize -> CandidateArticle.language -> CuratorRequest` 传播，不进入 `NewsItem`、legacy keyword gate、legacy sorting、daily digest Markdown、`market_news.py` 或 market brief renderer。
- 影响：v0.6.1 及后续 candidate contract 改动必须以 legacy production behavior unchanged 为回归硬要求。

### AI Curator 职责边界

- 决策：Curator 只负责候选新闻筛选、重复事件聚合、重要性排序、多语言理解、简体中文标题与摘要、来源追踪和低价值候选拒绝。
- Curator 不负责行情获取或计算、持仓收益计算、投资建议、目标价、市场方向预测、缺失事实推断或程序性的时间 / 数值计算。
- 所有 reader-facing Curator 文本必须基于 evidence、使用简体中文、不生成交易建议，并保留 evidence article id 可追溯性。

## 输出与使用入口

### 每日 08:00 生成早间回顾

- 决策：每日早间回顾以 08:00 本地自动运行为目标。
- 理由：早上阅读场景稳定，适合在用户开始一天前完成 RSS 抓取、简报生成、Obsidian 同步和 Bark 推送。
- 影响：`launchd` 定时任务保持 08:00；`pmset` 自动唤醒用于提前唤醒 Mac，但不替代运行期间的防睡眠保护。

### Reader-facing 使用简体中文输出

- 决策：面向个人阅读的日报和未来 Curator 输出默认使用简体中文组织标题、栏目和说明。
- 理由：减少早晨扫读成本，并保持中文财经、科技和全球新闻在同一阅读语境中。
- 影响：即使 RSS 原文为英文，栏目和 reason 仍应尽量使用简体中文表达。

### Obsidian iCloud 是主要阅读入口

- 决策：完整 Markdown 日报同步到 Obsidian iCloud，作为手机端主要阅读入口。
- 理由：Markdown 可保存、可搜索、可复盘，iCloud 能连接 Mac 自动生成和 iPhone 阅读。
- 影响：`.env` 中配置本机 Obsidian 目录；真实路径和个人 vault 信息不写入代码或提交文件。

### Bark 是手机推送入口

- 决策：Bark 只发送简短完成通知和 Obsidian 跳转，不发送完整日报正文。
- 理由：推送渠道适合提醒和入口，不适合承载长内容，也避免把完整日报塞进通知服务。
- 影响：Bark 失败不阻断日报生成；推送重试和错误日志用于提升稳定性。

## 自动化链路

### launchd + pmset 作为 Mac 本地自动化链路

- 决策：使用 `launchd` 负责 08:00 定时运行，使用 `pmset` 负责睡眠状态下自动唤醒。
- 理由：这是 macOS 本地自动化的低成本方案，不依赖 Codex、浏览器或终端保持打开。
- 影响：需要保持 Mac 不关机、用户账号已登录过、launchd 任务已加载、`pmset` 计划存在、网络可用、项目目录和 `.env` 未移动或删除。

### 运行期间使用 caffeinate 防止再次睡眠

- 决策：`scripts/run_daily_digest.sh` 在任务运行期间持有 `caffeinate -dimsu` 防睡眠 assertion。
- 理由：2026-06-19 已验证 07:58 唤醒和 08:00 启动成功，但 Mac 在 RSS 请求期间重新睡眠，导致日报接近 09:00 才完成。
- 影响：不建议单纯提前 `pmset` 到 07:45 或 07:30；核心是保证任务已启动后不会在链路完成前睡眠。

## 运行数据与迁移

### Canonical runtime data root

- 决策：运行时报告、日志、AI Curator shadow artifacts 和本地 holdings 统一放在 `~/Projects/_project-data/automation-brief/`；仓库只保存代码、配置模板和文档。
- 理由：把可增长、可变且可能含本地信息的运行数据与 Git 工作树分离，同时让默认路径在不同机器上通过 `Path.home()` 保持可移植。
- 影响：路径解析优先使用显式 CLI / 函数注入，其次读取 `AUTOMATION_BRIEF_DATA_ROOT`，最后使用 home 下 canonical 默认值。`--output`、`--output-dir` 和 `--holdings` 仍可覆盖默认值；tracked `config.json` 的 `output_dir: "output"` 仅作为兼容 token 映射到 `reports/`。
- Canonical tree：`reports/`、`runs/daily-news.log`、`runs/ai-curator-shadow/`、`manual-inputs/holdings.json` 和 metadata-only `migration-records/`。

### Legacy runtime data retention

- 决策：迁移后的 `output/`、仓库根 `daily-news.log` 和 `config/holdings.json` 暂不删除、不覆盖，保留为 legacy 证据和回滚参考，但不再作为默认运行时来源。
- 理由：先完成路径切换、下游读取验证和一段观察期，再单独评估清理，避免把迁移和不可逆删除绑定在一起。
- 影响：未来清理必须是独立任务，先核对 Obsidian / mobile / Bark 下游、launchd 运行记录和 audit worktree 状态；迁移记录只保留元数据，不记录 holdings 内容、报告正文、secrets 或 provider payload。

## 信息筛选

### RSS + 规则筛选是当前基础

- 决策：当前日报以 RSS 候选池和可解释规则筛选为基础，不调用 DeepSeek、Tavily 或付费搜索 API。
- 理由：规则版成本低、稳定、可解释，适合本地自动化先跑通。
- 影响：重要性判断通过 source role、关键词、section 规则、去重和 missed case 回归持续改进。

### v0.6.2 再评估 AI shadow provider

- 决策：v0.6.2 才评估真实 AI provider 的 shadow evaluation，复用 `CuratorProvider`、`CuratorRequest`、`CuratorResponse` 和 candidate trace；不做全网 AI 生成晨报。
- 理由：v0.4.1 扩源后，规则对重要性和重复内容的判断成本上升，AI 可作为候选新闻排序和解释辅助。
- 影响：AI 只能基于已有 RSS 字段和来源链接判断，不编造事实；AI 不可用时必须 fallback 到规则版日报。

### Phase 4B Provider-facing projection uses an explicit input mode

- 决策：Phase 4 live shadow 只能通过显式 `--input-mode phase4_live` 选择；Provider-facing summary cap 和 `200 / 200000` hard limits 不从 candidate 数量或其他运行状态自动推断。Phase 3B fixture gate 保持独立的 `phase3b_fixture` mode 与 `2 / 4096` limits。
- 理由：不同阶段的 limits 具有不同的安全语义；自动猜 mode 会让 live input 意外落入 fixture gate，或让 fixture contract 悄然改变。
- 影响：projection 只创建 immutable Provider-facing copy，并在 exact body serialization 后执行 body limit check；`request.json` 保存模型实际看到的 projected request，原始 live snapshot 保持独立完整，不连接 production daily digest / `market_brief`。

### Phase 4 real-output collection-invariant prompt alignment

- 决策：沿用现有 `CuratorResponse` validator 的 collection invariants，在 system prompt 中明确 input article membership、event/rejection/evidence uniqueness、selected/rejected disjoint，以及同一 article 多个 reject reason 只输出一条最合适 rejection。
- 理由：连续两次真实 shadow 的输入、projection、body limit 和 transport 均正常，失败都发生在模型的 rejection bookkeeping collection invariant；prompt 只描述了 schema 和 ID membership，没有把 validator 的集合约束完整暴露给模型。
- 影响：模型输出继续由 validator fail closed；不修改 validator、domain schema、自动 dedupe、Phase 4B limits、provider retry 或 production path。

### Phase 4 live selected-only Curator semantics

- 决策：仅对显式 `--input-mode phase4_live` 采用 selected-only semantics。Provider 只负责选择和聚合重要 events 及 evidence；`rejected_article_ids` 固定 canonicalize 为 `[]`，不要求模型枚举未选 candidate 或 rejection reason。
- 理由：同一 live snapshot 已连续两次在 rejection bookkeeping 上触发 `duplicate_rejected_article_id`；未被 event evidence 使用的 candidate 可由程序直接推导，LLM 维护大规模 rejection ID list 没有产品价值。
- 影响：在现有 `CuratorResponse` validator 前的局部 phase4_live provider boundary 丢弃非权威 rejection 字段，不 dedupe、不选择 reason、不保存 rejection list；selected event 的 schema、enum、event/evidence uniqueness、known evidence、report date、content policy、finish_reason 和 JSON parsing 仍严格 fail closed。default/full 与 Phase 3B fixture behavior 保持不变，artifact `response.json` 保存 canonical empty list，`review.md` 明确写明 rejection enumeration 未收集。

### Phase 4 live exact duplicate evidence canonicalization

- 决策：仅对显式 `--input-mode phase4_live`，在现有 provider canonicalization boundary 中对同一 event 的 `evidence_article_ids` 删除完全相同的重复值，保留首次出现顺序；不同 event 之间复用同一 evidence ID 继续允许。
- 理由：selected-only evidence references 是 set-like；完全相同的重复值没有语义增量，且已在第二次 selected-only live shadow 触发 `duplicate_evidence_article_id`。这是局部产品 canonicalization，不是通用 parser cleanup 或 validator 放宽。
- 影响：canonicalization 后仍由现有 validator 严格检查 known evidence、非空 evidence、event ID、schema、enum、report date、content policy、finish reason 和 JSON parsing；unknown ID、不同值、不同 event、空列表均不被修正。default/full 与 Phase 3B fixture 的 duplicate evidence contract 保持 fail closed。

### Phase 4 live editorial quality policy and narrow snapshot gate

- 决策：仅对显式 `phase4_live` instruction 增加集中编辑策略，统一定义 importance ranking、direct evidence、attribution preservation、confidence / uncertainty calibration 和 event grouping。第二次 same-snapshot quality validation 证明 attribution / uncertainty 已改善，但 5 条容量仍造成 recall pressure 和跨 news-peg 合并，因此 Phase 4 live runner 的 mode-scoped 默认容量调整为 `max_events=10`；domain、default/full 与 Phase 3B 默认仍为 5。
- 理由：159-candidate content audit 证明 technical pipeline 正常，但原 instruction 只有泛化的 “important events” 要求，无法约束 background 占位、主题相关 evidence 污染、单方声明事实化、机械式 `high + []` 和过度聚合。
- 影响：新增绑定 snapshot SHA-256 的紧凑 gold reference 和离线 evaluator，只检查人工明确的 capacity-scoped must-include、priority/background、forbidden evidence、attribution-required 与 uncertainty-expected 条件；它不读取新闻正文、不进入 provider request / production validator，不做 embedding、semantic similarity、事实核查或加权评分。Phase 4 prompt 以一个具体 news peg 为 event 边界，禁止为节省容量合并可独立成标题的行动。schema、validator、selected-only semantics、projection、transport、retry、artifact 和 production paths 均不变。

### v0.7 Morning Brief phase4_live 容量调整为 20

- 决策：Morning Brief（内部 `overnight_brief`）使用共享 `phase4_live` `max_events=20`；default/full、fixture 和 Phase 3B 的默认容量仍为 5。此前 same-snapshot sensitivity 的 10/15/20 运行仅作为历史决策依据保留，不属于正式 runtime。
- 理由：同一份 154-candidate snapshot 的 sensitivity 显示 10 存在明显容量挤压，15 没有形成稳定折中，而 20 的两次独立 DeepSeek Flash 运行都改善了重大事件覆盖。
- 影响：20 是最多允许的 CuratedEvent 数，不是补满目标；Flash 在边际事件排序上仍可能波动。该决定不新增 prompt、schema、classification、ranking/scoring、dedupe、feed 或 AI stage。

### v0.7 Morning Brief reader-facing rename

- 决策：reader-facing 产品名称统一为 `Morning Brief` / `早间简报`；Markdown 标题使用“早间简报”，canonical 文件名使用 `morning-brief-YYYY-MM-DD.md`。
- 影响：稳定 machine identifier `report_type="overnight_brief"`、Python module/function/internal symbol、Curator artifact run 前缀和既有显式 CLI 均保持不变；不新增 alias 或 compatibility layer。

### v0.7 Morning Brief watch composition

- 决策：AI success 时，“今日值得关注”不再机械取 CuratedEvent 前三个 `uncertainties`；仅投影已有 Curator `importance in {must_know, important}` 且属于政策、市场、能源或地缘类别的 unresolved variables，再按既有顺序复用结构化行情信号和无 RSS 解释的持仓异常，最多 3 条，不足不补。
- 影响：不新增 uncertainty 语义模型、keyword/template rule、schema 或第二次 AI 调用；provider fallback、market data 和 holdings anomaly trigger 保持原路径。

### v0.7 Morning Brief reader-facing importance boundary

- 决策：AI success 的 Morning Brief reader-facing event 仅展示现有 `importance` enum 中的 `must_know` 和 `important`；`background` 不进入主新闻、市场新闻、今日值得关注或持仓相关新闻投影。
- 影响：过滤仅发生在 Morning Brief writer projection；canonical CuratorResponse artifact 继续完整保存包括 `background` 在内的 validated events。`max_events=20`、schema、enum、provider、validator 和 fallback 均不变，不新增阈值或评分系统。

### GitHub Trending 不直接作为每日重点内容

- 决策：GitHub Trending 和 `ai_tools` 不适合直接进入 daily digest 的重点栏目。
- 理由：工具、仓库和项目热度更适合低频观察，直接进入每日早报容易稀释宏观、市场和商业化信号。
- 影响：`ai_tools` 默认排除 daily digest，可作为未来 weekly AI tools radar 的来源。

### 市场和持仓观察对象必须可配置

- 决策：持仓、关注公司、行业和资产观察对象应从可编辑配置读取，不能硬编码到业务逻辑。
- 理由：市场和持仓观察对象会变化，硬编码会让个人观察范围难以维护，也增加误提交敏感信息的风险。
- 影响：未来新增持仓观察或 watchlist 时，应设计独立配置或使用现有配置扩展，并避免在代码中写死具体持仓。

## 文档分工

- `README.md`：项目入口、运行方式、文档入口。
- `docs/PROJECT_STATE.md`：给 project-command-center 展示的人工状态，不记录 Git branch、latest commit 或 working tree。
- `docs/BACKLOG.md`：未来任务和优先级。
- `docs/DEVLOG.md`：开发过程记录和重要验证记录。
- `docs/TESTING.md`：测试命令、smoke checklist 和验收记录。
- `docs/DECISIONS.md`：长期产品、架构和工作流决策。
- `docs/EVENT_DRIVEN_MORNING_BRIEF_ARCHITECTURE.md`：v1.0 Event-driven Morning Brief 的 canonical architecture contract。
- `docs/MISSED_CASES.md`：missed coverage、漏报案例和质量追踪。
## 2026-08-12 — Phase 4 two-pass experiment is abandoned

- Decision: revert explicit `phase4_live` to its simple one-call Curator path and remove the internal selection-plan / synthesis boundary.
- Rationale: real two-pass validation did not improve the morning-brief product: must-include coverage fell from 4/8 to 3/8, while duplicate events, incorrect grouping, irrelevant evidence selection, and a category regression remained. Pass B containment alone did not justify a second provider call or the additional implementation surface.
- Impact: retain Phase 4 scoped capacity, projection/limits, selected-only semantics, the general editorial policy, and the narrow final-response gold evaluator. Do not add further stages, semantic validators, scoring systems, or orchestration to address this result; reassess single-pass strategy or model selection before any further live validation. Default/full, Phase 3B, production daily digest, and `market_brief` remain unchanged.

## 2026-08-13 — v0.6.2 Phase 4 closeout

- Decision: close Phase 4 with the simple single-pass Flash shadow path, retaining only the exact `GitHub Trending Python Daily` exclusion from the Phase 4 daily main pool.
- Rationale: real-provider technical boundaries succeeded. Flash same-snapshot recall remained about 4/8 known major events; Pro improved only marginally at materially higher cost, while GitHub-only cleanup improved grouping/evidence without improving recall. Further prompt, model, source-filter, validation, or orchestration tuning has no demonstrated product value.
- Impact: remove the one-time Pro runtime profile; historical artifacts retain their recorded model. Keep the gold/evaluator as offline development regression only. AI Curator remains shadow-only and production daily digest / `market_brief` remain unchanged. v0.7 starts only under a separate task.

## v0.7.1 Morning Brief explicit Curator projection and fallback

- 决策：显式手动 `overnight_brief` 复用 v0.6.2 已冻结的 `phase4_live` single-pass Curator；AI success 时 CuratedEvent 是 reader-facing 新闻的唯一选择、事件聚合和简体中文文本来源，现有行情与持仓异常能力继续由本地模块负责。
- 理由：v0.7.1 真实验收显示 legacy reader-facing 新闻会重新引入重复、英文摘要和 Market Brief 模板化表达；CuratorResponse 已有 canonical title、summary、category 和 evidence ids，不需要新增 schema、translation pipeline 或第二次 AI 调用。
- 影响：`financial_markets` / `energy_commodities` 与其他 event 只做既有 category 的互斥 section 投影；evidence ids 回查 CandidateArticle source/link。Provider 技术失败时整份新闻层回退到 legacy renderer，不混合、不投票、不补位。此路径仅由显式 `overnight_brief` 触发，默认 `digest`、显式 `market_brief`、feeds、launchd、pmset、Bark 和 Obsidian 保持不变；在 v0.7.2 Production Cutover 获得明确授权前不做生产切换。

## v0.7.2 Production routing and credential boundary

- 决策：复用同一个 `run_daily_digest.sh`、LaunchAgent label、08:00 schedule、working directory、日志、Obsidian 和 Bark 链路；shell 只接受 `digest` / `overnight_brief`，无参数默认 `digest`，并把同一 report type 显式传给所有 downstream。仓库 plist example 仅追加 `overnight_brief` 参数，不引入 feature flag。
- 凭据：Morning Brief 优先使用已有进程环境中的 `AUTOMATION_BRIEF_CURATOR_API_KEY`；缺失时仅从项目根目录 `.env` 以非执行方式读取并 export 到当前任务进程。`.env` 缺失或 key 缺失不泄露或中断任务，继续进入既有 `missing_api_key` whole-layer fallback。
- 影响：Obsidian/Bark 对 `digest` 使用 `daily-news-*`，对 `overnight_brief` 使用 `morning-brief-*`，未知 report type fail closed。用户已于 2026-08-15 完成人工 Terminal acceptance，确认实际 LaunchAgent、真实 provider、Obsidian 和 Bark 链路成功；rollback 只需恢复 plist 的无参数 shell 调用。

## v0.7.4 Legacy Product Retirement & Capability Consolidation（历史记录，实施路线已被 v1.0 取代）

- 决策：只有 v0.7.3 真实晨间长期使用证明 Morning Brief 稳定后，才开始 v0.7.4。最终 reader-facing 产品只保留 Morning Brief；Daily Digest 和 Market Brief 作为独立产品正式退役。
- 目标架构：`RSS / feeds → CandidateArticle → single-pass AI Curator → CuratedEvent → Morning Brief → canonical report → Obsidian / Bark`，并由独立、中性的 shared market data、holdings anomaly、technical whole-layer fallback 和 delivery capabilities 提供支撑。
- read-only audit 已确认 Morning 当前仍依赖 `main.py` 中的 legacy fallback projection / digest summary-time helpers，以及 `market_brief_writer.py` 中的公共行情与持仓渲染 helpers；这些依赖必须先完成最小迁移，不能把旧文件名直接当作可删除的 product-only surface。
- 约束：本轮只冻结边界，不修改 Python、shell、plist、tests、config、runtime data 或 production behavior；不预先决定替代文件名、模块名、package hierarchy 或新的 orchestration。v0.7.3 期间保留 Daily rollback；v0.8 不提前冻结内容。
- 完成条件：删除旧产品容器后，Morning 仍完整支持 AI Curator、market context、holdings anomaly、provider technical fallback、canonical writer、Obsidian 和 Bark；只有确认无消费者的旧 entry、writer、routing、tests、docs surface 才可删除。

状态说明：上述 v0.7.4 决策及其 read-only audit 结论保留为历史事实，但不再作为独立实施路线执行。v1.x 重新定义 legacy retirement 的时机：必须在 v1.8 完成 shadow / parallel validation、v1.9 完成 production cutover 后，才在 v1.10 进入旧产品 retirement。不得删除或改写 v0.7.4 的历史记录，也不得在 v0.7.3 baseline 期间提前退役旧 production surface。

## v1.0 Event-driven Morning Brief

- 决策：下一代产品世代使用单一 numeric token `v1.0 — Event-driven Morning Brief`。v1.0 是完整架构重建里程碑，不创建 `v1.0-alpha`、`v1.0-beta`、`Phase A/B/C` 或其它阶段型版本 token；内部过程只使用 narrative stages。
- 核心架构：Article 是输入，Event 是核心业务对象，Brief 是输出。冻结主链为 Sources → collection → normalization → Article-level deterministic deduplication → event-level clustering → relative event selection → post-selection classification → event writing → deterministic Brief rendering → delivery；`orchestrator` 与 `llm_gateway` 是基础设施边界。
- 职责边界：Article dedup 与 Event clustering 明确分离；event clustering 初期优先 local embedding；selector 不使用 numeric scoring / complex ranking formula；classification 发生在 selection 之后；category 不影响 importance；Evidence 作为 Article provenance 保留，不作为独立 AI 模块。
- 模型边界：collection、normalization、dedup、schema validation、provenance、rendering、delivery 和 orchestration 由代码负责；local semantic model 初期负责 clustering；LLM 主要负责 selection、classification 和 writing。模块职责拆分与物理 API call 次数分离，允许合理 batch，但不重新形成“大 Curator”。
- 故障边界：v1.0 遵循 `Fail locally, not globally`；StageResult 状态由 output/failure invariant 机械推导；合法 empty 不等于 technical failure；单个 Event 或 batch failure 只影响最小合理单元并保留 valid siblings。
- capability 边界：Holdings 不进入 v1.0；Market 仅作为未来 optional capability，不在本次设计 Market v2；v1.0 开发期间不增加与核心 Event pipeline 无关的新功能。
- 迁移边界：v0.7.3 保留为 Generation 1 Morning Brief 七天真实使用验证 baseline。v0.7.3 与当前旧 production pipeline 在 v1.x 开发期间保持可运行；只有完成 offline / snapshot、shadow / parallel validation、production acceptance 和 cutover 后，才执行 legacy retirement。
- dependency / migration route：READ-ONLY Dependency Audit 已完成。正式路线选择 preserve mature infrastructure + rewrite news core；保留成熟 collection、identity、path resolver、provider transport、artifact 和 delivery 基础，替换横跨 `main.py`、single-pass Curator、legacy rules 和 writer 的 news core。当前没有可安全 `DELETE NOW` 的 legacy tracked file。
- Core Data Contract：使用一个 canonical Event，由 selector、classifier、writer 各自返回 immutable derived value，不建立三套重复 stage object。Article 与 EventCandidate identity deterministic；selector 只表达入选与相对顺序，不保留 importance tier；classifier 使用 descriptive category vocabulary 且 category 不影响 selection；writer 只拥有 `title_zh`、`summary_zh`、`why_it_matters_zh`。classification 与 writing 是独立 optional sections，classifier failure 不阻止 writer。
- Evidence / runtime：Evidence 是 Article 的 deterministic projection，Article 是 source/URL/published_at/identity 唯一 authority。LLM 每个 physical request 最多两次 bounded attempts；selector 是独立 global logical operation，classifier / writer 只在各自 stage 内 batch，禁止 cross-stage response coalescing。Brief generation 与 delivery outcome 分离。
- Fallback：pre-cutover 继续由 Generation 1 production 提供正式输出，v1.8 shadow 不影响读者；v1.9 cutover 后可发布 durable valid complete/partial v1.x Brief，但 generation failure 不自动调用 legacy ranking、classification、Curator、writer 或 raw English fallback。Generation 1 rollback 只能是显式、人工、可审计的 routing decision。
- 详细 contract：模块职责与 narrative stages 记录在 `docs/EVENT_DRIVEN_MORNING_BRIEF_ARCHITECTURE.md`；唯一 canonical core data contract 记录在 `docs/EVENT_DRIVEN_MORNING_BRIEF_DATA_CONTRACT.md`；唯一 canonical runtime / failure contract 记录在 `docs/EVENT_DRIVEN_MORNING_BRIEF_RUNTIME_CONTRACT.md`。本决策不要求创建对应 Python 文件或开始 implementation。

## v1.x Implementation Version Roadmap（FROZEN）

本路线是 v1.0 Event-driven Morning Brief 同一产品世代内的 implementation milestones，不是新的产品架构或第二套版本治理。v1.0 的 `completed / closed` 指 Architecture、Dependency、Core Data、Runtime / Failure 四项治理合同基线已关闭；现有 canonical Architecture 文档中的最终 narrative `v1.0 CLOSED` 仍由 production cutover 与 legacy retirement 的完成条件表达，numeric closeout 对应 v1.10。这个映射不创建第二个 version token 体系。

`v1.9.1`、`v1.9.2` 与 `v1.9.3` 是 v1.9 之后单独追踪的 numeric correctives，不改变上述 v1.0→v1.10 主路线；具体状态与边界在各自小节记录。

### v1.0 — Event-driven Morning Brief architecture / governance baseline（COMPLETED / CLOSED）

- Architecture Freeze
- READ-ONLY Dependency Audit
- Core Data Contract Freeze
- Runtime / Failure Contract Freeze

### v1.1 — Canonical Domain & Runtime Foundation

- Article、EventCandidate、Event
- classification / writing sections、Brief
- StageResult、ItemFailure
- stable identity、datetime/window validation
- serialization/deserialization
- offline unit tests

### v1.2 — Deterministic Ingest（COMPLETED / CLOSED）

- collector、normalizer、article_dedup
- 目标：`Sources → canonical Article`

### v1.2 implementation closeout

- 决策：v1.2 以 side-by-side `collector.py`、`normalizer.py`、`article_dedup.py` 落地；collector 输出 source-scoped raw batches，normalizer 通过唯一的 canonical `Article.from_source` 生成 Article，dedup 只做 canonical URL / stable article ID exact dedup。
- 决策：成功但 0 entries 的 source 仍保留为空 batch；因此 A 成功空 batch、B technical failure 可以表达为 `StageResult.partial`，同时展开给 normalizer 的 raw entries 仍为空。
- 决策：timestamp 只接受可解析且 timezone-aware 的 source value，并统一 UTC；naive 或 malformed value item-local fail closed。linked Article 可缺 `published_at`，linkless Article 继续服从 canonical contract 的 timestamp 要求。
- 影响：只读取 `feeds.json` 的 source name / URL / language，忽略 legacy `mode` / `role` / `category` / keyword metadata；复用 Gen1 `parse_feed_with_retry` boundary，不修改 `main.py` 行为或 production routing。没有 semantic dedup、event clustering、embedding、LLM、orchestrator 或 dependency change。
- 权威性：`docs/V1.2_DETERMINISTIC_INGEST_SPEC.md` 只是本 milestone 的 implementation note，不是第四份 canonical contract；Article、StageResult、identity、URL、datetime 与 runtime semantics 仍以三份 frozen v1.0 contract 和 `canonical_domain.py` 为准。
- 验证：`tests/offline_deterministic_ingest_smoke.py` 只使用 fake/local fixtures；v1.1 canonical、Gen1 feed/CandidateArticle/digest 与 Project-State gate regressions 均保持通过。下一步唯一任务为 `v1.3 — Event Clustering`。

### v1.3 — Event Clustering（COMPLETED / CLOSED）

- local semantic / embedding based clustering
- `Article → EventCandidate`
- clustering validation / diagnostics
- roadmap freeze 时不预选具体 embedding model；closeout 后 accepted implementation configuration 由下方决策冻结。

#### v1.3 canonical semantic correction — Morning Brief story bundle

- 决策：Event / EventCandidate 的 operational semantics 是“同一约 24 小时
  Morning Brief report window 内，高度相关且适合 reader 作为一个 news story
  一次性消费的 Articles”，不是严格 atomic occurrence identity，也不是跨天
  persistent event identity。
- 允许同一新闻发展中的 announcement、immediate reaction、clarification、
  follow-up statement 与 closely related perspectives 合并；判断标准是分别展示
  是否造成明显重复，以及后续 Event Writer 是否能依据完整 Article provenance
  自然综合重要事实与不同侧面。
- hard-negative 仍以 reader 明显应视为不同新闻为准：共享关键词、国家、公司或
  主题不足以合并。正常 acceptance 只使用真实 ingest/window semantics 下可能
  同时出现的 Articles；人为跨越多个 report windows 的旧/新事件对不是核心 gate。
- v1.3 保持 local embedding + semantic similarity + simple deterministic
  clustering，不使用 DeepSeek、local LLM pair verifier、LLM adjudication、
  translation stage 或 second-pass AI clustering。是否 close v1.3 由修正后的
  acceptance 重新验证决定，本修正不改变 implementation。
- 当前 fixture 概念重新分类：A（production-relevant Morning Brief acceptance）
  包括 announcement/reaction/follow-up、gun/share/reverse-repo negatives 与同
  window broad-topic distinct events；B（useful synthetic robustness）包括
  Treasury cross-language 与 chaining；C（invalid / overly strict event-identity
  assumption）包括人为把几天前旧 Iran sanctions 与今天新 action 组成 critical
  hard negative。C 不作为正式 production acceptance gate；该分类不改写新闻
  事实标签。

#### v1.3 implementation closeout — accepted deterministic baseline

- 决策：v1.3 首版固定使用 `intfloat/multilingual-e5-small`，immutable revision
  `614241f622f53c4eeff9890bdc4f31cfecc418b3`，`article-title-summary-v1` projection
  （title 加 summary 前 300 个 Unicode 字符）、CPU/float32、L2 normalization、
  pairwise cosine、single threshold `0.91`、deterministic connected components，
  algorithm version `connected-components-v1`。这些是 implementation/runtime
  configuration，不扩展 canonical EventCandidate。
- 验证：四个 production-relevant fixture cases 在 `0.91` 下 production-critical
  overmerge / split 为 `0 / 0`，precision / recall / F0.5 为 `1.0 / 1.0 / 1.0`，
  expected reader memberships `8 / 8` exact；重复运行 deterministic。Treasury
  zh/en split 只作为 synthetic robustness limitation，temporal Iran pair merge
  只作为 outside-normal-window observation。
- 依赖：正式直接依赖为 `sentence-transformers==3.4.1`、
  `transformers==4.48.1`、`torch==2.5.1`；不手工 pin 不必要的 transitive packages。
  real-model evaluator 使用 `AUTOMATION_BRIEF_MODEL_CACHE`，未设置时使用 canonical
  data root 的 `runs/model-cache`；不提交模型或 cache binaries。
- 边界：v1.3 不使用任何 LLM、translation、keyword override、multiple thresholds、
  source/category weighting、vector database、ANN、complex graph clustering 或
  Generation 1 fallback；实现保持 side-by-side，不改变 production routing。
- 下一步：v1.4 — Event Selector；v1.3 closeout 不提前实现 selector、classifier、
  writer、renderer 或 orchestrator。

### v1.4 — Event Selector

- LLM event selection、relative ordering
- selector validation
- global selector failure semantics
- safe item salvage

### v1.5 — Event Classifier + Writer（COMPLETED / CLOSED）

- canonical category
- `title_zh`、`summary_zh`、`why_it_matters_zh`
- per-event validation / partial failure
- Slice 1 Classifier、Slice 2 Writer 与 Slice 3 Classifier → Writer continuation regression
  已完成并保持 side-by-side；Classifier 仅采用 specific natural category → canonical category、
  no natural specific category → `other`、technical/transport/parse/contract failure →
  `ItemFailure` 的既定语义，不引入 keyword rules、scores、category weighting 或 semantic
  fallback machinery。
- Writer 完成 Event bundle synthesis，输出自然 zh-CN 的 `title_zh`、`summary_zh` 与
  `why_it_matters_zh`；仅使用 supplied Article evidence，不做逐篇翻译、外部知识/来源
  推断或读者导向的投资、购买及行为建议，不提供 fallback writer。Classifier failure 仍
  继续原 selected Event → Writer → `written-unclassified`。
- 最终 real-provider acceptance 使用 `deepseek` / `deepseek-v4-flash` 与同一 6-Event
  synthetic fixture：classifier/writer stages 均 `succeeded`，6/6 Events written，双方
  technical failures 均为 0；分类合理且无 `other` 滥用，Event-level synthesis、中文
  可读性与 evidence grounding PASS。首次 `why_it_matters_zh` 读者建议问题由最小 prompt
  correction 解决，revalidation 无 release blocker。

### v1.6 — Renderer + Artifacts + Orchestrator Integration（COMPLETED / CLOSED）

- brief_renderer
- v1.x artifacts/checkpoints
- orchestrator
- llm_gateway integration boundary
- complete side-by-side v1.x pipeline
- 仍不做 production cutover。

### v1.7 — Offline / Snapshot Validation（COMPLETED / CLOSED）

- deterministic regression
- duplicate / event clustering cases
- invalid provider outputs
- partial failure、empty success
- snapshot / offline E2E validation
- 代表性 clean、empty、partial、hard-stop 与 malformed/provider protocol fixture matrix 已通过完整 Generation 2 pipeline；Brief、Markdown、checkpoint/artifact inventory、failure outcome 与 provenance projection 均稳定。
- Human Reader-Facing Acceptance: PASS。最终 Markdown 移除“今日要闻”，category 使用 `## *Category*`，Event title 使用 `###` + bold + `var(--text-accent)`，正文保留 `摘要：` / `为什么重要：`，来源使用 Obsidian-compatible `<details>/<summary>/<ul>/<li>/<a>` 结构。
- v1.7 保持 side-by-side，不接入 Generation 1 production routing，不调用真实 RSS/DeepSeek/provider，不新增评分、benchmark 或通用 evaluation framework；全部 28 个 offline scripts、compile/compileall、shell、Push Gate 与 diff checks 通过。

#### v1.7 reader-facing presentation amendment

- 决策（v1.7 baseline）：Generation 2 Morning Brief 的 Markdown 按 canonical category 分区展示，取代线性列表中不 regroup 的旧 reader-facing 选择。Section 顺序当时由各 category 最早的 `selection_order` 决定，section 内保持 `selection_order`；canonical `Brief.event_ids` 仍保持全局 selector order。该 section-order 规则已由 v1.9 focused presentation corrective supersede。
- 决策：written-unclassified Event 在 Markdown 中进入“其他” section，仅作 presentation fallback；Event 仍为 `classification=null`，不将 classifier failure 映射为 canonical `other`。
- 决策：Obsidian 可折叠来源块保留 `<details>/<summary>`，内容使用真正的 HTML `<ul>/<li>/<a>` children，展示全部 surviving provenance，不设 source ceiling。
- 最终 reader-facing layout：Markdown 直接以 H1 日期开始，不再输出“今日要闻”；category 为 `## *Category*`，Event title 为 `###` + bold + `var(--text-accent)`，正文保留 `摘要：` / `为什么重要：`。
- 边界：这是 renderer/presentation amendment，不改变 domain schema、Selector/Classifier/Writer ownership、category importance/weight/quota、StageResult/failure semantics 或 production routing。

### v1.8 — Shadow / Parallel Validation（COMPLETED / CLOSED）

- Generation 1 production 正常运行
- v1.x side-by-side real shadow execution；Gen2 runtime 是未来 production 可直接复用的正式 capability，不能依赖 Gen1 runtime 或 Gen1 report artifacts
- 不发送 reader-facing v1.x output
- Generation 1 继续作为 production reference；Gen1 comparison / human review 不属于本轮 runtime acceptance
- v1.8 第一小步的 canonical Gen2 report slot 以 `report_date` 当日 Asia/Shanghai 08:00 为 inclusive `window_end`，前推 24 小时为 inclusive `window_start`，进入 canonical domain 前转换为 aware UTC；该规则不改 Gen1 rolling window，也不把 Gen1 candidate min/max 当 publication window。
- manual validation 另提供与 `--date` 互斥的 `--as-of-now` rolling-24h mode：`window_end` 为当前 Asia/Shanghai aware datetime，`window_start` 精确向前 24 小时，进入 canonical runtime 前转换为 aware UTC；该 mode 不改变未来 production 的固定 08:00 report slot，也不加入 schedule。
- v1.8 acceptance 的最小真实门槛为至少一次有效 rolling-24h Gen2 run，并通过用户 reader-facing 人工验收；该门槛已满足，用户确认最终 reader-facing Brief 可接受。
- Gen2 real runtime 从 active `feeds.json`、冻结 E5 model/revision 的 local-only cache、共享 LLM gateway 与 canonical Artifact Manager 组装既有 `run_generation_2()`；manual runner 只负责显式 real-provider opt-in 和输出 outcome/artifact location，不接 delivery、schedule 或 `reports/`。
- Gen2 ingest 在 formal normalization/window admission 前独立 qualification 每个 fetched source snapshot；存在有效 entries 但全部无可解析 publication timestamp，且当前无其他经治理 bounded-recency evidence 的 snapshot 整体排除。不用 `collected_at`/URL 推断，不改 canonical Article nullable `published_at` contract，不影响 Gen1。
- v1.8 真实 hard negatives 将 v1.3 clustering implementation configuration 正式 corrective replacement 为 `identity-guarded-connected-components-v2` / `semantic-title-anchor-v1`。历史 v1.3 `connected-components-v1` acceptance 不重写；当前实现保留 model/revision、`article-title-summary-v1`、`0.91` base floor 与 connected components。
- edge acceptance 决策：`similarity >= 0.925` 接受；`0.91 <= similarity < 0.925` 仅在 title 经 Unicode NFKC、casefold、保留 Python `str.isalnum()` 字符后共享至少 4 字符连续 span 时接受；低于 `0.91` 拒绝。不使用人物/地点/category special case、中文关键词表、NER、第二 embedding model 或 LLM。
- 纯 threshold correction 被否决：3 个 hard negatives 最高为 `0.921938`，但同一 real run 的国防部记者会和 CrowdStrike positives 为 `0.920543 / 0.920444`；任何能拆分前者的单一 threshold 都会拆分已知后者。
- closeout acceptance：production-shaped Gen2 runtime、manual rolling-24h real run、local embedding、真实 DeepSeek 与完整 Gen2 pipeline 均已真实跑通；source freshness qualification 已将 unbounded-recency source pollution 收敛为 `published_at=null admitted = 0`；Selector 一次 `unknown_reference` 与 Writer 一次 invalid JSON 均按既有 local failure semantics 正确隔离，后续 real run 未复现 Writer 问题。Gen1 production routing、schedule、Bark/Obsidian delivery 与三份 frozen Architecture/Data/Runtime contracts 均未修改。
- 产品原则：Event Clustering 不追求理论上的 100% 同事件识别。只有长期真实使用中反复出现明显 duplicate、明显 overmerge 或明显不可接受 split 时，才重新打开 clustering；不为低概率边缘 case 持续调 threshold、projection 或叠加规则。
- No frozen-contract amendment required：v1.8 的 source freshness qualification、clustering corrective replacement 与 manual rolling-24h validation 均在既有 Architecture/Data/Runtime Contract 边界内完成。

### v1.9 — Production Cutover（COMPLETED / CLOSED；Slice 1–5 COMPLETED；FIRST SCHEDULED ACCEPTANCE PASS WITH ACCEPTED DEGRADATION；category presentation corrective COMPLETED）

- v1.x 接管正式 Morning Brief
- Slice 1：finalized Generation 2 artifact 的 canonical report publication adapter
- Slice 2：显式 `generation_2` shell route；仅在 adapter 成功后复用既有 `overnight_brief` publisher/Bark contract，failure fail closed 且不调用 Gen1
- checked-in plist example 与 installed LaunchAgent 均使用 `generation_2`；installed Label、script/working/log paths 与 08:00 schedule 保持不变
- Slice 3：shell 只计算一次 Asia/Shanghai canonical report date，并显式传给 adapter、publisher 与 Bark；publisher/Bark 对日期严格校验；两个 active delivery channel 独立尝试并聚合非零结果；Bark ambiguous timeout / 无法可靠判定送达的 transport failure 不自动 resend，HTTP 429/5xx 保留既有 bounded retry 分类
- Slice 3 不改变 `overnight_brief` Gen1 rollback route 的默认 semantic/fallback 行为；explicit `--report-date` 是新增兼容 seam
- Slice 4：Full Offline Acceptance 已通过完整 offline release gate；30 个 offline smoke、production-chain outcome matrix、publication/digest/date/delivery/secret boundary、runtime/orchestrator/artifact、shell/plist 与 Project-State gate 均 PASS
- Slice 4 仅完成 pre-activation acceptance，不执行真实 provider/delivery 或 installed schedule activation
- Slice 5：2026-08-29 08:00 前将 installed LaunchAgent route 从 `overnight_brief` 最小切换为 `generation_2` 并安全 reload；未 kickstart、未手动 generation、未调用真实 provider/delivery，当日 canonical report 保持不存在
- Slice 5 activation applied 后，第一次 scheduled Gen2 production run 的 artifact、report、delivery、reader-facing 与 no-Gen1 evidence 已完成验收；final closeout review 已通过
- 第一次 scheduled Gen2 production run 已 PASS WITH ACCEPTED DEGRADATION：唯一 partial 为 Investing.com 10 条 timezone-less timestamp 的既有 `item_validation_failed` fail-closed variation；finalized artifact、canonical report、Obsidian 与 Bark 均属于同一次 run，未发现 Gen1、fallback 或 duplicate semantic run
- v1.9 focused presentation corrective：Renderer section 固定为 `geopolitics → china_policy → macro_policy → financial_markets → energy_commodities → company_industry → technology_ai → public_safety → other`；仅改变 reader-facing presentation，section 内继续保持 selector `selection_order`，`Brief.event_ids`、Event classification 与 canonical schema 不变；written-unclassified 仍映射到“其他”，且“其他”最后
- v1.9 final closeout：Slice 1–5、第一次 scheduled acceptance 与 category presentation corrective 均 COMPLETED / PASS；Generation 2 保持 active production route，v1.9 正式 CLOSED。后续先观察 production stability，确认后才进入 v1.10 Legacy Retirement READ-ONLY dependency audit
- cutover acceptance
- explicit auditable rollback path
- 禁止 automatic Generation 1 semantic fallback。

### v1.9.1 — Classifier “other” Boundary Correction（COMPLETED / CLOSED）

- 说明：`v1.9.1` 是 v1.9 production cutover 之后的 numeric corrective，不改变已冻结的 v1.0→v1.10 milestone 顺序，也不代表 v1.10 已开始。
- 决策：只在现有 classifier system prompt 增加简短 category boundary clarification 与 specific-category preference；`public_safety` 覆盖灾害、洪水、地震、事故、重大伤亡、救援、公共卫生紧急事件与应急响应，`technology_ai` 覆盖以 AI 公司/模型/训练数据/产品或 AI 版权/知识产权争议或诉讼为核心的事件。
- 决策：`other` 仅在没有任何 named category 自然适用时使用；不要因为法律、诉讼、任免或人员形式就选择 `other`；混合事件按 dominant subject 选择最自然的 named category。保留 canonical vocabulary、response validator、Event/Brief schema 与 runtime failure semantics。
- 决策：以 focused offline fixture/regression 覆盖高置信度灾害边界、AI 版权诉讼边界与合理 `other` counterexample；不引入 keyword/score/source/entity rule、category weighting、second classifier、judge、semantic repair 或 taxonomy redesign。production route、LaunchAgent、delivery 与 Gen1 rollback seam 不变。
- 决策：为用户手动 real-provider same-case validation 复用既有 quality runner，增加显式 `--classifier-only` compact-fixture 分支；该分支只调用 classifier gateway、只向 stdout 输出安全结果，不调用 Writer、feeds、完整 Gen2 runtime、artifacts 或 delivery，不改变 production semantic behavior。
- 验收：offline regression PASS；用户手动完成 3 次 same-case real-provider validation，均 `exit=0`、classifier stage `succeeded`、technical failures 为空，5/5 case expectations 每次全部匹配；灾害 cases 稳定为 `public_safety`、AI legal-dispute cases 稳定为 `technology_ai`、intentional `other` counterexample 稳定保持 `other`。
- 状态：v1.9.1 已 COMPLETED / CLOSED。partial banner 未修改，作为独立 presentation follow-up；v1.10 尚未开始。

### v1.9.2 — Source Timezone Normalization（COMPLETED / CLOSED）

- 说明：`v1.9.2` 是 v1.9.1 之后的 numeric source corrective；v1.9 与 v1.9.1 保持 CLOSED，v1.10 尚未开始。
- 决策：在现有 Gen2 source metadata 中增加可选 `timezone` 字段；缺失表示没有 source-level timezone assumption，空值或非法值由 `SourceConfig` deterministic reject。使用 Python 标准 `zoneinfo.ZoneInfo` 做 IANA-compatible validation，`UTC` 合法且不新增依赖。
- 决策：仅当 raw source timestamp 已成功解析为 naive datetime 且 `SourceConfig.timezone` 已声明时，按该 source timezone attach/localize 后进入既有 canonical aware-UTC normalization；source timestamp 已 aware 时保留其自身 offset/instant，未声明 timezone 的 naive value 继续 fail closed。
- 决策：`feeds.json` 仅为 `Investing.com 中文财经` 声明 `timezone: "UTC"`；不按 source name、language 或 URL 猜测，不把 collected_at 冒充 published_at，不改变 `Article` identity、canonical URL、language、dedup、clustering、Selector、Classifier、Writer、Renderer、StageResult、runtime routing 或 delivery。
- 决策：以 deterministic ingest smoke 覆盖 declared UTC、undeclared-naive rejection、already-aware passthrough、invalid metadata、Investing representative 与 report-window admission；source timezone localization 只恢复进入 normalizer/window 的资格，不保证条目数量或最终入选。
- 验收：offline ingest validation PASS；用户完成 source-only controlled live RSS validation，collector `succeeded`、10 条 raw entries、normalizer `succeeded`、10 条 normalized articles、`failure_codes=[]`，sample published timestamp 为 aware UTC；未调用 DeepSeek、embedding、Bark、Obsidian 或 production run。
- 状态：v1.9.2 已 COMPLETED / CLOSED。Investing source 保留并声明 `UTC`；不修改 partial banner、不改变 canonical datetime contract 或 semantic/production architecture，v1.10 尚未开始。

### v1.9.3 — Classifier Boundary Correction（COMPLETED / CLOSED）

- 说明：`v1.9.3` 是 v1.9.2 之后的 numeric classifier corrective，不改变已冻结的 v1.0→v1.10 milestone 顺序，也不代表 v1.10 已开始。
- 决策：只在现有 classifier system prompt 增加最小 category boundary clarification。`geopolitics` 自然覆盖 foreign national-government / state-level political events，其中外国政府领导、内阁改组、部长任免或国家级政治权力/政府结构变化是核心 subject；不把所有人物任免机械归入该类。`china_policy` 自然覆盖中国中央政府、国务院部门或多个中央部委出台的重要全国性制度、监管、行业政策与政策改革，中央层面的住房销售制度、预售门槛和优先现房销售调整优先归入该类。`macro_policy` 仍用于更广义宏观经济、货币或财政政策；`other` 仅在没有任何 named category 自然适用时使用；mixed event 继续按 dominant subject。
- 生产根因：2026-08-31 scheduled production 中“韩国总统李在明改组内阁、提名六部长官”与“中国三部门完善商品住房销售制度、提高预售门槛并优先现房销售”均由 provider 合法返回 `other`；strict parsing 与 overlay 正常，缺口是上述两个正向 boundary 未在 prompt 中明确。
- 决策：focused fixture 精确保留 v1.9.1 五个 case 并新增韩国/中国两个 boundary case；不引入 keyword/entity/source rule、第二 classifier、repair call、taxonomy 新类别或其它 stage 逻辑。production routing、clustering、selector、writer、renderer、collector、normalizer、runtime、delivery、canonical schema 与 frozen contracts 不变。
- 验收：focused classifier、classifier → writer continuation、Python compile、JSON validation、`git diff --check` 与全部 30 个 offline smoke 均 PASS；用户连续 3 次 real-provider validation 均 `classifier_stage_status=succeeded`、`technical_failures=[]`、7/7 match，新增 case 分别得到 `geopolitics` 与 `china_policy`。
- 说明：首次 `invalid_input` invocation 只因 shell 未加载 `.env.local` / process-env credential，在 gateway provider preflight 前失败且未产生质量结果；该 invocation 不是产品、fixture 或 classifier defect，也不计为 classifier quality failure。
- 状态：v1.9.3 已 COMPLETED / CLOSED。Generation 2 保持 active production；clustering 继续现有 frozen policy，2026-08-31 相似灾害 overmerge 仅为历史 observation、不构成当前 blocker；VentureBeat 单次 `transport_failed` 为 accepted transient degradation / observation，不开启 corrective version。下一步继续观察 Generation 2 scheduled production stability，v1.10 尚未开始。

### v1.10 — Legacy Retirement & v1.x Closeout

- post-cutover consumer audit
- 删除无 consumer 的 Generation 1 news core
- 删除 obsolete Curator product layer
- 删除 obsolete Daily Digest / Market Brief reader-facing product surfaces
- 删除 Holdings legacy capability
- 删除 obsolete routing / writer / tests / docs
- 保留仍被 v1.x 使用的成熟 shared infrastructure
- final regression / governance closeout
- v1.x milestone closed

Market 不属于 v1.x core；Holdings 不进入 v1.x。v1.9 cutover 已完成，Generation 1 仅保留为 explicit human-approved rollback route；保留 Gen1 不代表长期双架构，legacy retirement 进入 v1.10 后才开始。

### Roadmap governance rules

1. 正式版本 token 只使用纯数字：`v1.0`、`v1.1`、`v1.2` … `v1.10`；不使用 alpha、beta、Phase A/B 或其它阶段型 version token。
2. v1.0 已冻结的 Architecture、Core Data Contract、Runtime / Failure Contract 默认不在 implementation 中重新打开。
3. 如果真实实现发现 frozen contract 存在不可实现矛盾，不得在业务代码中静默改变；必须先报告证据，做最小、显式、可审计的 contract amendment，不扩大架构范围。
4. v1.7、v1.8 与 v1.9 已完成并关闭；v1.9 Slice 1–5、第一次 scheduled acceptance 与 category presentation corrective 均已完成，第一次 scheduled acceptance 为 PASS WITH ACCEPTED DEGRADATION。不得以 commit hash 或 narrative slice 名称替代已冻结的 numeric milestone。
5. 本路线不提前选择 embedding model、模型迁移、prompt、token budget 或其它 implementation tuning。
