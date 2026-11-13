// Low-level HTTP client: adds the token, turns errors into readable messages,
// and tells the UI when a request is slow (free backends sleep when idle).
// UI code never calls this directly; it uses the typed functions in the other api/ modules.

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const TOKEN_KEY = "taskpilot_token";
const SLOW_AFTER_MS = 6000;
const TIMEOUT_MS = 90000;

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string): void => localStorage.setItem(TOKEN_KEY, token),
  clear: (): void => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** A readable message for anything thrown by an API call. */
export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Something went wrong. Please try again.";
}

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

// Number of requests currently running longer than SLOW_AFTER_MS, shared with any listener.
let slowCount = 0;
const slowListeners = new Set<(slow: boolean) => void>();
export function subscribeSlow(listener: (slow: boolean) => void): () => void {
  slowListeners.add(listener);
  return () => {
    slowListeners.delete(listener);
  };
}
function changeSlow(delta: number): void {
  slowCount = Math.max(0, slowCount + delta);
  slowListeners.forEach((listener) => listener(slowCount > 0));
}

function messageFrom(data: unknown, status: number): string {
  const detail = typeof data === "object" && data !== null && "detail" in data ? data.detail : undefined;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    // FastAPI validation errors: [{ msg: "..." }, ...]
    return detail
      .map((d: unknown) => (typeof d === "object" && d !== null && "msg" in d ? String(d.msg) : ""))
      .map((msg) => msg.replace(/^Value error, /, ""))
      .join(" ");
  }
  if (status >= 500) return "Something went wrong on the server. Please try again.";
  return `Request failed (${status}).`;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  form?: Record<string, string>;
}

export async function request<T>(path: string, { method = "GET", body, form }: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let payload: string | undefined;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(form).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;

  const controller = new AbortController();
  let markedSlow = false;
  const slowTimer = setTimeout(() => {
    markedSlow = true;
    changeSlow(1);
  }, SLOW_AFTER_MS);
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(BASE + path, { method, headers, body: payload, signal: controller.signal });
  } catch (err) {
    const aborted = err instanceof DOMException && err.name === "AbortError";
    throw new ApiError(
      aborted
        ? "The server took too long to respond. Please try again."
        : "Can't reach the server. Check your connection, or wait a minute if it's waking up.",
      0
    );
  } finally {
    clearTimeout(slowTimer);
    clearTimeout(timeout);
    if (markedSlow) changeSlow(-1);
  }

  // 204 responses have no body; those endpoints are typed as Promise<void>.
  if (res.status === 204) return undefined as T;

  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    // Not JSON (e.g. a proxy error page). Fall through: the status code produces the message below.
    data = null;
  }
  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized();
    throw new ApiError(messageFrom(data, res.status), res.status);
  }
  // Trust boundary: the backend validates every response against its response_model,
  // and types.ts mirrors those schemas.
  return data as T;
}
