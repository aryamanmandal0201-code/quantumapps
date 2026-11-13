// Shapes of the backend's response models (backend/app/schemas.py).

export type Role = "admin" | "user";
export type Priority = "low" | "medium" | "high";
export type TaskStatus = "todo" | "done";

export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Task {
  id: number;
  title: string;
  description: string | null;
  due_date: string | null; // "YYYY-MM-DD"
  priority: Priority;
  status: TaskStatus;
  assigned_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminTask extends Task {
  owner_id: number;
  owner_name: string;
  owner_email: string;
}

export interface AdminUser extends User {
  open_tasks: number;
  done_tasks: number;
}

export interface NewTask {
  title: string;
  due_date: string | null;
}

export type TaskChanges = Partial<Pick<Task, "title" | "description" | "due_date" | "priority" | "status">>;

export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
  ok: boolean;
  summary: string;
}

export interface PendingAction {
  type: "delete_task";
  task_id: number;
  title: string;
}

export interface ChatReply {
  reply: string;
  tool_calls: ToolCall[];
  pending_actions: PendingAction[];
  tasks_changed: boolean;
}

export interface StoredMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  tool_calls: ToolCall[] | null;
  created_at: string;
}
