// Proposed API contract. No network requests or token storage are enabled yet.
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
