import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import * as chatApi from "../api/chat";
import { ApiError, errorMessage } from "../api/client";
import { deleteTask } from "../api/tasks";
import { useCurrentUser } from "../auth";
import type { PendingAction, StoredMessage, ToolCall } from "../types";

const USER_EXAMPLES = [
  "Add a task to submit the monthly report by Friday, high priority",
  "What’s due this week?",
  "Mark the report task as done and add a task to start the next one",
];
const ADMIN_EXAMPLES = ["Which users have open tasks?", "Assign “Prepare the audit checklist” to user@taskpilot.demo for Monday"];

type UiMessage =
  | { id: string | number; role: "user"; content: string }
  | { id: string | number; role: "assistant"; content: string; toolCalls: ToolCall[]; pending: PendingAction[] }
  | { id: string; role: "error"; content: string; retry: string };

let localId = 0;
const nextId = (): string => `local-${++localId}`;

function fromStored(m: StoredMessage): UiMessage {
  return m.role === "user"
    ? { id: m.id, role: "user", content: m.content }
    : { id: m.id, role: "assistant", content: m.content, toolCalls: m.tool_calls ?? [], pending: [] };
}

function ToolLog({ calls }: { calls: ToolCall[] }) {
  if (!calls.length) return null;
  return (
    <ul className="tool-log" aria-label="Actions the assistant took">
      {calls.map((c, i) => (
        <li key={i} className={c.ok ? "ok" : "failed"}>
          <span className="tool-mark" aria-hidden="true">{c.ok ? "✓" : "✕"}</span>
          <code>{c.name}</code>
          <span className="tool-summary">{c.summary}</span>
        </li>
      ))}
    </ul>
  );
}

type ConfirmState = "idle" | "busy" | "deleted" | "kept" | "error";

function ConfirmDelete({ action, onResolved }: { action: PendingAction; onResolved: () => void }) {
  const [state, setState] = useState<ConfirmState>("idle");
  const [error, setError] = useState("");

  async function confirm() {
    setState("busy");
    try {
      await deleteTask(action.task_id);
      setState("deleted");
      onResolved();
    } catch (err) {
      setError(err instanceof ApiError && err.status === 404 ? "That task no longer exists." : errorMessage(err));
      setState("error");
    }
  }

  if (state === "deleted") return <p className="confirm-done">Deleted “{action.title}”.</p>;
  if (state === "kept") return <p className="confirm-done">Kept “{action.title}”.</p>;
  return (
    <div className="confirm">
      <p>Delete “{action.title}”? This can’t be undone.</p>
      {state === "error" && <p className="form-error">{error}</p>}
      <div className="confirm-actions">
        <button className="btn-danger" onClick={confirm} disabled={state === "busy"}>
          {state === "busy" ? "Deleting…" : "Delete task"}
        </button>
        <button className="btn-quiet" onClick={() => setState("kept")} disabled={state === "busy"}>
          Keep it
        </button>
      </div>
    </div>
  );
}

export default function ChatPanel({ onTasksChanged }: { onTasksChanged: () => void }) {
  const user = useCurrentUser();
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    chatApi
      .fetchHistory()
      .then((rows) => setMessages(rows.map(fromStored)))
      .catch((err: unknown) => setHistoryError(errorMessage(err)));
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, sending]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || sending) return;
    setInput("");
    setMessages((m) => [...m, { id: nextId(), role: "user", content: message }]);
    setSending(true);
    try {
      const res = await chatApi.sendMessage(message);
      setMessages((m) => [
        ...m,
        { id: nextId(), role: "assistant", content: res.reply, toolCalls: res.tool_calls, pending: res.pending_actions },
      ]);
      if (res.tasks_changed) onTasksChanged();
    } catch (err) {
      setMessages((m) => [...m, { id: nextId(), role: "error", content: errorMessage(err), retry: message }]);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  async function clearChat() {
    if (!window.confirm("Clear the whole conversation? Your tasks are not affected.")) return;
    try {
      await chatApi.clearHistory();
      setMessages([]);
    } catch (err) {
      setHistoryError(errorMessage(err));
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(input);
    }
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    void send(input);
  }

  const examples = user.role === "admin" ? [...USER_EXAMPLES, ...ADMIN_EXAMPLES] : USER_EXAMPLES;

  return (
    <section className="panel chat" aria-label="Assistant">
      <div className="panel-head">
        <h2>Assistant</h2>
        {messages.length > 0 && (
          <button className="btn-quiet" onClick={clearChat}>Clear chat</button>
        )}
      </div>

      <div className="chat-scroll" ref={scrollRef} aria-live="polite">
        {historyError && <p className="form-error">{historyError}</p>}
        {messages.length === 0 && !historyError && (
          <div className="chat-empty">
            <p>Ask in plain words. Try one of these:</p>
            <div className="examples">
              {examples.map((ex) => (
                <button key={ex} className="example" onClick={() => void send(ex)} disabled={sending}>
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => {
          if (m.role === "user") return <div key={m.id} className="msg msg-user">{m.content}</div>;
          if (m.role === "error") {
            return (
              <div key={m.id} className="msg msg-error" role="alert">
                <p>{m.content}</p>
                <button className="btn-quiet" onClick={() => void send(m.retry)} disabled={sending}>Try again</button>
              </div>
            );
          }
          return (
            <div key={m.id} className="msg msg-bot">
              <p>{m.content}</p>
              <ToolLog calls={m.toolCalls} />
              {m.pending.map((a) => (
                <ConfirmDelete key={a.task_id} action={a} onResolved={onTasksChanged} />
              ))}
            </div>
          );
        })}
        {sending && (
          <div className="msg msg-bot thinking" aria-label="Assistant is working">
            <span /><span /><span />
          </div>
        )}
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <textarea
          ref={inputRef}
          rows={2}
          maxLength={1000}
          placeholder="e.g. Move the insurance renewal to next Monday"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          aria-label="Message the assistant"
        />
        <button className="btn-primary" disabled={sending || !input.trim()}>Send</button>
      </form>
    </section>
  );
}
