import type { TokenResponse, User } from "../types";
import { request } from "./client";

export const login = (email: string, password: string): Promise<TokenResponse> =>
  request("/api/auth/login", { method: "POST", form: { username: email, password } });

export const signup = (name: string, email: string, password: string): Promise<TokenResponse> =>
  request("/api/auth/signup", { method: "POST", body: { name, email, password } });

export const fetchMe = (): Promise<User> => request("/api/auth/me");
