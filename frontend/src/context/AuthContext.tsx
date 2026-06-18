import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import * as api from "../api";
import { clearAuthToken, getAuthToken, setAuthToken } from "../lib/auth";

type AuthState = {
  user: api.AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    securityQuestion: string,
    securityAnswer: string,
    name?: string,
  ) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<api.AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const token = getAuthToken();
    if (!token) {
      setUser(null);
      return;
    }
    try {
      const me = await api.fetchCurrentUser();
      setUser(me);
    } catch {
      clearAuthToken();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    void refreshUser().finally(() => setLoading(false));
  }, [refreshUser]);

  const applyAuth = useCallback((response: api.AuthResponse) => {
    setAuthToken(response.access_token);
    setUser(response.user);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      applyAuth(await api.login(email, password));
    },
    [applyAuth],
  );

  const register = useCallback(
    async (
      email: string,
      password: string,
      securityQuestion: string,
      securityAnswer: string,
      name?: string,
    ) => {
      applyAuth(await api.register(email, password, securityQuestion, securityAnswer, name));
    },
    [applyAuth],
  );

  const loginWithGoogle = useCallback(
    async (idToken: string) => {
      applyAuth(await api.loginWithGoogle(idToken));
    },
    [applyAuth],
  );

  const logout = useCallback(() => {
    clearAuthToken();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, loginWithGoogle, logout, refreshUser }),
    [user, loading, login, register, loginWithGoogle, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
