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
  };
  topics: Topic[];
  dailyCheckIn: {
    moodLabel: string;
    description: string;
    recordedAt: string;
    source: "self_report";
  };
  screenings: Array<{
    instrument: "PHQ-9" | "GAD-7" | "AD8";
    label: string;
    status: "not_started" | "completed" | "follow_up";
    familyVisibility: "authorized_summary" | "not_authorized";
  }>;
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
