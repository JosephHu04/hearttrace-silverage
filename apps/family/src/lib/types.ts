export type ConcernLevel = "green" | "yellow" | "orange" | "red";

export type Topic = {
  name: string;
  note: string;
  tone: "lavender" | "peach" | "mint";
};

export type FamilyToday = {
  elder: {
    id: string;
    name: string;
    age: number;
  };
  status: {
    level: ConcernLevel;
    label: string;
    headline: string;
    summary: string;
    score: number;
    baselineDelta: number;
  };
  topics: Topic[];
  safety: {
    hasActiveEmergency: boolean;
    message: string;
    status: "open" | "acknowledged" | "resolved" | "cancelled" | null;
    source: "elder_button" | "device_button" | null;
    triggeredAt: string | null;
  };
  riskEventId: string | null;
  access: {
    scopes: string[];
    careActionsAllowed: boolean;
  };
  recentActions: Array<{
    action: FamilyAction;
    recordedAt: string;
  }>;
};

export type FamilyAction = "contacted" | "video_planned" | "referral_requested";

export type ActionResult = {
  status: "recorded";
  action: FamilyAction;
  recordedAt: string;
  duplicate?: boolean;
};

export type RegistrationStatus = "pending" | "approved" | "rejected";

export type RegistrationApplication = {
  id: string;
  displayName: string;
  loginIdentifier: string;
  relationship: string;
  elderName: string;
  consentVersion: string;
  status: RegistrationStatus;
  reviewNote: string | null;
  reviewedAt: string | null;
  createdAt: string;
};

export type AuthMessage = { message: string };

export type LoginResult = {
  accessToken: string;
  tokenType: "bearer";
  expiresAt: string;
  actor: { id: string; displayName: string; role: "family" };
};

export type FamilyElder = {
  id: string;
  name: string;
  age: number;
  authorizationStatus: "active";
};

export type FamilyElderList = { items: FamilyElder[] };
