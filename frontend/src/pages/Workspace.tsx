import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../api/client";
import { listMyTasks } from "../api/tasks";
import ChatPanel from "../components/ChatPanel";
import TaskPanel from "../components/TaskPanel";
import type { Task } from "../types";

export default function Workspace() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [flashIds, setFlashIds] = useState<number[]>([]);
  const previous = useRef<Task[] | null>(null);

  const loadTasks = useCallback(async (): Promise<void> => {
    try {
      const data = await listMyTasks();
      // Highlight tasks that are new or changed since the last load, so the agent's edits are easy to spot.
      if (previous.current) {
        const before = new Map(previous.current.map((t) => [t.id, t.updated_at]));
        setFlashIds(data.filter((t) => before.get(t.id) !== t.updated_at).map((t) => t.id));
      }
      previous.current = data;
      setTasks(data);
      setError("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  return (
    <main className="workspace">
      <ChatPanel onTasksChanged={() => void loadTasks()} />
      <TaskPanel tasks={tasks} loading={loading} error={error} flashIds={flashIds} onChanged={loadTasks} />
    </main>
  );
}
