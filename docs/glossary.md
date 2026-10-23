# ShopPilot 术语表

设计讨论中，以下术语**必须**按定义使用，禁止近义替换（不要说"组件/服务/边界"）。

## 设计词汇（源自 deep-module 设计法）

| 术语 | 定义 | 反例（禁用） |
|---|---|---|
| **模块（Module）** | 有接口和实现之物，刻意尺度无关：函数、类、包或跨层切片均可 | 单元、组件、服务 |
| **接口（Interface）** | 调用者正确使用模块必须知道的一切：类型签名 + 不变量 + 顺序约束 + 错误模式 + 必需配置 + 性能特征 | API、签名（太窄） |
| **实现（Implementation）** | 模块内部的代码主体 | —— |
| **接缝（Seam）** | 不修改彼处即可改变行为的位置；模块接口所在之处 | 边界（与 DDD 限界上下文混淆） |
| **适配器（Adapter）** | 在接缝处满足接口的具体实现，描述角色而非实质 | —— |
| **深度（Depth）** | 接口处的杠杆率：每学一单位接口能撬动多少行为。深模块=小接口大实现 | —— |
| **杠杆（Leverage）** | 深度给调用者的回报：一处处实现，N 个调用点与 M 个测试复用 | —— |
| **局部性（Locality）** | 深度给维护者的回报：变更、缺陷、知识、验证集中一处 | —— |

判断口诀：**一个适配器意味着假设性接缝，两个才是真实接缝。**

## 项目术语

| 术语 | 定义 |
|---|---|
| **ShopPilot** | 本项目名。开源电商客服 Agent 框架（FastAPI + DeepSeek + Function Calling） |
| **ToolSet（领域插件）** | 一个领域的完整插入单元 = 工具声明（function calling schema + 实现）+ 领域适配器协议 + 领域系统提示片段。向 Agent 注册即生效。内置：`orders`、`aftersales` |
| **SourceAdapter / 领域适配器协议** | 各领域 ToolSet 声明的数据访问协议（如 `OrderAdapter`、`AftersaleAdapter`）。工具访问外部数据的唯一通道 |
| **MockShopAdapter** | 内置示例适配器，实现全部内置领域协议，附 demo 种子数据（模拟商城：用户/订单/售后单） |
| **IdentityProvider** | 身份接缝：校验签名 token、解析出 `Identity` 的接口。内置 `HmacIdentityProvider`（生产）与 `MockIdentityProvider`（demo） |
| **Identity** | 一次会话的已验证用户身份（`user_id` + claims），挂在工具执行上下文上随调用传递，永不出现在 LLM 可见参数中 |
| **签名 Token** | 接入方服务端用共享密钥对 `{user_id, exp}` 做 HMAC 签发的凭证；前端凭它创建会话 |
| **Agent 循环（Agent Loop）** | 单轮请求的核心执行流：模型回复 ↔ function calling 工具执行往复，直到产出最终回答或达轮次上限 |
| **ToolRegistry** | 工具注册表：收集各 ToolSet 的工具，转成模型侧 schema；工具名命名空间化为 `领域__工具名` |
| **会话（Session）** | 一次多轮对话的持久化单元，绑定 Identity；含有序消息列表 |
| **所有权校验（Ownership Check）** | 会话相关接口的鉴权不变量：请求者 token 解析出的 `user_id` 必须等于会话归属者，否则 404/403；demo 模式豁免（ADR-0011） |
| **历史读回（Read-back）** | 把已落库的历史经 HTTP 查回的能力。用户消息读回（`GET /sessions/{id}/messages`，不透出 tool 消息）与审计事件读回（`GET /sessions/{id}/events`，全量）是两个契约（ADR-0011） |
| **审计事件（Audit Events）** | 会话内全部落库消息（含 tool 调用与结果）的完整视图，供排查/审计；与终端用户可见的消息读回严格分开 |
| **游标分页（Cursor Pagination）** | 用 `before=<message_id>` + `limit` 取游标之前一页的分页方式；不用 offset，避免并发追加时页漂移 |
| **最近活跃（last_message_at）** | sessions 表的专用字段，append_message 时写入，会话列表按其倒序；不借用公共字段 `updated_at` 承载此语义 |
| **示例集成（Sample Integration）** | 内置聊天窗、MockShopAdapter、种子数据的统一定位——证明接缝可用，非产品本体 |
| **SSE 事件** | `/chat` 流式接口的事件协议：`message.delta` / `tool_call.started` / `tool_call.completed` / `done` / `error` |
