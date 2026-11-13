import { useCallback, useEffect, useState } from "react";
import * as adminApi from "../api/admin";
import { errorMessage } from "../api/client";
import { useCurrentUser } from "../auth";
import Segmented from "../components/Segmented";
import { dueInfo, shortDate } from "../dates";
import type { AdminTask, AdminUser, Role, TaskStatus, User } from "../types";

type Tab = "users" | "tasks";

interface UsersTableProps {
  users: AdminUser[];
  me: User;
  onRoleChange: (user: AdminUser, role: Role) => void;
  busyId: number | null;
}

function UsersTable({ users, me, onRoleChange, busyId }: UsersTableProps) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
            <th className="num">Open</th>
            <th className="num">Done</th>
            <th>Joined</th>
            <th><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.name}</td>
              <td>{u.email}</td>
              <td><span className={`role-badge role-${u.role}`}>{u.role === "admin" ? "Admin" : "User"}</span></td>
              <td className="num">{u.open_tasks}</td>
              <td className="num">{u.done_tasks}</td>
              <td>{shortDate(u.created_at)}</td>
              <td className="actions">
                {u.id === me.id ? (
                  <span className="muted">You</span>
                ) : (
                  <button
                    className="btn-quiet"
                    disabled={busyId === u.id}
                    onClick={() => onRoleChange(u, u.role === "admin" ? "user" : "admin")}
                  >
                    {u.role === "admin" ? "Make user" : "Make admin"}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TasksTable({ tasks }: { tasks: AdminTask[] }) {
  if (!tasks.length) return <p className="empty">No tasks match this filter.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Task</th>
            <th>Owner</th>
            <th>Priority</th>
            <th>Due</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => {
            const due = dueInfo(t.due_date, t.status === "done");
            return (
              <tr key={t.id} className={t.status === "done" ? "row-done" : ""}>
                <td>
                  {t.title}
                  {t.assigned_by && <span className="assigned"> (from {t.assigned_by})</span>}
                </td>
                <td>{t.owner_name}<br /><span className="muted small">{t.owner_email}</span></td>
                <td><span className={`prio-tag prio-${t.priority}`}>{t.priority}</span></td>
                <td>{due ? <span className={`due due-${due.tone}`}>{due.label.replace("Due ", "")}</span> : <span className="muted">None</span>}</td>
                <td>{t.status === "done" ? "Done" : "Open"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function AdminPage() {
  const me = useCurrentUser();
  const [tab, setTab] = useState<Tab>("users");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [tasks, setTasks] = useState<AdminTask[]>([]);
  const [ownerFilter, setOwnerFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<TaskStatus | "">("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async (): Promise<void> => {
    setError("");
    try {
      const [u, t] = await Promise.all([
        adminApi.listUsers(),
        adminApi.listAllTasks({ userId: ownerFilter, status: statusFilter }),
      ]);
      setUsers(u);
      setTasks(t);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [ownerFilter, statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function changeRole(user: AdminUser, role: Role) {
    const verb = role === "admin" ? "give admin access to" : "remove admin access from";
    if (!window.confirm(`Do you want to ${verb} ${user.name}?`)) return;
    setBusyId(user.id);
    try {
      await adminApi.setUserRole(user.id, role);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  const totalOpen = users.reduce((n, u) => n + u.open_tasks, 0);
  const totalDone = users.reduce((n, u) => n + u.done_tasks, 0);

  return (
    <main className="admin">
      <div className="admin-head">
        <h1>Admin</h1>
        <p className="muted">
          {users.length} users, {totalOpen} open tasks, {totalDone} done
        </p>
      </div>

      <Segmented
        label="Admin sections"
        value={tab}
        onChange={setTab}
        options={[
          { id: "users", label: "Users" },
          { id: "tasks", label: "All tasks" },
        ]}
      />

      {error && <p className="form-error" role="alert">{error}</p>}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : tab === "users" ? (
        <UsersTable users={users} me={me} onRoleChange={(u, role) => void changeRole(u, role)} busyId={busyId} />
      ) : (
        <>
          <div className="filters">
            <label>
              Owner
              <select value={ownerFilter} onChange={(e) => setOwnerFilter(e.target.value)}>
                <option value="">Everyone</option>
                {users.map((u) => (
                  <option key={u.id} value={String(u.id)}>{u.name}</option>
                ))}
              </select>
            </label>
            <label>
              Status
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as TaskStatus | "")}>
                <option value="">Any</option>
                <option value="todo">Open</option>
                <option value="done">Done</option>
              </select>
            </label>
          </div>
          <TasksTable tasks={tasks} />
        </>
      )}
    </main>
  );
}
