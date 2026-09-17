import type { ActionResult, AuthMessage, FamilyAction, FamilyCarePlanItem, FamilyElderList, FamilyToday, FamilyTrend, LoginResult, NotificationList, NotificationReadResult, RegistrationApplication, RegistrationApplicationStatus } from "./types";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

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
    throw new ApiError(body?.detail ?? `请求失败：${response.status}`, response.status);
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

export function getFamilyTrend(token: string, elderId: string, days: 7 | 30) {
  return request<FamilyTrend>(`/api/family/elders/${elderId}/trend?days=${days}`, token);
}

export function getFamilyCarePlan(token: string, elderId: string) {
  return request<FamilyCarePlanItem[]>(`/api/family/elders/${elderId}/care-plan`, token);
}

export function createFamilyCarePlanItem(token: string, elderId: string, title: string, scheduledFor?: string) {
  return request<FamilyCarePlanItem>(`/api/family/elders/${elderId}/care-plan`, token, {
    method: "POST",
    body: JSON.stringify({ title, ...(scheduledFor ? { scheduledFor } : {}) })
  });
}

export function completeFamilyCarePlanItem(token: string, elderId: string, itemId: string) {
  return request<FamilyCarePlanItem>(`/api/family/elders/${elderId}/care-plan/${itemId}/complete`, token, {
    method: "POST"
  });
}

export function getNotifications(token: string) {
  return request<NotificationList>("/api/notifications/me?perPage=25", token);
}

export function markNotificationRead(token: string, notificationId: string) {
  return request<NotificationReadResult>(`/api/notifications/${notificationId}/read`, token, {
    method: "POST"
  });
}

export function recordFamilyAction(token: string, elderId: string, riskEventId: string | null, action: FamilyAction, requestId: string) {
  const path = riskEventId ? `/api/family/risk-events/${riskEventId}/actions` : `/api/family/elders/${elderId}/actions`;
  return request<ActionResult>(path, token, {
    method: "POST",
    body: JSON.stringify({ requestId, action })
  });
}

export function createRegistrationApplication(body: {
  displayName: string;
  loginIdentifier: string;
  relationship: string;
  elderName: string;
  password: string;
  consentVersion: string;
}) {
  return request<RegistrationApplication>("/api/auth/registration-applications", undefined, {
    method: "POST",
    body: JSON.stringify(body)
  });
}

export function getRegistrationApplication(applicationId: string) {
  return request<RegistrationApplicationStatus>(`/api/auth/registration-applications/${applicationId}`);
}

export function loginWithPassword(loginIdentifier: string, password: string) {
  return request<LoginResult>("/api/auth/login", undefined, {
    method: "POST",
    body: JSON.stringify({ loginIdentifier, password })
  });
}

export function changePassword(token: string, currentPassword: string, newPassword: string) {
  return request<AuthMessage>("/api/auth/password/change", token, {
    method: "POST",
    body: JSON.stringify({ currentPassword, newPassword })
  });
}

export function requestPasswordRecovery(loginIdentifier: string) {
  return request<AuthMessage>("/api/auth/password-recovery", undefined, {
    method: "POST",
    body: JSON.stringify({ loginIdentifier })
  });
}

export function confirmPasswordRecovery(token: string, newPassword: string) {
  return request<AuthMessage>("/api/auth/password-recovery/confirm", undefined, {
    method: "POST",
    body: JSON.stringify({ token, newPassword })
  });
}
