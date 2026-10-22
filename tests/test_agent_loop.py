"""Agent 循环：工具调用往复、事件流、持久化回调。"""

import json

from shoppilot.core.agent import AgentEvent, run_chat
from shoppilot.core.tools import ToolRegistry, ToolSet, ToolSpec
from shoppilot.identity.provider import Identity
from tests.conftest import FakeLLM, text_script, tool_script


class EchoToolSet(ToolSet):
    name = "echo"
    description = "回声测试领域"

    def __init__(self) -> None:
        self.adapter = object()

    def build_tools(self) -> list[ToolSpec]:
        async def handler(args: dict, ctx) -> dict:
            return {"echo": args["text"], "caller": ctx.identity.user_id}

        return [
            ToolSpec(
                name="ping",
                description="回显文本",
                parameters={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                handler=handler,
            )
        ]


def make_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(EchoToolSet())
    return registry


async def collect(aiter) -> list[AgentEvent]:
    return [event async for event in aiter]


async def test_tool_call_roundtrip_and_done():
    llm = FakeLLM(
        [
            tool_script("call_1", "echo__ping", '{"text":"hi"}'),
            text_script("你好，测试完成！"),
        ]
    )
    persisted: list[dict] = []

    async def persist(**kwargs):
        persisted.append(kwargs)

    events = await collect(
        run_chat(
            llm=llm,
            registry=make_registry(),
            messages=[{"role": "user", "content": "测试一下"}],
            identity=Identity(user_id="u_1001"),
            session_id="s1",
            persist=persist,
        )
    )

    assert [e.type for e in events] == [
        "tool_call.started",
        "tool_call.completed",
        "message.delta",
        "done",
    ]
    done = events[-1]
    assert done.content == "你好，测试完成！"
    assert done.rounds_used == 2
    completed = events[1]
    assert completed.ok is True
    assert completed.result == {"echo": "hi", "caller": "u_1001"}

    # 第二轮请求应包含工具结果回填
    second_call_messages = llm.calls[1]["messages"]
    assert any(m["role"] == "tool" and '"echo": "hi"' in m["content"] for m in second_call_messages)

    # 持久化：assistant(tool_calls) → tool → assistant(final)
    assert [p["role"] for p in persisted] == ["assistant", "tool", "assistant"]
    assert json.loads(persisted[0]["tool_calls"])[0]["function"]["name"] == "echo__ping"


async def test_unknown_tool_and_bad_arguments_fold_into_result():
    llm = FakeLLM(
        [
            tool_script("call_9", "echo__missing", "not-json"),
            text_script("明白了"),
        ]
    )
    events = await collect(
        run_chat(
            llm=llm,
            registry=make_registry(),
            messages=[{"role": "user", "content": "x"}],
            identity=Identity(user_id="u_1001"),
            session_id="s1",
        )
    )
    completed = [e for e in events if e.type == "tool_call.completed"][0]
    assert completed.ok is False
    assert "未知工具" in completed.result["error"]
    assert events[-1].type == "done"


async def test_max_rounds_guard():
    llm = FakeLLM([tool_script("call_x", "echo__ping", '{"text":"loop"}') for _ in range(3)])
    events = await collect(
        run_chat(
            llm=llm,
            registry=make_registry(),
            messages=[{"role": "user", "content": "x"}],
            identity=Identity(user_id="u_1001"),
            session_id="s1",
            max_rounds=3,
        )
    )
    assert events[-1].type == "error"
    assert "上限" in events[-1].error


async def test_plain_text_answer_without_tools():
    llm = FakeLLM([text_script("您好，有什么可以帮您？")])
    events = await collect(
        run_chat(
            llm=llm,
            registry=make_registry(),
            messages=[{"role": "user", "content": "在吗"}],
            identity=Identity(user_id="u_1001"),
            session_id="s1",
        )
    )
    assert [e.type for e in events] == ["message.delta", "done"]
    assert events[-1].rounds_used == 1
