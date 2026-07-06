import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getToken, setToken, clearToken, listEndpoints, ApiError } from "../api";

interface AuthState {
  status: "checking" | "unauthenticated" | "authenticated";
  error: string | null;
  signIn: (token: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthState["status"]>("checking");
  const [error, setError] = useState<string | null>(null);

  async function trySavedToken() {
    const existing = getToken();
    if (!existing) {
      setStatus("unauthenticated");
      return;
    }
    try {
      await listEndpoints();
      setStatus("authenticated");
    } catch {
      clearToken();
      setStatus("unauthenticated");
    }
  }

  useEffect(() => {
    trySavedToken();
  }, []);

  async function signIn(token: string) {
    setToken(token);
    try {
      await listEndpoints();
      setError(null);
      setStatus("authenticated");
    } catch (err) {
      clearToken();
      setStatus("unauthenticated");
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setError("That token was rejected by the server.");
      } else {
        setError("Could not reach the server — check it's running.");
      }
    }
  }

  function signOut() {
    clearToken();
    setStatus("unauthenticated");
  }

  return (
    <AuthContext.Provider value={{ status, error, signIn, signOut }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
