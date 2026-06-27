# automation-brief 开发日志

本文记录 automation-brief 从 v0.2 到 v0.3.3-beta 的主要开发节点、验证结果和阶段结论。

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
- 不 commit，不 push，等待人工确认。

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
