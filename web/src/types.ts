/** SSE 事件（与后端 AgentEvent 对应） */
export interface AgentEvent {
  type: "message.delta" | "tool_call.started" | "tool_call.completed" | "done" | "error";
  content?: string;
  tool_call_id?: string;
  tool_name?: string;
  arguments?: string;
  ok?: boolean;
  result?: unknown;
  error?: string;
  usage?: Record<string, unknown>;
  rounds_used?: number;
}

export interface ToolCallView {
  id: string;
  name: string;
  arguments: string;
  status: "running" | "completed";
  ok?: boolean;
  result?: unknown;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools?: ToolCallView[];
  streaming?: boolean;
}
