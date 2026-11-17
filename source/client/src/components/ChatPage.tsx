import { useCallback, useEffect, useRef, useState } from "react";
import {
  ask, listConversations, loadMessages, removeConversation, toolLabels,
  type ChatMessage, type Citation, type Conversation,
} from "../lib/chat";
import "./chat.css";

const time = (value: string) => new Date(value).toLocaleTimeString("vi-VN", {
  timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", minute: "2-digit",
});

export default function ChatPage({ token }: { token: string }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState("");
  const [tool, setTool] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);

  const refreshList = useCallback(() => {
    listConversations(token).then(setConversations).catch(() => { /* Keep the current list. */ });
  }, [token]);

  useEffect(refreshList, [refreshList]);

  // Abort any in-flight answer when the page goes away, so no state lands on an unmounted tree.
  useEffect(() => () => abort.current?.abort(), []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streaming, tool]);

  const open = async (id: string) => {
    if (busy) return;
    setActiveId(id);
    setError("");
    setStreaming("");
    setCitations([]);
    try {
      setMessages(await loadMessages(token, id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được đoạn chat.");
    }
  };

  const startNew = () => {
    if (busy) return;
    setActiveId(null);
    setMessages([]);
    setStreaming("");
    setCitations([]);
    setError("");
  };

  const discard = async (id: string) => {
    if (busy) return;
    try {
      await removeConversation(token, id);
      if (id === activeId) startNew();
      refreshList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không xoá được đoạn chat.");
    }
  };

  const send = async () => {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    setError("");
    setCitations([]);
    setStreaming("");
    setBusy(true);
    // Shown immediately; the server stores its own copy as part of the same request.
    setMessages(current => [...current, {
      id: `local-${Date.now()}`, role: "user", content: text,
      citations: [], created_at: new Date().toISOString(),
    }]);

    const controller = new AbortController();
    abort.current = controller;
    let answer = "";
    let sources: Citation[] = [];
    await ask(token, text, activeId, {
      onDelta: chunk => { answer += chunk; setStreaming(answer); setTool(""); },
      onTool: name => setTool(toolLabels[name] ?? "Đang lấy dữ liệu…"),
      onCitations: list => { sources = list; setCitations(list); },
      onDone: (conversationId) => {
        setActiveId(conversationId);
        setMessages(current => [...current, {
          id: `done-${Date.now()}`, role: "model", content: answer,
          citations: sources, created_at: new Date().toISOString(),
        }]);
        setStreaming("");
        refreshList();
      },
      onError: message => setError(message),
    }, controller.signal);
    setTool("");
    setBusy(false);
  };

  return <div className="chat-layout">
    <aside className="glass chat-threads">
      <button type="button" className="chat-new" onClick={startNew} disabled={busy}>
        + Đoạn chat mới
      </button>
      {!conversations.length && <p className="chat-empty">Chưa có đoạn chat nào.</p>}
      <ul>
        {conversations.map(item => <li key={item.id}>
          <button type="button" className={item.id === activeId ? "active" : ""}
            onClick={() => open(item.id)} disabled={busy}>
            <span>{item.title}</span>
            <small>{time(item.updated_at)}</small>
          </button>
          <button type="button" className="chat-delete" aria-label={`Xoá ${item.title}`}
            onClick={() => discard(item.id)} disabled={busy}>×</button>
        </li>)}
      </ul>
    </aside>

    <section className="glass chat-main" aria-live="polite">
      <div className="chat-log">
        {!messages.length && !streaming && <div className="chat-intro">
          <h2>Trợ lý thời tiết</h2>
          <p>Hỏi thời tiết một địa điểm, hoặc hỏi về các báo cáo nghiên cứu của dự án.</p>
          <ul>
            <li>Thời tiết ở Hà Nội bây giờ thế nào?</li>
            <li>Mai trời mưa không, tôi có cần mang ô?</li>
            <li>Model dự báo ngập của nhóm cho kết quả ra sao?</li>
          </ul>
        </div>}

        {messages.map(message => <article key={message.id} className={`chat-bubble ${message.role}`}>
          <p>{message.content}</p>
          {message.citations?.length > 0 && <footer className="chat-sources">
            <strong>Nguồn:</strong>
            {message.citations.map((c, i) => <span key={`${c.source_path}-${i}`}>
              {c.source_path}{c.heading ? ` · ${c.heading}` : ""}
            </span>)}
          </footer>}
        </article>)}

        {streaming && <article className="chat-bubble model">
          <p>{streaming}<span className="chat-caret" aria-hidden="true" /></p>
          {citations.length > 0 && <footer className="chat-sources">
            <strong>Nguồn:</strong>
            {citations.map((c, i) => <span key={`${c.source_path}-${i}`}>
              {c.source_path}{c.heading ? ` · ${c.heading}` : ""}
            </span>)}
          </footer>}
        </article>}

        {tool && <p className="chat-tool" role="status">{tool}</p>}
        {busy && !streaming && !tool && <p className="chat-tool" role="status">Đang suy nghĩ…</p>}
        {error && <p className="chat-error" role="alert">{error}</p>}
        <div ref={bottom} />
      </div>

      <form className="chat-input" onSubmit={event => { event.preventDefault(); send(); }}>
        <textarea value={draft} onChange={event => setDraft(event.target.value)} rows={2}
          placeholder="Hỏi về thời tiết hoặc nghiên cứu của dự án…" disabled={busy}
          onKeyDown={event => {
            // Enter sends, Shift+Enter keeps writing.
            if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); }
          }} />
        <button type="submit" disabled={busy || !draft.trim()}>
          {busy ? "Đang trả lời…" : "Gửi"}
        </button>
      </form>
      <small className="chat-note">
        Câu trả lời do Gemini sinh ra từ dữ liệu Open-Meteo và tài liệu trong repo. Hãy tự kiểm chứng
        trước khi dùng cho quyết định quan trọng.
      </small>
    </section>
  </div>;
}
