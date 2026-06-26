# Decisions

本文记录 automation-brief 的长期产品、架构和工作流决策。只记录相对稳定的判断；短期任务放在 `docs/BACKLOG.md`，过程记录放在 `docs/DEVLOG.md`。

## 输出与使用入口

### 每日 08:00 生成早间回顾

- 决策：每日早间回顾以 08:00 本地自动运行为目标。
- 理由：早上阅读场景稳定，适合在用户开始一天前完成 RSS 抓取、简报生成、Obsidian 同步和 Bark 推送。
- 影响：`launchd` 定时任务保持 08:00；`pmset` 自动唤醒用于提前唤醒 Mac，但不替代运行期间的防睡眠保护。

### 使用简体中文输出

- 决策：日报面向个人阅读，默认使用简体中文组织标题、栏目和说明。
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

## 信息筛选

### RSS + 规则筛选是当前基础

- 决策：当前日报以 RSS 候选池和可解释规则筛选为基础，不调用 DeepSeek、Tavily 或付费搜索 API。
- 理由：规则版成本低、稳定、可解释，适合本地自动化先跑通。
- 影响：重要性判断通过 source role、关键词、section 规则、去重和 missed case 回归持续改进。

### 后续可加入轻量 AI 筛选

- 决策：未来可以评估 RSS 候选新闻 + AI rerank 的轻量架构，但不做全网 AI 生成晨报。
- 理由：v0.4.1 扩源后，规则对重要性和重复内容的判断成本上升，AI 可作为候选新闻排序和解释辅助。
- 影响：AI 只能基于已有 RSS 字段和来源链接判断，不编造事实；AI 不可用时必须 fallback 到规则版日报。

### GitHub Trending 不直接作为每日重点内容

- 决策：GitHub Trending 和 `ai_tools` 不适合直接进入 daily digest 的重点栏目。
- 理由：工具、仓库和项目热度更适合低频观察，直接进入每日早报容易稀释宏观、市场和商业化信号。
- 影响：`ai_tools` 默认排除 daily digest，可作为未来 weekly AI tools radar 的来源。

### 市场投研观察对象必须可配置

- 决策：持仓、关注公司、行业和资产观察对象应从可编辑配置读取，不能硬编码到业务逻辑。
- 理由：投研关注对象会变化，硬编码会让个人持仓和观察范围难以维护，也增加误提交敏感信息的风险。
- 影响：未来新增持仓观察或 watchlist 时，应设计独立配置或使用现有配置扩展，并避免在代码中写死具体持仓。

## 文档分工

- `README.md`：项目入口、运行方式、文档入口。
- `docs/PROJECT_STATE.md`：给 project-command-center 展示的人工状态，不记录 Git branch、latest commit 或 working tree。
- `docs/BACKLOG.md`：未来任务和优先级。
- `docs/DEVLOG.md`：开发过程记录和重要验证记录。
- `docs/TESTING.md`：测试命令、smoke checklist 和验收记录。
- `docs/DECISIONS.md`：长期产品、架构和工作流决策。
- `docs/MISSED_CASES.md`：missed coverage、漏报案例和质量追踪。
