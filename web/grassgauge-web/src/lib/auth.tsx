import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, getToken, LOGOUT_EVENT, LEGACY_LOGOUT_EVENT, type LoginResponse } from './api';

interface AuthState {
  token: string | null;
  user: Pick<LoginResponse, 'id' | 'nombre' | 'email'> | null;
  login: (email: string, password: string) => Promise<void>;
  registro: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

const USER_KEY = 'grassgauge_user';
// Clave anterior (ForageMap): se lee una vez para migrar la sesión existente.
const LEGACY_USER_KEY = 'foragemap_user';

function loadUser(): AuthState['user'] {
  try {
    const raw = localStorage.getItem(USER_KEY) ?? localStorage.getItem(LEGACY_USER_KEY);
    if (raw && !localStorage.getItem(USER_KEY)) {
      // Migración automática a la nueva key.
      localStorage.setItem(USER_KEY, raw);
      localStorage.removeItem(LEGACY_USER_KEY);
    }
    return raw ? (JSON.parse(raw) as AuthState['user']) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const [user, setUser] = useState<AuthState['user']>(() => loadUser());

  const login = useCallback(async (email: string, password: string) => {
    const data = await api.login(email.trim(), password);
    setTokenState(data.access_token);
    const u = { id: data.id, nombre: data.nombre, email: data.email };
    setUser(u);
    localStorage.setItem(USER_KEY, JSON.stringify(u));
    localStorage.removeItem(LEGACY_USER_KEY);
  }, []);

  const registro = useCallback(async (email: string, password: string) => {
    await api.registro(email.trim(), password);
    // Registro no devuelve token: encadenar login automático.
    await login(email, password);
  }, [login]);

  const logout = useCallback(() => {
    api.logout();
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(LEGACY_USER_KEY);
    setTokenState(null);
    setUser(null);
  }, []);

  // Un 401 en cualquier request (token vencido/revocado) cierra la sesión
  // en el contexto también, no solo en localStorage (evita sesión zombie).
  useEffect(() => {
    window.addEventListener(LOGOUT_EVENT, logout);
    window.addEventListener(LEGACY_LOGOUT_EVENT, logout);
    return () => {
      window.removeEventListener(LOGOUT_EVENT, logout);
      window.removeEventListener(LEGACY_LOGOUT_EVENT, logout);
    };
  }, [logout]);

  const value = useMemo(() => ({ token, user, login, registro, logout }), [token, user, login, registro, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>');
  return ctx;
}
