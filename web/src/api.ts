import type { AgentEvent } from "./types";

interface CreateSessionResult {
  session_id: string;
  user_id: string;
  demo_mode: boolean;
}

function authHeaders(token?: string): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseError(resp: Response, fallback: string): Promise<Error> {
  const detail = await resp.json().catch(() => null);
  return new Error(detail?.detail ?? `${fallback}（${resp.status}）`);
}

export async function createSession(opts: {
  userId?: string;
  token?: string;
}): Promise<CreateSessionResult> {
  const body = opts.token ? { token: opts.token } : { user_id: opts.userId };
  const resp = await fetch("/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw await parseError(resp, "创建会话失败");
  return resp.json();
}

export interface SessionSummary {
  session_id: string;
  created_at: string;
  last_message_at: string | null;
}

/** 会话列表，按最近活跃倒序（ADR-0011）。demo 模式传 userId，生产传 token */
export async function listSessions(
  opts: { userId?: string; token?: string; limit?: number } = {}
): Promise<SessionSummary[]> {
  const params = new URLSearchParams();
  if (opts.userId) params.set("user_id", opts.userId);
  if (opts.limit) params.set("limit", String(opts.limit));
  const resp = await fetch(`/sessions?${params.toString()}`, {
    headers: authHeaders(opts.token),
  });
  if (!resp.ok) throw await parseError(resp, "获取会话列表失败");
  const data = (await resp.json()) as { sessions: SessionSummary[] };
  return data.sessions;
}

export interface HistoryMessage {
  id: string;
  role: "user" | "assistant";
  content: string | null;
  created_at: string;
}

export interface MessagePage {
  has_more: boolean;
  messages: HistoryMessage[];
}

/** 历史读回：只含 user/assistant 消息，游标分页（ADR-0011） */
export async function fetchMessages(
  sessionId: string,
  opts: { token?: string; before?: string; limit?: number } = {}
): Promise<MessagePage> {
  const params = new URLSearchParams();
  if (opts.before) params.set("before", opts.before);
  if (opts.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  const resp = await fetch(`/sessions/${sessionId}/messages${qs ? `?${qs}` : ""}`, {
    headers: authHeaders(opts.token),
  });
  if (!resp.ok) throw await parseError(resp, "读取历史消息失败");
  return resp.json();
}

export interface StreamHandlers {
  onEvent: (event: AgentEvent) => void;
}

/** POST /chat 并逐行解析 SSE data 事件 */
export async function streamChat(
  sessionId: string,
  message: string,
  handlers: StreamHandlers,
  token?: string
): Promise<void> {
  const resp = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ session_id: sessionId, message, token }),
  });
  if (!resp.ok || !resp.body) throw await parseError(resp, "对话请求失败");
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (line.startsWith("data: ")) {
        handlers.onEvent(JSON.parse(line.slice(6)) as AgentEvent);
      }
    }
  }
}
