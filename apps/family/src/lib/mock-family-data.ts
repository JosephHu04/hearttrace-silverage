import type { FamilyToday } from "./types";

export const mockFamilyToday: FamilyToday = {
  elder: {
    id: "elder-demo-001",
    name: "陈奶奶",
    age: 82
  },
  status: {
    level: "yellow",
    label: "需要轻度关怀",
    headline: "陈奶奶今天更适合收到一句不着急的问候。",
    summary: "系统观察到她昨晚提到睡眠不太踏实；今天的交流中也出现了“想家人”的话题。没有发现紧急安全信号。",
    score: 72,
    baselineDelta: -6
  },
  topics: [
    { name: "睡眠与作息", note: "轻度关注", tone: "lavender" },
    { name: "想念家人", note: "建议联系", tone: "peach" },
    { name: "午后晒太阳", note: "正向事件", tone: "mint" }
  ],
  safety: {
    hasActiveEmergency: false,
    message: "暂无紧急安全事件",
    status: null,
    source: null,
    triggeredAt: null
  },
  riskEventId: "risk-demo-001",
  access: {
    scopes: ["daily_summary", "care_actions"],
    careActionsAllowed: true
  },
  recentActions: []
};
