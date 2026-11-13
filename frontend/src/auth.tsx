import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import * as authApi from "./api/auth";
import { setUnauthorizedHandler, tokenStore } from "./api/client";
import type { TokenResponse, User } from "./types";

interface AuthContextValue {
  user: User | null;
  checking: boolean;
  login: (email: string, password: string) => Promise<User>;
  signup: (name: string, email: string, password: string) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState<boolean>(Boolean(tokenStore.get()));

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (!tokenStore.get()) return;
    authApi
      .fetchMe()
      .then(setUser)
      .catch((err: unknown) => {
        // Saved token is expired/invalid or the server is unreachable: start again from the login page.
        console.warn("Could not restore session:", err);
        logout();
      })
      .finally(() => setChecking(false));
  }, [logout]);

  const finish = (data: TokenResponse): User => {
    tokenStore.set(data.access_token);
    setUser(data.user);
    return data.user;
  };

  const value: AuthContextValue = {
    user,
    checking,
    logout,
    login: async (email, password) => finish(await authApi.login(email, password)),
    signup: async (name, email, password) => finish(await authApi.signup(name, email, password)),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>.");
  return ctx;
}

/** For pages behind <RequireAuth>, where a user is always present. */
export function useCurrentUser(): User {
  const { user } = useAuth();
  if (!user) throw new Error("useCurrentUser used outside a logged-in route.");
  return user;
}
