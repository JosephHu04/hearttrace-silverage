import type { LoginResult } from "./types";

export const ADMIN_SESSION_KEY = "hearttrace.admin.session";

export type AdminSession = Pick<LoginResult, "accessToken" | "expiresAt" | "actor">;

export function saveAdminSession(result: LoginResult): void {
  sessionStorage.setItem(ADMIN_SESSION_KEY, JSON.stringify({
    accessToken: result.accessToken,
    expiresAt: result.expiresAt,
    actor: result.actor
  } satisfies AdminSession));
}

export function clearAdminSession(): void {
  sessionStorage.removeItem(ADMIN_SESSION_KEY);
}

export function readAdminSession(): AdminSession | null {
  try {
    const raw = sessionStorage.getItem(ADMIN_SESSION_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<AdminSession>;
    if (!value.accessToken || !value.actor?.id || value.actor.role !== "admin" || !value.expiresAt || Date.parse(value.expiresAt) <= Date.now()) {
      clearAdminSession();
      return null;
    }
    return value as AdminSession;
  } catch {
    clearAdminSession();
    return null;
  }
}
