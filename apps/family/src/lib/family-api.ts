import type { ActionResult, FamilyAction, FamilyToday } from "./types";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getFamilyToday(elderId: string) {
  return request<FamilyToday>(`/api/family/elders/${elderId}/today`);
}

export function recordFamilyAction(riskEventId: string, action: FamilyAction) {
  return request<ActionResult>(`/api/family/risk-events/${riskEventId}/actions`, {
    method: "POST",
    body: JSON.stringify({ action })
  });
}
