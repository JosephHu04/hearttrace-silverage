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
};

export type FamilyAction = "contacted" | "video_planned" | "referral_requested";

export type ActionResult = {
  status: "recorded";
  action: FamilyAction;
  recordedAt: string;
};
