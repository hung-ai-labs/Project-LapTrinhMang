// Session storage survives reloads in this tab; the server still validates every JWT.
export type AuthUser = { id: string; name: string; email: string };
export type LoginInput = { email: string; password: string };
export type RegisterInput = LoginInput & { name: string };
export type JwtAuthResult = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: AuthUser;
};

// Inject a real implementation into the UI when the backend is ready.
export interface AuthAdapter {
  login(input: LoginInput): Promise<JwtAuthResult>;
  register(input: RegisterInput): Promise<JwtAuthResult>;
  loginWithGoogle(): Promise<JwtAuthResult>;
  logout(): Promise<void>;
}

export function bearerHeaders(accessToken: string): Record<string, string> {
  return { Authorization: `Bearer ${accessToken}` };
}

type StoredSession = { auth: JwtAuthResult; expiresAt: number };
const storageKey = "weather-stream.auth";
let session: JwtAuthResult | null = null;
let expiresAt = 0;
let expiryTimer: ReturnType<typeof setTimeout> | undefined;

function clearSession(notify = false) {
  clearTimeout(expiryTimer);
  session = null;
  expiresAt = 0;
  try { window.sessionStorage.removeItem(storageKey); } catch { /* Storage may be disabled. */ }
  if (notify) window.dispatchEvent(new Event("auth-expired"));
}

function scheduleExpiry() {
  clearTimeout(expiryTimer);
  expiryTimer = setTimeout(() => clearSession(true), Math.max(0, expiresAt - Date.now()));
}

function persistSession() {
  try {
    window.sessionStorage.setItem(storageKey, JSON.stringify({ auth: session, expiresAt }));
  } catch { /* Keep the in-memory session when browser storage is unavailable. */ }
}

function restoreSession() {
  try {
    const raw = window.sessionStorage.getItem(storageKey);
    if (!raw) return;
    const stored: StoredSession = JSON.parse(raw);
    const value = stored.auth;
    if (!Number.isFinite(stored.expiresAt) || stored.expiresAt <= Date.now() ||
        stored.expiresAt - Date.now() > 86400000 ||
        typeof value?.access_token !== "string" || !value.access_token ||
        value.token_type !== "bearer" || typeof value.user?.id !== "string" ||
        typeof value.user?.name !== "string" || typeof value.user?.email !== "string") {
      clearSession();
      return;
    }
    session = value;
    expiresAt = stored.expiresAt;
    scheduleExpiry();
  } catch { clearSession(); }
}
restoreSession();

export function getAuthSession() {
  if (session && Date.now() >= expiresAt) clearSession();
  return session;
}

export async function restoreAuthSession() {
  const saved = getAuthSession();
  if (!saved) return null;
  try {
    const response = await fetch("/api/v1/auth/me", { headers: bearerHeaders(saved.access_token) });
    if (session !== saved) return getAuthSession();
    if (response.status === 401) {
      clearSession(true);
      return null;
    }
    if (!response.ok) return getAuthSession();
    const payload = await response.json();
    if (session === saved && payload.success === true && payload.data?.id === saved.user.id) {
      session = { ...saved, user: payload.data };
      persistSession();
    }
  } catch { /* A temporary outage must not discard an otherwise unexpired session. */ }
  return getAuthSession();
}

async function requestAuth(path: string, body?: unknown): Promise<JwtAuthResult> {
  const response = await fetch(`/api/v1/auth/${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    const message = payload.error?.message ||
      (typeof payload.detail === "string" ? payload.detail : null);
    throw new Error(message || "Không thể xử lý yêu cầu. Vui lòng thử lại sau.");
  }
  if (payload.success !== true || !payload.data?.access_token) {
    throw new Error("Máy chủ đang chạy phiên bản cũ. Vui lòng khởi động lại backend; nếu vừa đăng ký, hãy thử đăng nhập.");
  }
  const data: JwtAuthResult = payload.data;
  session = data;
  expiresAt = Date.now() + data.expires_in * 1000;
  persistSession();
  scheduleExpiry();
  return data;
}
export const auth = {
  login: (input: LoginInput) => requestAuth("login", input),
  register: (input: RegisterInput) => requestAuth("register", input),
  async logout() {
    if (session) {
      const response = await fetch("/api/v1/auth/logout", { method: "POST", headers: bearerHeaders(session.access_token) });
      if (!response.ok && response.status !== 401) throw new Error("Không thể đăng xuất. Vui lòng thử lại.");
    }
    clearSession();
  },
};
