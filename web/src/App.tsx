import { useEffect, useRef, useState } from "react";
import { createSession, streamChat } from "./api";
import type { AgentEvent, ChatMessage } from "./types";

const DEMO_USERS = ["u_1001", "u_1002", "u_1003"];

let nextId = 1;
const genId = () => `m${nextId++}`;

export default function App() {
  const [userIdInput, setUserIdInput] = useState("");
  const [session, setSession] = useState<{ sessionId: string; userId: string } | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function handleLogin(uid?: string) {
    const userId = (uid ?? userIdInput).trim();
    if (!userId) return;
    setError(null);
    try {
      const res = await createSession({ userId });
      setSession({ sessionId: res.session_id, userId: res.user_id });
      setMessages([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function patchLastAssistant(fn: (m: ChatMessage) => ChatMessage) {
    setMessages((prev) => {
      const idx = prev.length - 1;
      if (idx < 0 || prev[idx].role !== "assistant") return prev;
      const copy = [...prev];
      copy[idx] = fn(copy[idx]);
      return copy;
    });
  }

  function applyEvent(event: AgentEvent) {
    switch (event.type) {
      case "message.delta":
        patchLastAssistant((m) => ({ ...m, content: m.content + (event.content ?? "") }));
        break;
      case "tool_call.started":
        patchLastAssistant((m) => ({
          ...m,
          tools: [
            ...(m.tools ?? []),
            {
              id: event.tool_call_id ?? genId(),
              name: event.tool_name ?? "",
              arguments: event.arguments ?? "",
              status: "running",
            },
          ],
        }));
        break;
      case "tool_call.completed":
        patchLastAssistant((m) => ({
          ...m,
          tools: (m.tools ?? []).map((t) =>
            t.id === event.tool_call_id
              ? { ...t, status: "completed", ok: event.ok, result: event.result }
              : t
          ),
        }));
        break;
      case "done":
        patchLastAssistant((m) => ({ ...m, streaming: false }));
        break;
      case "error":
        patchLastAssistant((m) => ({
          ...m,
          streaming: false,
          content: m.content || `出错了：${event.error ?? "未知错误"}`,
        }));
        break;
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || !session || busy) return;
    setInput("");
    setBusy(true);
    setError(null);
    setMessages((prev) => [
      ...prev,
      { id: genId(), role: "user", content: text },
      { id: genId(), role: "assistant", content: "", tools: [], streaming: true },
    ]);
    try {
      await streamChat(session.sessionId, text, {
        onEvent: (event) => applyEvent(event),
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      patchLastAssistant((m) => ({ ...m, streaming: false }));
    } finally {
      setBusy(false);
    }
  }

  if (!session) {
    return (
      <div className="login-wrap">
        <div className="login-card">
          <div className="logo">🛍️</div>
          <h1>ShopPilot 客服助手</h1>
          <p className="sub">演示模式：输入用户编号直接进入（免签发 token）</p>
          <div className="quick-users">
            {DEMO_USERS.map((u) => (
              <button key={u} className="chip" onClick={() => handleLogin(u)}>
                {u}
              </button>
            ))}
          </div>
          <div className="login-row">
            <input
              value={userIdInput}
              placeholder="或输入任意用户编号…"
              onChange={(e) => setUserIdInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            />
            <button className="primary" onClick={() => handleLogin()}>
              开始对话
            </button>
          </div>
          {error && <p className="error">{error}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="chat-wrap">
      <header>
        <div>
          <span className="logo-sm">🛍️</span> ShopPilot 客服助手
        </div>
        <div className="session-info">
          身份：{session.userId}
          <button className="link" onClick={() => setSession(null)}>
            退出
          </button>
        </div>
      </header>
      <div className="msg-list" ref={listRef}>
        {messages.length === 0 && (
          <div className="empty-hint">
            <p>你好，我是本店智能客服 🤖</p>
            <p>可以问我：我的订单到哪了 / 帮我查一下售后进度</p>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`bubble-row ${m.role}`}>
            <div className="bubble">
              {m.role === "assistant" && m.tools?.map((t) => <ToolChip key={t.id} tool={t} />)}
              {m.content && <div className="content">{m.content}</div>}
              {m.streaming && !m.content && (m.tools?.length ?? 0) === 0 && (
                <span className="typing">正在思考…</span>
              )}
            </div>
          </div>
        ))}
      </div>
      {error && <div className="error banner">{error}</div>}
      <footer>
        <input
          value={input}
          placeholder="输入消息，回车发送…"
          disabled={busy}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
        />
        <button className="primary" disabled={busy || !input.trim()} onClick={handleSend}>
          发送
        </button>
      </footer>
    </div>
  );
}

const TOOL_LABELS: Record<string, string> = {
  "orders__query_orders": "查询订单列表",
  "orders__get_order": "查询订单详情",
  "aftersales__list_aftersales": "查询售后列表",
  "aftersales__get_aftersale": "查询售后详情",
};

function ToolChip({ tool }: { tool: import("./types").ToolCallView }) {
  const label = TOOL_LABELS[tool.name] ?? tool.name;
  return (
    <details className={`tool-chip ${tool.status}`}>
      <summary>
        <span className="tool-icon">{tool.status === "running" ? "⏳" : tool.ok ? "✅" : "⚠️"}</span>
        {label}
        {tool.status === "running" && <span className="tool-hint">（执行中）</span>}
      </summary>
      <pre>{JSON.stringify(tool.result ?? tool.arguments, null, 2)}</pre>
    </details>
  );
}
