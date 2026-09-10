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
    summary: "系统观察到她昨晚提到睡眠不太踏实；今天的交流中也出现了“想家人”的话题。没有发现紧急安全信号。"
  },
  topics: [
    { name: "睡眠与作息", note: "轻度关注", tone: "lavender" },
    { name: "想念家人", note: "建议联系", tone: "peach" },
    { name: "午后晒太阳", note: "正向事件", tone: "mint" }
  ],
  dailyCheckIn: {
    moodLabel: "平静",
    description: "今日 10:10 由陈奶奶自主完成心情打卡；这不是心理量表或诊断结果。",
    recordedAt: "2026-09-10T10:10:00+08:00",
    source: "self_report"
  },
  screenings: [
    { instrument: "PHQ-9", label: "抑郁筛查", status: "not_started", familyVisibility: "authorized_summary" },
    { instrument: "GAD-7", label: "焦虑筛查", status: "not_started", familyVisibility: "authorized_summary" },
    { instrument: "AD8", label: "认知筛查", status: "not_started", familyVisibility: "authorized_summary" }
  ],
  safety: {
    hasActiveEmergency: false,
    message: "暂无紧急安全事件"
  }
};
