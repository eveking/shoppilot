import type { AgentEvent } from "./types";

interface CreateSessionResult {
  session_id: string;
  user_id: string;
  demo_mode: boolean;
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
  if (!resp.ok) {
    const detail = await resp.json().catch(() => null);
    throw new Error(detail?.detail ?? `创建会话失败（${resp.status}）`);
  }
  return resp.json();
}

export interface StreamHandlers {
  onEvent: (event: AgentEvent) => void;
}

/** POST /chat 并逐行解析 SSE data 事件 */
export async function streamChat(
  sessionId: string,
  message: string,
  handlers: StreamHandlers
): Promise<void> {
  const resp = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!resp.ok || !resp.body) {
    const detail = await resp.json().catch(() => null);
    throw new Error(detail?.detail ?? `对话请求失败（${resp.status}）`);
  }
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
