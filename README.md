# ShopPilot

开源电商客服 Agent 框架：FastAPI + DeepSeek + Function Calling。

ShopPilot 定位是**开发者的框架/脚手架**——你基于它构建自己的电商客服产品。核心资产是四条扩展接缝；内置的 React 聊天窗、Mock 商城适配器、演示数据都是**示例集成**，证明接缝可用。

```
┌───────────────────────────────────────────────────┐
│  渠道示例  web/ React 聊天窗（可不用，直接调 API）    │
├───────────────────────────────────────────────────┤
│  API 层  POST /sessions · POST /chat (SSE 流式)     │
├───────────────────────────────────────────────────┤
│  Agent 核心  循环（模型回复 ↔ 工具执行）· 工具注册表   │
├───────────────┬───────────────────────────────────┤
│ 身份接缝        │ LLM 接缝（OpenAI 兼容，默认 DeepSeek）│
│ IdentityProvider│  base_url / api_key / model 配置化   │
├───────────────┴───────────────────────────────────┤
│  领域插件（ToolSet 注册即生效）                       │
│    orders · aftersales  ←  物流/商品/营销… 你来加     │
├───────────────────────────────────────────────────┤
│  数据源接缝  OrderAdapter / AftersaleAdapter         │
│    ▲ 内置 MockShopAdapter   ▲ 接你的淘宝/Shopify/自建 │
├───────────────────────────────────────────────────┤
│  存储  SQLAlchemy + Alembic   SQLite → PostgreSQL    │
└───────────────────────────────────────────────────┘
```

设计决策见 [docs/adr/](docs/adr/)，架构总览见 [docs/architecture.md](docs/architecture.md)。

## 特性

- **单 Agent + 工具集插件**：一个领域 = 一个 ToolSet（工具声明 + 适配器协议 + 领域提示），注册即生效，核心零改动
- **流式对话**：SSE 事件流（增量文本 / 工具调用状态 / 结束 / 错误），前端与 Agent 循环解耦
- **身份内建**：服务端签发 HMAC token；用户身份随工具上下文传递，**不进入 LLM 参数**，越权防护契约在适配器内执行
- **第一版全只读**：无副作用工具，安全面最小
- **LLM 可换**：OpenAI 兼容协议，默认 `deepseek-chat`，一行配置切换 Kimi / Qwen / GLM
- **存储平滑升级**：SQLite 开箱即跑，Alembic 管迁移，随时切 PostgreSQL

## 快速开始

要求：Python 3.12+、[uv](https://docs.astral.sh/uv/)。

```bash
git clone <repo-url> shop-agent && cd shop-agent
uv sync
copy .env.example .env        # Windows；Linux/macOS 用 cp
# 编辑 .env：填入 SHOPILOT_LLM_API_KEY=sk-xxx（DeepSeek API Key）
uv run uvicorn shoppilot.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000>，点击演示用户（如 `u_1001`）进入对话，试试：

- 「我的待发货订单有哪些？」
- 「帮我查一下订单 SO20260315001 的详情」
- 「我有售后单在处理吗？」
- 「查一下售后单 AF20260416002 的进度」

### Docker 一键启动

```bash
SHOPILOT_LLM_API_KEY=sk-xxx docker compose up --build
```

### 前端开发模式

聊天窗源码在 `web/`，改完 `npm run build` 后由 FastAPI 托管；开发时热更新：

```bash
cd web && npm install && npm run dev   # http://localhost:5173，自动代理到 8000
```

## 配置

全部配置带 `SHOPILOT_` 前缀，支持 `.env` 与环境变量：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `SHOPILOT_LLM_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容服务地址 |
| `SHOPILOT_LLM_API_KEY` | — | API Key |
| `SHOPILOT_LLM_MODEL` | `deepseek-chat` | 模型名，需支持 function calling |
| `SHOPILOT_IDENTITY_SECRET` | `change-me-…` | HMAC 签名密钥，**生产必须更换** |
| `SHOPILOT_DEMO_MODE` | `true` | demo 模式免签发 token；生产务必关闭 |
| `SHOPILOT_DATABASE_URL` | `sqlite+aiosqlite:///./data/shoppilot.db` | 换 PG：`postgresql+asyncpg://…` |
| `SHOPILOT_AGENT_MAX_TOOL_ROUNDS` | `8` | 单次对话工具调用轮次上限 |
| `SHOPILOT_CONTEXT_MAX_MESSAGES` | `20` | 送入模型的历史消息条数 |
| `SHOPILOT_TOOL_RESULT_MAX_CHARS` | `6000` | 工具结果截断阈值 |
| `SHOPILOT_AUTO_MIGRATE` | `true` | 启动时自动执行 Alembic 迁移 |

## 接入你的订单系统

两步：**实现领域适配器协议** + **关闭 demo 模式**。

### 1. 实现 OrderAdapter

```python
# myproject/adapters.py
from shoppilot.contrib.orders import OrderDetail, OrderSummary
from shoppilot.contrib.aftersales import AftersaleDetail, AftersaleSummary
from shoppilot.identity.provider import Identity


class TaobaoOrderAdapter:
    """实现 shoppilot.contrib.orders.adapter.OrderAdapter 协议。

    实现契约（docs/adr/0002-数据源适配器接缝-Mock先行.md）：
    1. 必须按 identity.user_id 过滤数据（越权防护），非本人数据返回 None；
    2. 收件人姓名/手机号/地址必须脱敏后返回；
    3. 网络与平台错误抛 ToolExecutionError，框架会折叠成 {"error": ...}。
    """

    async def list_orders(self, identity: Identity, *, status=None, limit=5, offset=0):
        ...  # -> (list[OrderSummary], total)

    async def get_order(self, identity: Identity, order_id: str):
        ...  # -> OrderDetail | None（查无或不属于该用户都返回 None）
```

### 2. 组装应用

```python
# main.py
from shoppilot.api.app import create_app
from shoppilot.contrib.orders import OrdersToolSet
from shoppilot.contrib.aftersales import AftersalesToolSet
from myproject.adapters import TaobaoOrderAdapter, TaobaoAftersaleAdapter

app = create_app(
    toolsets=[
        OrdersToolSet(TaobaoOrderAdapter()),
        AftersalesToolSet(TaobaoAftersaleAdapter()),
    ]
)
```

```bash
SHOPILOT_DEMO_MODE=false SHOPILOT_IDENTITY_SECRET=你的长随机密钥 \
  uv run uvicorn main:app --factory --port 8000
```

### 3. 你的服务端签发身份 token

```python
from shoppilot.identity.signing import sign_token

token = sign_token({"user_id": "u_1001"}, secret="你的长随机密钥", expires_in=86400)
# 前端凭 token 创建会话：POST /sessions {"token": "..."}
```

## 新增一个领域（如物流）

框架核心不认识任何具体领域——新领域 = 新 ToolSet：

```python
# src/shoppilot/contrib/logistics/toolset.py
from shoppilot.core.context import ToolContext
from shoppilot.core.tools import ToolSet, ToolSpec


class LogisticsToolSet(ToolSet):
    name = "logistics"                       # 工具全名将是 logistics__track
    description = "物流领域：可查询订单的快递轨迹。"  # 注入系统提示

    def __init__(self, adapter) -> None:     # adapter 满足你定义的协议
        self.adapter = adapter

    def build_tools(self) -> list[ToolSpec]:
        async def track(args: dict, ctx: ToolContext) -> dict:
            # ctx.identity 由框架注入——不要从 args 里取用户身份
            return await self.adapter.track(ctx.identity, args["order_id"])

        return [
            ToolSpec(
                name="track",
                description="按订单号查询快递轨迹",
                parameters={
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"],
                },
                handler=track,
            )
        ]
```

在 `create_app(toolsets=[…])` 里多注册一个即可；前端无需任何改动（工具调用状态条自动出现）。

## HTTP API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查与运行模式 |
| POST | `/sessions` | 创建会话。demo 模式传 `{"user_id": "…"}`；生产传 `{"token": "…"}` |
| GET | `/sessions` | 当前用户会话列表，按最近活跃倒序。生产传 `Authorization: Bearer <token>`；demo 传 `?user_id=`。支持 `?limit=` |
| GET | `/sessions/{id}/messages` | 历史读回（用户视角）：只含 user/assistant 消息。游标分页 `?limit=50&before=<message_id>`，返回 `{has_more, messages}` |
| GET | `/sessions/{id}/events` | 审计读回：全量消息含 tool 调用与结果，分页参数同上 |
| POST | `/chat` | `{"session_id": "…", "message": "…"}`，返回 SSE 流。生产模式需带 token（Authorization 头优先，body `token` 字段兜底） |

生产模式下除 `/health`、`POST /sessions` 外的所有会话接口均要求 token，且 token 对应的 user_id 必须等于会话归属者，否则返回 404（不泄露会话存在性）；demo 模式豁免。详见 ADR-0011。

`/chat` SSE 事件（`data: {json}\n\n`）：

| type | 字段 | 含义 |
|---|---|---|
| `message.delta` | `content` | 回答增量文本 |
| `tool_call.started` | `tool_call_id, tool_name, arguments` | 开始调用工具 |
| `tool_call.completed` | `tool_call_id, tool_name, ok, result` | 工具执行返回 |
| `done` | `content, usage, rounds_used` | 本轮回答结束 |
| `error` | `error` | 失败（含轮次上限） |

## 项目结构

```
shop-agent/
├── src/shoppilot/
│   ├── core/          # Agent 循环 / ToolRegistry / 上下文组装
│   ├── llm/           # OpenAI 兼容客户端
│   ├── identity/      # 身份接缝（HMAC / Mock）
│   ├── storage/       # SQLAlchemy 模型 / 仓库 / 迁移
│   ├── api/           # FastAPI 路由 / SSE / 应用工厂
│   ├── contrib/       # 领域插件：orders、aftersales
│   └── adapters/      # mock_shop：示例适配器 + 种子数据
├── web/               # React 聊天窗（示例集成）
├── docs/              # adr/ 决策记录 · architecture.md · glossary.md
├── tests/
├── alembic/           # 数据库迁移
├── Dockerfile · docker-compose.yml · pyproject.toml
└── .env.example
```

## 开发

```bash
uv sync                          # 安装依赖
uv run pytest -q                 # 运行测试
uv run ruff check src tests      # 代码检查
```

## Roadmap

- [ ] 写操作工具（发起退款/售后），含确认流程与幂等键
- [ ] RAG / 知识库（迁移 PostgreSQL + pgvector）
- [ ] 工具规模膨胀后的注册表筛选策略
- [ ] 更多领域插件（物流、商品、营销）

## License

[MIT](LICENSE)
