"""API 全链路：会话创建、SSE 对话、身份校验、404。"""

import json

from fastapi.testclient import TestClient

from shoppilot.api.app import create_app
from tests.conftest import FakeLLM, text_script, tool_script


def make_client(settings, scripts: list) -> TestClient:
    app = create_app(settings, llm_client=FakeLLM(scripts))
    return TestClient(app)


def parse_sse(body: str) -> list[dict]:
    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def test_health(settings):
    with make_client(settings, []) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["demo_mode"] is True


def test_create_session_demo_mode(settings):
    with make_client(settings, []) as client:
        resp = client.post("/sessions", json={"user_id": "u_1001"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["session_id"]
        assert data["user_id"] == "u_1001"
        # 两者同传 → 400
        assert client.post("/sessions", json={"user_id": "u", "token": "t"}).status_code == 400
        # 都不传 → 400
        assert client.post("/sessions", json={}).status_code == 400


def test_chat_full_flow_with_tool_call(settings):
    llm_scripts = [
        tool_script(
            "call_1",
            "orders__query_orders",
            '{"status":"待发货"}',
        ),
        text_script("您有一笔待发货订单 SO20260315001，共 299.00 元，我们会尽快安排发出。"),
    ]
    with make_client(settings, llm_scripts) as client:
        session_id = client.post("/sessions", json={"user_id": "u_1001"}).json()["session_id"]
        resp = client.post("/chat", json={"session_id": session_id, "message": "我的待发货订单"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        events = parse_sse(resp.text)
        types = [e["type"] for e in events]
        assert types == [
            "tool_call.started",
            "tool_call.completed",
            "message.delta",
            "done",
        ]
        completed = events[1]
        assert completed["ok"] is True
        assert completed["result"]["total"] == 1
        assert completed["result"]["orders"][0]["order_id"] == "SO20260315001"
        assert events[-1]["rounds_used"] == 2


def test_chat_unknown_session_404(settings):
    with make_client(settings, []) as client:
        resp = client.post("/chat", json={"session_id": "nope", "message": "hi"})
        assert resp.status_code == 404


def test_chat_empty_message_400(settings):
    with make_client(settings, []) as client:
        session_id = client.post("/sessions", json={"user_id": "u_1001"}).json()["session_id"]
        resp = client.post("/chat", json={"session_id": session_id, "message": "   "})
        assert resp.status_code == 400


def test_multi_turn_history_reaches_llm(settings):
    llm_scripts = [
        text_script("您好，我是 ShopPilot 客服。"),
        text_script("您刚才打过招呼，请问需要查订单吗？"),
    ]
    with make_client(settings, llm_scripts) as client:
        session_id = client.post("/sessions", json={"user_id": "u_1001"}).json()["session_id"]
        client.post("/chat", json={"session_id": session_id, "message": "你好"})
        client.post("/chat", json={"session_id": session_id, "message": "我上一句说了什么？"})

    # 直接验证库表：历史消息已持久化
    import sqlite3

    db_path = settings.database_url.split("///", 1)[1]
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT role, content FROM messages ORDER BY created_at").fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["user", "assistant", "user", "assistant"]
    assert rows[0][1] == "你好"


def test_registry_has_builtin_domains(settings):
    app = create_app(settings, llm_client=FakeLLM([]))
    names = [ts.name for ts in app.state.registry.toolsets]
    assert names == ["orders", "aftersales"]
    tools = [t["function"]["name"] for t in app.state.registry.openai_tools()]
    assert "orders__query_orders" in tools
    assert "aftersales__get_aftersale" in tools


def test_create_app_with_custom_toolsets(settings):
    from shoppilot.core.tools import ToolSet, ToolSpec

    class OnlyEcho(ToolSet):
        name = "echo"
        description = "仅回声"

        def build_tools(self) -> list[ToolSpec]:
            async def handler(args, ctx):
                return {}

            return [
                ToolSpec(
                    name="ping",
                    description="回显",
                    parameters={"type": "object", "properties": {}},
                    handler=handler,
                )
            ]

    app = create_app(settings, llm_client=FakeLLM([]), toolsets=[OnlyEcho()])
    assert [ts.name for ts in app.state.registry.toolsets] == ["echo"]
    assert [t["function"]["name"] for t in app.state.registry.openai_tools()] == ["echo__ping"]
