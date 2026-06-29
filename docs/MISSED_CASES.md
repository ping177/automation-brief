# Missed Cases

记录 daily digest 漏报事件，用于把单次漏报转化为源、关键词、role、规则或未来 AI rerank 的可追踪改进。

## 2026-06-17 Visa / OpenAI / ChatGPT 支付合作

- 日期：2026-06-17
- 漏报事件标题：Visa / OpenAI / ChatGPT 支付合作
- 原始链接：https://apnews.com/article/d769dec86344cb4977c98789e8ec492f
- 期望 section：core_event 或 market_signal
- 为什么重要：该事件代表支付网络接入 ChatGPT 和 AI agent commerce 场景，属于支付基础设施、OpenAI 商业化和 AI agent 生态的重要进展。
- 漏报原因：source gap / keyword gap / role gap / rule gap
- AI rerank gap：暂不适用，v0.4.1 不引入 AI rerank
- 采取动作：新增 `global_tech_business` 和 `ai_industry` role；补充 OpenAI News、TechCrunch AI、VentureBeat AI、CNBC Technology RSS；补充支付、commerce、agentic commerce、OpenAI 商业化相关关键词；增加离线 smoke 回归样本。
- 回归状态：v0.4.1 已加入离线样本，要求该类事件不能被 drop，至少进入 quick_scan；当前规则目标为进入 market_signal。

## 2026-06-18 v0.4.1 扩源后出现重复报道与内容形态重复

- 日期：2026-06-18
- 案例标题：v0.4.1 扩源后出现重复报道与内容形态重复
- 原始现象：
  1. `core_event` 重复出现“美官员：特朗普已亲自签署美伊谅解备忘录，协议现已生效”和“美官员称特朗普亲自签署美伊谅解备忘录”。
  2. `market_signal` / `quick_scan` 分别出现“NEA’s Tiffany Luck on AI IPOs, personal agents, and the ROI reckoning”和“NEA’s Tiffany Luck says enterprises are still figuring out their AI ROI”，属于同一采访或主题的不同内容形态。
  3. NEA podcast 标题虽然包含 IPOs / ROI，但不是具体 IPO、融资、估值、财报、监管或交易事件，却误升格为 `market_signal`。
  4. “World model maker Odyssey nabs $1.45B valuation backed by Amazon and other big names”包含明确估值和战略背书，却仅进入 `quick_scan`。
- 漏报 / 误报类型：`duplicate_event` / `cross_section_duplicate` / `content_format_duplicate` / `market_signal_false_positive` / `market_signal_false_negative`
- 原因分析：v0.4.1 扩充英文科技商业和 AI 产业源后，不同来源及 podcast、video、interview 等不同内容形态会报道同一事件或主题。此前去重主要覆盖 `market_signal` 内部和部分跨 section 场景，对 `core_event` 中文近似标题及内容形态重复覆盖不足；同时规则对 IPOs / ROI 等词过敏，而对明确 valuation / 大厂背书信号优先级不足。
- 采取动作：扩展最终 section 组装级去重，并在各 section 截断前去重；跨 section 按 `core_event > market_signal > watch_item > quick_scan` 优先级保留；增强中文相似事件 key；podcast / video / interview / 泛讨论默认不进入 `market_signal`，除非包含具体融资、估值、IPO、交易、监管或财报等硬事件；允许明确估值、融资及大厂背书信号进入 `market_signal`；增加 section 组装级回归测试。
- 回归状态：已修复；组装级测试通过；真实日报未发现目标类型明显重复；抓取失败为无；v0.3.5 自动运行链路未受影响。

## 2026-06-27 v0.5-beta 轻量行情源字段限制

- 日期：2026-06-27
- 案例标题：轻量公开行情接口可能缺失成交额、涨跌幅或临时不可用
- 原始现象：v0.5-beta 第一阶段为了避免 AKShare / TuShare 等重依赖，使用标准库请求轻量公开行情接口。该接口字段稳定性和可用性不由本项目控制，成交额或个股行情可能缺失。
- 漏报 / 误报类型：`market_data_source_gap` / `field_missing` / `runtime_availability`
- 原因分析：第一阶段只做最小行情验证，不建立多数据源交叉校验，也不计算板块强度或复杂相对强弱。公开接口返回字段缺失时，继续推断会引入编造风险。
- 采取动作：`market_data.py` 将行情失败收敛到 `failures`，report 中显示“数据暂不可用”或“行情数据源未返回该字段，本次不做该项判断”；离线 smoke 覆盖字段缺失和请求失败。
- 回归状态：已加入 `tests/offline_market_data_smoke.py` 和 `tests/offline_market_brief_smoke.py`；后续真实样例若出现长期缺字段，再评估更稳定数据源。

## 2026-06-27 v0.5-beta 真实样例 IPO 与行情展示噪音

- 日期：2026-06-27
- 案例标题：周末 market brief 混淆 report date / market date，IPO 新闻刷屏，风险变量重复
- 原始现象：真实 `output/market-brief-2026-06-27.md` 在周末生成时显示 `Data date: 2026-06-27`，但行情实际截至 2026-06-26；成交额字段直接展示且口径未确认；今日主线为空时出现“暂无可展示内容”；重要新闻几乎全是 IPO / 融资；风险与反证重复同一条资本市场变量；持仓有涨跌但缺少相对主要指数的轻量描述。
- 漏报 / 误报类型：`report_date_confusion` / `field_semantics_uncertain` / `empty_template` / `ipo_overweight` / `duplicate_risk_variable`
- 原因分析：v0.5-beta 第一阶段只完成最小行情接入，没有把非交易日行情日期、成交额口径、新闻类型配额和风险变量去重作为单独约束。
- 采取动作：v0.5-beta.1 增加 `market_data_date`；成交额口径未确认前显示“数据暂不可用”；今日主线空内容不输出空模板；风险变量文本去重；IPO / 融资类最多 2 条；无法映射 A 股产业链或当前主线的海外 IPO 不展示；holdings 增加强于 / 弱于 / 接近主要指数均值的轻量观察。
- 回归状态：已扩展 `tests/offline_market_data_smoke.py` 和 `tests/offline_market_brief_smoke.py` 覆盖。

## 2026-06-29 v0.5-beta.2 行情与新闻主线融合误判

- 日期：2026-06-29
- 案例标题：单条低相关度新能源新闻误生成今日主线，科创50强势和持仓逆势没有充分表达
- 原始现象：真实 market brief 中科创50 +4.61% 显著强于其他主要指数，但报告没有提示科创 / 硬科技方向的指数层面强势；“宁德时代积极响应《动力和储能电池企业供应商账款支付规范倡议》”单条低相关度新闻触发“新闻线索指向：新能源 / 储能”；金风科技在主要指数整体上涨背景下 -6.86%，但仅显示“弱于主要指数均值”，且 RSS 候选无相关新闻解释。
- 漏报 / 误报类型：`weak_theme_false_positive` / `market_led_signal_missing` / `holding_anomaly_understated` / `news_type_misclassification`
- 原因分析：v0.5-beta.1 的主题聚合仍按主题命中输出，缺少新闻数量、相关度和主题一致性的置信度门槛；行情层面只有市场温度，没有把科创50相对强势作为独立观察；持仓相对观察等级过粗；财报 / 营收 / 利润词在分类中与 IPO / 融资混在一起。
- 采取动作：v0.5-beta.2 增加主题置信度门槛；行情层面单独输出科创50强势观察；持仓相对观察升级为小幅 / 明显 / 逆势等级；持仓异常且 RSS 无相关新闻时输出后续观察变量；新增“公司经营 / 财报”新闻类型；成交额不可用和今日继续观察文案改为读者向说明。
- 回归状态：已扩展 `tests/offline_market_news_smoke.py` 和 `tests/offline_market_brief_smoke.py` 覆盖。
