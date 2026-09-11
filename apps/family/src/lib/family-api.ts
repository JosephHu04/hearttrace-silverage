import type { ActionResult, FamilyAction, FamilyElderList, FamilyToday, LoginResult } from "./types";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

async function request<T>(path: string, token?: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? `请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function demoLogin(actorId: string) {
  return request<LoginResult>("/api/auth/demo-login", undefined, {
    method: "POST",
    body: JSON.stringify({ actorId })
  });
}

export function getFamilyElders(token: string) {
  return request<FamilyElderList>("/api/family/me/elders", token);
}

export function getFamilyToday(token: string, elderId: string) {
  return request<FamilyToday>(`/api/family/elders/${elderId}/today`, token);
}

export function recordFamilyAction(token: string | null, riskEventId: string, action: FamilyAction) {
  return request<ActionResult>(`/api/family/risk-events/${riskEventId}/actions`, token ?? undefined, {
    method: "POST",
    body: JSON.stringify({ requestId: crypto.randomUUID(), action })
  });
}
