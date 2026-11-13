import { useState, type FormEvent } from "react";
import { errorMessage } from "../api/client";
import { createTask, deleteTask, updateTask } from "../api/tasks";
import { dueInfo } from "../dates";
import type { Task, TaskStatus } from "../types";
import Segmented from "./Segmented";

type Filter = TaskStatus | "all";

const FILTER_LABELS: Record<Filter, string> = { todo: "Open", done: "Done", all: "All" };
const EMPTY_TEXT: Record<Filter, string> = {
  todo: "No open tasks. Ask the assistant to add one.",
  done: "Nothing finished yet. Tick a task or tell the assistant it’s done.",
  all: "No tasks yet. Ask the assistant to add your first one.",
};

interface RowProps {
  task: Task;
  flash: boolean;
  onChanged: () => Promise<void>;
  onError: (message: string) => void;
}

function TaskRow({ task, flash, onChanged, onError }: RowProps) {
  const [busy, setBusy] = useState(false);
  const done = task.status === "done";
  const due = dueInfo(task.due_date, done);
  const priorityLabel = task.priority.charAt(0).toUpperCase() + task.priority.slice(1);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    try {
      await action();
      await onChanged();
    } catch (err) {
      onError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const toggle = () => run(() => updateTask(task.id, { status: done ? "todo" : "done" }));
  const remove = () => {
    if (window.confirm(`Delete “${task.title}”?`)) void run(() => deleteTask(task.id));
  };

  return (
    <li className={`task prio-${task.priority} ${done ? "is-done" : ""} ${flash ? "flash" : ""}`}>
      <input
        type="checkbox"
        checked={done}
        onChange={() => void toggle()}
        disabled={busy}
        aria-label={done ? `Mark “${task.title}” as not done` : `Mark “${task.title}” as done`}
      />
      <div className="task-body">
        <span className="task-title">{task.title}</span>
        {task.description && <span className="task-desc">{task.description}</span>}
        <span className="task-meta">
          <span className="prio">{priorityLabel} priority</span>
          {due && <span className={`due due-${due.tone}`}>{due.label}</span>}
          {task.assigned_by && <span className="assigned">From {task.assigned_by}</span>}
        </span>
      </div>
      <button className="btn-icon" onClick={remove} disabled={busy} aria-label={`Delete “${task.title}”`} title="Delete">
        ×
      </button>
    </li>
  );
}

function QuickAdd({ onChanged, onError }: Pick<RowProps, "onChanged" | "onError">) {
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [busy, setBusy] = useState(false);

  async function add(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      await createTask({ title: title.trim(), due_date: due || null });
      setTitle("");
      setDue("");
      await onChanged();
    } catch (err) {
      onError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="quick-add" onSubmit={add}>
      <input
        placeholder="Add a task yourself"
        value={title}
        maxLength={200}
        onChange={(e) => setTitle(e.target.value)}
        aria-label="New task title"
      />
      <input type="date" value={due} onChange={(e) => setDue(e.target.value)} aria-label="Due date (optional)" />
      <button className="btn-secondary" disabled={busy || !title.trim()}>Add</button>
    </form>
  );
}

interface TaskPanelProps {
  tasks: Task[];
  loading: boolean;
  error: string;
  flashIds: number[];
  onChanged: () => Promise<void>;
}

export default function TaskPanel({ tasks, loading, error, flashIds, onChanged }: TaskPanelProps) {
  const [filter, setFilter] = useState<Filter>("todo");
  const [actionError, setActionError] = useState("");

  const counts: Record<Filter, number> = {
    todo: tasks.filter((t) => t.status === "todo").length,
    done: tasks.filter((t) => t.status === "done").length,
    all: tasks.length,
  };
  const visible = filter === "all" ? tasks : tasks.filter((t) => t.status === filter);
  const filters: Filter[] = ["todo", "done", "all"];

  return (
    <section className="panel tasks" aria-label="Your tasks">
      <div className="panel-head">
        <h2>Your tasks</h2>
        <Segmented
          label="Filter tasks"
          value={filter}
          onChange={setFilter}
          options={filters.map((id) => ({
            id,
            label: (
              <>
                {FILTER_LABELS[id]} <span className="count">{counts[id]}</span>
              </>
            ),
          }))}
        />
      </div>

      <QuickAdd onChanged={onChanged} onError={setActionError} />
      {(error || actionError) && (
        <p className="form-error" role="alert">
          {error || actionError}{" "}
          {actionError && <button className="btn-link" onClick={() => setActionError("")}>Dismiss</button>}
        </p>
      )}

      {loading ? (
        <p className="muted">Loading tasks…</p>
      ) : visible.length === 0 ? (
        <p className="empty">{EMPTY_TEXT[filter]}</p>
      ) : (
        <ul className="task-list">
          {visible.map((t) => (
            <TaskRow key={t.id} task={t} flash={flashIds.includes(t.id)} onChanged={onChanged} onError={setActionError} />
          ))}
        </ul>
      )}
    </section>
  );
}
