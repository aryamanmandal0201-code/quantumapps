import type { AdminTask, AdminUser, Role, TaskStatus, User } from "../types";
import { request } from "./client";

export const listUsers = (): Promise<AdminUser[]> => request("/api/admin/users");

export function listAllTasks(filters: { userId?: string; status?: TaskStatus | "" }): Promise<AdminTask[]> {
  const params = new URLSearchParams();
  if (filters.userId) params.set("user_id", filters.userId);
  if (filters.status) params.set("status_filter", filters.status);
  return request(`/api/admin/tasks?${params}`);
}

export const setUserRole = (userId: number, role: Role): Promise<User> =>
  request(`/api/admin/users/${userId}/role`, { method: "PATCH", body: { role } });
