# Testing

本文记录 automation-brief 的测试命令、smoke checklist 和验收习惯。根据改动类型选择最小必要检查，不为 docs-only 任务运行不必要的业务链路。

## Docs-only 验证

仅修改 Markdown 文档时，通常运行：

```bash
git diff --check
git status --short
```

`git diff --check` 用于检查尾随空格、空白错误和 patch 格式问题。docs-only 改动不需要跑 Python 编译、RSS 健康检查或真实日报生成，除非文档改动同时暴露出需要验证的运行假设。

## Python 改动验证

修改 Python 运行逻辑时，建议至少运行：

```bash
PYTHONPYCACHEPREFIX=/private/tmp python3 -m py_compile main.py check_feeds.py
.venv/bin/python tests/offline_digest_smoke.py
```

For v0.5-alpha market brief changes, also compile the market brief modules and run:

```bash
PYTHONPYCACHEPREFIX=/private/tmp python3 -m py_compile holdings.py market_brief_writer.py market_data.py market_analysis.py market_news.py
.venv/bin/python tests/offline_market_data_smoke.py
.venv/bin/python tests/offline_market_news_smoke.py
.venv/bin/python tests/offline_market_brief_smoke.py
```

For v0.5.1-alpha holdings local config changes, also compile the holdings scripts and run:

```bash
PYTHONPYCACHEPREFIX=/private/tmp python3 -m py_compile scripts/init_holdings_config.py scripts/validate_holdings_config.py
.venv/bin/python tests/offline_holdings_config_smoke.py
```

如改动涉及脚本调用链、RSS 抓取、Bark、Obsidian 同步或真实输出，再按需运行：

```bash
.venv/bin/python check_feeds.py
.venv/bin/python main.py
scripts/run_daily_digest.sh
```

不要在验证输出中打印 `.env`、Bark key、Obsidian 私有路径等敏感配置或其他 secrets。

## JSON 配置验证

修改 JSON 配置或示例配置时，建议运行：

```bash
python3 -m json.tool feeds.json
python3 -m json.tool feeds.example.json
python3 -m json.tool config.json
python3 -m json.tool config.example.json
python3 -m json.tool keywords.json
python3 -m json.tool keywords.example.json
python3 -m json.tool config/holdings.example.json
```

如果只改其中一部分文件，可只验证对应 JSON；发布前或较大改动时建议全量验证。

## 自动化链路 smoke checklist

当改动影响真实运行链路，或需要确认早报闭环时，按以下顺序检查：

- 生成每日简报：运行 `scripts/run_daily_digest.sh` 或 `.venv/bin/python main.py`，确认 `output/daily-news-YYYY-MM-DD.md` 生成。
- 输出到 Obsidian iCloud：确认 Obsidian iCloud 目标目录出现同名日报，且内容与 `output/` 中文件一致。
- Bark 推送：确认 iPhone 收到 Bark 通知；如配置了 Obsidian URI，点击后应打开当天日报。
- launchd 定时：使用 `launchctl print gui/$(id -u)/com.ping.automation-brief.daily` 检查任务状态、运行次数和退出码。
- Mac 自动唤醒链路：使用 `pmset -g sched` 检查计划，必要时结合 `pmset -g log` 判断 07:58 唤醒和 08:00 运行是否按预期发生。

自动化链路 smoke 涉及本机环境、iCloud、Bark 和网络，只有在运行逻辑或自动化链路相关改动后才需要执行。

## missed coverage 复盘流程

当真实早报出现漏报、误升格、误降级或重复展示时：

1. 在 `docs/MISSED_CASES.md` 新增案例，记录日期、标题、原始链接、期望 section、重要性、原因类型和采取动作。
2. 判断问题属于 source gap、keyword gap、role gap、rule gap、dedupe gap、content format gap 或未来 AI rerank gap。
3. 优先补离线 smoke 样本或 section 组装级样本，再做规则调整。
4. 调整后运行 `tests/offline_digest_smoke.py`，必要时再运行真实 `main.py` 或 `scripts/run_daily_digest.sh`。
5. 回填 `docs/MISSED_CASES.md` 的回归状态。

`docs/MISSED_CASES.md` 是漏报和质量追踪文档，应保留为长期复盘入口。

## market_brief smoke checklist

v0.5-beta first stage 的显式 `market_brief` 会复用 RSS 候选新闻，并尝试用轻量公开接口抓取主要指数和 holdings 个股行情。修改持仓读取、行情数据、新闻筛选、市场简报结构或投资安全边界时，至少确认：

- `market_brief` 能生成 Markdown。
- 输出包含固定 section。
- 持仓标题来自 holdings fixture，fixture 改变后输出随之变化。
- 指数行情 mock 正常返回时，输出展示上证 / 深成指 / 创业板 / 科创 50 涨跌。
- holdings 行情 mock 正常返回时，输出展示持仓个股涨跌。
- 行情字段缺失或请求失败时，输出显示“数据暂不可用”，报告仍能生成。
- 未配置 holdings 时，report 不崩溃。
- holdings 相关新闻只来自 `code`、`name`、`sector`、`watch_tags` 动态匹配。
- 离线 `offline_market_news_smoke.py` 使用 fixture，不依赖真实 RSS 网络。
- 离线 `offline_market_data_smoke.py` 使用 fixture / mock，不依赖真实行情网络。
- 业务代码不硬编码示例持仓。
- 输出不包含直接交易建议词。
- 行情限制说明只出现在市场温度、行情验证或数据限制相关位置，避免多 section 重复空文案。
- `tests/offline_digest_smoke.py` 仍通过，确保普通 daily digest 不回退。
- `scripts/init_holdings_config.py` 不覆盖已有本地 holdings。
- `scripts/validate_holdings_config.py` 对合法配置通过、对 JSON/字段错误失败、对成本/仓位/市值/盈亏字段 warning 且不输出具体值。
- `python3 main.py --report-type market_brief` 或 `scripts/run_market_brief.sh` 能显式生成 `output/market-brief-YYYY-MM-DD.md`。
- `scripts/run_daily_digest.sh` 不增加 `--report-type market_brief`，默认每日普通 digest 链路不变。

当前不要求 AKShare、TuShare、AI rerank、Bark、Obsidian、launchd 或 pmset 级联 smoke。真实行情网络只在手动显式 market brief 样例中观察，不作为离线测试前置条件。
