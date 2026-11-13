import type { ChatReply, StoredMessage } from "../types";
import { request } from "./client";

export const sendMessage = (message: string): Promise<ChatReply> =>
  request("/api/chat", { method: "POST", body: { message } });

export const fetchHistory = (): Promise<StoredMessage[]> => request("/api/chat/history");

export const clearHistory = (): Promise<void> => request("/api/chat/history", { method: "DELETE" });
