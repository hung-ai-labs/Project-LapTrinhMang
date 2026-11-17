import { bearerHeaders } from "./auth";

export type Conversation = {
  id: string; title: string; created_at: string; updated_at: string;
};
export type Citation = { source_path: string; heading: string; score: number };
export type ChatMessage = {
  id: string; role: "user" | "model"; content: string;
  citations: Citation[]; created_at: string;
};

export type AskHandlers = {
  onDelta(text: string): void;
  onTool(name: string): void;
  onCitations(citations: Citation[]): void;
  onDone(conversationId: string, title: string): void;
  onError(message: string): void;
};

async function authed<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/chat${path}`, {
    ...init,
    headers: { ...bearerHeaders(token), ...(init?.headers ?? {}) },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || body?.success !== true) {
    throw new Error(body?.error?.message || `Không gọi được trợ lý (${response.status}).`);
  }
  return body.data as T;
}

export const listConversations = (token: string) =>
  authed<Conversation[]>(token, "/conversations");

export const loadMessages = (token: string, id: string) =>
  authed<ChatMessage[]>(token, `/conversations/${id}/messages`);

export const removeConversation = (token: string, id: string) =>
  authed<null>(token, `/conversations/${id}`, { method: "DELETE" });

/**
 * Streams one answer. EventSource only speaks GET, so the SSE frames are read off the fetch body
 * and parsed by hand: blocks separated by a blank line, each carrying an `event:` and a `data:`.
 */
export async function ask(
  token: string,
  message: string,
  conversationId: string | null,
  handlers: AskHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch("/api/v1/chat/ask", {
      method: "POST",
      headers: { ...bearerHeaders(token), "Content-Type": "application/json" },
      body: JSON.stringify({ message, conversation_id: conversationId }),
      signal,
    });
  } catch {
    handlers.onError("Không kết nối được máy chủ.");
    return;
  }

  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null);
    handlers.onError(body?.error?.message || `Trợ lý không phản hồi (${response.status}).`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // A frame is complete only once its blank-line terminator has arrived.
      let split = buffer.indexOf("\n\n");
      while (split !== -1) {
        dispatch(buffer.slice(0, split), handlers);
        buffer = buffer.slice(split + 2);
        split = buffer.indexOf("\n\n");
      }
    }
  } catch {
    if (!signal?.aborted) handlers.onError("Mất kết nối khi đang trả lời.");
  }
}

function dispatch(frame: string, handlers: AskHandlers) {
  let event = "message";
  const data: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trim());
  }
  if (!data.length) return;
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(data.join("\n"));
  } catch {
    return;
  }
  if (event === "delta") handlers.onDelta(String(payload.text ?? ""));
  else if (event === "tool") handlers.onTool(String(payload.name ?? ""));
  else if (event === "citations") handlers.onCitations((payload.citations as Citation[]) ?? []);
  else if (event === "done")
    handlers.onDone(String(payload.conversation_id ?? ""), String(payload.title ?? ""));
  else if (event === "error") handlers.onError(String(payload.message ?? "Trợ lý gặp lỗi."));
}

/** Friendly names for the tool chips shown while the model is working. */
export const toolLabels: Record<string, string> = {
  find_ward: "Đang tra địa danh…",
  get_current_weather: "Đang lấy thời tiết hiện tại…",
  get_forecast: "Đang lấy dự báo…",
  get_history: "Đang tra lịch sử quan sát…",
  get_alerts: "Đang kiểm tra ngưỡng cảnh báo…",
  get_detailed_conditions: "Đang lấy UV và chất lượng không khí…",
  search_documents: "Đang tra tài liệu nghiên cứu…",
};
