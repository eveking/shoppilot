# ADR-0005：LLM 层走 OpenAI 兼容协议，DeepSeek 为默认配置

- 状态：已接受
- 日期：2026-10-22

## 背景

框架定位（ADR-0001）下，"能不能换模型"是迟早被提的 issue。主模型为 DeepSeek，而 DeepSeek 本身提供 OpenAI 兼容接口。

## 决策

- LLM 客户端按 **OpenAI 兼容协议**实现，`base_url` / `api_key` / `model` 全部配置化；默认 `deepseek-chat`。
- 不做逐厂商的 LLM 适配层，不追协议细节差异。
- Function calling 与流式行为均以 OpenAI 协议语义为准；模型须支持 function calling，写入文档作为选型前提。

## 备选方案

- **硬绑 DeepSeek SDK**：被否。换模型等于改代码，框架定位下不可接受。
- **完整 LLM 适配层（每厂商一适配器）**：被否。第一版只有一个真实使用者（OpenAI 兼容协议）时抽象是假设性的；等真出现协议不兼容的厂商，再为它写适配器。

## 影响

- 正面：一行配置切换 Kimi / Qwen / GLM 等兼容服务；实现薄。
- 负面：个别兼容实现的细微差异（工具调用格式、流式分片）不在框架兜底范围，文档中声明。
