import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import api, {
  clearAuthTokens,
  getAccessToken,
  setAuthTokens,
} from '../services/api';
import type {
  AuthTokens,
  LoginPayload,
  RegisterPayload,
  User,
} from '../types';

export interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => void;
  refreshProfile: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshProfile = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      return;
    }
    const { data } = await api.get<User>('/auth/me');
    setUser(data);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const bootstrap = async () => {
      if (!getAccessToken()) {
        if (!cancelled) {
          setIsLoading(false);
        }
        return;
      }
      try {
        const { data } = await api.get<User>('/auth/me');
        if (!cancelled) {
          setUser(data);
        }
      } catch {
        if (!cancelled) {
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void bootstrap();

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async ({ email, password }: LoginPayload) => {
      // Backend POST /auth/login takes a JSON LoginRequest { email, password }.
      const { data } = await api.post<AuthTokens>('/auth/login', {
        email,
        password,
      });
      setAuthTokens(data);
      await refreshProfile();
    },
    [refreshProfile],
  );

  const register = useCallback(
    async ({ email, password, full_name }: RegisterPayload) => {
      await api.post<User>('/auth/register', { email, password, full_name });
      await login({ email, password });
    },
    [login],
  );

  const logout = useCallback(() => {
    clearAuthTokens();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isLoading, login, register, logout, refreshProfile }),
    [user, isLoading, login, register, logout, refreshProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
