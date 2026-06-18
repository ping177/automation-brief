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
