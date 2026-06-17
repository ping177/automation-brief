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
