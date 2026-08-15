# automation-brief 开发日志

本文记录 automation-brief 从 v0.2 到 v0.3.3-beta 的主要开发节点、验证结果和阶段结论。

## 2026-07-30

### Project State Push Gate 正在接入与待验收

- 已新增本地 `pre-push` 检查、安装脚本和 Python 标准库的临时 Git/bare remote 离线测试；合同限定为 `docs/PROJECT_STATE.md` 最终 tree 净差异与 `Project-State-Review` trailer 对应。
- 同步补齐 AGENTS、README 与 TESTING 的 push 前复核、安装、手动检查和本地可绕过边界说明。
- 当前尚未在真实仓库安装 hook，未修改 `core.hooksPath`，未 commit、未 push；rollout 尚待后续单独验收。
- 不修改每日晨报生产脚本、RSS、Bark、Obsidian、launchd、pmset、AI provider 或业务实现，也未读取 `.env` 或 secrets。

## 当前最终链路

```text
08:00 自动生成日报
→ 同步到 Obsidian iCloud
→ Bark 推送提醒
→ 点击通知直达 Obsidian 当天日报
```

## 当前结论

v0.3.3-beta 已经形成可用闭环。下一步不急着继续加功能，建议观察 2-3 天真实早间运行稳定性，重点看 launchd 触发、RSS 抓取、iCloud 同步和 Bark 跳转是否都稳定。

## v0.2 规则版日报收口

### 目标

完成不依赖 AI 的规则版日报：RSS → 规则过滤 → Markdown 输出，让每日早间回顾具备稳定、可解释、可本地运行的基本能力。

### 实际改动

- 从 `feeds.json` 配置 RSS 源抓取文章。
- 根据 `keywords.json` 和 `config.json` 执行规则过滤、分类和数量控制。
- 输出 `output/daily-news-YYYY-MM-DD.md`。
- 收口 digest 模式的栏目结构：昨日最重要的事、昨日市场信号、今天值得关注的变量、快速扫读、一句话主线、抓取失败。
- 解决旧新闻过滤问题，避免旧链接或旧内容混入“过去 24 小时”的日报。
- 增加快速扫读，用于承接未进入核心栏目的可扫读内容。
- 增加栏目隔离，避免快讯、市场、科技产业和 AI 工具源互相污染。
- 增加低价值内容过滤，减少普通活动、泛宣传、普通社会个案、体育娱乐等内容进入 digest。

### 验证结果

- 规则版 Markdown 输出可稳定生成。
- 离线 smoke 覆盖了旧新闻过滤、栏目隔离、市场信号、今日变量、快速扫读和低价值内容过滤等关键行为。
- 多轮规则收紧后，误入核心栏目的泛科技、AI 工具、普通活动和低价值内容明显减少。

### 结论

规则版可用，不继续无限调规则。v0.2 的重点从“继续微调规则”转为“让日报稳定自动运行和可阅读”。

### 后续备注

- 后续不再轻易扩大筛选规则范围。
- 如需调整规则，应基于连续多天真实样本，而不是单条偶发误判。
- 暂不接 AI，保留规则版的可解释性和低成本优势。

## v0.3.1 本地定时运行

### 目标

让日报每天早上自动运行，不依赖手动执行命令。

### 实际改动

- 新增 `scripts/run_daily_digest.sh`，进入项目目录后使用项目 `.venv` 执行 `main.py`。
- 新增 launchd plist 示例，配置每天 08:00 调用脚本。
- README 增加本地定时运行说明。
- README 补充现代 macOS 更稳的 launchd 命令：`bootstrap`、`print`、`kickstart`、`bootout`。
- README 增加睡眠说明、`caffeinate` 临时保持唤醒和 `pmset` 自动唤醒说明。

### 验证结果

- 已验证 LaunchAgent 加载成功。
- 已验证早上 08:00 自动触发。
- 已验证自动生成当日 Markdown 简报。

### 结论

v0.3.1 完成了“本地自动生成”的基础能力，日报从手动工具变成可定时运行的本地自动化。

### 后续备注

- Mac 睡眠时不保证 08:00 准点运行。
- 若需要确保早上打开手机前已经生成，可配合 `pmset` 自动唤醒。
- launchd 日志和 `daily-news.log` 是排查定时问题的主要入口。

## v0.3.2 Bark 推送接入

### 目标

日报生成成功后向手机发送简短提醒，让用户知道今天的日报已经完成。

### 实际改动

- 新增 `scripts/send_bark_notification.py`。
- 从本地 `.env` 读取 `BARK_URL`。
- 新增 `.env.example` 中的 `BARK_URL=` 示例字段。
- `scripts/run_daily_digest.sh` 在 `main.py` 成功后调用 Bark 通知脚本。
- Bark 推送失败不阻断日报生成结果。
- README 增加 Bark 配置、curl 测试和 `.env` 不提交说明。

### 验证结果

- 已验证 iPhone 收到“每日早间回顾已生成”通知。
- 已验证 `.env` 中的 Bark key 不进入 README、示例配置或提交文件。
- 已验证通知失败不会改变日报已经生成的事实。

### 结论

v0.3.2 完成了“生成后提醒”的能力，解决了用户需要主动检查 output 的问题。

### 后续备注

- 限制：通知本身不包含完整正文。
- 限制：这一版不能直接打开 Mac 本地 Markdown。
- 不推送完整 Markdown，避免通知过长，也避免把日报正文塞进推送渠道。

## v0.3.3-alpha 同步到 Obsidian iCloud

### 目标

让 iPhone 能阅读完整日报，而不是只收到一条提醒。

### 实际改动

- 新增 `scripts/publish_mobile_digest.py`。
- 从本地 `.env` 读取 `MOBILE_DIGEST_DIR`。
- `main.py` 成功生成日报后，额外复制一份 Markdown 到 Obsidian iCloud 目录。
- 目标目录为 MindPalace vault 内的 `10 Atlas/Sources/每日早间回顾/`。
- 文件名保持 `daily-news-YYYY-MM-DD.md`，和 `output/` 中的文件一一对应。
- 同步失败不阻断 Bark 推送，也不影响日报已经生成的事实。
- README 增加 Obsidian iCloud 同步配置说明。

### 验证结果

- 已验证 `output/` 中生成当日日报。
- 已验证 Obsidian iCloud 目标目录出现同名日报。
- 已验证同步文件与 `output/` 文件内容一致。
- 已验证 iPhone Obsidian 可以打开并看到完整 Markdown。

### 结论

v0.3.3-alpha 完成了“手机可阅读完整日报”的能力。日报已经从 Mac 本地文件扩展为可在 iPhone Obsidian 中阅读的内容。

### 后续备注

- iCloud 同步需要时间，手机端打开 Obsidian 后可能需要等待。
- 这一版不保证 Bark 点击直达，只保证 Obsidian 中能看到完整日报。
- Obsidian 目录由 `.env` 配置，不把本机绝对路径写进代码。

## v0.3.3-beta Bark 点击直达 Obsidian

### 目标

让 Bark 通知不仅提醒日报已生成，还能点击后直接打开 iPhone Obsidian 中的当天日报。

### 实际改动

- `scripts/send_bark_notification.py` 改用 Bark JSON POST。
- Bark payload 增加 `url` 字段。
- 从 `.env` 读取 `OBSIDIAN_VAULT_NAME` 和 `MOBILE_DIGEST_RELATIVE_PATH`。
- 根据当天日期拼出 vault 内相对路径：`10 Atlas/Sources/每日早间回顾/daily-news-YYYY-MM-DD.md`。
- 使用标准库 URL 编码生成 Obsidian URI。
- 若 Obsidian 配置缺失，仍发送普通 Bark 通知，不带点击跳转。
- README 增加 Obsidian URI、iPhone 前置条件和跳转排查说明。

### 验证结果

- 已验证日报生成成功。
- 已验证日报同步到 Obsidian iCloud 目标目录。
- 已验证 Bark 手机收到通知。
- 已验证点击 Bark 通知可以直接打开 iPhone Obsidian 中的当天日报。

### 结论

v0.3.3-beta 完成了当前闭环：自动生成、手机同步、手机提醒、点击直达阅读。

### 后续备注

- 该能力依赖 iPhone 已安装 Obsidian，并已打开或登录过 `MindPalace` vault。
- 若点击不跳转，优先确认 vault 名称、相对路径和 iCloud 同步状态。
- 下一步建议先观察 2-3 天真实早间运行稳定性，再决定是否继续扩展功能。

v0.3.3-beta 已形成可用闭环，并已补充 DEVLOG。

当前链路：
08:00 自动生成日报
→ 同步到 Obsidian iCloud
→ Bark 推送提醒
→ 点击通知直达 Obsidian 当天日报

下一步：
不急着继续加功能，先观察 2-3 天真实早间运行稳定性。

## v0.3.4 Bark 推送失败重试

### 背景

2026-06-14 早上 08:00，日报正常生成，Obsidian iCloud 同步成功，但 Bark 没有收到通知。日志中同时出现 RSS 和 Bark 的 SSL EOF 错误：

- Investing.com RSS 出现 `EOF occurred in violation of protocol`
- GitHub Trending RSS 出现 `EOF occurred in violation of protocol`
- Bark 出现 `EOF occurred in violation of protocol (_ssl.c:1129)`

判断是 Mac 早上唤醒后网络或 SSL 连接短暂不稳定。v0.3.3-beta 的行为是正确的：Bark 失败不会阻断日报生成，但缺少自动重试。

### 修复内容

- `scripts/send_bark_notification.py` 增加 Bark 发送重试。
- 最多尝试 3 次。
- 第 1 次失败后等待 10 秒，第 2 次失败后等待 20 秒。
- 每次失败都会把 attempt 信息写入 stderr，便于 launchd err log 排查。
- 最终失败时输出 `Bark notification failed after 3 attempts: ...`。
- 成功时继续输出 `Bark notification sent with Obsidian URL.`。
- 保持原有行为：Bark 失败不影响日报已生成事实，`run_daily_digest.sh` 不因为 Bark 失败而整体失败。

### 验证结果

- `scripts/send_bark_notification.py` 可编译通过。
- 手动执行 Bark 通知脚本可成功补发通知。
- 未修改日报筛选规则、feeds、keywords 或 config。

### 结论

v0.3.4 提升了早上网络刚恢复时 Bark 推送的稳定性。若 3 次重试后仍失败，说明网络或 Bark 服务仍不可用，可在网络稳定后手动执行通知脚本补发。

## v0.3.5 自动唤醒运行条件记录

### 背景

当前链路已经真实验证通过：

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

已执行：

```bash
sudo pmset repeat wakeorpoweron MTWRFSU 07:58:00
```

`pmset -g sched` 显示：

```text
Repeating power events:
  wakepoweron at 7:58AM every day
```

### 验证结果

- 不合盖、睡眠状态下，Mac 可以自动唤醒。
- 08:00 launchd 成功运行。
- Bark 成功推送。
- Obsidian iCloud 中出现当天日报。
- Codex 不需要打开。
- 浏览器、终端也不需要打开。

### 运行条件

需要保持：

- Mac 不关机。
- 用户账号已登录过。
- launchd 任务仍加载。
- `pmset` 自动唤醒计划仍存在。
- 网络可用。
- 项目目录和 `.env` 未移动或删除。

可以关闭：

- Codex。
- 浏览器。
- 终端。

### 结论

v0.3.5 不修改 Python 或 shell 运行逻辑，只补充自动唤醒运行条件和验证记录。当前自动化闭环已经可以在 Mac 睡眠后自动唤醒、生成日报、同步到 Obsidian iCloud，并通过 Bark 点击直达 iPhone Obsidian 当天日报。

## v0.4.1 RSS 覆盖和 source role 扩展

### 背景

v0.3.5 已收口自动唤醒、launchd、Obsidian iCloud 和 Bark 推送链路。后续问题转向信息覆盖和重要性判断。用户发现 Visa / OpenAI / ChatGPT 支付合作漏报，该事件属于 AI agent commerce、支付基础设施和 OpenAI 商业化的重要事件，当前中文 RSS + keyword 体系覆盖不足。

### 实际改动

- 新增 `global_tech_business` 和 `ai_industry` source role。
- `global_tech_business` 和 `ai_industry` 可进入核心事件、市场信号、今日变量和快速扫读。
- `ai_tools` 继续默认排除 daily digest，保留给未来 weekly AI tools radar。
- 第一批新增 4 个 RSS 源：OpenAI News、TechCrunch AI、VentureBeat AI、CNBC Technology。
- 补充 Visa、Mastercard、Stripe、PayPal、payments、checkout、commerce、agentic commerce、merchant、partnership、commercialization、Anthropic、Microsoft、Google、Nvidia、agent 等关键词和规则信号。
- 新增 `docs/MISSED_CASES.md`，记录 Visa / OpenAI / ChatGPT 支付合作漏报案例。
- 离线 smoke 增加 Visa / OpenAI / ChatGPT payments / agentic commerce 样本，验证不会被 drop。

### 结论

v0.4.1 只扩展 RSS 候选池、source role、关键词和漏报样本闭环，不引入 AI rerank，不修改 Bark、Obsidian、launchd 或 pmset 链路。

## v0.4.1.2 runtime stability hotfix

### 背景

2026-06-19 的自动日报直到 08:49 才生成。电源和应用日志确认：

- 07:58 `pmset` 自动唤醒成功。
- 08:00 launchd 正常触发，`main.py` 于 08:00:05 开始运行。
- Mac 在任务运行期间重新进入 Maintenance Sleep。
- RSS 网络请求随系统睡眠被挂起，仅在后续 DarkWake 中断续继续。
- Bark 没有单独延迟，而是在日报生成和 Obsidian 同步完成后正常发送。

因此不建议单纯把 `pmset` 唤醒时间提前到 07:45 或 07:30。核心问题不是唤醒或 launchd 触发时间，而是整条任务运行期间没有持续持有防睡眠 assertion。

### 修复内容

- `scripts/run_daily_digest.sh` 使用 `caffeinate -dimsu` 包裹完整任务链路。
- 防睡眠范围覆盖 `main.py`、`publish_mobile_digest.py` 和 `send_bark_notification.py`。
- 任务结束后 `caffeinate` 随子脚本自动退出，不常驻。
- 脚本增加 task/main/publish/Bark 的 start/end、exit code 和 elapsed seconds 阶段日志，继续写入 launchd 现有 stdout/stderr。
- RSS 请求增加单次 15 秒网络超时。
- 保留每个 feed 最多 2 次尝试、失败后等待 3 秒、单源最终失败不中断整体日报的行为。

### 兼容性

- 不修改 `pmset` 计划或 launchd plist。
- 不修改 Bark 和 Obsidian 的业务逻辑。
- 不影响 v0.4.1 RSS 扩源及 v0.4.1.1 分类、去重和内容形态降级逻辑。
- v0.3.5 自动唤醒、launchd、Obsidian iCloud 和 Bark 推送链路保持不变，只增强任务运行期间的稳定性与可观测性。

## P1 基础文档补齐

### 背景

项目已经形成稳定的本地自动化闭环，后续需要让 project-command-center 和人工交接都能快速理解当前状态、后续任务、测试方式和长期决策。

### 实际改动

- 新增 `docs/BACKLOG.md`，按 P0/P1/P2/P3 整理自动运行稳定性、市场投研晨报、RSS 覆盖、AI 筛选、missed coverage、Bark、Obsidian、launchd 和 pmset 后续任务。
- 新增 `docs/TESTING.md`，记录 docs-only、Python、JSON 配置、自动化链路 smoke 和 missed coverage 复盘流程。
- 新增 `docs/DECISIONS.md`，记录 08:00 早间回顾、简体中文输出、Obsidian iCloud、Bark、launchd + pmset、RSS + 规则筛选、未来 AI 筛选、GitHub Trending 和可配置持仓观察等长期决策。
- README 增加项目文档入口。
- `docs/PROJECT_STATE.md` 轻量更新 P1 基础文档状态，不写入 Git 快照字段。

### 结论

本次为 docs-only 变更，不修改业务代码、配置、RSS 源、Bark、Obsidian、launchd 或 pmset 链路。

## v0.5-alpha Market Research Brief 基础版

### 背景

项目从普通新闻晨报开始升级为轻量级市场投研晨报。目标是每日市场雷达、持仓观察、主线发现和风险提醒，不做自动交易，不输出买卖建议，也不替用户做投资决策。

### 实际改动

- 新增显式 `market_brief` report type，输出 `market-brief-YYYY-MM-DD.md`。
- 新增 `holdings.py`，从 `config/holdings.json` 读取真实关注列表；不存在时回退到 `config/holdings.example.json`。
- 新增 `config/holdings.example.json` 示例持仓，不包含成本、仓位、市值、亏损金额等敏感信息；真实 `config/holdings.json` 已加入 `.gitignore`。
- 新增 `market_data.py`、`market_analysis.py`、`market_brief_writer.py`，分别承载离线 sample 数据、占位分析和 Markdown 输出。
- 从 `main.py` 移除示例个股名的业务规则硬编码；持仓观察标题只来自 holdings 配置。
- 新增 `tests/offline_market_brief_smoke.py`，验证 market brief section、动态 holdings、禁止业务硬编码、禁止直接交易建议词和免责声明。

### 边界

- 不接 AKShare、TuShare 或真实行情。
- 不接 AI rerank。
- 不修改 Bark、Obsidian、launchd、pmset 或 `scripts/run_daily_digest.sh` 链路。
- `python main.py` 仍按当前 `config.json` 生成现有普通日报；`market_brief` 只能通过显式配置触发。

### 结论

v0.5-alpha 完成市场投研晨报最小骨架。后续 v0.5-beta 可在 `market_data.py` 后面接真实 A 股市场数据，同时继续保持持仓动态配置和不构成投资建议的安全边界。

## v0.5.1-alpha holdings 本地配置体验完善

### 背景

v0.5-alpha 已经完成 `market_brief` 骨架，但用户还需要更安全、清楚的本地 holdings 配置流程：不手动复制 example、不猜命令、不担心误提交真实持仓，也能在调仓或调整关注对象后快速校验。

### 实际改动

- 新增 `scripts/init_holdings_config.py`，从 `config/holdings.example.json` 创建本地 `config/holdings.json`；如果本地文件已存在则不覆盖。
- 新增 `scripts/validate_holdings_config.py`，校验 `holdings` list、允许字段、必填字段和 `watch_tags` 类型。
- `holdings.py` 新增共享校验 helper，统一允许字段和敏感字段列表。
- 校验脚本对成本、仓位、持股数量、市值、盈亏金额、账户金额等字段给出 warning，但不输出具体值，也不因为这些字段直接失败。
- `main.py` 新增显式 `--report-type` 覆盖参数，可用 `python3 main.py --report-type market_brief` 手动生成市场投研晨报；不传参数时仍按 `config.json` 默认行为运行。
- 新增 `scripts/run_market_brief.sh`，作为独立手动生成入口，输出 `output/market-brief-YYYY-MM-DD.md`。
- 新增 `tests/offline_holdings_config_smoke.py`，用临时目录覆盖 init、validate、敏感字段 warning、显式 market brief 生成和 `run_daily_digest.sh` 不变。
- README 和 TESTING 补充 holdings 初始化、编辑、校验、允许字段、敏感字段边界和手动 market brief 命令。
- `docs/PROJECT_STATE.md` 更新到 v0.5.1-alpha，便于 project-command-center 展示当前阶段。

### 边界

- 不接 AKShare、TuShare 或真实行情。
- 不接 AI rerank。
- 不做买卖建议。
- 不修改 Bark、Obsidian、launchd、pmset 或 `scripts/run_daily_digest.sh` 链路。
- `config/holdings.json` 继续被 `.gitignore` 忽略，不应提交真实持仓。

### 结论

v0.5.1-alpha 完成 holdings 本地配置体验完善。后续 v0.5-beta 可以在现有 market data interface 后接真实 A 股行情，但仍需保持不保存敏感仓位信息、不输出交易建议的边界。

## v0.5.2-alpha RSS 新闻驱动 market_brief

### 背景

v0.5-alpha/v0.5.1-alpha 已经完成 market brief 骨架和 holdings 本地配置体验，但手动生成的市场投研晨报仍主要依赖离线 sample 占位，不能体现当天 RSS 候选新闻。目标是在不接 AI、不接真实行情、不影响默认 daily digest 自动化链路的前提下，让显式 `market_brief` 使用真实 RSS 候选新闻生成更有信息量的观察。

### 实际改动

- 新增 `market_news.py`，从已收集的 RSS 候选文章中提取重要市场事件、产业催化、风险/反证、今日观察点、主题线索、AI 深挖问题和 holdings 相关新闻。
- `market_analysis.py` 扩展为组合层：把离线行情占位、holdings 配置、新闻分析和 RSS 失败源汇总成 `MarketBriefContext`。
- `market_brief_writer.py` 改为新的八段结构：市场环境观察、重要市场事件、产业催化与主线线索、我的持仓新闻观察、风险与反证、今日观察清单、建议交给 AI 投研小组深挖、数据与限制说明。
- `main.py` 的显式 `market_brief` 分支开始复用 `normalize_feeds`、`normalize_keywords` 和 `collect_news()`；单个 RSS 源失败继续记录并降级，不中断整体输出。
- 新增 `tests/offline_market_news_smoke.py`，用 fixture 验证新闻分析、风险线索、watch 点和 holdings 动态匹配。
- 扩展 `tests/offline_market_brief_smoke.py`，验证新八段结构、fixture 新闻进入 holdings 相关新闻、移除旧 1/5/20 日强势栏目、降噪和交易建议边界。
- 调整 `tests/offline_holdings_config_smoke.py`，显式传入空 feeds/keywords fixture，避免离线测试触发真实 RSS。
- README、PROJECT_STATE、BACKLOG、TESTING 同步 v0.5.2-alpha 状态。

### 边界

- 不接 AKShare、TuShare 或真实行情。
- 不接 AI rerank。
- 不输出买卖等交易动作建议。
- 不读取、打印或修改 `.env`。
- 不修改 `scripts/run_daily_digest.sh`、Bark、Obsidian、launchd 或 pmset 链路。
- `config/holdings.json` 继续只作为本地忽略文件；业务代码不硬编码具体持仓。

### 验证结果

- `tests/offline_market_news_smoke.py` 通过。
- `tests/offline_market_brief_smoke.py` 通过。
- `tests/offline_holdings_config_smoke.py` 通过。
- `tests/offline_digest_smoke.py` 通过，普通 daily digest 规则未回退。

### 结论

v0.5.2-alpha 让显式 market brief 从离线骨架升级为 RSS 新闻驱动的观察报告。下一步仍是 v0.5-beta 接入真实 A 股行情数据，但必须继续保持默认 digest 链路不变、holdings 动态配置和无交易建议边界。

## v0.5.2-alpha PROJECT_STATE Next Action 修正

### 背景

v0.5.2-alpha 已完成并 push 到 `origin/main`，提交为 `7339145`。真实 RSS 样例评审后，结论已经从“下一步接真实 A 股行情”调整为“先做新闻质量调优”。`docs/PROJECT_STATE.md` 的 Next Action 仍指向 v0.5-beta，滞后于 v0.5.2-alpha 样例评审结论。

### 实际改动

- `docs/PROJECT_STATE.md` 补充 v0.5.2-alpha 已完成并 push 的状态和 commit。
- `docs/PROJECT_STATE.md` 记录当前结论：技术链路成功，显式 `market_brief` 已可复用真实 RSS，但新闻筛选质量还不够投研化。
- `docs/PROJECT_STATE.md` 记录已发现的问题：事件筛选偏泛、观察理由模板化、AI/人工智能重复、风险/反证混入弱相关新闻、今日观察清单质量一般、holdings 暂未匹配到高价值相关新闻。
- `docs/PROJECT_STATE.md` 将 Next Action 改为 v0.5.3-alpha news quality tuning，并明确 v0.5-beta 真实 A 股行情接入排在其后。
- `docs/BACKLOG.md` 将 P0 / Next 调整为 v0.5.3-alpha news filtering quality tuning，并把 v0.5-beta real A-share market data 放到 Later。

### 边界

- docs-only correction。
- 不修改业务代码、配置、脚本、测试、RSS 源、Bark、Obsidian、launchd 或 pmset。
- docs-only correction；不修改业务代码、配置、脚本、测试、RSS 源、Bark、Obsidian、launchd 或 pmset。

## v0.5.3-alpha news quality tuning

### 背景

v0.5.2-alpha 已经跑通显式 `market_brief` 复用 RSS 候选新闻的技术链路，但真实样例评审发现新闻质量不够投研化：关键词命中容易误升格，观察理由偏模板化，AI / 人工智能线索可能重复，弱相关商业内容可能进入核心段落，holdings 匹配需要区分高精度和宽泛标签。

### 实际改动

- `market_news.py` 为 `NewsInsight` 增加 `relevance_score` 和 `news_type`，在进入 market events、industry catalysts、risk、watch points 和 holdings 相关新闻前先做相关度评分。
- 新闻类型分为宏观风险、政策监管、产业催化、公司融资 / IPO、普通商业新闻和弱相关内容。
- 对泛圆桌、泛访谈、普通消费维权、食品检验、普通活动/体验类内容做弱相关降权；没有明确行情、政策、订单、监管或公司资本事件支撑时不进入核心段落。
- 对 AI / 人工智能 / 大模型 / 算力 / 数据中心电力做主题聚合，避免同义主题重复铺新闻。
- 观察理由改为基于命中的具体变量生成，说明它可能影响风险偏好、板块预期、资金定价、订单/投资节奏或可比公司预期。
- holdings 相关新闻继续来自 `config/holdings.json` 或 example fixture 的 `code`、`name`、`sector`、`watch_tags`，并过滤 `出海`、`AI`、`新能源` 等宽泛标签单独触发。
- `market_brief_writer.py` 在核心新闻和 holdings 相关新闻中展示新闻类型和相关度。
- 扩展 `tests/offline_market_news_smoke.py` 和 `tests/offline_market_brief_smoke.py`，覆盖 relevance score、弱相关过滤、主题聚合、具体观察理由和 holdings 高/低精度匹配。

### 边界

- 不接真实 A 股行情。
- 不接 AKShare / TuShare。
- 不接 AI rerank。
- 不输出买卖等交易动作建议。
- 不读取、打印或修改 `.env`。
- 不修改 `scripts/run_daily_digest.sh`、Bark、Obsidian、launchd 或 pmset 链路。
- `config/holdings.json` 继续只作为本地忽略文件；业务代码不硬编码具体持仓。

### 验证结果

- `PYTHONPYCACHEPREFIX=/private/tmp python3 -m py_compile main.py market_news.py market_analysis.py market_brief_writer.py holdings.py market_data.py` 通过。
- `tests/offline_market_news_smoke.py` 通过。
- `tests/offline_market_brief_smoke.py` 通过。
- `tests/offline_holdings_config_smoke.py` 使用项目 `.venv` 前置 PATH 后通过；系统 `python3` 缺少 `feedparser`，未安装新依赖。
- JSON example 校验、`sh -n scripts/run_market_brief.sh`、`sh -n scripts/run_daily_digest.sh` 和 `git diff --check` 通过。
- 使用显式 `scripts/run_market_brief.sh --date 2026-06-27` 生成真实 RSS 样例 `output/market-brief-2026-06-27.md`；`output/` 为 gitignored。

### 结论

v0.5.3-alpha 把显式 market brief 的新闻筛选从“关键词命中即可进入”推进到“相关度评分 + 新闻类型 + 弱相关过滤 + 主题聚合 + 精确 holdings 匹配”。下一步应生成一份真实 RSS market brief 样例人工复核；样例质量稳定后，再考虑 v0.5-beta 接真实 A 股行情数据。

## v0.5.3-alpha quality fix

### 背景

人工复核 `output/market-brief-2026-06-27.md` 后，发现 v0.5.3-alpha 仍有几类质量问题：`9点1氪`、`氪星晚报` 等综合快讯合集因子事件关键词叠加导致相关度虚高；DeepSeek 招聘 / 智元灵巧手、IPO / 上市 / 开盘暴涨等分类仍会误判；产业催化可能只显示主题不显示代表新闻；风险与反证、今日观察清单仍偏复制标题或理由；holdings 可能被泛行业词误触发。

### 实际改动

- 综合快讯合集、晚报、早报、日报、周报类内容整体降权，不再直接进入核心事件；本轮不做子事件抽取。
- 新闻分类改为标题优先：IPO、上市、融资、估值、并购等优先归为公司融资 / IPO；只有标题或正文出现正式监管处罚、证监会、交易所、监管函、政策文件等才归为政策监管。
- 观察理由加入来源、标题、类别和对应市场变量，不再只输出命中词模板。
- 产业主题线索只从已入选的代表产业催化新闻生成；没有代表新闻时不展示孤立主题。
- 风险与反证改为风险变量 / 反证逻辑，不再重复重要事件标题。
- 今日观察清单改为可观察变量，不再复制观察理由。
- holdings 相关新闻匹配进一步区分精度，`电力设备`、`风电设备` 等泛行业词不能单独触发强相关新闻。
- 扩展离线 smoke，覆盖 `9点1氪` / `氪星晚报` 合集、IPO 分类、弱相关 theme、风险/观察变量和泛行业 holdings 误挂。

### 验证结果

- `tests/offline_market_news_smoke.py` 通过。
- `tests/offline_market_brief_smoke.py` 通过。
- 使用显式 `scripts/run_market_brief.sh --date 2026-06-27` 重新生成真实 RSS 样例 `output/market-brief-2026-06-27.md`；样例中 `9点1氪` / `氪星晚报` 不再进入核心事件，IPO / 上市样本归为公司融资 / IPO，holdings 不再误挂 *ST 电力设备并购新闻。

### 结论

v0.5.3-alpha quality fix 明显改善了真实样例的误升格、误分类、重复和 holdings 泛匹配问题。剩余质量仍受规则方案限制，后续若继续追求投研级筛选，建议基于 `docs/MISSED_CASES.md` 记录具体样例后再评估 AI rerank 或子事件抽取。

## v0.5-beta real A-share market data first stage

### 背景

v0.5-alpha 到 v0.5.3-alpha 已经让显式 `market_brief` 具备 holdings 配置、RSS 新闻驱动观察和新闻质量规则，但报告仍缺少最小行情验证。第一阶段目标不是完整投研系统，而是在不影响普通 daily brief 自动化链路的前提下，为显式 market brief 增加主要指数和 holdings 个股涨跌。

### 实际改动

- `market_data.py` 增加小型行情数据层：`fetch_market_snapshot()`、`fetch_index_quotes()`、`fetch_holding_quotes()`。
- 行情数据结构包含 `indexes`、`holdings` 和 `failures`；单个行情请求失败只记录 failure，不中断 report。
- 第一阶段使用标准库请求轻量公开行情接口，不新增 AKShare、TuShare 或其他生产依赖。
- 主要指数覆盖上证指数、深成指、创业板指、科创50；字段包括名称、代码、涨跌幅、成交额、source 和 as_of。
- holdings 个股涨跌从本地 holdings 动态读取代码；行业 / 板块优先来自 holdings 配置中的 `sector` 字段，不做外部行业硬猜。
- `market_analysis.py` 将行情 quote 合并进持仓观察。
- `market_brief_writer.py` 改为六段结构：市场温度、今日主线、我的持仓观察、重要新闻与验证、风险与反证、今日继续观察。
- `tests/offline_market_data_smoke.py` 新增离线行情 fixture，覆盖正常返回、字段缺失、行情失败和未配置 holdings。
- `tests/offline_market_brief_smoke.py` 覆盖指数和 holdings 涨跌展示、行情失败降级、无 holdings 不崩溃和交易建议词边界。

### 边界

- 不修改 `scripts/run_daily_digest.sh`。
- 不改变默认 `python3 main.py` 行为；只有显式 `market_brief` 或配置为 `market_brief` 时才尝试行情。
- 不提交 `config/holdings.json` 或 `output/`。
- 不输出买卖、加减仓、止损止盈等具体交易动作。
- 行情字段缺失时显示“数据暂不可用”，不编造。
- 第一阶段不计算板块强度、相对强弱、复杂策略或产业催化强度。

### 验证结果

- `tests/offline_market_data_smoke.py` 通过。
- `tests/offline_market_brief_smoke.py` 通过。
- `tests/offline_holdings_config_smoke.py` 通过，子进程显式使用离线行情开关，避免 smoke 依赖真实网络。

### 结论

v0.5-beta 第一阶段把显式 market brief 从“新闻驱动观察”升级为“新闻 + 最小行情验证”。普通 daily brief 自动化链路仍保持原样；后续再根据真实样例决定是否继续评估更稳定行情源、行业 / 板块行情和相对强弱指标。

## v0.5-beta.1 market brief quote polish

### 背景

基于真实 `output/market-brief-2026-06-27.md` 样例复核，v0.5-beta 第一阶段暴露出几个小问题：周末生成时 report date 和行情实际交易日容易混淆；轻量行情源成交额字段口径尚未校验却被直接展示；今日主线为空时出现空模板；IPO / 融资类新闻刷屏；风险变量重复；持仓已有行情但缺少轻量相对描述。

### 实际改动

- `MarketSnapshot` 增加 `market_data_date`，从行情 `as_of` 推导实际行情交易日，报告中与 report date 分开展示。
- 成交额字段在口径确认前统一显示“数据暂不可用”，并在 `failures` 中记录 amount 字段口径限制。
- 今日主线没有产业催化内容时，不再追加“暂无可展示内容”空模板句。
- 风险与反证变量按文本去重。
- IPO / 融资类重要新闻最多展示 2 条。
- 海外 IPO / pre-IPO 新闻如果无法映射到 A 股产业链或当前主线，则不进入重要新闻。
- 持仓观察增加相对主要指数均值的轻量描述：强于、弱于或接近主要指数均值；不输出交易动作。
- 扩展 `tests/offline_market_data_smoke.py` 和 `tests/offline_market_brief_smoke.py` 覆盖上述问题。

### 边界

- 不新增依赖。
- 不修改 `scripts/run_daily_digest.sh`。
- 不改变默认 `python3 main.py` 行为。
- 不提交 `output/` 或 `config/holdings.json`。
- 不做买卖建议、不输出交易动作。

### 结论

v0.5-beta.1 只做真实样例暴露的小修复，继续保持显式 market brief 与普通 daily brief 自动化链路隔离。后续如果要恢复成交额展示，应先确认轻量行情源字段口径或更换更明确的数据源，并补离线回归。

## v0.5-beta.2 market-led theme and holdings anomaly polish

### 背景

2026-06-29 手动生成的真实 `market_brief` 样例证明轻量行情接入有效，但也暴露出行情和新闻融合表达的问题：单条低相关度新能源 / 储能新闻被提升为今日主线，科创50显著强于其他主要指数却没有单独提示，持仓明显逆势走弱但只显示“弱于主要指数均值”，成交额不可用说明偏工程化，财报 / 营收新闻可能被误归为 IPO / 融资。

### 实际改动

- 新闻主题聚合增加置信度门槛：单条低相关度产业新闻不再直接生成“新闻线索指向”。
- 今日主线在新闻证据不足时输出“RSS 候选新闻中暂未提取到足够明确的产业主线”。
- 基于现有宽基指数数据增加轻量行情层面观察：科创50显著强于其他主要指数时，提示“科创 / 硬科技方向风险偏好较强”，并明确该判断仅来自宽基指数表现。
- 持仓相对观察从“强于 / 弱于 / 接近”升级为“小幅 / 明显 / 逆势走强 / 逆势走弱”等简单等级。
- 持仓明显逆势且 RSS 候选无相关新闻时，增加异常提示，提醒后续观察板块、公司消息或资金行为。
- 成交额不可用提示改为读者向说明：当前轻量行情源未稳定返回成交额字段，本次不判断放量 / 缩量。
- 今日继续观察在成交额不可用时，不再要求观察成交额是否支持新闻主线。
- 新闻分类新增“公司经营 / 财报”，财报、营收、利润、经营数据类新闻不再误归为“公司融资 / IPO”。
- 扩展 `tests/offline_market_news_smoke.py` 和 `tests/offline_market_brief_smoke.py` 覆盖上述场景。

### 边界

- 不新增行情源或依赖。
- 不修改 `scripts/run_daily_digest.sh`。
- 不改变默认 `python3 main.py` 行为。
- 不接入 Bark / Obsidian / launchd / pmset。
- 不提交 `output/` 或 `config/holdings.json`。
- 不做买卖建议、不输出交易动作。

### 结论

v0.5-beta.2 继续保持 `market_brief` 为手动显式生成，只改善已有轻量行情与 RSS 新闻的融合质量。普通 daily brief 自动化链路不变，后续继续观察真实交易日样例，再决定是否需要更稳定的数据源或 AI rerank。

### 2026-06-29 真实样例复核

- 重新手动生成 `output/market-brief-2026-06-29.md` 后，确认单条低相关度新能源 / 储能新闻未再直接生成新闻主线。
- 科创50 +4.61% 被输出为“行情层面观察”，且说明该判断仅来自宽基指数表现。
- 金风科技 -6.86% 在主要指数整体偏强背景下被识别为“逆势走弱”，RSS 无相关新闻时输出“RSS 候选新闻暂未解释该波动”的异常提示。
- 成交额不可用文案改为读者向口径，今日继续观察不再要求观察不可用成交额。
- 复核中发现“上市公司 + 营收 / 利润”真实新闻仍可能被泛“上市”词拉入“公司融资 / IPO”，已补离线样本并修正为优先识别“公司经营 / 财报”。

## v0.5-beta.3 news event ranking and consolidation polish

### 背景

2026-07-03 手动生成的真实 `market_brief` 样例显示，v0.5-beta.2 已避免弱新闻硬凑主线，但新闻事件处理仍有投研排序和表达问题：证监会再融资 / 定增政策被普通 IPO 新闻压在后面；同主题证监会政策拆成两条重复展示；创新药出海 / 阿斯利康海外投资被误归为公司融资 / IPO；海外基建 / 风电弱变量被挂到金风科技下时语气偏“明确相关新闻”；风险与反证没有优先覆盖政策变量。

### 实际改动

- 提高政策监管新闻优先级，扩展证监会、交易所、再融资、定增、储架发行、减持、退市、并购重组、问询、处罚、征求意见等规则信号。
- 增加轻量政策事件合并：证监会再融资 / 定增 / 储架发行 / 征求意见类同主题新闻会合并为一个重要事件，并在观察理由中保留另一条同主题线索。
- 收紧公司融资 / IPO 分类：IPO、递表、招股书、募资、港股 IPO、美股 IPO、纳斯达克、Pre-IPO、融资轮等明确资本市场词才触发；“投资 / 重押 / 出海 / 营收 / 欧洲 / 欧元”等不再单独归入 IPO / 融资。
- 创新药出海 / 海外投资类新闻改走产业催化观察，不再挤占公司融资 / IPO。
- 持仓相关新闻增加置信度分层：公司名 / 代码 / 高精度线索为“明确相关新闻”，低相关度行业或外部变量为“弱相关变量”。
- `relevance < 60` 或仅命中宽泛行业词的 holdings 新闻不再输出“高精度线索”；弱相关变量会同时提示 RSS 候选新闻暂未解释该波动。
- 风险与反证从入选重要新闻补政策变量：再融资和定增储架制度会输出落地细则、适用范围和市场解读相关风险。
- 扩展 `tests/offline_market_news_smoke.py` 和 `tests/offline_market_brief_smoke.py`，覆盖政策排序、政策合并、IPO 分类收紧、公司经营 / 财报保持、弱相关 holdings 渲染和直接交易建议词边界。

### 边界

- 不新增依赖。
- 不新增行情源、AKShare、TuShare、AI rerank、券商、交易账户或自动交易能力。
- 不修改 `scripts/run_daily_digest.sh`。
- 不改变默认 `python3 main.py` 行为。
- 不接入 Bark / Obsidian / launchd / pmset，也不自动推送 `market_brief`。
- 不提交 `output/`、`config/holdings.json`、`.env` 或 secrets。
- 不输出买入、卖出、加仓、减仓、止损、止盈等直接交易建议。

### 验证结果

- 本轮完成代码和文档更新后，按 `docs/TESTING.md` 和任务要求运行离线验证。
- 普通 daily brief smoke 保持通过，确认默认日报链路未回退。
- `scripts/run_daily_digest.sh` 未修改；普通 daily brief 仍是唯一自动推送链路，`market_brief` 仍需手动显式生成。

### 结论

v0.5-beta.3 将显式 `market_brief` 的 RSS 新闻处理从“单条新闻排序”推进到轻量事件级处理：政策监管更靠前、同主题政策不重复刷屏、IPO / 融资分类更克制、持仓相关新闻表达更区分置信度。后续若继续出现复杂跨源重复或重要性判断问题，再基于真实样例评估 AI rerank，不在本轮扩大范围。

## v0.5-beta.3.1 policy ranking and theme threshold hotfix

### 背景

2026-07-03 真实 `market_brief` 样例继续暴露出几个规则边界问题：证监会再融资 / 定增政策仍可能被普通 IPO / 创业融资新闻压过；创新药出海文本里的泛“监管”可能误归为政策监管；今日主线兜底后仍展示低相关度产业新闻；观察理由里可能重复展示命中词；风险与反证需要更明确覆盖再融资 / 定增储架发行变量；大型券商业绩预告排序仍偏低。

### 实际改动

- 强化 A 股制度变量排序：再融资、定增、储架发行与证监会 / 交易所 / 规则 / 制度 / 征求意见同现时提高相关度。
- 收紧政策监管分类：单独出现“监管”不再足以归为政策监管，需更强政策词或监管组合；否定语境中的政策词不会被当作正向命中。
- 观察理由中的命中关键词按原顺序去重，避免 `出海、出海`、`监管、监管`。
- 对大型金融 / 券商利润预告增加窄范围排序权重，确保重要上市公司业绩变量高于普通创业融资 / IPO。
- 今日主线渲染增加 `relevance >= 70` 门槛，低相关产业候选不再跟在“暂未提取到足够明确的产业主线”后展示。
- 风险与反证文案明确输出再融资和定增储架发行制度的落地细则、适用范围、融资节奏和资金偏好变量。
- 扩展离线 smoke，覆盖政策排序、泛监管分类、关键词去重、低相关主线阈值、政策风险文案和交易建议词边界。

### 边界

- 不新增依赖、行情源、AI rerank、券商 / 交易账户或自动交易能力。
- 不修改 `scripts/run_daily_digest.sh`，不改变默认 `python3 main.py` 行为。
- 不接入 Bark / Obsidian / launchd / pmset，也不自动推送 `market_brief`。
- 不读取、打印或提交 `.env`、`config/holdings.json`、`output/` 或 secrets。
- 不输出买入、卖出、加仓、减仓、止损、止盈等直接交易建议。

### 验证结果

- 已新增 regression 后先跑出失败，再小步修复规则。
- `tests/offline_market_news_smoke.py` 通过。
- `tests/offline_market_brief_smoke.py` 通过。
- 完整验证覆盖 Python 编译、market data / market news / market brief / holdings config / ordinary digest 离线 smoke、脚本语法检查和 `git diff --check`。

### 结论

v0.5-beta.3.1 将本轮真实样例中的排序、分类、低相关主线和风险变量问题收口为离线回归。显式 `market_brief` 仍保持规则驱动和手动运行，不影响普通 daily digest 自动链路。

## v0.5-beta.4 daily digest readability polish

### 背景

普通 daily digest 自动化链路已经稳定，但每日新闻条目仍以标题加多行元信息呈现：来源、时间、为什么重要和裸链接占用空间较多，而标题下缺少新闻梗概。读者扫读时需要打开原文才能理解事件细节，“为什么重要”也容易变成低信息量模板句。

### 实际改动

- 普通 `digest` 新闻条目统一改为：标题、RSS 摘要清洗后的梗概、一行压缩来源 / 时间 / 原文链接。
- 摘要只使用现有 RSS 字段，不接 AI、不联网补充、不新增数据源。
- 摘要清洗会去除 HTML tag、HTML entity、多余空白和少量站点模板残留。
- 中文摘要优先保留最多 3 个完整短句，并在约 180 字以内截断；英文摘要控制在约 90 个词以内。
- 无可用 RSS 摘要时使用保守 fallback：提示当前仅能确认标题所述事件，建议查看原文。
- 元信息压缩为 `` `来源 · MM-DD HH:MM` · [原文](url) ``；时间解析失败时保留现有时间字符串但不拆成多行。
- `tests/offline_digest_smoke.py` 增加 Markdown 渲染回归，覆盖 HTML 摘要清洗、压缩时间、原文链接、无摘要 fallback 和旧 bullet 格式移除。

### 边界

- 不修改 `scripts/run_daily_digest.sh` 或 `scripts/run_market_brief.sh`。
- 不改变 Bark / Obsidian / launchd / pmset 自动化链路。
- 不修改 `market_brief` 核心规则、行情、新闻排序或持仓逻辑。
- 不读取、打印或提交 `.env`、`config/holdings.json`、`output/` 或 secrets。
- 不新增 AI summary、外部 API、新 RSS 源、AKShare、TuShare、券商 / 交易账户或自动交易能力。

### 验证结果

- 先新增 digest Markdown 渲染 regression 并确认旧格式下失败，再小步实现新 renderer。
- `tests/offline_digest_smoke.py` 已通过，证明普通 digest 分流逻辑和新条目格式同时满足预期。
- 本轮完成后按任务要求运行完整离线回归、脚本语法检查和 `git diff --check`。

### 结论

v0.5-beta.4 只改善普通 daily digest 的 Markdown 阅读体验，让每条新闻更接近“可直接扫读”的摘要卡片。market_brief 和自动化执行链路保持隔离，后续重点观察真实每日 digest 的 RSS 摘要质量和无摘要 fallback 出现频率。

## v0.5-beta.5 important news relevance and classification polish

### 实际改动

- `market_brief` 重要新闻最多保留 5 条，同一来源最多 2 条，`公司融资 / IPO` 最多 2 条；高相关政策和业绩事件不再被单一来源融资稿挤占。
- 融资与财报分类按标题主动作处理；`完成融资`、轮次、领投和递表等优先归融资，`亿元`、`上半年`不再单独触发财报。
- 投资机构名册、榜单、名单等行业资料在没有具体融资 / IPO / 递表 / 招股书等资本事件时不归为 `公司融资 / IPO`，并降低优先级。
- 政府部门 / 监管部门作为标题主体且主动作是立案、查处、处罚、整治、通报、执法或专项行动时，优先归为 `政策监管`；`上半年`、`同比增长` 和百分比不覆盖监管主动作。
- AI 应用 / 企业软件不再升级为算力或数据中心电力主题；算力和数据中心电力均要求直接基础设施证据。
- 风险与反证、今日继续观察优先使用市场强弱和持仓异常，单条普通融资新闻只作为后置补充。
- 扩展 market news / market brief 离线 smoke，覆盖来源与类型限额、分类冲突、投资机构名册降权、政府监管统计分类、主题直接证据、市场反证和持仓异常优先级。

### 边界与验证

- 未修改普通 daily digest 展示结构、默认 `python3 main.py`、Bark / Obsidian / launchd / pmset 或两个运行脚本。
- 未接入 AI rerank、新 RSS 或行情源、外部 API、market_brief 自动推送或交易能力。
- 已通过 Python 编译、market data/news/brief、holdings config、ordinary digest 离线 smoke、脚本语法检查和 `git diff --check`。

### 结论

v0.5-beta.5 已完成，准备随当前 commit/push 收口。后续继续观察真实 `market_brief` 样例中来源限额、类型限额、行业资料降权、政策监管统计分类、主题直接证据和市场 / 持仓异常优先级是否稳定。

## v0.6.0-alpha AI Curator shadow foundation

### 背景

v0.5-beta.5 后的审计结论是：整个项目仍可维护，但新闻判断层已经形成显著局部规则债，尤其是 `market_news.py::_score_article`。后续不应继续向 `_score_article`、digest 分类规则、主题规则或风险规则追加单条新闻补丁，而应建立独立的 AI Curator shadow 路径。

### 实际改动

- 新增 `ai_curator.py`，定义 `CandidateArticle`、`CuratorRequest`、`CuratedEvent`、`CuratorResponse`、`CuratorProvider`、`FixtureCuratorProvider` 和严格 response validator。
- RSS 候选池移动到 legacy 关键词 gate 之前：RSS entry 先完成字段标准化、时间窗口过滤和 exact deduplication，再分流到 legacy pipeline 与 shadow pipeline。
- `fetch_feed()` 继续返回旧 `NewsItem`，并保持 legacy 关键词过滤、数量限制、digest 和 `market_brief` 行为不变。
- 新增 candidate trace，用于记录完整候选池和 legacy 诊断字段，帮助区分 source miss、selection miss、classification miss 和 deduplication miss。
- 新增 `scripts/run_ai_curator_shadow.py` 作为显式 shadow preview 入口，必须提供本地 fixture response，不调用真实 AI。
- `scripts/run_ai_curator_shadow.py` 增加 `--candidate-fixture`，可用本地候选文章 fixture 完全离线生成 request、trace 和 preview；提供该参数时不读取 feeds、不调用 RSS。
- 无链接 RSS 条目在具备标题、feed/source metadata 和发布时间时可进入 shadow `CandidateArticle` pool，并使用 source + normalized title + published_at 的稳定 fallback `article_id`；legacy `NewsItem` / daily digest 路径继续保持链接要求。
- validator 将同一 event 内重复 `evidence_article_ids` 视为 contract violation，但仍允许同一 article 支持不同 event。
- 新增 `docs/AI_CURATOR_ARCHITECTURE.md` 记录 Global Event Curator 边界、数据契约、trace 和下一步 provider 接入点。
- 新增 `tests/offline_ai_curator_candidate_smoke.py`、`tests/offline_ai_curator_contract_smoke.py` 和 `tests/offline_ai_curator_cli_smoke.py`，覆盖候选池绕过关键词 gate、稳定 article id、无链接 candidate、response contract、完全离线 CLI、trace 字段隔离和 preview 安全边界。

### 边界

- 不接 OpenAI、Anthropic、Gemini、DeepSeek、Codex CLI 或任何真实外部 AI API。
- 不修改默认 `python3 main.py` 行为。
- 不修改 `scripts/run_daily_digest.sh` 或 `scripts/run_market_brief.sh`。
- 不改变 Bark / Obsidian / launchd / pmset 自动化链路。
- Global Event Curator request 不包含 holdings、持仓行业标签、持仓涨跌、指数涨跌、legacy relevance score、legacy category、matched keywords、legacy theme 或 risk/watch 输出。
- 本阶段不生成投资建议、买卖建议、目标价或个股推荐。
- 本阶段不验证真实 AI 选闻质量；provider 接入前仍只使用 fixture response。

### 结论

v0.6.0-alpha 只完成 AI Curator 的 shadow foundation。legacy 规则路径被保留并冻结为 fallback；下一步是接入真实 provider 进行 shadow comparison，在质量验证前不替换 ordinary daily digest、显式 `market_brief` 或任何生产自动化链路。

## 2026-08-08 canonical runtime data root migration

### 实际改动

- 新增 `project_paths.py`，统一解析 `~/Projects/_project-data/automation-brief/`；优先级为显式 CLI / 函数参数、`AUTOMATION_BRIEF_DATA_ROOT`、home 默认值。
- 默认报告写入 `reports/`，日志写入 `runs/daily-news.log`，AI Curator shadow 写入 `runs/ai-curator-shadow/`，本地 holdings 使用 `manual-inputs/holdings.json`；显式 `--output`、`--output-dir`、`--holdings` 保持可用。
- downstream mobile digest 和 Bark reader 改为读取 canonical reports；Obsidian / iCloud 仍由下游 `.env` 配置决定。
- `config.json` 保留 `output_dir: "output"` 兼容 token，由 resolver 映射到 canonical reports；没有写入绝对路径。

### 数据迁移与验证

- migration id：`migration-20260808T095613Z`。
- 从 legacy `output/` 复制 68 份 daily / market Markdown，从仓库根复制 `daily-news.log` 和 `config/holdings.json`，共 70 个文件；逐文件验证字节数、SHA-256 和 UTF-8 可读性。
- legacy `output/ai-curator-shadow/` 不存在，因此没有伪造历史 shadow artifacts；仅创建 canonical shadow 目录。`output/.DS_Store` 明确排除。
- 迁移记录位于 canonical `migration-records/<migration-id>/`，只含路径、大小、哈希和校验元数据，不含 holdings 值、报告正文、`.env`、secrets 或 provider payload。legacy 文件原样保留。
- 新增 `tests/offline_project_paths_smoke.py`，覆盖 resolver precedence、temp reports / market brief / shadow / log、holdings canonical/example/empty/explicit 和 downstream canonical reader；所有离线 smoke 均通过，AI Curator candidate smoke 连续 5 次通过。

### 边界

- 未调用真实 RSS、AI provider、Bark、Obsidian、launchd 或 pmset；未读取或打印 `.env` 内容；未创建 commit 或执行 push。
- 不删除 legacy 文件，不清理 audit worktree；后续清理另行评估。

## 2026-08-12 v0.6.2 Phase 2 Provider Adapter + Shadow Artifact Foundation

### 实际改动与验证

- 新增 OpenAI-compatible 标准库 HTTP adapter，保留 shadow-only 边界、timeout、有限重试、response validator 和最小 content policy；不接入 production entry。
- 新增 shadow run artifact writer：validated success persistence、request/response date consistency、atomic staging publish、failure cleanup、byte measurements、safe review rendering、Legacy evaluation labels、candidate context 和 typed fetch-failure trace allowlist。
- 增加 provider / artifact / CLI targeted regressions，并完成全部 AI Curator、digest/feed、market、holdings fixture、project paths、Project State push-gate、Python compile 和 `git diff --check` 验证。

### 边界与结论

- 未调用真实 RSS、AI provider 或 holdings；未读取 `.env`，未写 canonical runtime data；daily digest、`market_brief`、Bark、Obsidian、launchd、pmset 和 Curator domain schema 保持不变。
- Final Corrective Audit 结果为 PASS。Phase 2 foundation 完成；整体 `v0.6.2 — AI Curator Shadow Evaluation` 尚未完成，后续阶段另行评估。

## 2026-08-12 v0.6.2 Phase 3A DeepSeek Configuration + Real-call Preflight

### 实际改动与验证

- 在现有标准库 OpenAI-compatible adapter 上增加冻结的 DeepSeek one-shot profile：`deepseek-v4-flash`、`https://api.deepseek.com/chat/completions`、90 秒、最多 2 次、8192 tokens、disabled thinking 和 JSON mode；最终 body 只保留显式 allowlist 字段，不启用 stream/tools 或 arbitrary passthrough。
- 新增 `--real-provider deepseek` 显式 opt-in 和 `--dry-run` preflight；fixture 默认路径不因环境中存在 key 而联网。preflight 使用 exact serialized bytes 报告 CuratorRequest / provider body 大小，transport calls 固定为 0，不生成伪造 succeeded artifact。
- 增加 provider body/response safety、`choices[0].finish_reason == "stop"` 成功边界、其他 finish reason fail closed / no retry、preflight limit 0-call、unknown provider、fake key 隔离和真实 provider failed metadata 的离线回归；Phase 3A 不启用 payload limit 正式默认值。

### Phase 3B temporary fixture one-shot gate（下一阶段冻结决策，当前未启用）

记录下一阶段 fixture one-shot gate 的临时限制：

- `max_candidate_count = 2`
- `max_provider_request_body_bytes = 4096`
- `max_attempts = 2`
- `max_tokens = 8192`

这些只是 Phase 3B fixture one-shot gate limits，不是 live RSS / production limits；本轮没有启用它们，也没有进入 Phase 3B。

### 边界与结论

- 本阶段未调用真实 DeepSeek API、真实 RSS、Bark 或 Obsidian，未读取 `.env` 或真实 holdings，未写 canonical runtime data；没有改动 `main.py`、daily/market brief、launchd、pmset 或生产自动化。
- Phase 3A 的配置与 preflight boundary 已完成，但整体 `v0.6.2 — AI Curator Shadow Evaluation` 仍未完成：尚未进行真实 provider 质量评估、比较器或生产切换。

## 2026-08-12 v0.6.2 Phase 3B Fixture One-shot Gate Offline Safety Preparation

### 实际改动与验证

- 在显式 `--real-provider deepseek` fixture path 中冻结并启用 `max_candidate_count=2`、`max_provider_request_body_bytes=4096`；该模式强制要求 `--candidate-fixture`，不会退回 feeds/RSS；同一组限制同时用于 `--dry-run` 和 actual provider path，通用 Phase 3A provider 默认仍不注入 limit。
- hard-limit 检查在 exact request-body serialization 后、API key lookup / `urllib.request.Request` / HTTP transport 前执行；超限 fail closed，`attempts=0`、transport calls 为 0，不自动截断、删除或替换 candidates/payload。
- 保持 DeepSeek `deepseek-v4-flash`、90 秒、最多 2 次、8192 tokens、disabled thinking、JSON mode、`finish_reason == "stop"` 和既有 retryable contract；artifact writer、allowlist、atomic publish、production daily/market paths 未改变。
- provider/CLI offline smoke 增加恰好 2 个候选、候选超限、body 边界、无截断、dry-run 0 calls、actual 缺 key 前置失败等回归；未新增依赖。

### Final offline dry-run measurement

- `candidate_count=2`
- `curator_request_bytes=1178`
- `provider_request_body_bytes=2487`
- `transport_calls=0`

### 边界与结论

- 本阶段未调用真实 DeepSeek API、真实 RSS、Bark 或 Obsidian，未读取 `.env` 或真实 holdings，未写 canonical runtime data；没有改动 `main.py`、daily/market brief、launchd、pmset 或生产自动化。
- Phase 3B 只完成 one-shot real-provider gate 的离线 safety preparation；整体 `v0.6.2 — AI Curator Shadow Evaluation` 尚未完成，真实 provider 质量评估仍待用户下一步明确执行。

## 2026-08-12 v0.6.2 Phase 3B Failed Provider Validation Diagnostics

### 问题定位

第一次 DeepSeek one-shot 已经完成 HTTP success、`finish_reason`、assistant content JSON parse，并在本地 `validate_curator_response()` 阶段失败。旧 provider boundary 捕获 `CuratorContractError` / `CuratorContentPolicyError` 时丢弃了 exception，本地只保留 `failure_stage=validation`、`failure_code=invalid_curator_response`，因此 failed artifact 无法区分具体 validator rule。

### 实际改动

- 为现有 `CuratorContractError` 增加最小结构化 metadata：allowlisted diagnostic code、field path 和可选已知 article id；不改变 `CuratorResponse` domain schema。
- provider error 继续保留 generic `failure_code` 与 secret-safe string，同时向 CLI / artifact writer 传递 bounded diagnostic metadata。
- failed `run.json` / `review.md` 可记录 `failure_diagnostic` 的 rule/path（必要时 known candidate article id）；成功 artifact 不增加该字段。
- 不保存 raw provider response、完整模型 payload、raw exception text、API key、Authorization header 或 HTTP envelope；unknown evidence id 不进入 artifact。
- 增加 invalid evidence、missing required field、duplicate evidence、selected/rejected overlap 和 direct trading advice content-policy regressions。

### 验证与边界

- 全部 AI Curator offline candidate / contract / provider / artifact / CLI smoke 通过；未进行第二次真实 DeepSeek 调用、未调用 RSS、未读取 `.env` 或 holdings、未写 canonical runtime data。
- 未改变 provider request body、retry policy、Phase 3B limits、production entry 或 success artifact contract。
- 整体 `v0.6.2 — AI Curator Shadow Evaluation` 仍未完成，Blockers 保持 `暂无明确阻塞。`。

## 2026-08-12 v0.6.2 Phase 3B Prompt Contract Alignment

### 问题定位

第二次真实 DeepSeek one-shot 已完成 Provider/HTTP/JSON pipeline，但真实 response 在本地 validator 因缺少 `events[].canonical_title` 失败。旧 system prompt 只列出顶层 response keys，并未给出 event/rejected article 的 exact output skeleton，因此没有充分约束 `canonical_title` 这个字段名。

### 实际改动

- 在现有 OpenAI-compatible / DeepSeek 共用的 system prompt 中加入紧凑 exact `CuratorResponse` JSON skeleton。
- 明确所有顶层、event、rejected article key；特别要求 `canonical_title`，禁止 `title` / `headline` alias，禁止省略 required keys 或返回额外 prose / Markdown fence。
- 明确空 collection 使用空数组、evidence/rejected article ids 必须来自 request、现有 enum values 和 `zh-CN` target language。
- 未修改 Curator domain schema、validator、parser alias、request body allowlist、retry、finish_reason、Phase 3B limits、artifact contract 或 production entry。

### 验证与边界

- fake provider exact valid response、`title` alias / missing `canonical_title` fail-closed、prompt contract、evidence boundary 和 target-language regressions 已覆盖。
- 两候选 prompt-aligned baseline fixture 的 DeepSeek request body 为 `3944` bytes，仍低于既有 `4096` Phase 3B gate；`curator_request_bytes=1178`、transport calls 保持 `0`；未执行第三次真实 DeepSeek、RSS 或 holdings 读取，未写 canonical runtime data。
- 整体 `v0.6.2 — AI Curator Shadow Evaluation` 仍未完成，Blockers 保持 `暂无明确阻塞。`。

## 2026-08-12 v0.6.2 Phase 3B Real Provider Shadow Gate Closeout

### Real-provider gate result

- Fixture-only real-provider one-shot run `20260812T075832.935190Z-ffb3a259aaa6` 使用 DeepSeek `deepseek-v4-flash`，`attempts=1`、`candidate_count=2`、`status=succeeded`、`validation_status=passed`。
- Exact measurements：`curator_request_bytes=1178`、`provider_request_body_bytes=3944`；AI event count 为 `1`，rejected article count 为 `1`，Legacy comparison 为 `not evaluated`。
- 成功 shadow artifact 已生成 `run.json`、`request.json`、`response.json`、`trace.json` 和 `review.md`。本记录只保留安全 metadata，不记录 API key、Authorization header、raw HTTP envelope 或 raw provider response。

### Human review observation

- Provider / HTTP / JSON / `finish_reason` / `CuratorResponse` validation / content policy / artifact persistence 全链路通过；canonical title、中文 summary、evidence mapping、reject 行为正常，未出现交易建议。
- `why_important` 在事实 evidence 之上加入了更强的解释性推断，例如把协调流动性行动进一步解释为系统性压力或政策转向。该问题不阻塞 Phase 3B，但进入 Phase 4 人工 evaluation 维度：fact vs interpretation boundary、unsupported causal inference、unsupported market implication 和 uncertainty handling。
- 当前不修改 validator、不增加关键词或 content scoring，也不建设复杂 fact-check framework。

### 边界与结论

- Phase 3B 技术 verdict 为 PASS；本次 gate 只使用 two-candidate fixture，未使用真实 RSS，未影响 production daily digest / `market_brief`，Bark、Obsidian、launchd 和 pmset 保持不变。
- `max_candidate_count=2`、`max_provider_request_body_bytes=4096` 以及对应 request profile 仍只属于 Phase 3B fixture one-shot gate，不是 live RSS / Phase 4 / production limits。
- 整体 `v0.6.2 — AI Curator Shadow Evaluation` 尚未完成；Next Action 进入 Phase 4 — Live RSS Shadow Evaluation，先重新测量并冻结 live limits，保持 shadow-only。Blockers 保持 `暂无明确阻塞。`。

## 2026-08-12 v0.6.2 Phase 4A Snapshot Contract Correction + Payload Decomposition

### Snapshot contract correction

- 上一轮 live RSS audit 发现：collector 合法保留了 19 条 `published_at=null` 且有 link 的候选，但 `load_candidate_fixture()` 把 null 当作缺失必填值。
- `ai_curator.py` 现允许显式 `published_at: null`，但仅限 link 非空；字段缺失、空字符串、malformed ISO datetime，以及 linkless + null 仍 fail closed。不会伪造当前时间或 report date，不改变 link-based article identity、language、dedup 或 legacy semantics。
- 新增 targeted contract regression，覆盖 linked null、valid timestamp、malformed timestamp 和 linkless null；现有 candidate/response contract 继续通过。

### Formal replay and offline measurements

- `/private/tmp/automation-brief-live-candidates-20260812T081815290841Z.json` 通过正式 loader replay 为 exactly `159` candidates。
- 使用当前 `deepseek-v4-flash` exact serializer、完整 summary 的 `curator_request_bytes=478169`、`provider_request_body_bytes=492741`；transport calls=`0`。
- Counterfactual provider body bytes：title-only `97583`；summary 300/500/1000 characters 分别为 `132770` / `138482` / `152332`。按 snapshot 原始顺序取 first 25/50/100/all 的 current-summary body 分别为 `23451` / `44273` / `85883` / `492741`。
- Summary 分布为 p50=`95`、p90=`6524`、p95=`13889`、最大=`54536` characters，11 条缺失 summary；GitHub Trending Python Daily 占 candidate serialized article bytes 的 `62.7564%`，VentureBeat AI 占 `16.1705%`。少量异常长 summary 明显主导 payload，但本轮不因此设计 source policy、candidate cap 或 truncation。

### Window and production boundary

- Phase 4A 未修改 window semantics：`main.py` 的 `within_lookback_hours()` 对每篇文章动态调用 `datetime.now(timezone.utc)`，没有冻结 reference time；`CuratorRequest.window_start/end` 仍由候选最早/最晚 non-null `published_at` 推导。
- 不改变上述语义，因为 `fetch_feed_candidates()` 同时服务 candidate shadow path 和 legacy `collect_news()` path；后续 window 修复必须单独完成 production-impact review。
- 未再次访问 RSS、未调用 DeepSeek、未读取 secret/.env/holdings、未修改 production entry、未写 canonical runtime data、未 commit/push。整体 `v0.6.2` 仍未完成，Phase 4 hard limits 尚未冻结。

## 2026-08-12 v0.6.2 Phase 4B Provider-facing Projection + Live Hard Limits

### Provider-facing boundary

- 新增 immutable Provider-facing projection：只对正式 `CandidateArticle.summary` 做一次 Python character cap，`>500` 截至前 500 chars；`<500`、`==500`、空 summary 和现有 null 语义保持不变。所有 article identity、title、source/feed metadata、link、normalized identity、language、published_at 和 request window 保持不变，原始 CandidateArticle / live snapshot 不会被修改。
- Provider preparation 明确先检查完整 candidate list，再按显式 mode projection、构建 exact request/body、检查 body bytes，最后才允许 API-key lookup / HTTP transport。candidate/body overflow 均 fail closed，0 transport calls，不自动 pruning、truncation、iterative shrinking 或提高 limit。
- `phase4_live` 只能通过 `--input-mode phase4_live` 显式选择；默认 real-provider CLI 继续使用独立 Phase 3B fixture mode 与 `2 / 4096` limits，不根据 candidate 数量自动推断。

### Frozen Phase 4B limits and replay

- Phase 4B limits：`summary_max_chars=500`、`max_candidate_count=200`、`max_provider_request_body_bytes=200000`。
- 正式 loader replay `/private/tmp/automation-brief-live-candidates-20260812T081815290841Z.json` 为 `original_candidate_count=159`；projection 后 `summaries_capped_count=25`、`summaries_unchanged_count=134`。
- Exact offline Phase 4 provider-body construction：`curator_request_bytes=127574`、`provider_request_body_bytes=138482`、`transport_calls=0`。该结果与 Phase 4A 500-character counterfactual 一致，不是硬编码 measurement。

### Artifact and boundaries

- Phase 4 real-provider artifact 的 `request.json` 保存 Provider 实际看到的 projected `CuratorRequest`；run metadata 增加 input mode、summary cap、projection counts、candidate/body limits。原始 snapshot 继续作为独立完整输入事实。
- 新增 projection/provider/CLI/artifact regressions；Phase 3B one-shot contract、retry、finish_reason、secret handling、artifact validation 保持通过。
- 本轮完全离线：未调用 DeepSeek、未访问真实 RSS、未读取 `.env` / API key / holdings、未修改 `main.py`、`feeds.json`、daily digest、`market_brief` 或 production automation，未安装依赖、未 commit/push。

## 2026-08-12 v0.6.2 Phase 4 real-output Collection-invariant Prompt Alignment

### First live shadow result

- 已执行第一次真实 RSS snapshot + DeepSeek shadow，使用显式 `--real-provider deepseek --input-mode phase4_live`；本轮不重复执行真实调用。
- Failed run：`/Users/wp/Projects/_project-data/automation-brief/runs/ai-curator-shadow/20260812T095634.808715Z-3d8fe868baf3`。`run.json` 确认 `input_mode=phase4_live`、`candidate_count=159`、`summaries_capped_count=25`、`summaries_unchanged_count=134`、`curator_request_bytes=127574`、`provider_request_body_bytes=138482`、`max_candidate_count=200`、`max_provider_request_body_bytes=200000`、`attempts=1`。
- 输入、projection、body limit、API-key lookup 后的 transport 均正常；真实 output 在本地 validator 阶段 fail closed：`failure_code=invalid_curator_response`，diagnostic=`duplicate_rejected_article_id`，path=`rejected_article_ids.article_id`。没有写入 `response.json` 或 raw provider response。

### Validator-derived prompt alignment

- 现有 validator 要求：input article IDs 必须唯一；`event_id` 全局唯一；每个 event 至少一个 evidence ID，且同一 event 内 evidence IDs 唯一；同一 evidence article 可在多个 event 复用；rejected article IDs 必须来自 input 且全局唯一；selected evidence 与 rejected IDs 互斥；reject reason 必须属于现有枚举。
- 新增最小 system-prompt wording：明确 rejected list uniqueness、同一 article 多理由只输出一条最合适 rejection、selected/rejected disjoint 和 per-event evidence rules。没有修改 validator、domain schema、parser normalization、auto dedupe、limits、retry、finish_reason 或 production path。
- 不自动 dedupe 是有意的 fail-closed 行为：重复 ID 的多个 reason 存在歧义，静默选择或丢弃会掩盖模型 contract violation 并改变原始 output 语义。

### Offline verification after alignment

- 正式 159-candidate dry-run 仍为 `candidate_count=159`、25 capped、134 unchanged、`curator_request_bytes=127574`、`provider_request_body_bytes=138631`、limits=`200 / 200000`、`transport_calls=0`。provider body 因 prompt alignment 从 `138482` 变为 `138631`，未硬编码旧数字。
- Phase 3B provider smoke two-candidate body 为 `3964` bytes，CLI candidate fixture body 为 `4093` bytes，均低于既有 `4096` limit；candidate / contract / provider / artifact / CLI regressions 继续通过。
- 本轮未执行第二次 DeepSeek call、未访问 RSS、未读取真实 API key / `.env` / holdings、未 commit/push。

## 2026-08-12 v0.6.2 Phase 4 Live Selected-only Simplification

### Trigger

- 连续两次 Phase 4 live RSS + DeepSeek shadow 的 input/projection/body/transport 均正常，但 real output 因 `duplicate_rejected_article_id` rejection bookkeeping failure fail closed；本轮不执行第三次真实调用。

### Product decision and provider boundary

- 仅对显式 `--input-mode phase4_live` 采用 selected-only Curator semantics：模型只负责选择/聚合重要 events 及其 evidence，不枚举未选 candidate，也不生成 rejection reason bookkeeping。
- 保留 `CuratorResponse.rejected_article_ids` 历史字段；phase4_live system instruction 要求固定输出 `[]`，未被任何 event evidence 使用的 candidate 由程序直接推导。
- 在 `OpenAICompatibleCuratorProvider.curate()` 解析 JSON 后、进入现有 `validate_curator_response()` 前，phase4_live provider boundary 对 payload 做局部产品 canonicalization：只将非权威 `rejected_article_ids` 投影为 `[]`。不 dedupe、不选择 reject reason、不保存 rejection list；default/full 与 Phase 3B 仍直接使用原有严格 rejection validator。
- event_id、canonical_title、required fields、enum、known/per-event-unique evidence、report_date、schema version、content policy、finish_reason 和 JSON parsing 继续严格 fail closed；production path 未修改。

### Artifact and offline verification

- 成功的 phase4_live `response.json` 保存 canonical `"rejected_article_ids": []`；`review.md` 使用 `Rejection enumeration: not collected in phase4_live`，不写成 AI 没有 reject。
- 同一 snapshot `/private/tmp/automation-brief-live-candidates-20260812T081815290841Z.json` 离线 replay：`candidate_count=159`、summaries `25 / 134` capped/unchanged、`curator_request_bytes=127574`、phase4_live `provider_request_body_bytes=138433`、limits=`200 / 200000`、`transport_calls=0`。snapshot SHA-256 保持 `2cbb32a286f12c26bd963ea20100463bcce053561376945f5b90bef01a6d9def`。
- 新增/更新 prompt、provider canonicalization、artifact semantics、contract/provider/CLI regression；Phase 3B provider two-candidate body=`3964`、CLI fixture body=`4093`，既有 `4096` limit 未修改。
- 本轮完全离线：未调用 DeepSeek、未访问 RSS、未读取 API key / `.env`、未访问 holdings、未修改 production、未 commit/push。

## 2026-08-12 v0.6.2 Phase 4 Live Evidence-ID Canonicalization

### Trigger and boundary

- 第二次 selected-only Phase 4 live shadow 已通过 Provider/JSON/input boundary，但 response validation 因 `duplicate_evidence_article_id` / `events.evidence_article_ids` fail closed；本轮不执行下一次真实调用。
- 仅在显式 `phase4_live` provider canonicalization boundary 中，对同一 event 的 `evidence_article_ids` 删除完全相同的重复值并保留首次出现顺序；这是 set-like evidence reference 的 exact canonicalization，不是 generic dedupe、parser normalization 或 validator 放宽。
- canonicalization 后仍由现有 validator 检查 known evidence、非空 evidence、required fields、canonical title、event ID、enum、report date/schema、content policy、finish reason 和 JSON parsing。unknown ID 不删除或修正，不合并不同 ID，不排序；跨 event evidence reuse 继续合法。default/full 与 Phase 3B duplicate evidence contract 保持原样。

### Offline verification

- provider regression 覆盖 `['a', 'a', 'b'] -> ['a', 'b']`、首次出现顺序、unknown/empty evidence、duplicate event、missing canonical title、跨 event reuse、selected-only rejection canonicalization，以及 full/Phase 3B strict duplicate evidence behavior。
- 同一 snapshot `/private/tmp/automation-brief-live-candidates-20260812T081815290841Z.json` replay 预期保持 `candidate_count=159`、summaries `25 / 134` capped/unchanged、`curator_request_bytes=127574`、`provider_request_body_bytes=138433`、limits=`200 / 200000`、`transport_calls=0`，SHA-256 不变。
- 本轮完全离线：未调用 DeepSeek、未访问 RSS、未读取 API key / `.env`、未访问 holdings、未修改 prompt、validator、schema、limits、retry、endpoint、model 或 production path，未 commit/push。

## 2026-08-12 — Phase 4 quality tuning retained; two-pass experiment abandoned

- Same-snapshot monolithic runs were technically successful but content quality remained FAIL: attribution/uncertainty improved, while must-include recall and news-peg evidence grouping remained weak. Phase 4 scoped capacity remains 10.
- The two-pass real validation did not improve the product: must-include coverage fell from 4/8 to 3/8, a duplicate 霍尔木兹 event appeared, grouping/evidence contamination remained, and C919 classification regressed. Pass B containment prevented one unrelated Pass A evidence item from reaching the final response, but that isolated benefit did not justify the added path.
- `phase4_live` has therefore returned to one projected-candidates → CuratorResponse provider call. Selection-plan parsing, synthesis request handling, containment mapping, second-stage metadata/artifacts, and their smoke coverage were removed. The compact gold/evaluator remains final-response-only.
- Public Curator schemas, generic validator, provider transport/retry/key boundary, collector, production digest/market brief, feeds/config, and holdings remain unchanged. No real Provider or RSS was used during the simplification.

## 2026-08-13 — Phase 4 allowlisted V4-Pro comparison profile

- Added one explicit shadow CLI switch, `--model-profile flash|pro`. Flash remains the default; Pro maps only to `deepseek-v4-pro` and is accepted only with explicit `phase4_live`.
- Both profiles reuse the exact endpoint, serializer, prompt, thinking mode, JSON response format, max tokens, timeout, retry, candidate projection/body limits, response validation, and artifact writer. Arbitrary model strings fail closed; the existing artifact `model` field records the selected model.
- Offline provider/CLI regression proves the serialized request contracts differ only by model ID and Phase 3B remains Flash. Same-snapshot Pro dry-run measured `159 / 127575 / 140127 / 0` (candidates / curator bytes / provider bytes / transport calls), below the existing 200000-byte limit. No real Provider, RSS, API key, `.env`, or holdings was accessed.

## 2026-08-13 — v0.6.2 Phase 4 closeout

- Real Phase 4 shadows established a working large-pool Flash path and validated selected-only response handling, artifacts, failure isolation, and production separation. The final GitHub-only cleaned Flash run processed `159 -> 140` candidates successfully; it improved evidence grouping and removed known forbidden contamination, while known major-event recall remained about `4/8` on this audited snapshot.
- The one-time Pro comparison reached `5/8` with better grouping/evidence, but only a marginal overall gain at materially higher cost. The runtime `--model-profile` / Pro allowlist was removed; historical Pro artifacts remain intact because each artifact records its actual model.
- v0.6.2 therefore closes with one simple Flash provider configuration, `phase4_live` scoped `max_events=10`, the exact GitHub Trending daily-main-pool exclusion, and the narrow offline gold/evaluator. No further tuning or production integration is authorized; v0.7 is not started here.

## 2026-08-13 — v0.7.1 Morning Brief MVP

- 新增显式 `overnight_brief` report type 和 `overnight_brief_writer.py`，默认 `config.json` 仍为 `digest`；Daily Digest、显式 `market_brief`、feeds、AI Curator、launchd、pmset、Bark 和 Obsidian 发布链保持不变。
- Morning Brief 复用 Daily Digest 的 core selection/summary/time helpers，以及 Market Brief 的行情展示、市场新闻分析和持仓匹配；当前结构化行情明确标注为前一交易日 A 股指数数据，不包装成完整全球隔夜行情。
- 报告级 assembly dedupe 以 link / normalized title / 近似标题做最后防线；“今日值得关注”最多 3 条，持仓异常 section 仅在逆势异常或高精度持仓新闻时渲染。
- 新增 `tests/offline_overnight_brief_smoke.py`，覆盖正常生成、跨 section 去重、0–3 条观察变量、conditional holdings、行情缺失、无 holdings、RSS failure 和显式 dispatch 输出文件名。
- 本轮未接入默认自动化链，也未调用真实 AI provider；新增 unified smoke、digest、market brief、market news、market data、holdings、project paths 及全部 offline AI Curator smoke 均通过。未 commit、未 push，等待人工查看 v0.7.1 生成样例。

## 2026-08-13 — v0.7.1 Curator integration correction

- 显式 `overnight_brief` 现在只抓取一次 `CandidateArticle` pool，并将同一 pool 复用到现有 `phase4_live` single-pass Curator 与 legacy fallback；默认 `digest`、显式 `market_brief` 和自动化发布链不变。
- AI success 时只渲染 validated `CuratorResponse.events`：`financial_markets` / `energy_commodities` 进入“隔夜市场”，其余 event 进入“昨夜最重要的事”；同一 events 集合做互斥投影，不再对 AI event 使用 legacy 标题 dedupe、英文 RSS 摘要或 Market Brief 规则化新闻字段。
- Curator event 的 `evidence_article_ids` 只用于回查现有 candidate source/link；“今日值得关注”优先使用 event uncertainties，最多三条，并可保留已有结构化行情观察；行情、conditional holdings anomaly、RSS failure footer、Markdown safety 和 canonical output 保持复用。
- Provider preflight/config/transport/JSON/validation/content-policy 技术失败时，writer 收到 `curated_events=None`，整份 reader-facing 新闻层回退到原 v0.7.1 legacy 输出，不与 AI 结果混合。phase4_live limits 提升为 `ai_curator_provider.py` 的共享常量，shadow CLI 改为引用该处，v0.6.2 shadow 行为不变。
- 新增 overnight smoke 覆盖 Curator success、category projection、evidence source/link、英文候选与中文 event、AI/legacy 隔离、AI event 不二次 dedupe、整份 fallback 和 holdings evidence overlap；offline Curator/provider、Daily Digest、Market Brief、py_compile、diff check 与 Project State push-gate 均需继续通过。未调用真实 Provider，未 commit、未 push，不进入 v0.7.2。

## 2026-08-13 — v0.7.1 market empty-state correction and recall audit

- 修复 `overnight_brief_writer.py` 的 reader-facing 空态条件：AI success 已渲染至少一个 market event 时，不再追加“暂无明确的市场新闻或市场信号”；AI market events 为空和 legacy fallback 行为保持不变。
- `tests/offline_overnight_brief_smoke.py` 新增 market events 非空/为空两条最小边界断言。
- 对 2026-08-13 16:49 的真实报告和 canonical 日志做只读审计：同日 `daily-news` 已选出央行二季度货币政策报告与隔夜逆回购报道，且 16:49 的中国新闻网相关 RSS fetch 成功；但显式 overnight path 没有保存本次 CandidateArticle pool、CuratorRequest 或 CuratorResponse，无法从现有 artifacts 证明精确 candidate/provider-facing 计数或将该事件严格归类为 B/C/D。既有 shadow artifacts 的 report_date 为 2026-08-12，因此仅作为边界证据，不冒充本次运行。

## 2026-08-13 — v0.7.1 direct Morning Brief Curator artifact persistence

- 显式 `overnight_brief` 现在直接复用 `ai_curator_artifacts.write_shadow_run`、`ShadowRunInfo` 和现有 provider `last_prepared_request` / `last_call_metadata`；不新增 persistence subsystem、Curator schema 或 provider stage。
- direct success/failure 均写入 canonical `runs/ai-curator-shadow/`：成功包含已有 `run.json`、provider-facing `request.json`、validated `response.json`、candidate `trace.json` 和 `review.md`；技术失败不写 `response.json`，但保留失败阶段/代码及可用 request/trace。`overnight-` run-id 前缀用于 caller 区分，shadow CLI 的 timestamp run-id 与行为保持不变。
- direct trace 由同一 CandidateArticle pool 生成，包含 legacy comparison 与 fetch failures；run metadata 记录 original/provider-facing candidate counts、phase4_live source exclusion/summary projection、request/body bytes、validation status 和 candidate collection window。AI failure 仍让 writer 收到 `curated_events=None`，保持整份 legacy 新闻 fallback。
- 新增 offline overnight artifact success/failure smoke；未调用真实 DeepSeek、未访问 RSS、未修改 feeds/Prompt/selection/model/default report type、未 commit/push，不进入 v0.7.2。

## 2026-08-13 — v0.7.1 same-snapshot max_events sensitivity preparation

- 现有 shadow CLI 只能从 candidate fixture 或 RSS 构造 request，不能直接复用保存的 provider-facing `request.json`；因此新增 development-only `scripts/run_ai_curator_max_events_sensitivity.py`，不修改 `main.py`、shadow CLI、生产默认 `max_events` 或 provider contract。
- 入口固定现有 `phase4_live` DeepSeek Flash 配置、limits、prompt 和 validator，只接受 baseline `request.json` 与 `--max-events`。加载后重建同一 `CuratorRequest`，要求 baseline `max_events=10`，并在真实 transport 前确认 provider-facing projection 除该字段外逐字段相同。
- 实验结果通过既有 `write_shadow_run` 写入 canonical `runs/ai-curator-shadow/`，使用 `sensitivity-max-events-15-*` / `sensitivity-max-events-20-*` 前缀；offline smoke 使用 fake transport，已验证 candidate 顺序、window、target language、selection goal 和 article content 不变。未调用真实 DeepSeek、未重新抓 RSS、未 commit/push，不进入 v0.7.2。

## 2026-08-13 — v0.7.1 phase4_live capacity decision

- 同一 154-candidate snapshot 的 `max_events` sensitivity 已完成：10 存在明显容量挤压，15 未形成稳定折中，20 的两次独立 DeepSeek Flash 运行均改善重大事件覆盖。
- 将共享 `PHASE_4_LIVE_MAX_EVENTS` 从 10 调整为 20；Morning Brief 与现有 phase4_live 使用方继续引用同一常量，default/full、fixture、Phase 3B、Prompt、schema、feeds、model/provider、writer 和 production default report type 不变。
- 20 仅是允许的 CuratedEvent 上限，不要求填满；Flash 边际事件排序仍可能波动，本轮不增加规则、ranking/scoring、dedupe 或新的 AI stage。未调用真实 DeepSeek、未 commit/push，不进入 v0.7.2。

## 2026-08-13 — v0.7.1 Morning Brief reader-facing correction

- phase4_live prompt 增加最小 contract clarification：`max_events=20` 是 ceiling 而非 quota；达到重要性门槛的事件不足时应返回更少，不为填满容量纳入低价值、常规、局部或影响有限的事件；schema、importance enum、分类和 provider 行为不变。
- AI success 的“今日值得关注”改为 composition projection：只使用已有 CuratedEvent `importance in {must_know, important}` 且属于政策、市场、能源或地缘类别的 unresolved variables，再复用已有结构化行情信号与无 RSS 解释的持仓异常，最多 3 条，不足不补；不新增关键词、模板规则、schema 或第二次 AI 调用。
- reader-facing 产品同步更名为 Morning Brief / 早间简报，标题和 canonical 文件名改为 `morning-brief-YYYY-MM-DD.md`；稳定 machine identifier `report_type="overnight_brief"`、内部 module/function symbol、artifact run 前缀和显式 CLI 保持不变。
- 新增/更新 offline smoke 覆盖 prompt ceiling、少于 20 个 event、watch composition、低价值 uncertainty 排除、宏观/地缘变量、持仓异常和不足三条；未调用真实 DeepSeek，未修改 feeds 或默认生产链，不 commit/push，不进入 v0.7.2。

## 2026-08-13 — v0.7.1 background projection and Curator contract correction

- Morning Brief writer 在 reader-facing projection 入口仅保留现有 `importance in {must_know, important}`；主新闻、市场新闻、watch 和持仓相关新闻共用过滤后的事件集合。validated CuratorResponse 及 canonical artifact 仍完整保留 `background`，不改变 schema、enum、validator 或 `max_events=20`。
- phase4_live prompt 明确：同一主体、同一时间段、同一核心市场/政策/地缘变化即使采用不同指标或标题角度也属于一个 underlying news peg，应聚合为一个 event 并可合并直接相关 evidence；不同 news peg 仍不得错误合并。
- phase4_live prompt 同时要求 canonical title、summary、why-important 和 evidence IDs 支持同一实体与事件，禁止借用其他候选的公司、人物、金额或事实；无法一致支持时修正或舍弃，不新增 semantic validator、repair pass 或第二次 AI 调用。
- offline smoke 新增 `must_know` / `important` 展示、core/market `background` 隐藏、background uncertainty 不进入 watch，以及两组 prompt contract 断言；未调用真实 DeepSeek、未 commit/push，不进入 v0.7.2。

## 2026-08-13 — v0.7.1 Morning Brief closeout — CLOSED

- Morning Brief 已通过真人 reader-facing acceptance；v0.7.1 永久路径保持 `CandidateArticle → phase4_live single-pass Curator → validated CuratedEvent → thin reader projection → market data / holdings anomaly → canonical artifact/report`，Provider 技术失败仍使用整层 legacy 新闻 fallback。
- 已删除仅用于已完成 10/15/20 same-snapshot sensitivity 实验的 development-only runner 与 offline smoke；10/15/20 结果和 `max_events=20` 决策依据保留在历史 DECISIONS / DEVLOG 记录中，canonical artifacts 不变。
- v0.7.1 业务行为、Prompt、schema、feeds、model/provider、默认 report type 和自动化发布链不再继续调整；Next Action 转为用户明确授权后的 v0.7.2 评估。

## 2026-08-14 — v0.7.2 Production Cutover implementation

- `scripts/run_daily_digest.sh` 增加唯一可选 report type 参数：无参数默认 `digest`，另允许 `overnight_brief`，未知值 exit 2；同一值显式传给 `main.py`、`publish_mobile_digest.py` 和 `send_bark_notification.py`，既有 caffeinate、stage timing、main failure exit 与 downstream best-effort 行为保持不变。
- Morning Brief credential 使用 process-env-first / project `.env`-second：已有 `AUTOMATION_BRIEF_CURATOR_API_KEY` 不覆盖；缺失时以非执行方式从项目根目录 `.env` 读取。`.env` 缺失或 key 缺失时只记录 available / unavailable，并继续现有 `missing_api_key` whole-layer legacy fallback。
- Obsidian publisher 和 Bark sender 以显式 report type 选择 `daily-news-*` / `morning-brief-*`，未知值 fail closed。Morning Bark 标题为“早间简报已生成”，body 不读取 Daily 专属 `Displayed items`，Obsidian URI 使用实际 Morning 文件名；Daily 默认行为保持兼容。
- checked-in plist example 只在既有 `ProgramArguments` 追加 `overnight_brief`，未修改 label、08:00、working directory 或日志路径；未覆盖/reload 用户实际 LaunchAgent，也未修改 pmset。
- 新增 `tests/offline_production_routing_smoke.py`，使用 fake Python / 临时项目 `.env` / 临时 data root / monkeypatched Bark 覆盖 shell、env precedence、缺失 fallback、routing、旧 Daily 防误读、unknown fail-closed 和 plist cutover；同步更新旧 shell 默认断言。未调用真实 DeepSeek，未读取或打印真实 secret，v0.7.2 等待用户 macOS production acceptance，不标记 CLOSED。

## 2026-08-15 — v0.7.2 Production Cutover closeout

- 用户已完成真实 macOS acceptance：项目 `.env` 配置了 `AUTOMATION_BRIEF_CURATOR_API_KEY`，文件权限为 `0600`，实际 LaunchAgent 已 reload，`ProgramArguments` 使用 `run_daily_digest.sh overnight_brief`，受控 `launchctl kickstart` 成功。
- 真实链路成功生成 `morning-brief-2026-08-15.md` 并同步到既有 Obsidian 目录，Bark 已发送。对应 artifact `overnight-20260815T143736.428601Z-f8958055f793` 的非敏感验收字段为 `status=succeeded`、`provider_id=deepseek`、`model=deepseek-v4-flash`、`validation_status=passed`、空 `failure_code`、`ai_event_count=20`。
- 确认生产链路为 `launchd → project .env → DeepSeek → AI Curator → Morning Brief → Obsidian → Bark`。v0.7.2 标记为 CLOSED；无参数 `digest` 继续作为 rollback。下一版本 v0.7.3 只做真实晨间长期使用验证，不新增 AI、Prompt、新闻质量或 production 架构实现。
