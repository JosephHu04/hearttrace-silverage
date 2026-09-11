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
  };
  riskEventId: string | null;
};

export type FamilyAction = "contacted" | "video_planned" | "referral_requested";

export type ActionResult = {
  status: "recorded";
  action: FamilyAction;
  recordedAt: string;
  duplicate?: boolean;
};

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
