"""Agent 循环（ADR-0003/0008）：模型回复 ↔ 工具执行往复，事件流输出。

一次 run_chat 对应 API 层一次 /chat 请求的完整 SSE 流。
持久化通过 persist 回调注入（依赖接受而非创建，便于测试）。
"""

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Literal

from pydantic import BaseModel

from shoppilot.core.context import ToolContext
from shoppilot.core.tools import ToolExecutionError, ToolRegistry
from shoppilot.identity.provider import Identity

logger = logging.getLogger(__name__)

PersistFn = Callable[..., Awaitable[None]]


class AgentEvent(BaseModel):
    """SSE 事件信封。字段按 type 取用：

    - message.delta        content
    - tool_call.started    tool_call_id, tool_name, arguments
    - tool_call.completed  tool_call_id, tool_name, ok, result
    - done                 content, usage, rounds_used
    - error                error
    """

    type: Literal[
        "message.delta",
        "tool_call.started",
        "tool_call.completed",
        "done",
        "error",
    ]
    content: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    arguments: str | None = None
    ok: bool | None = None
    result: dict | None = None
    error: str | None = None
    usage: dict | None = None
    rounds_used: int | None = None


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…[结果过长已截断，原始长度 {len(text)} 字符]"


async def run_chat(
    *,
    llm,
    registry: ToolRegistry,
    messages: list[dict],
    identity: Identity,
    session_id: str,
    max_rounds: int = 8,
    tool_result_max_chars: int = 6000,
    persist: PersistFn | None = None,
) -> AsyncIterator[AgentEvent]:
    """执行一轮完整对话，产出 AgentEvent 流。

    messages 需已含 system、历史与本轮用户消息。
    persist(role=..., content=..., tool_calls=..., tool_call_id=..., tool_name=...)
    """
    tools = registry.openai_tools()
    rounds_used = 0

    for round_index in range(max_rounds):
        rounds_used = round_index + 1
        content_parts: list[str] = []
        tool_calls_acc: dict[int, dict] = {}
        usage: dict | None = None

        async for chunk in llm.stream_chat(messages, tools):
            if chunk.content:
                content_parts.append(chunk.content)
                yield AgentEvent(type="message.delta", content=chunk.content)
            if chunk.tool_call is not None:
                acc = tool_calls_acc.setdefault(
                    chunk.tool_call.index,
                    {"id": "", "name": "", "arguments": ""},
                )
                if chunk.tool_call.id:
                    acc["id"] = chunk.tool_call.id
                if chunk.tool_call.name:
                    acc["name"] = chunk.tool_call.name
                acc["arguments"] += chunk.tool_call.arguments_delta
            if chunk.usage:
                usage = chunk.usage

        full_content = "".join(content_parts)

        if not tool_calls_acc:
            if persist is not None:
                await persist(role="assistant", content=full_content)
            yield AgentEvent(
                type="done", content=full_content, usage=usage, rounds_used=rounds_used
            )
            return

        assistant_tool_calls = [
            {
                "id": acc["id"] or f"call_{index}",
                "type": "function",
                "function": {"name": acc["name"], "arguments": acc["arguments"] or "{}"},
            }
            for index, acc in sorted(tool_calls_acc.items())
        ]
        messages.append(
            {
                "role": "assistant",
                "content": full_content or None,
                "tool_calls": assistant_tool_calls,
            }
        )
        if persist is not None:
            await persist(
                role="assistant",
                content=full_content or None,
                tool_calls=json.dumps(assistant_tool_calls, ensure_ascii=False),
            )

        for tc in assistant_tool_calls:
            fn = tc["function"]
            yield AgentEvent(
                type="tool_call.started",
                tool_call_id=tc["id"],
                tool_name=fn["name"],
                arguments=fn["arguments"],
            )
            ok, result_payload = await _execute_tool(
                registry, fn, identity, session_id, tool_result_max_chars
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result_payload, ensure_ascii=False, default=str),
                }
            )
            if persist is not None:
                await persist(
                    role="tool",
                    content=json.dumps(result_payload, ensure_ascii=False, default=str),
                    tool_call_id=tc["id"],
                    tool_name=fn["name"],
                )
            yield AgentEvent(
                type="tool_call.completed",
                tool_call_id=tc["id"],
                tool_name=fn["name"],
                ok=ok,
                result=result_payload,
            )

    yield AgentEvent(
        type="error",
        error=f"已达到单轮工具调用上限（{max_rounds} 轮），请稍后重试或换个问法。",
    )


async def _execute_tool(
    registry: ToolRegistry,
    fn: dict,
    identity: Identity,
    session_id: str,
    result_max_chars: int,
) -> tuple[bool, dict]:
    """执行单个工具调用，永不抛出——错误折叠进结果。"""
    name = fn["name"]
    if name not in registry:
        return False, {"error": f"未知工具: {name}"}
    try:
        args = json.loads(fn["arguments"] or "{}")
        if not isinstance(args, dict):
            raise ValueError("工具参数必须是 JSON 对象")
    except (json.JSONDecodeError, ValueError) as exc:
        return False, {"error": f"工具参数解析失败: {exc}"}
    try:
        spec = registry.get(name)
        result = await spec.handler(args, ToolContext(identity=identity, session_id=session_id))
        payload = json.loads(json.dumps(result, ensure_ascii=False, default=str))
        text = json.dumps(payload, ensure_ascii=False)
        if len(text) > result_max_chars:
            truncated = _truncate(text, result_max_chars)
            try:
                payload = json.loads(truncated)
            except json.JSONDecodeError:
                payload = {"error": "工具结果过长且无法安全截断", "raw_head": truncated[:200]}
            return True, payload
        return True, payload
    except ToolExecutionError as exc:
        return False, {"error": str(exc)}
    except Exception:
        logger.exception("工具 %s 执行异常", name)
        return False, {"error": f"工具 {name} 执行异常，请稍后重试"}
