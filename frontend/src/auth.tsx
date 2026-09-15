import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Navigate } from "react-router-dom";
import { fetchMe, requestLogout, type AuthUser } from "./api";

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setUser(await fetchMe());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backend unreachable");
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    await requestLogout();
    setUser(null);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({ user, loading, error, refresh, logout }),
    [user, loading, error, refresh, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading, error } = useAuth();
  if (loading) {
    return <p className="p-8 text-sm text-slate-500">Checking session…</p>;
  }
  if (error) {
    return (
      <p className="p-8 text-sm text-red-600" role="alert">
        Backend unreachable: {error}
      </p>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
