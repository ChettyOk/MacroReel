const TOKEN_KEY = "macroreel-auth-token";

export function getAuthToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAuthToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearAuthToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}
