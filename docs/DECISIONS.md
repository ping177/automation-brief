# Decisions

本文记录 automation-brief 的长期产品、架构和工作流决策。只记录相对稳定的判断；短期任务放在 `docs/BACKLOG.md`，过程记录放在 `docs/DEVLOG.md`。

## Morning Brief 产品合同

### 个人早间简报定位

- 决策：automation-brief 的最终 reader-facing 产品定位是个人早间简报（Morning Brief）。目标是让读者每天早上约 5 分钟了解昨晚世界发生了什么、全球市场发生了什么、今天哪些变量值得继续关注。
- 不定位为 AI 投研助手、A 股机会发现系统、股票推荐工具、新闻到股票机会映射器或每日投资观点生成器。
- 未来统一结构为“昨夜最重要的事 / 隔夜市场 / 今日值得关注 / 持仓异常（仅异常时出现）”。“今日值得关注”最多 3 条，不是市场预测；“持仓异常”不得输出成本、仓位、盈亏或买卖建议。
- 影响：v0.6.1 冻结产品与语言合同并完成最小 candidate wiring，不正式生成 Morning Brief 输出，不删除 daily digest 或 `market_brief`，不切换生产输出。

### Numeric version route

- 决策：从本轮起新的正式 machine version token 使用 numeric 形式：`v0.6.1` Product Reset + Language Boundary、`v0.6.2` AI Curator Shadow Evaluation，以及 `v0.7` Morning Brief 总里程碑下的 `v0.7.1` Morning Brief MVP（CLOSED）、`v0.7.2` Production Cutover（CLOSED）、`v0.7.3` Morning Brief Long-term Usage Validation（next）和 `v0.7.4` Legacy Product Retirement & Capability Consolidation（planned after v0.7.3）；后续不再新增字母阶段标签作为正式阶段命名。
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

## v0.7.4 Legacy Product Retirement & Capability Consolidation

- 决策：只有 v0.7.3 真实晨间长期使用证明 Morning Brief 稳定后，才开始 v0.7.4。最终 reader-facing 产品只保留 Morning Brief；Daily Digest 和 Market Brief 作为独立产品正式退役。
- 目标架构：`RSS / feeds → CandidateArticle → single-pass AI Curator → CuratedEvent → Morning Brief → canonical report → Obsidian / Bark`，并由独立、中性的 shared market data、holdings anomaly、technical whole-layer fallback 和 delivery capabilities 提供支撑。
- read-only audit 已确认 Morning 当前仍依赖 `main.py` 中的 legacy fallback projection / digest summary-time helpers，以及 `market_brief_writer.py` 中的公共行情与持仓渲染 helpers；这些依赖必须先完成最小迁移，不能把旧文件名直接当作可删除的 product-only surface。
- 约束：本轮只冻结边界，不修改 Python、shell、plist、tests、config、runtime data 或 production behavior；不预先决定替代文件名、模块名、package hierarchy 或新的 orchestration。v0.7.3 期间保留 Daily rollback；v0.8 不提前冻结内容。
- 完成条件：删除旧产品容器后，Morning 仍完整支持 AI Curator、market context、holdings anomaly、provider technical fallback、canonical writer、Obsidian 和 Bark；只有确认无消费者的旧 entry、writer、routing、tests、docs surface 才可删除。
