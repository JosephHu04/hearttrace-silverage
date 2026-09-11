import type { AuditFilters, AuditListResponse, LoginResult, RiskAction, RiskActionResponse, RiskDetail, RiskListResponse } from "./types";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function demoLogin() {
  return request<LoginResult>("/api/auth/demo-login", {
    method: "POST",
    body: JSON.stringify({ actorId: "staff-admin-001" })
  });
}

export function getRiskQueue(token: string) {
  return request<RiskListResponse>("/api/admin/risk-events?perPage=50", {
    headers: { Authorization: `Bearer ${token}` }
  });
}

export function getRiskDetail(token: string, eventId: string) {
  return request<RiskDetail>(`/api/admin/risk-events/${eventId}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
}

export function performRiskAction(
  token: string,
  eventId: string,
  action: RiskAction,
  expectedVersion: number,
  note?: string
) {
  return request<RiskActionResponse>(`/api/admin/risk-events/${eventId}/actions`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      requestId: crypto.randomUUID(),
      action,
      expectedVersion,
      note: note?.trim() || null
    })
  });
}

export function getAuditLogs(token: string, filters: AuditFilters = {}) {
  const query = new URLSearchParams();
  if (filters.actorId) query.set("actorId", filters.actorId);
  if (filters.action) query.set("action", filters.action);
  if (filters.targetType) query.set("targetType", filters.targetType);
  if (filters.targetId) query.set("targetId", filters.targetId);
  query.set("page", String(filters.page ?? 1));
  query.set("perPage", String(filters.perPage ?? 25));
  return request<AuditListResponse>(`/api/admin/audit-logs?${query.toString()}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
}
