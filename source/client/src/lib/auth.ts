// Access tokens stay in memory; reloading the page requires signing in again.
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

let session: JwtAuthResult | null = null;
let expiryTimer: ReturnType<typeof setTimeout> | undefined;
export function getAuthSession() { return session; }
async function requestAuth(path: string, body?: unknown): Promise<JwtAuthResult> {
  const response = await fetch(`/api/v1/auth/${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Vui lòng kiểm tra thông tin đã nhập.");
  session = data;
  clearTimeout(expiryTimer);
  expiryTimer = setTimeout(() => {
    session = null;
    window.dispatchEvent(new Event("auth-expired"));
  }, data.expires_in * 1000);
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
    clearTimeout(expiryTimer);
    session = null;
  },
};
