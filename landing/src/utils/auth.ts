// Base de la API: mismo-origen por defecto (usa el proxy /api de Astro,
// funciona en local y detrás de túneles/dominios). Solo definir
// PUBLIC_GRASSGAUGE_API_URL si el front y la API van en orígenes distintos.
const API_BASE =
  import.meta.env.PUBLIC_GRASSGAUGE_API_URL ??
  import.meta.env.PUBLIC_FORAGEMAP_API_URL ?? '';

const TOKEN_KEY = 'grassgauge_token';
const USER_KEY = 'grassgauge_user';
// Claves anteriores (ForageMap): se leen una vez para migrar la sesión existente.
const LEGACY_TOKEN_KEY = 'foragemap_token';
const LEGACY_USER_KEY = 'foragemap_user';

interface Session {
  userId: number;
  email: string;
  name: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  id: number;
  nombre: string;
  email: string;
}

function apiUrl(path: string): string {
  if (!API_BASE) return path; // mismo-origen: /api/... via proxy Astro
  return `${API_BASE.replace(/\/$/, '')}${path}`;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error('No se pudo conectar con el servidor. Verificá tu conexión.');
  }
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      const data = await res.json();
      if (typeof data?.detail === 'string') detail = data.detail;
    } catch {
      /* cuerpo no JSON */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

function validarCredenciales(
  email: string,
  password: string
): { email: string } | { error: string } {
  const cleanEmail = email.trim().toLowerCase();
  if (!cleanEmail || !cleanEmail.includes('@') || !cleanEmail.includes('.')) {
    return { error: 'Ingresá un correo electrónico válido' };
  }
  if (cleanEmail.length > 100) {
    return { error: 'Email demasiado largo (máx. 100)' };
  }
  if (!password || password.length < 6) {
    return { error: 'La contraseña debe tener al menos 6 caracteres' };
  }
  if (new TextEncoder().encode(password).length > 72) {
    return { error: 'Contraseña demasiado larga (máx. 72 bytes)' };
  }
  return { email: cleanEmail };
}

function saveAuth(data: LoginResponse): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
  const session: Session = {
    userId: data.id,
    email: data.email,
    name: data.nombre,
  };
  localStorage.setItem(USER_KEY, JSON.stringify(session));
  localStorage.removeItem(LEGACY_USER_KEY);
}

export async function register(
  email: string,
  password: string
): Promise<{ success: boolean; error?: string }> {
  const valid = validarCredenciales(email, password);
  if ('error' in valid) return { success: false, error: valid.error };

  try {
    // El registro no devuelve token: encadenar login automático.
    await postJson('/api/auth/registro', { email: valid.email, password });
    return await login(valid.email, password);
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : 'Error al registrarse',
    };
  }
}

export async function login(
  email: string,
  password: string
): Promise<{ success: boolean; error?: string }> {
  const valid = validarCredenciales(email, password);
  if ('error' in valid) return { success: false, error: valid.error };

  try {
    const data = await postJson<LoginResponse>('/api/auth/login', {
      email: valid.email,
      password,
    });
    saveAuth(data);
    return { success: true };
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Error al iniciar sesión';
    // Mensajes 401 del backend a lenguaje de producto
    if (message === 'Email no existe' || message === 'Contraseña incorrecta') {
      return { success: false, error: 'Credenciales incorrectas. Verifica tu correo y contraseña.' };
    }
    return { success: false, error: message };
  }
}

export function logout(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
  localStorage.removeItem(LEGACY_USER_KEY);
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  const token = localStorage.getItem(TOKEN_KEY) ?? localStorage.getItem(LEGACY_TOKEN_KEY);
  if (token && !localStorage.getItem(TOKEN_KEY)) {
    // Migración automática a la nueva key.
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
  }
  return token;
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

export function getCurrentUser(): Session | null {
  if (typeof window === 'undefined') return null;
  try {
    const data = localStorage.getItem(USER_KEY) ?? localStorage.getItem(LEGACY_USER_KEY);
    if (data && !localStorage.getItem(USER_KEY)) {
      // Migración automática a la nueva key.
      localStorage.setItem(USER_KEY, data);
      localStorage.removeItem(LEGACY_USER_KEY);
    }
    return data ? (JSON.parse(data) as Session) : null;
  } catch {
    return null;
  }
}

/** Valida el token contra la API (detecta expirados/revocados). */
export async function validateSession(): Promise<boolean> {
  const token = getToken();
  if (!token) return false;
  try {
    const res = await fetch(apiUrl('/api/potreros'), {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401) {
      logout();
      return false;
    }
    return res.ok;
  } catch {
    // Sin conexión: no invalidar la sesión local
    return true;
  }
}
