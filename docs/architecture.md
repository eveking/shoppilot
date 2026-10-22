# ShopPilot 架构总览

> 决策依据见 [adr/](adr/)，词汇以 [glossary.md](glossary.md) 为准。

## 定位

开源电商客服 Agent **框架**：开发者基于它构建自己的电商客服产品。核心资产是四条接缝，内置物（聊天窗、Mock 适配器、种子数据）皆为示例集成。

## 模块图

```
┌───────────────────────────────────────────────────┐
│  渠道示例  web/ React 聊天窗（示例集成，可不用）        │
└────────────────────┬──────────────────────────────┘
                     │ 签名 Token 开会话 · SSE 对话
┌────────────────────▼──────────────────────────────┐
│  API 层  FastAPI                                   │
│    POST /sessions   创建会话（校验签名 Token）        │
│    POST /chat       Agent 循环，SSE 事件流           │
│    GET  /health                                      │
├───────────────────────────────────────────────────┤
│  核心模块 shoppilot.core                            │
│    Agent Loop（模型回复 ↔ 工具执行往复）               │
│    ToolRegistry（收集 ToolSet → 模型侧 schema）      │
│    Context（系统提示组装 + 历史裁剪）                  │
├───────────────┬───────────────────────────────────┤
│ 身份接缝        │ LLM 接缝（OpenAI 兼容协议）          │
│ IdentityProvider│ base_url/key/model 配置化           │
│ HMAC │ Mock    │ 默认 deepseek-chat                  │
├───────────────┴───────────────────────────────────┤
│  领域插件 shoppilot.contrib（ToolSet，注册即生效）     │
│    orders     : query_orders / get_order            │
│    aftersales : list_aftersales / get_aftersale     │
├───────────────────────────────────────────────────┤
│  数据源接缝（各领域协议归 ToolSet 所有）               │
│    OrderAdapter  AftersaleAdapter                   │
│    ▲ 内置 MockShopAdapter（种子数据）                 │
│    ▲ 社区：taobao / shopify / 自建商城 适配器          │
├───────────────────────────────────────────────────┤
│  存储  SQLAlchemy 2.0 async + Alembic               │
│    sessions / messages        SQLite → PostgreSQL   │
└───────────────────────────────────────────────────┘
```

## 四条接缝（框架的接口面）

| 接缝 | 接口 | 内置适配器 | 社区扩展方向 |
|---|---|---|---|
| 数据源 | `OrderAdapter` / `AftersaleAdapter`（领域自有协议） | `MockShopAdapter` | 各电商平台、自建商城 |
| 身份 | `IdentityProvider` | `HmacIdentityProvider` / `MockIdentityProvider` | 对接商家自有账号体系 |
| LLM | OpenAI 兼容配置（base_url/key/model） | deepseek-chat | 任意兼容服务 |
| 领域 | ToolSet 注册 | `orders` / `aftersales` | 物流、商品、营销… |

## 一次请求的执行流

1. 前端携签名 Token `POST /sessions` → `IdentityProvider` 校验 → 建会话记录。
2. 前端 `POST /chat`（会话 ID + 用户消息）→ 进入 **Agent 循环**：
   - 组装上下文（系统提示 + 裁剪后的历史 + 本轮消息）→ 调 LLM；
   - 若返回工具调用：从 `ToolRegistry` 取实现，挂上 `Identity` 执行（工具内部只走适配器）→ 结果回填 → 再调 LLM；
   - 循环至最终回答或达轮次上限。
3. 全程以 SSE 事件流出：`tool_call.started/completed` → `message.delta` → `done`。
4. 消息与工具调用记录落库（`messages` 表）。

关键不变量：**用户身份不进 LLM 参数**——工具参数不含 user_id，越权防护契约在适配器内按 `Identity` 过滤执行。

## 仓库结构（规划）

```
shoppilot/
├── src/shoppilot/
│   ├── core/          # Agent Loop / ToolRegistry / Context
│   ├── llm/           # OpenAI 兼容客户端
│   ├── identity/      # IdentityProvider + HMAC/Mock 实现
│   ├── storage/       # SQLAlchemy 模型 + 会话仓库 + Alembic
│   ├── api/           # FastAPI 路由 / SSE
│   ├── contrib/       # 领域插件
│   │   ├── orders/    # tools + OrderAdapter 协议
│   │   └── aftersales/# tools + AftersaleAdapter 协议
│   └── adapters/mock_shop/   # Mock 适配器 + 种子数据
├── web/               # React 聊天窗（示例集成）
├── docs/              # adr/ + glossary + 本文件
├── docker-compose.yml
└── pyproject.toml
```

## 路线图备忘（未拍板，仅记录）

- 写操作（退款/售后申请）：等真实需求，届时独立 ToolSet + 确认流程 + 幂等键（ADR-0006）。
- RAG/知识库：V2 候选，届时迁 PostgreSQL + pgvector（ADR-0007）。
- 工具规模膨胀后的筛选/分组策略：单 Agent 内解决（ADR-0003）。
- 更多渠道（IM 机器人）：渠道方消费 HTTP/SSE API 即可，框架不内置渠道适配。
