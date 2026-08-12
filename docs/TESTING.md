# Testing

本文记录 automation-brief 的测试命令、smoke checklist 和验收习惯。根据改动类型选择最小必要检查，不为 docs-only 任务运行不必要的业务链路。

## Docs-only 验证

仅修改 Markdown 文档时，通常运行：

```bash
git diff --check
git status --short
```

`git diff --check` 用于检查尾随空格、空白错误和 patch 格式问题。docs-only 改动不需要跑 Python 编译、RSS 健康检查或真实日报生成，除非文档改动同时暴露出需要验证的运行假设。

## Project State Push Gate 验证

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_project_state_push_gate
sh -n .githooks/pre-push
sh -n scripts/check-project-state-push.sh
sh -n scripts/install-git-hooks.sh
git diff --check
```

`tests.test_project_state_push_gate` 仅使用 Python 标准库、临时 Git 仓库、临时 bare remote 和临时 Git identity，覆盖 branch、tag、首次 push、多 ref、真实 pre-push 接线、路径空格/非 ASCII 与安装脚本。测试通过 `GIT_CONFIG_GLOBAL` 临时文件和 `GIT_CONFIG_NOSYSTEM=1` 隔离用户 global/system config；不访问网络，不运行 RSS、Bark、Obsidian、launchd、pmset、生产晨报或 AI provider。

## Project State Push Gate checklist

- [ ] push 前已复核 Current version、Current status、Next Action、Blockers、Version Index，以及受影响时的 Deployment。
- [ ] 无明确 blocker 时 Blockers 精确为 `暂无明确阻塞。`。
- [ ] 最终 branch commit 只有一个合法 `Project-State-Review` trailer，且与最终 tree diff 一致；tag 只检查其 commit 上的合法声明。
- [ ] 不以 `git push --no-verify` 作为常规绕过手段。
- [ ] 知道此 gate 可被本地绕过，且不会验证 PROJECT_STATE 内容真实性或自动执行 commit / push。

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
PYTHONPYCACHEPREFIX=/private/tmp python3 -m py_compile project_paths.py scripts/init_holdings_config.py scripts/validate_holdings_config.py
.venv/bin/python tests/offline_holdings_config_smoke.py
```

For v0.6.0-alpha / v0.6.2 Phase 2–3B AI Curator shadow changes, compile the curator, provider, artifact, and explicit shadow modules, then run:

```bash
PYTHONPYCACHEPREFIX=/private/tmp python3 -m py_compile ai_curator.py ai_curator_provider.py ai_curator_artifacts.py project_paths.py scripts/run_ai_curator_shadow.py scripts/publish_mobile_digest.py scripts/send_bark_notification.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/offline_ai_curator_candidate_smoke.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/offline_ai_curator_contract_smoke.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/offline_ai_curator_cli_smoke.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/offline_ai_curator_provider_smoke.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/offline_ai_curator_artifacts_smoke.py
.venv/bin/python tests/offline_project_paths_smoke.py
```

这些测试必须保持离线：不接真实 AI provider，不调用真实 RSS，不调用 Bark，不写入 Obsidian，不运行 launchd / pmset；真实 holdings 只允许由 validator 做不打印值的校验，其他 smoke 一律使用临时 fixture。Provider smoke 使用 fake transport，覆盖冻结 DeepSeek 配置与 exact body allowlist（`max_tokens`、disabled thinking、JSON mode、无 stream/tools）、`choices[0].finish_reason == "stop"` 成功边界，以及 `length`、`content_filter`、`tool_calls`、`insufficient_system_resource`、unknown 和缺失值的 fail-closed / no-retry 行为；同时覆盖 API key 缺失、timeout、瞬态网络错误、429、5xx、不可重试 4xx、空 content、invalid JSON、schema/evidence validation、missing required field、duplicate/overlap、content policy、safe validation diagnostics、max attempts、真实 request-body byte measurement、preflight limit 0-call 和 secret 不泄露。Artifact smoke 使用临时目录，覆盖成功/失败 run、atomic publish、same-day 不覆盖、writer success-boundary revalidation、allowlist、bounded failure diagnostics、content rendering safety、Legacy label、fetch-failure trace、metadata、response.json 只在 validated success 存在和两个 byte measurement 字段语义。

Phase 3B fixture one-shot gate 的最终离线 dry-run 命令为：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_ai_curator_shadow.py \
  --candidate-fixture /private/tmp/ai-curator-candidates.json \
  --real-provider deepseek \
  --dry-run
```

它必须输出 `mode: dry_run`、`provider_id: deepseek`、`model: deepseek-v4-flash`、`candidate_count <= 2`、`provider_request_body_bytes <= 4096` 和 `transport_calls: 0`，并报告 `curator_request_bytes` / exact `provider_request_body_bytes`。当前 baseline fixture measurement 为 `candidate_count=2`、`curator_request_bytes=1178`、`provider_request_body_bytes=2487`。该路径不需要真实 key、不输出 API key/Authorization、不写 artifact。`--real-provider deepseek` 必须同时提供 `--candidate-fixture`，不能退回 feeds/RSS；默认不带 `--real-provider` 仍使用 fixture provider；未知 provider 必须 fail closed。Phase 3A 通用 provider 仍不启用默认 limit，只有 Phase 3B 显式 fixture gate 传入 `2 / 4096`；候选数或 body 超限必须在 HTTP 前失败且 0 calls，不自动截断候选或 payload。

Phase 3B 离线回归至少锁住：恰好 2 个候选通过；超过 2 个候选 fail closed；body `<=4096` 通过、`>4096` fail closed；不自动截断 candidates/payload；dry-run transport calls 为 0 且不依赖 key；actual real path 缺 key 在 transport 前失败；unknown provider、retry count、`finish_reason == "stop"`、secret、atomic artifact 和 production isolation 回归保持通过。冻结配置仍为 `max_attempts=2`、`max_tokens=8192`、`timeout=90s`；这些仅适用于本次 fixture gate，不是 live RSS / production limits。

## Canonical runtime data migration verification

路径迁移先运行全部离线 smoke，再复制真实数据。迁移记录只包含文件名、大小、SHA-256、UTF-8 和来源/目标元数据，不包含 holdings 内容、报告正文、secrets 或 provider payload。canonical 默认树为：

```text
~/Projects/_project-data/automation-brief/
├── reports/
├── runs/daily-news.log
├── runs/ai-curator-shadow/
├── manual-inputs/holdings.json
└── migration-records/<migration-id>/
```

迁移后可使用仓库 validator 检查 canonical holdings（输出不得出现具体值），并使用临时 env 文件、临时 mobile 目录和 monkeypatch 进行下游读取 smoke。不要运行真实 RSS、AI provider、Bark、Obsidian、launchd 或 pmset。

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

- 生成每日简报：运行 `scripts/run_daily_digest.sh` 或 `.venv/bin/python main.py`，确认 `~/Projects/_project-data/automation-brief/reports/daily-news-YYYY-MM-DD.md` 生成。
- 输出到 Obsidian iCloud：确认 Obsidian iCloud 目标目录出现同名日报，且内容与 canonical `reports/` 中文件一致。
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

## AI Curator shadow checklist

v0.6.0-alpha adds the original shadow plumbing; v0.6.2 Phase 2 adds provider and run-artifact boundaries, Phase 3A adds an explicit DeepSeek opt-in and no-transport preflight, and Phase 3B adds an explicit fixture-only hard-limit gate without enabling production. When modifying the AI Curator path, confirm:

- Candidate pool is built before legacy keyword filtering.
- Fully offline shadow CLI validation can use `--candidate-fixture` plus `--fixture-response`; that path must not read real feeds or call RSS.
- Linkless RSS entries with title, source/feed metadata, and published time may enter the shadow candidate pool, while legacy digest output keeps its link requirement.
- Legacy daily digest and explicit `market_brief` behavior remain unchanged.
- `CuratorRequest.articles` does not include holdings, matched keywords, legacy score, legacy category, market data, or holdings price moves.
- Candidate trace may include legacy diagnostic fields, but must not include cost, position, market value, profit/loss, `.env`, API keys, or secrets.
- Fixture responses fail loudly on unknown evidence ids, duplicate evidence ids within one event, duplicate event ids, invalid enums, empty required text, overlap between selected and rejected ids, and max event violations.
- Shadow preview does not contain direct trading advice terms such as 买入、卖出、加仓、减仓、止损、止盈 or 目标价.
- The OpenAI-compatible adapter reads the API key only from the configured environment variable, treats candidate text as untrusted, sends no provider-specific strict-schema option, validates parsed JSON with `validate_curator_response()`, and retries only transient transport errors, 429, and 5xx once by default.
- Failed provider/parser/validator runs record safe `run.json` metadata plus available request/trace artifacts and never write `response.json`; validator/content-policy failures may record only bounded rule/path diagnostics (and a known candidate id when needed), never raw exception text or the full model response; successful `response.json` is an explicit allowlist of validated domain fields.
- Each run lives under `runs/ai-curator-shadow/<run_id>/`; repeated same-day runs do not overwrite prior runs. Artifacts contain no API key value, Authorization header, holdings, or raw provider envelope.
- `run.json` records `candidate_count`, `curator_request_bytes`, and `provider_request_body_bytes`; fixture provider body bytes are `null`, and the Phase 3B candidate/body hard limits apply only to the explicit DeepSeek fixture gate, not the generic provider or production paths.
- `scripts/run_daily_digest.sh` 仍只生成普通 digest；`scripts/run_market_brief.sh` 不再硬编码仓库 `output/`，由 resolver 选择 canonical `reports/`。

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
- `python3 main.py --report-type market_brief` 或 `scripts/run_market_brief.sh` 能显式生成 canonical `reports/market-brief-YYYY-MM-DD.md`。
- `scripts/run_daily_digest.sh` 不增加 `--report-type market_brief`，默认每日普通 digest 链路不变。

当前不要求 AKShare、TuShare、AI rerank、Bark、Obsidian、launchd 或 pmset 级联 smoke。真实行情网络只在手动显式 market brief 样例中观察，不作为离线测试前置条件。
