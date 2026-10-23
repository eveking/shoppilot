import { useEffect, useRef, useState } from "react";
import { createSession, fetchMessages, listSessions, streamChat } from "./api";
import type { AgentEvent, ChatMessage, HistoryMessage, SessionSummary } from "./types";

const DEMO_USERS = ["u_1001", "u_1002", "u_1003"];
const SUGGESTIONS = ["我的订单到哪了？", "帮我查一下售后进度"];
const STORAGE_KEY = "shoppilot.session";

/** localStorage 持久化的会话凭据（ADR-0011 刷新恢复） */
interface StoredSession {
  sessionId: string;
  userId: string;
  token?: string;
}

function loadStoredSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

function saveStoredSession(s: StoredSession | null) {
  if (s) localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  else localStorage.removeItem(STORAGE_KEY);
}

/** 服务端历史消息 → 聊天窗消息（srv_ 前缀避免与本地 genId 冲突） */
function mapHistory(rows: HistoryMessage[]): ChatMessage[] {
  return rows.map((m) => ({
    id: `srv_${m.id}`,
    role: m.role,
    content: m.content ?? "",
  }));
}

function fmtTime(iso: string | null): string {
  const d = iso ? new Date(iso) : null;
  if (!d || Number.isNaN(d.getTime())) return "新会话";
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  return sameDay
    ? d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

let nextId = 1;
const genId = () => `m${nextId++}`;

/* ---- 品牌与语义图标（描边风格，替代 emoji） ---- */
function BagIcon({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 8h12l-1.2 11a2 2 0 0 1-2 1.8H9.2a2 2 0 0 1-2-1.8L6 8Z" />
      <path d="M9 10V6a3 3 0 0 1 6 0v4" />
    </svg>
  );
}

function SparkIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M11 4l1.5 4L16.5 9.5 12.5 11 11 15 9.5 11 5.5 9.5 9.5 8 11 4Z" />
      <path d="M18.5 14.5l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9.9-2.1Z" />
    </svg>
  );
}

function ArrowUpIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 19V5" />
      <path d="M5.5 11.5 12 5l6.5 6.5" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export default function App() {
  const [userIdInput, setUserIdInput] = useState("");
  const [session, setSession] = useState<StoredSession | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  // 启动恢复：localStorage 有会话则拉取历史回显；404 则静默开新（ADR-0011）
  useEffect(() => {
    const stored = loadStoredSession();
    if (!stored) {
      setRestoring(false);
      return;
    }
    (async () => {
      try {
        const page = await fetchMessages(stored.sessionId, { token: stored.token });
        setSession(stored);
        setMessages(mapHistory(page.messages));
        setHasMore(page.has_more);
        refreshSessions(stored);
      } catch {
        saveStoredSession(null); // 会话已失效，静默放弃
      } finally {
        setRestoring(false);
      }
    })();
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function refreshSessions(s: StoredSession) {
    try {
      setSessions(await listSessions({ userId: s.userId, token: s.token }));
    } catch {
      /* 列表加载失败不打断主流程 */
    }
  }

  async function handleLogin(uid?: string) {
    const userId = (uid ?? userIdInput).trim();
    if (!userId) return;
    setError(null);
    try {
      // 优先恢复该身份最近活跃的会话（退出重登不丢历史）；从未聊过才新建
      const list = await listSessions({ userId }).catch(() => []);
      const active = list.find((s) => s.last_message_at !== null);
      if (active) {
        const page = await fetchMessages(active.session_id);
        const stored: StoredSession = { sessionId: active.session_id, userId };
        saveStoredSession(stored);
        setSession(stored);
        setMessages(mapHistory(page.messages));
        setHasMore(page.has_more);
        refreshSessions(stored);
        return;
      }
      const res = await createSession({ userId });
      const stored: StoredSession = { sessionId: res.session_id, userId: res.user_id };
      saveStoredSession(stored);
      setSession(stored);
      setMessages([]);
      setHasMore(false);
      refreshSessions(stored);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleNewSession() {
    if (!session || busy) return;
    setError(null);
    try {
      const res = await createSession(
        session.token ? { token: session.token } : { userId: session.userId }
      );
      const stored: StoredSession = {
        sessionId: res.session_id,
        userId: res.user_id,
        token: session.token,
      };
      saveStoredSession(stored);
      setSession(stored);
      setMessages([]);
      setHasMore(false);
      refreshSessions(stored);
      setDrawerOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleSwitch(targetId: string) {
    if (!session || busy || targetId === session.sessionId) return;
    setError(null);
    try {
      const page = await fetchMessages(targetId, { token: session.token });
      const stored = { ...session, sessionId: targetId };
      saveStoredSession(stored);
      setSession(stored);
      setMessages(mapHistory(page.messages));
      setHasMore(page.has_more);
      setDrawerOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function loadOlder() {
    if (!session || !hasMore || loadingOlder) return;
    const oldestServerId = messages
      .map((m) => (m.id.startsWith("srv_") ? m.id.slice(4) : null))
      .find((v): v is string => v !== null);
    if (!oldestServerId) return;
    setLoadingOlder(true);
    try {
      const page = await fetchMessages(session.sessionId, {
        token: session.token,
        before: oldestServerId,
      });
      setMessages((prev) => [...mapHistory(page.messages), ...prev]);
      setHasMore(page.has_more);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingOlder(false);
    }
  }

  function handleLogout() {
    saveStoredSession(null);
    setSession(null);
    setSessions([]);
    setMessages([]);
    setHasMore(false);
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

  /** 实际发送（文本已 trim） */
  async function sendText(text: string) {
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
      await streamChat(session.sessionId, text, { onEvent: (event) => applyEvent(event) }, session.token);
      refreshSessions(session);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      patchLastAssistant((m) => ({ ...m, streaming: false }));
    } finally {
      setBusy(false);
    }
  }

  function handleSend() {
    sendText(input.trim());
  }

  if (restoring) {
    return (
      <div className="login-wrap">
        <p className="sub" style={{ textAlign: "center" }}>
          正在恢复会话…
        </p>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="login-wrap">
        <div className="login-card">
          <div className="brand-mark">
            <BagIcon />
          </div>
          <h1>
            <span className="brand-name">ShopPilot</span>
            <br />
            智能客服助手
          </h1>
          <p className="sub">演示模式：输入用户编号直接进入，免签发 token</p>
          <div className="login-rule">客服工作台 · 演示环境</div>
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
    <div className="app-shell">
      {drawerOpen && <div className="backdrop" onClick={() => setDrawerOpen(false)} />}
      <aside className={`sidebar${drawerOpen ? " open" : ""}`}>
        <div className="sidebar-head">
          <span>会话记录</span>
          <button className="icon-btn close-btn" aria-label="关闭会话列表" onClick={() => setDrawerOpen(false)}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
        <button className="new-session-btn" onClick={handleNewSession} disabled={busy}>
          <PlusIcon />
          新会话
        </button>
        <div className="session-list">
          {sessions.map((s) => (
            <button
              key={s.session_id}
              className={`session-item ${s.session_id === session.sessionId ? "active" : ""}`}
              onClick={() => handleSwitch(s.session_id)}
              disabled={busy}
            >
              会话 {s.session_id.slice(0, 8)}
              <span className="t">{fmtTime(s.last_message_at)}</span>
            </button>
          ))}
          {sessions.length === 0 && <p className="sidebar-hint">暂无历史会话</p>}
        </div>
      </aside>
      <div className="chat-wrap">
        <header>
          <div className="header-left">
            <button className="icon-btn menu-btn" aria-label="打开会话列表" onClick={() => setDrawerOpen(true)}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M3 6h18M3 12h18M3 18h18" />
              </svg>
            </button>
            <span className="logo-sm">
              <BagIcon size={18} />
            </span>
            <span>
              ShopPilot<span className="header-sub"> · 客服助手</span>
            </span>
          </div>
          <div className="session-info">
            <span className="uid">
              <span className="status-dot" aria-label="在线" />
              <span className="label">身份：</span>
              {session.userId}
            </span>
            <button className="link" onClick={handleLogout}>
              退出
            </button>
          </div>
        </header>
        <div className="msg-list" ref={listRef}>
          {hasMore && (
            <button className="older-btn" onClick={loadOlder} disabled={loadingOlder}>
              {loadingOlder ? "加载中…" : "加载更早的消息"}
            </button>
          )}
          {messages.length === 0 && (
            <div className="empty-hint">
              <div className="empty-icon">
                <SparkIcon />
              </div>
              <p>你好，我是本店智能客服</p>
              <p>随时为你查订单、跟进售后</p>
              <div className="suggest-row">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="chip" onClick={() => sendText(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={`bubble-row ${m.role}`}>
              <div className="bubble">
                {m.role === "assistant" && m.tools?.map((t) => <ToolChip key={t.id} tool={t} />)}
                {m.content && <div className="content">{m.content}</div>}
                {m.streaming && !m.content && (m.tools?.length ?? 0) === 0 && (
                  <span className="typing">
                    正在思考<i /><i /><i />
                  </span>
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
          <button className="primary" disabled={busy || !input.trim()} onClick={handleSend} aria-label="发送">
            发送
            <ArrowUpIcon />
          </button>
        </footer>
      </div>
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
    <details className={`tool-chip ${tool.status} ${tool.ok === false ? "fail" : "ok"}`}>
      <summary>
        <span className="tool-dot" aria-hidden="true" />
        <span className="tool-name">{label}</span>
        {tool.status === "running" ? (
          <span className="tool-hint">执行中…</span>
        ) : (
          <span className="tool-hint">{tool.ok ? "完成" : "异常"}</span>
        )}
      </summary>
      <pre>{JSON.stringify(tool.result ?? tool.arguments, null, 2)}</pre>
    </details>
  );
}
