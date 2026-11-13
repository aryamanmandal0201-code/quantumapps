import type { NewTask, Task, TaskChanges } from "../types";
import { request } from "./client";

export const listMyTasks = (): Promise<Task[]> => request("/api/tasks");

export const createTask = (task: NewTask): Promise<Task> => request("/api/tasks", { method: "POST", body: task });

export const updateTask = (id: number, changes: TaskChanges): Promise<Task> =>
  request(`/api/tasks/${id}`, { method: "PATCH", body: changes });

export const deleteTask = (id: number): Promise<void> => request(`/api/tasks/${id}`, { method: "DELETE" });
