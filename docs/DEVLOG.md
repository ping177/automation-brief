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
