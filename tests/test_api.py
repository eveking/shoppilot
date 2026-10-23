"""API 全链路：会话创建、SSE 对话、身份校验、404、历史读回（ADR-0011）。"""

import json

from fastapi.testclient import TestClient

from shoppilot.api.app import create_app
from shoppilot.identity.signing import sign_token
from shoppilot.settings import Settings
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


# ---- 历史读回（ADR-0011）----


def test_readback_messages_exclude_tool_rows(settings):
    llm_scripts = [
        tool_script("call_1", "orders__query_orders", '{"status":"待发货"}'),
        text_script("您有一笔待发货订单。"),
    ]
    with make_client(settings, llm_scripts) as client:
        session_id = client.post("/sessions", json={"user_id": "u_1001"}).json()["session_id"]
        client.post("/chat", json={"session_id": session_id, "message": "我的待发货订单"})

        resp = client.get(f"/sessions/{session_id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_more"] is False
        assert [m["role"] for m in data["messages"]] == ["user", "assistant"]
        assert data["messages"][0]["content"] == "我的待发货订单"
        assert data["messages"][1]["content"] == "您有一笔待发货订单。"
        # 用户视角不透出 tool 消息
        assert all("tool_calls" not in m for m in data["messages"])

        # 审计视角：全量含 tool 行
        resp = client.get(f"/sessions/{session_id}/events")
        assert resp.status_code == 200
        roles = [e["role"] for e in resp.json()["events"]]
        assert roles == ["user", "assistant", "tool", "assistant"]
        tool_row = resp.json()["events"][2]
        assert tool_row["tool_name"] == "orders__query_orders"
        assert tool_row["tool_call_id"] == "call_1"
        # tool_calls JSON 在 assistant 中间消息上
        scaffold = resp.json()["events"][1]
        assert scaffold["tool_calls"][0]["id"] == "call_1"
        assert scaffold["tool_calls"][0]["function"]["name"] == "orders__query_orders"


def test_readback_cursor_pagination(settings):
    llm_scripts = [text_script(f"回复{i}") for i in range(3)]
    with make_client(settings, llm_scripts) as client:
        session_id = client.post("/sessions", json={"user_id": "u_1001"}).json()["session_id"]
        for i in range(3):
            client.post("/chat", json={"session_id": session_id, "message": f"消息{i}"})

        # 第一页：最新 2 条（每轮对话 = user + assistant 两条）
        resp = client.get(f"/sessions/{session_id}/messages", params={"limit": 2})
        page1 = resp.json()
        assert [m["content"] for m in page1["messages"]] == ["消息2", "回复2"]
        assert page1["has_more"] is True

        # 用第一页最早一条作游标，取更早一页
        cursor_id = page1["messages"][0]["id"]
        resp = client.get(
            f"/sessions/{session_id}/messages", params={"limit": 2, "before": cursor_id}
        )
        page2 = resp.json()
        assert [m["content"] for m in page2["messages"]] == ["消息1", "回复1"]
        assert page2["has_more"] is True

        # 再翻一页到头
        resp = client.get(
            f"/sessions/{session_id}/messages",
            params={"limit": 2, "before": page2["messages"][0]["id"]},
        )
        page3 = resp.json()
        assert [m["content"] for m in page3["messages"]] == ["消息0", "回复0"]
        assert page3["has_more"] is False

        # 无效游标 → 400
        assert (
            client.get(f"/sessions/{session_id}/messages", params={"before": "nope"}).status_code
            == 400
        )


def test_list_sessions_ordered_by_last_message_at(settings):
    llm_scripts = [text_script("好的。")]
    with make_client(settings, llm_scripts) as client:
        first = client.post("/sessions", json={"user_id": "u_1001"}).json()["session_id"]
        second = client.post("/sessions", json={"user_id": "u_1001"}).json()["session_id"]
        # 只在 first 会话里聊过 → first 应排在最前（最近活跃）
        client.post("/chat", json={"session_id": first, "message": "hi"})

        resp = client.get("/sessions", params={"user_id": "u_1001"})
        assert resp.status_code == 200
        ids = [s["session_id"] for s in resp.json()["sessions"]]
        assert ids == [first, second]
        assert resp.json()["sessions"][0]["last_message_at"] is not None
        assert resp.json()["sessions"][1]["last_message_at"] is None

        # demo 模式不传 user_id → 400
        assert client.get("/sessions").status_code == 400


def test_readback_unknown_session_404(settings):
    with make_client(settings, []) as client:
        assert client.get("/sessions/nope/messages").status_code == 404
        assert client.get("/sessions/nope/events").status_code == 404


# ---- 生产模式统一鉴权（ADR-0011）----


def prod_settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/prod.db",
        demo_mode=False,
        identity_secret="unit-test-secret-0001",
        auto_migrate=True,
        llm_api_key="test-key",
        cors_origins=[],
    )


def test_production_mode_requires_token_and_ownership(tmp_path):
    settings = prod_settings(tmp_path)
    owner = sign_token({"user_id": "u_1001"}, secret=settings.identity_secret)
    other = sign_token({"user_id": "u_1002"}, secret=settings.identity_secret)

    with make_client(settings, [text_script("您好。")]) as client:
        created = client.post("/sessions", json={"token": owner})
        assert created.status_code == 201
        session_id = created.json()["session_id"]

        # /chat 无凭证 → 401
        assert client.post("/chat", json={"session_id": session_id, "message": "hi"}).status_code == 401
        # /chat 伪造凭证 → 401
        assert (
            client.post(
                "/chat",
                json={"session_id": session_id, "message": "hi", "token": "bad.token"},
            ).status_code
            == 401
        )
        # 读回接口同样要求凭证
        assert client.get(f"/sessions/{session_id}/messages").status_code == 401
        # 非归属者 → 404（不泄露存在性）
        headers = {"Authorization": f"Bearer {other}"}
        assert (
            client.get(f"/sessions/{session_id}/messages", headers=headers).status_code == 404
        )
        assert (
            client.get("/sessions", headers=headers).json()["sessions"] == []
        )

        # 归属者：Authorization 头通行
        ok_headers = {"Authorization": f"Bearer {owner}"}
        resp = client.post(
            "/chat", json={"session_id": session_id, "message": "你好"}, headers=ok_headers
        )
        assert resp.status_code == 200
        events = parse_sse(resp.text)
        assert events[-1]["type"] == "done"

        resp = client.get(f"/sessions/{session_id}/messages", headers=ok_headers)
        assert resp.status_code == 200
        assert [m["role"] for m in resp.json()["messages"]] == ["user", "assistant"]

        # /chat body.token 兜底也通行
        resp = client.post(
            "/chat", json={"session_id": session_id, "message": "在吗", "token": owner}
        )
        assert resp.status_code == 200

        # 会话列表只含本人会话
        resp = client.get("/sessions", headers=ok_headers)
        assert [s["session_id"] for s in resp.json()["sessions"]] == [session_id]
