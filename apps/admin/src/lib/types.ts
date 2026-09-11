export type RiskLevel = "green" | "yellow" | "orange" | "red";
export type RiskStatus =
  | "new"
  | "assigned"
  | "reviewing"
  | "action_required"
  | "escalated"
  | "resolved"
  | "false_positive"
  | "closed";

export type RiskAction =
  | "claim"
  | "begin_review"
  | "request_action"
  | "escalate"
  | "resolve"
  | "mark_false_positive"
  | "close"
  | "reopen";

export type Actor = {
  id: string;
  displayName: string;
  role: "admin" | "professional";
};

export type LoginResult = {
  accessToken: string;
  tokenType: "bearer";
  expiresAt: string;
  actor: Actor;
};

export type RiskListItem = {
  id: string;
  elderId: string;
  elderName: string;
  level: RiskLevel;
  status: RiskStatus;
  title: string;
  assigneeId: string | null;
  slaDueAt: string | null;
  version: number;
  createdAt: string;
  updatedAt: string;
};

export type RiskEvidence = {
  id: string;
  sourceType: "trend" | "screening" | "model_signal" | string;
  label: string;
  detail: string;
  evidenceRef: string;
  recordedAt: string;
};

export type RiskActionRecord = {
  id: string;
  requestId: string;
  actorId: string;
  action: RiskAction;
  note: string | null;
  fromStatus: RiskStatus;
  toStatus: RiskStatus;
  eventVersion: number;
  createdAt: string;
};

export type RiskDetail = RiskListItem & {
  summary: string;
  modelVersion: string | null;
  ruleVersion: string;
  evidence: RiskEvidence[];
  actions: RiskActionRecord[];
};

export type RiskListResponse = {
  items: RiskListItem[];
  page: number;
  perPage: number;
  total: number;
};

export type RiskActionResponse = {
  event: RiskDetail;
  action: RiskActionRecord;
  duplicate: boolean;
};

export type AuditLogItem = {
  id: string;
  actorId: string;
  actorDisplayName: string | null;
  action: string;
  targetType: string;
  targetId: string;
  metadata: Record<string, unknown>;
  createdAt: string;
};

export type AuditListResponse = {
  items: AuditLogItem[];
  page: number;
  perPage: number;
  total: number;
};

export type AuditFilters = {
  actorId?: string;
  action?: string;
  targetType?: string;
  targetId?: string;
  page?: number;
  perPage?: number;
};
