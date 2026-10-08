"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, changeFamilyGrant, getAdminCheckIns, getAuditLogs, getElderAccounts, getEmergencyQueue, getFamilyGrants, getNotifications, getRegistrationApplications, getRiskDetail, getRiskQueue, getScreeningQueue, markNotificationRead, performEmergencyAction, performRiskAction, reviewRegistrationApplication } from "@/lib/admin-api";
import { clearAdminSession, readAdminSession } from "@/lib/admin-session";
import { AccountSetup } from "./account-setup";
import type { Actor, AdminCheckIn, AuditFilters, AuditListResponse, AuthorizationScope, ElderAccount, EmergencyAction, EmergencyEvent, EmergencyStatus, FamilyGrant, GrantAction, NotificationCategory, NotificationItem, NotificationListResponse, RegistrationApplication, RiskAction, RiskDetail, RiskLevel, RiskListItem, RiskStatus, ScreeningSummary } from "@/lib/types";

type AdminView = "risk" | "screenings" | "emergency" | "checkins" | "relationships" | "notifications" | "audit" | "registrations";

const emptyAuditFilters: AuditFilters = { actorId: "", action: "", targetType: "", targetId: "", page: 1, perPage: 25 };

const auditActionLabels: Record<string, string> = {
  "account.password_changed": "本人修改登录密码",
  "risk.viewed": "查看风险详情",
  "risk.claim": "认领风险事件",
  "risk.begin_review": "开始人工复核",
  "risk.request_action": "要求跟进",
  "risk.escalate": "升级处置",
  "risk.resolve": "记录已解决",
  "risk.mark_false_positive": "标记误报",
  "risk.close": "关闭风险事件",
  "risk.reopen": "重新打开",
  "family.today_viewed": "家属查看今日摘要",
  "family.trend_viewed": "家属查看关怀趋势",
  "family.care_plan_viewed": "家属查看陪伴计划",
  "family.care_plan_created": "家属新增陪伴计划",
  "family.care_plan_completed": "家属完成陪伴计划",
  "family.check_ins_viewed": "家属查看已分享自述",
  "family.contacted": "家属记录已联系",
  "family.video_planned": "家属记录视频联络计划",
  "family.referral_requested": "家属申请专业转介",
  "emergency.created": "发起紧急求助",
  "emergency.acknowledge": "确认收到求助",
  "emergency.resolve": "解除紧急事件",
  "emergency.cancel": "取消紧急事件",
  "emergency.reopen": "重新打开紧急事件",
  "grant.created": "创建家属授权",
  "grant.update_scopes": "调整授权范围",
  "grant.revoke": "撤销家属授权",
  "grant.reactivate": "重新启用授权",
  "conversation.analysis_queued": "提交授权会话分析",
  "conversation.session_created": "老人开启陪伴会话",
  "conversation.consent_revoked": "老人撤回会话授权",
  "conversation.messages_read": "老人查看本人对话记录",
  "analysis.completed": "完成结构化关怀分析",
  "analysis.skipped": "因授权变化跳过分析",
  "analysis.failed": "关怀分析任务失败",
  "analysis.summary_published": "发布已复核家属摘要",
  "screening.started": "老人开始标准筛查",
  "screening.completed": "老人完成标准筛查",
  "screening.answer_corrected": "老人更正筛查答案",
  "screening.queue_viewed": "查看标准筛查队列",
  "daily_check_in.created": "老人提交每日自述",
  "daily_check_in.updated": "老人更新每日自述",
  "daily_check_in.sharing_updated": "老人调整自述分享范围",
  "daily_check_in.queue_viewed": "工作人员查看已分享自述队列",
  "family.screenings_viewed": "家属查看筛查摘要",
  "elder.created": "管理员开通老人账号",
  "registration.approved": "管理员通过家属申请",
  "registration.rejected": "管理员驳回家属申请",
  "task.retry_requested": "管理员请求重试后台任务",
  "voice_call.started": "发起家人语音通话",
  "voice_call.answered": "接听家人语音通话",
  "voice_call.declined": "拒绝家人语音通话",
  "voice_call.ended": "结束家人语音通话",
  "notification.read": "读取站内通知",
  "notification.delivered": "确认通知投递",
  "notification.delivery_failed": "通知投递失败"
};

const auditTargetLabels: Record<string, string> = {
  elder: "老人账号", user: "用户账号", risk_event: "风险事件", emergency_event: "安全事件",
  family_elder_grant: "家属授权关系", registration_application: "家属注册申请",
  conversation_session: "陪伴会话", conversation_analysis: "关怀分析", daily_insight: "每日摘要",
  daily_check_in: "每日自述", daily_check_in_queue: "已分享自述队列",
  screening_session: "标准筛查", screening_queue: "筛查队列", outbox_event: "后台任务",
  notification: "站内通知", voice_call: "家人语音通话", family_care_plan_item: "陪伴计划"
};

function auditScopeSummary(action: string, metadata: Record<string, unknown>) {
  if (action === "daily_check_in.queue_viewed") return `近${metadata.days ?? "—"}天 · ${metadata.attentionOnly ? "只看待关注" : "全部已分享记录"}`;
  if (action === "conversation.session_created") return `聊天保存：${metadata.saveMessages ? "允许" : "不允许"} · 分析：${metadata.allowAnalysis ? "允许" : "不允许"}`;
  if (action === "screening.queue_viewed") return "仅查看本人同意分享的结构化结果";
  if (action === "family.today_viewed") return "已授权的结构化关怀摘要";
  if (action === "analysis.completed") return "结构化候选线索，非诊断";
  if (action === "risk.viewed") return "仅查看结构化风险线索";
  return "完整字段见详情，不含聊天全文";
}

function auditAssessment(action: string) {
  if (["analysis.failed", "notification.delivery_failed"].includes(action)) return "任务失败，需排查";
  if (action === "analysis.skipped") return "因授权变化已停止";
  return "已留痕 · 待人工核对";
}

const riskLevelPriority: Record<RiskLevel, number> = { red: 0, orange: 1, yellow: 2, green: 3 };
function prioritizeRisks(items: RiskListItem[]) {
  return [...items].sort((a, b) => {
    const aClosed = ["resolved", "false_positive", "closed"].includes(a.status) ? 1 : 0;
    const bClosed = ["resolved", "false_positive", "closed"].includes(b.status) ? 1 : 0;
    return aClosed - bClosed || riskLevelPriority[a.level] - riskLevelPriority[b.level] || Date.parse(a.createdAt) - Date.parse(b.createdAt);
  });
}

const emergencyStatusLabels: Record<EmergencyStatus, string> = {
  open: "等待确认",
  acknowledged: "跟进中",
  resolved: "已解除",
  cancelled: "已取消"
};

const emergencyActionLabels: Record<EmergencyAction, string> = {
  acknowledge: "确认收到",
  resolve: "确认安全并解除",
  cancel: "取消事件",
  reopen: "重新打开"
};

const emergencyNextActions: Record<EmergencyStatus, EmergencyAction[]> = {
  open: ["acknowledge", "resolve", "cancel"],
  acknowledged: ["resolve", "cancel"],
  resolved: ["reopen"],
  cancelled: ["reopen"]
};

const statusLabels: Record<RiskStatus, string> = {
  new: "待认领",
  assigned: "已认领",
  reviewing: "复核中",
  action_required: "待处置",
  escalated: "已升级",
  resolved: "已解决",
  false_positive: "误报",
  closed: "已关闭"
};

const riskLevelLabels: Record<RiskLevel, string> = {
  green: "绿色",
  yellow: "黄色",
  orange: "橙色",
  red: "红色"
};

const actionLabels: Record<RiskAction, string> = {
  claim: "认领事件",
  begin_review: "开始复核",
  request_action: "要求跟进",
  escalate: "升级处置",
  resolve: "记录已解决",
  mark_false_positive: "标记误报",
  close: "关闭事件",
  reopen: "重新打开"
};

const nextActions: Record<RiskStatus, RiskAction[]> = {
  new: ["claim"],
  assigned: ["begin_review"],
  reviewing: ["resolve", "request_action", "escalate", "mark_false_positive"],
  action_required: ["resolve", "escalate"],
  escalated: ["resolve"],
  resolved: ["close"],
  false_positive: ["close"],
  closed: ["reopen"]
};

const noteRequired = new Set<RiskAction>(["request_action", "escalate", "resolve", "mark_false_positive", "reopen"]);

const notificationCategoryLabels: Record<NotificationCategory, string> = {
  emergency: "安全事件",
  risk_follow_up: "风险跟进",
  registration: "注册审核",
  authorization: "授权变更",
  analysis_summary: "关怀摘要"
};

const evidenceSourceLabels: Record<string, string> = {
  trend: "近期状态变化",
  screening: "标准量表结果",
  model_signal: "聊天摘要中的关注线索"
};

const actionableNotificationTargets = new Set(["risk_event", "emergency_event", "registration_application", "family_elder_grant"]);

const viewHeadings: Record<AdminView, { eyebrow: string; title: string }> = {
  risk: { eyebrow: "风险复核 / 今日工作", title: "先处理需要人工判断的事项" },
  screenings: { eyebrow: "标准筛查 / 人工复核", title: "只查看本人同意分享的标准化结果" },
  emergency: { eyebrow: "安全事件 / 紧急求助", title: "确认每一条求助都得到人工响应" },
  checkins: { eyebrow: "每日自述 / 人工关注", title: "只查看老人主动分享且需要关注的感受" },
  relationships: { eyebrow: "关系管理 / 授权范围", title: "让每一次访问都有明确授权依据" },
  notifications: { eyebrow: "通知中心 / 个人待办", title: "从业务提醒直接进入处置闭环" },
  audit: { eyebrow: "审计查询 / 操作留痕", title: "核对每一次敏感读取与人工操作" },
  registrations: { eyebrow: "账号管理 / 关系核验", title: "审核家属账户申请" }
};

function formatTime(value: string | null) {
  if (!value) return "未设置";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date(value));
}

export default function AdminDashboard() {
  const router = useRouter();
  const [activeView, setActiveView] = useState<AdminView>("risk");
  const [actor, setActor] = useState<Actor | null>(null);
  const [token, setToken] = useState("");
  const [risks, setRisks] = useState<RiskListItem[]>([]);
  const [screenings, setScreenings] = useState<ScreeningSummary[]>([]);
  const [selected, setSelected] = useState<RiskDetail | null>(null);
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<RiskAction | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("正在连接共享业务后端");
  const [audits, setAudits] = useState<AuditListResponse>({ items: [], page: 1, perPage: 25, total: 0 });
  const [auditFilters, setAuditFilters] = useState<AuditFilters>(emptyAuditFilters);
  const [appliedAuditFilters, setAppliedAuditFilters] = useState<AuditFilters>(emptyAuditFilters);
  const [auditLoading, setAuditLoading] = useState(false);
  const [applications, setApplications] = useState<RegistrationApplication[]>([]);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [emergencies, setEmergencies] = useState<EmergencyEvent[]>([]);
  const [checkIns, setCheckIns] = useState<AdminCheckIn[]>([]);
  const [checkInsTotal, setCheckInsTotal] = useState(0);
  const [checkInsDays, setCheckInsDays] = useState(7);
  const [checkInsAttentionOnly, setCheckInsAttentionOnly] = useState(false);
  const [checkInsLoading, setCheckInsLoading] = useState(false);
  const [selectedEmergency, setSelectedEmergency] = useState<EmergencyEvent | null>(null);
  const [emergencyNote, setEmergencyNote] = useState("");
  const [emergencyBusy, setEmergencyBusy] = useState<EmergencyAction | null>(null);
  const [elderAccounts, setElderAccounts] = useState<ElderAccount[]>([]);
  const [applicationElders, setApplicationElders] = useState<Record<string, string>>({});
  const [applicationNotes, setApplicationNotes] = useState<Record<string, string>>({});
  const [grants, setGrants] = useState<FamilyGrant[]>([]);
  const [grantDrafts, setGrantDrafts] = useState<Record<string, AuthorizationScope[]>>({});
  const [grantNotes, setGrantNotes] = useState<Record<string, string>>({});
  const [grantBusy, setGrantBusy] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<NotificationListResponse>({ items: [], unreadCount: 0, page: 1, perPage: 25, total: 0 });
  const [notificationUnreadOnly, setNotificationUnreadOnly] = useState(false);
  const [notificationLoading, setNotificationLoading] = useState(false);
  const [notificationBusy, setNotificationBusy] = useState<string | null>(null);
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    const expire = () => {
      clearAdminSession();
      setAuthorized(false);
      setToken("");
      setActor(null);
      router.replace("/account");
    };
    window.addEventListener("hearttrace.admin.unauthorized", expire);
    return () => window.removeEventListener("hearttrace.admin.unauthorized", expire);
  }, [router]);

  useEffect(() => {
    let active = true;
    async function boot() {
      const session = readAdminSession();
      if (!session) {
        router.replace("/account");
        return;
      }
      try {
        // Verify the stored token against an admin-only endpoint before revealing any workbench data.
        const registrationQueue = await getRegistrationApplications(session.accessToken);
        if (!active) return;
        setActor(session.actor);
        setToken(session.accessToken);
        setAuthorized(true);
        setApplications(registrationQueue.items);
        const [riskResult, screeningResult, emergencyResult, elderResult, grantResult, notificationResult] = await Promise.allSettled([
          getRiskQueue(session.accessToken), getScreeningQueue(session.accessToken), getEmergencyQueue(session.accessToken),
          getElderAccounts(session.accessToken), getFamilyGrants(session.accessToken), getNotifications(session.accessToken)
        ]);
        if (!active) return;
        const failures = [riskResult, screeningResult, emergencyResult, elderResult, grantResult, notificationResult]
          .filter((result): result is PromiseRejectedResult => result.status === "rejected")
          .map((result) => result.reason);
        const authFailure = failures.find((cause) => cause instanceof ApiError && [401, 403].includes(cause.status));
        if (authFailure) throw authFailure;
        if (riskResult.status === "fulfilled") {
          const sorted = prioritizeRisks(riskResult.value.items);
          setRisks(sorted);
          if (sorted[0]) {
            try { setSelected(await getRiskDetail(session.accessToken, sorted[0].id)); }
            catch { failures.push(new Error("风险详情暂时无法读取")); }
          }
        }
        if (!active) return;
        if (screeningResult.status === "fulfilled") setScreenings(screeningResult.value.items);
        if (emergencyResult.status === "fulfilled") {
          setEmergencies(emergencyResult.value.items);
          setSelectedEmergency(emergencyResult.value.items[0] ?? null);
        }
        if (elderResult.status === "fulfilled") setElderAccounts(elderResult.value.items);
        if (grantResult.status === "fulfilled") {
          setGrants(grantResult.value.items);
          setGrantDrafts(Object.fromEntries(grantResult.value.items.map((grant) => [`${grant.familyId}:${grant.elderId}`, grant.scopes])));
        }
        if (notificationResult.status === "fulfilled") setNotifications(notificationResult.value);
        setNotice(failures.length ? `已连接业务后端；${failures.length}项资料暂时不可用，可进入对应页面重试。` : "已连接业务后端 · 当前仅展示结构化证据");
      } catch (cause) {
        if (!active) return;
        if (cause instanceof ApiError && (cause.status === 401 || cause.status === 403)) {
          clearAdminSession();
          setAuthorized(false);
          router.replace("/account");
          return;
        }
        setError(cause instanceof Error ? cause.message : "服务暂时不可用");
        setNotice("无法连接共享业务后端");
      } finally {
        if (active) setLoading(false);
      }
    }
    void boot();
    return () => {
      active = false;
    };
  }, [router]);

  const activeCount = useMemo(
    () => risks.filter((item) => !["resolved", "false_positive", "closed"].includes(item.status)).length,
    [risks]
  );
  const urgentCount = useMemo(
    () => risks.filter((item) => ["orange", "red"].includes(item.level) && item.status !== "closed").length,
    [risks]
  );
  const prioritizedRisks = useMemo(() => prioritizeRisks(risks), [risks]);

  const selectRisk = async (item: RiskListItem) => {
    if (!token || item.id === selected?.id) return;
    setError("");
    try {
      setSelected(await getRiskDetail(token, item.id));
      setNote("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "读取风险详情失败");
    }
  };

  const runAction = async (action: RiskAction) => {
    if (!token || !selected) return;
    if (noteRequired.has(action) && !note.trim()) {
      setError("该操作需要填写复核说明");
      return;
    }
    setBusyAction(action);
    setError("");
    try {
      const result = await performRiskAction(token, selected.id, action, selected.version, note);
      setSelected(result.event);
      setRisks((current) => current.map((item) => (
        item.id === result.event.id ? { ...item, ...result.event } : item
      )));
      setNote("");
      setNotice(`已记录“${actionLabels[action]}”并写入审计日志`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "操作提交失败");
    } finally {
      setBusyAction(null);
    }
  };

  const loadAudits = async (filters: AuditFilters) => {
    if (!token) return;
    setAuditLoading(true);
    setError("");
    try {
      const result = await getAuditLogs(token, filters);
      setAudits(result);
      setAppliedAuditFilters(filters);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "读取审计记录失败");
    } finally {
      setAuditLoading(false);
    }
  };

  const loadNotifications = async (page = 1, unreadOnly = notificationUnreadOnly) => {
    if (!token) return;
    setNotificationLoading(true);
    setError("");
    try {
      setNotifications(await getNotifications(token, unreadOnly, page));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "读取通知失败");
    } finally {
      setNotificationLoading(false);
    }
  };

  const loadCheckIns = async (days = checkInsDays, attentionOnly = checkInsAttentionOnly) => {
    if (!token) return;
    setCheckInsLoading(true);
    setError("");
    try {
      const result = await getAdminCheckIns(token, days, attentionOnly);
      setCheckIns(result.items);
      setCheckInsTotal(result.total);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "读取每日自述失败");
    } finally {
      setCheckInsLoading(false);
    }
  };

  const recordNotificationRead = async (item: NotificationItem, related: NotificationItem[] = [item]) => {
    if (!token || related.every((entry) => entry.isRead)) return;
    setNotificationBusy(item.id);
    setError("");
    try {
      await Promise.all(related.filter((entry) => !entry.isRead).map((entry) => markNotificationRead(token, entry.id)));
      await loadNotifications(notifications.page, notificationUnreadOnly);
      setNotice("通知已标记为已读，操作已写入审计日志");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "更新通知状态失败");
    } finally {
      setNotificationBusy(null);
    }
  };

  const openNotificationTarget = async (item: NotificationItem, related: NotificationItem[] = [item]) => {
    if (!token) return;
    if (related.some((entry) => !entry.isRead)) await recordNotificationRead(item, related);
    setError("");
    try {
      if (item.targetType === "risk_event") {
        const [queue, detail] = await Promise.all([getRiskQueue(token), getRiskDetail(token, item.targetId)]);
        setRisks(queue.items);
        setSelected(detail);
        setActiveView("risk");
        setNotice("已从通知定位到风险事件");
        return;
      }
      if (item.targetType === "emergency_event") {
        const queue = await getEmergencyQueue(token);
        setEmergencies(queue.items);
        setSelectedEmergency(queue.items.find((event) => event.id === item.targetId) ?? null);
        setActiveView("emergency");
        setNotice(queue.items.some((event) => event.id === item.targetId) ? "已从通知定位到安全事件" : "该安全事件已不在当前队列中");
        return;
      }
      if (item.targetType === "registration_application") {
        const queue = await getRegistrationApplications(token);
        setApplications(queue.items);
        setActiveView("registrations");
        setNotice("已打开注册审核队列");
        return;
      }
      if (item.targetType === "family_elder_grant") {
        await loadGrants();
        setActiveView("relationships");
        setNotice("已打开关系与授权台账");
        return;
      }
      setNotice("该通知已读；当前管理端没有对应详情页面");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "打开相关事项失败");
    }
  };

  const openView = (view: AdminView) => {
    setActiveView(view);
    setError("");
    setNotice(`${viewHeadings[view].eyebrow} · 仅显示当前账号有权访问的内容`);
    if (view === "audit" && audits.items.length === 0) void loadAudits(emptyAuditFilters);
    if (view === "screenings") void getScreeningQueue(token).then((queue) => setScreenings(queue.items)).catch(() => setError("读取标准筛查队列失败"));
    if (view === "registrations") {
      void getRegistrationApplications(token).then((queue) => setApplications(queue.items)).catch(() => setError("读取注册申请失败"));
    }
    if (view === "emergency") {
      void getEmergencyQueue(token).then((queue) => {
        setEmergencies(queue.items);
        setSelectedEmergency((current) => queue.items.find((item) => item.id === current?.id) ?? queue.items[0] ?? null);
      }).catch(() => setError("读取紧急事件失败"));
    }
    if (view === "relationships") void loadGrants();
    if (view === "notifications") void loadNotifications(1, notificationUnreadOnly);
    if (view === "checkins") void loadCheckIns();
  };

  const auditPageCount = Math.max(1, Math.ceil(audits.total / audits.perPage));
  const notificationPageCount = Math.max(1, Math.ceil(notifications.total / notifications.perPage));
  const groupedNotifications = Object.values(notifications.items.reduce<Record<string, NotificationItem[]>>((groups, item) => {
    const key = `${item.category}:${item.targetType}:${item.targetId}`;
    (groups[key] ??= []).push(item);
    return groups;
  }, {}));

  const logout = () => {
    clearAdminSession();
    setAuthorized(false);
    setToken("");
    setActor(null);
    router.replace("/account");
  };

  const reviewApplication = async (application: RegistrationApplication, decision: "approved" | "rejected") => {
    if (!token) return;
    const elderId = applicationElders[application.id];
    if (decision === "approved" && !elderId) {
      setError("通过申请前必须选择已核验的老人账号");
      return;
    }
    if (decision === "approved" && !applicationNotes[application.id]?.trim()) {
      setError("通过申请前请填写身份及关系核验依据；仅凭同名不能授权");
      return;
    }
    setReviewingId(application.id);
    setError("");
    try {
      await reviewRegistrationApplication(token, application.id, decision, elderId, applicationNotes[application.id]);
      setApplications((current) => current.filter((item) => item.id !== application.id));
      if (decision === "approved") await loadGrants();
      setNotice(decision === "approved" ? "申请已通过，家属账户已激活。" : "申请已驳回，结果已写入审计记录。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "审核提交失败");
    } finally {
      setReviewingId(null);
    }
  };

  const grantKey = (grant: FamilyGrant) => `${grant.familyId}:${grant.elderId}`;

  const loadGrants = async () => {
    if (!token) return;
    try {
      const queue = await getFamilyGrants(token);
      setGrants(queue.items);
      setGrantDrafts(Object.fromEntries(queue.items.map((grant) => [grantKey(grant), grant.scopes])));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "读取授权关系失败");
    }
  };

  const runGrantAction = async (grant: FamilyGrant, action: GrantAction) => {
    if (!token) return;
    const key = grantKey(grant);
    const note = grantNotes[key] ?? "";
    if (["revoke", "reactivate"].includes(action) && !note.trim()) {
      setError("撤销或重新启用授权必须填写说明");
      return;
    }
    const scopes = grantDrafts[key] ?? grant.scopes;
    if (action === "update_scopes" && scopes.length === 0) {
      setError("至少保留一项授权；如需全部停止，请使用撤销授权");
      return;
    }
    setGrantBusy(key);
    setError("");
    try {
      const updated = await changeFamilyGrant(token, grant, action, scopes, note);
      setGrants((current) => current.map((item) => grantKey(item) === key ? updated : item));
      setGrantDrafts((current) => ({ ...current, [key]: updated.scopes }));
      setGrantNotes((current) => ({ ...current, [key]: "" }));
      setNotice(action === "revoke" ? "授权已撤销，家属访问立即停止。" : action === "reactivate" ? "授权已重新启用。" : "授权范围已更新并立即生效。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "授权操作失败");
    } finally {
      setGrantBusy(null);
    }
  };

  const runEmergencyAction = async (action: EmergencyAction) => {
    if (!token || !selectedEmergency) return;
    if (["resolve", "cancel", "reopen"].includes(action) && !emergencyNote.trim()) {
      setError("解除、取消或重新打开事件时必须填写处置说明");
      return;
    }
    setEmergencyBusy(action);
    setError("");
    try {
      const result = await performEmergencyAction(token, selectedEmergency.id, action, selectedEmergency.version, emergencyNote);
      setSelectedEmergency(result.event);
      setEmergencies((current) => current.map((item) => item.id === result.event.id ? result.event : item));
      setEmergencyNote("");
      setNotice(`已记录“${emergencyActionLabels[action]}”并同步家属安全状态`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "紧急事件操作失败");
    } finally {
      setEmergencyBusy(null);
    }
  };

  if (!authorized) return <main className="admin-auth-loading" role="status">{error ? <><p>暂时无法验证管理身份：{error}</p><button onClick={() => window.location.reload()}>重试连接</button></> : "正在验证管理身份…"}</main>;

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span>心</span><div><strong>心迹银龄</strong><small>管理工作台</small></div></div>
        <nav aria-label="管理端主导航">
          <button className={`nav-item ${activeView === "risk" ? "active" : ""}`} onClick={() => openView("risk")}><span>01</span>风险复核</button>
          <button className={`nav-item ${activeView === "screenings" ? "active" : ""}`} onClick={() => openView("screenings")}><span>02</span>标准筛查{screenings.filter((item) => item.band === "moderate" || item.band === "high").length > 0 && <em>{screenings.filter((item) => item.band === "moderate" || item.band === "high").length} 关注</em>}</button>
          <button className={`nav-item ${activeView === "registrations" ? "active" : ""}`} onClick={() => openView("registrations")}><span>03</span>注册审核{applications.length > 0 && <em>{applications.length} 待办</em>}</button>
          <button className={`nav-item ${activeView === "emergency" ? "active" : ""}`} onClick={() => openView("emergency")}><span>04</span>安全事件{emergencies.filter((item) => ["open", "acknowledged"].includes(item.status)).length > 0 && <em>{emergencies.filter((item) => ["open", "acknowledged"].includes(item.status)).length} 待办</em>}</button>
          <button className={`nav-item ${activeView === "checkins" ? "active" : ""}`} onClick={() => openView("checkins")}><span>05</span>每日自述{checkIns.filter((item) => item.attentionNeeded).length > 0 && <em>{checkIns.filter((item) => item.attentionNeeded).length} 关注</em>}</button>
          <button className={`nav-item ${activeView === "relationships" ? "active" : ""}`} onClick={() => openView("relationships")}><span>06</span>关系与授权<em>{grants.filter((grant) => grant.isActive).length} 生效</em></button>
          <button className={`nav-item ${activeView === "notifications" ? "active" : ""}`} onClick={() => openView("notifications")}><span>07</span>通知中心{notifications.unreadCount > 0 && <em>{notifications.unreadCount} 未读</em>}</button>
          <button className={`nav-item ${activeView === "audit" ? "active" : ""}`} onClick={() => openView("audit")}><span>08</span>审计查询</button>
        </nav>
        <div className="sidebar-note">
          <span className="connection-dot" />
          {error ? "服务需要检查" : "权限校验正常"}
          <small>浏览器不计算风险等级或授权范围</small>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div><p>{viewHeadings[activeView].eyebrow}</p><h1>{viewHeadings[activeView].title}</h1></div>
          <div className="actor"><span>{actor?.displayName?.slice(0, 1) ?? "管"}</span><div><strong>{actor?.displayName ?? "管理员"}</strong><small>管理员</small></div><a className="actor-logout" href="/account/security">账号安全</a><button className="actor-logout" onClick={logout}>退出</button></div>
        </header>

        <div className={error ? "notice error" : "notice"} role="status">
          <b>{error ? "!" : "i"}</b>{error || notice}
        </div>

        {activeView === "risk" ? <>
        <section className="metrics" aria-label="风险概览">
          <article><p>开放事项</p><strong>{loading ? "—" : activeCount}</strong><small>等待认领或处置</small></article>
          <article className="urgent"><p>橙红风险</p><strong>{loading ? "—" : urgentCount}</strong><small>优先完成复核</small></article>
          <article><p>当前队列</p><strong>{loading ? "—" : risks.length}</strong><small>未结事项优先，按关注等级排列</small></article>
          <article><p>证据策略</p><strong className="text-value">结构化</strong><small>默认不返回聊天全文</small></article>
        </section>

        <section className="review-layout">
          <div className="queue-panel panel">
            <div className="panel-heading"><div><p>待办队列</p><h2>风险事件</h2></div><span>{risks.length} 项</span></div>
            <div className="queue-list">
              {loading && <div className="empty">正在读取风险队列…</div>}
              {!loading && risks.length === 0 && <div className="empty">当前没有待复核事件</div>}
              {prioritizedRisks.map((risk) => (
                <button
                  key={risk.id}
                  className={`queue-item ${selected?.id === risk.id ? "selected" : ""}`}
                  onClick={() => { void selectRisk(risk); }}
                >
                  <div className="queue-top"><span className={`level ${risk.level}`}>{riskLevelLabels[risk.level]}</span><time>{formatTime(risk.slaDueAt)}</time></div>
                  <strong>{risk.title}</strong>
                  <p>{risk.elderName} · {statusLabels[risk.status]}</p>
                </button>
              ))}
            </div>
          </div>

          <div className="detail-panel panel">
            {!selected && <div className="empty detail-empty">选择一条风险事件查看证据与处置动作</div>}
            {selected && (
              <>
                <div className="detail-head">
                  <div><div className="detail-meta"><span className={`level ${selected.level}`}>{riskLevelLabels[selected.level]}</span><span>{statusLabels[selected.status]}</span></div><h2>{selected.title}</h2><p>{selected.summary}</p></div>
                  <div className="elder-card"><small>服务对象</small><strong>{selected.elderName}</strong><span>{selected.elderId}</span></div>
                </div>

                <div className="detail-columns">
                  <section>
                    <div className="section-title"><div><p>为什么需要关注</p><h3>供工作人员核对的线索</h3></div><span>不含聊天全文</span></div>
                    <p className="evidence-help">这些信息来自近期变化、量表或经授权的聊天摘要。系统只负责提示，是否需要跟进由工作人员结合实际情况判断。</p>
                    <div className="evidence-list">
                      {selected.evidence.map((item, index) => (
                        <article key={item.id}>
                          <span>{String(index + 1).padStart(2, "0")}</span>
                          <div><small>{evidenceSourceLabels[item.sourceType] ?? item.label}</small><strong>{item.detail}</strong><p>记录时间：{formatTime(item.recordedAt)}</p></div>
                        </article>
                      ))}
                    </div>
                    <details className="evidence-trace">
                      <summary>查看后台核对信息</summary>
                      <p>以下编号仅用于核对数据来源，不是诊断结论，也不能打开聊天全文。</p>
                      <ul>{selected.evidence.map((item, index) => <li key={item.id}>线索 {index + 1}：<code>{item.evidenceRef}</code></li>)}</ul>
                      <p>分析版本：<code>{selected.modelVersion ?? "未使用模型"}</code>；判断规则版本：<code>{selected.ruleVersion}</code></p>
                    </details>
                  </section>

                  <aside className="action-box">
                    <p>下一步处置</p>
                    <h3>{statusLabels[selected.status]}</h3>
                    <label htmlFor="review-note">复核说明</label>
                    <textarea
                      id="review-note"
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      placeholder="记录判断依据、已联系对象或后续安排"
                      rows={5}
                    />
                    <div className="action-buttons">
                      {nextActions[selected.status].map((action, index) => (
                        <button
                          key={action}
                          className={index === 0 ? "primary" : "secondary"}
                          disabled={busyAction !== null}
                          onClick={() => { void runAction(action); }}
                        >
                          {busyAction === action ? "提交中…" : actionLabels[action]}
                        </button>
                      ))}
                    </div>
                    <small>状态、动作和审计在同一后端事务中写入。</small>
                  </aside>
                </div>

                <section className="timeline-section">
                  <div className="section-title"><div><p>处置轨迹</p><h3>事件状态与人工动作</h3></div><span>{selected.actions.length} 条记录</span></div>
                  {selected.actions.length === 0 ? <div className="empty compact">尚未产生人工处置记录</div> : (
                    <div className="timeline">
                      {[...selected.actions].reverse().map((item) => (
                        <article key={item.id}><span /><div><strong>{actionLabels[item.action]}</strong><p>{item.fromStatus} → {item.toStatus} · {item.actorId}</p>{item.note && <blockquote>{item.note}</blockquote>}</div><time>{formatTime(item.createdAt)}</time></article>
                      ))}
                    </div>
                  )}
                </section>
              </>
            )}
          </div>
        </section>
        </> : activeView === "screenings" ? (
          <section className="screening-console panel">
            <div className="panel-heading"><div><p>本人授权分享</p><h2>标准化筛查记录</h2></div><span>{screenings.length} 项</span></div>
            <p className="registration-intro">量表题目和计分固定在服务端，模型不能代答或改分。这里只显示结构化分层与建议，不显示逐题答案和聊天全文。</p>
            <section className="metrics" aria-label="筛查概览">
              <article><p>完成记录</p><strong>{screenings.filter((item) => item.status === "completed").length}</strong><small>本人同意分享给关怀团队</small></article>
              <article><p>需要关注</p><strong>{screenings.filter((item) => item.band === "moderate").length}</strong><small>已自动进入人工复核</small></article>
              <article className="urgent"><p>尽快评估</p><strong>{screenings.filter((item) => item.band === "high").length}</strong><small>优先查看对应风险事件</small></article>
              <article><p>计分依据</p><strong className="text-value">WS/T 802-2022</strong><small>GDS-15 与 GAD-7；固定题目和计分，仅供筛查，不是诊断</small></article>
            </section>
            <div className="application-list">
              {screenings.length === 0 && <div className="empty">当前没有本人授权分享的标准筛查记录</div>}
              {screenings.map((item) => <article key={item.id} className="application-row">
                <div><span className={`level ${item.band === "high" ? "orange" : item.band === "moderate" ? "yellow" : "green"}`}>{item.label}</span><strong>{item.elderName} · {item.instrumentName}</strong><p>{item.recommendation ?? "筛查正在进行中"}</p><small>{formatTime(item.completedAt ?? item.createdAt)} · {item.id}</small></div>
                <div className="registration-actions"><button className="secondary" onClick={() => openView("risk")}>查看风险复核队列</button></div>
              </article>)}
            </div>
            <p className="registration-intro">以上结果仅为标准化筛查提示，不构成精神疾病诊断；最终处置由受训人员结合实际情况完成。</p>
          </section>
        ) : activeView === "emergency" ? (
          <section className="review-layout emergency-console">
            <div className="queue-panel panel">
              <div className="panel-heading"><div><p>安全队列</p><h2>紧急求助</h2></div><span>{emergencies.length} 项</span></div>
              <div className="queue-list">
                {emergencies.length === 0 && <div className="empty">当前没有紧急求助事件</div>}
                {emergencies.map((item) => (
                  <button key={item.id} className={`queue-item ${selectedEmergency?.id === item.id ? "selected" : ""}`} onClick={() => { setSelectedEmergency(item); setEmergencyNote(""); }}>
                    <div className="queue-top"><span className={`emergency-state ${item.status}`}>{emergencyStatusLabels[item.status]}</span><time>{formatTime(item.createdAt)}</time></div>
                    <strong>{item.elderName}的紧急求助</strong>
                    <p>{item.source === "elder_button" ? "老人端求助键" : "绑定设备求助键"} · 版本 {item.version}</p>
                  </button>
                ))}
              </div>
            </div>
            <div className="detail-panel panel">
              {!selectedEmergency && <div className="empty detail-empty">选择一条紧急事件进行确认或解除</div>}
              {selectedEmergency && <>
                <div className="detail-head emergency-head">
                  <div><div className="detail-meta"><span className={`emergency-state ${selectedEmergency.status}`}>{emergencyStatusLabels[selectedEmergency.status]}</span><span>版本 {selectedEmergency.version}</span></div><h2>{selectedEmergency.elderName}的紧急求助</h2><p>来源：{selectedEmergency.source === "elder_button" ? "老人主动按键" : "已绑定设备按键"}。事件由服务端保存并同步至家属安全摘要。</p></div>
                  <div className="elder-card"><small>服务对象</small><strong>{selectedEmergency.elderName}</strong><span>{selectedEmergency.elderId}</span></div>
                </div>
                <div className="emergency-details">
                  <section className="emergency-facts"><div className="section-title"><div><p>事件事实</p><h3>最小必要信息</h3></div><span>不含定位与聊天</span></div><dl><div><dt>创建时间</dt><dd>{formatTime(selectedEmergency.createdAt)}</dd></div><div><dt>触发账号</dt><dd>{selectedEmergency.triggerActorId}</dd></div><div><dt>确认人员</dt><dd>{selectedEmergency.acknowledgedBy ?? "尚未确认"}</dd></div><div><dt>解除人员</dt><dd>{selectedEmergency.resolvedBy ?? "尚未解除"}</dd></div></dl>{selectedEmergency.note && <blockquote>{selectedEmergency.note}</blockquote>}</section>
                  <aside className="action-box"><p>下一步处置</p><h3>{emergencyStatusLabels[selectedEmergency.status]}</h3><label htmlFor="emergency-note">处置说明</label><textarea id="emergency-note" value={emergencyNote} onChange={(event) => setEmergencyNote(event.target.value)} placeholder="解除、取消或重新打开时必须说明核实结果" rows={5}/><div className="action-buttons">{emergencyNextActions[selectedEmergency.status].map((action, index) => <button key={action} className={index === 0 ? "primary" : "secondary"} disabled={emergencyBusy !== null} onClick={() => { void runEmergencyAction(action); }}>{emergencyBusy === action ? "提交中…" : emergencyActionLabels[action]}</button>)}</div><small>状态变化使用版本号防止多人覆盖，并与审计日志同事务写入。</small></aside>
                </div>
              </>}
            </div>
          </section>
        ) : activeView === "checkins" ? (
          <section className="checkin-console panel">
            <div className="checkin-toolbar"><div><p>老人主动分享的结构化自述</p><h2>每日自述关注台</h2><small>只读取老人明确分享给关怀团队的数据；低分仅提示人工关注，不代表抑郁、自残或任何疾病诊断。</small></div><div className="checkin-controls"><label>时间范围<select value={checkInsDays} onChange={(event) => { const days = Number(event.target.value); setCheckInsDays(days); void loadCheckIns(days, checkInsAttentionOnly); }}><option value={7}>近 7 天</option><option value={14}>近 14 天</option><option value={30}>近 30 天</option></select></label><label className="checkin-toggle"><input type="checkbox" checked={checkInsAttentionOnly} onChange={(event) => { const only = event.target.checked; setCheckInsAttentionOnly(only); void loadCheckIns(checkInsDays, only); }} /> 只看需要关注</label><button className="secondary" disabled={checkInsLoading} onClick={() => void loadCheckIns()}>{checkInsLoading ? "刷新中…" : "刷新"}</button></div></div>
            <div className="checkin-summary"><strong>{checkInsTotal}</strong><span>条已获授权的自述</span><b>{checkIns.filter((item) => item.attentionNeeded).length}</b><span>条建议人工关注</span></div>
            <div className="checkin-table"><div className="checkin-row checkin-header"><span>日期</span><span>老人</span><span>心情</span><span>睡眠</span><span>交流意愿</span><span>提示</span></div>{checkInsLoading && <div className="empty">正在读取每日自述…</div>}{!checkInsLoading && checkIns.length === 0 && <div className="empty">当前筛选范围内没有已分享的每日自述</div>}{!checkInsLoading && checkIns.map((item) => <article className={`checkin-row ${item.attentionNeeded ? "attention" : ""}`} key={item.id}><time>{item.checkinDate}</time><strong>{item.elderName}<small>{item.elderId}</small></strong><span>{item.mood}/5</span><span>{item.sleep}/5</span><span>{item.socialWillingness}/5</span><span>{item.attentionNeeded ? <em>建议人工问候</em> : <i>本次未触发提醒</i>}</span></article>)}</div>
          </section>
        ) : activeView === "relationships" ? (
          <section className="relationship-panel panel">
            <div className="panel-heading"><div><p>授权台账</p><h2>家属与老人关系</h2></div><span>{grants.length} 条关系</span></div>
            <p className="registration-intro">授权范围由服务端实时执行。撤销后家属的摘要与行动接口立即停止，不开放聊天全文或设备视频。</p>
            <div className="grant-list">
              {grants.length === 0 && <div className="empty">当前没有授权关系</div>}
              {grants.map((grant) => {
                const key = grantKey(grant);
                const draft = grantDrafts[key] ?? grant.scopes;
                return <article className={`grant-card ${grant.isActive ? "" : "revoked"}`} key={key}>
                  <div className="grant-head"><div><span className={`grant-state ${grant.isActive ? "active" : "revoked"}`}>{grant.isActive ? "授权生效" : "已撤销"}</span><h3>{grant.familyName} → {grant.elderName}</h3><p>{grant.relationship ?? "关系待补充"} · 版本 {grant.version} · {grant.consentVersion ?? "历史授权"}</p></div><small>{grant.familyId}<br />{grant.elderId}</small></div>
                  <div className="scope-options">
                    {(["daily_summary", "care_actions"] as AuthorizationScope[]).map((scope) => <label key={scope}><input type="checkbox" disabled={!grant.isActive || grantBusy === key} checked={draft.includes(scope)} onChange={(event) => setGrantDrafts((current) => ({ ...current, [key]: event.target.checked ? [...draft, scope] : draft.filter((item) => item !== scope) }))} /><span>{scope === "daily_summary" ? "每日结构化摘要" : "关怀行动记录"}</span></label>)}
                    <label className="scope-disabled"><input type="checkbox" disabled /><span>聊天全文（不开放）</span></label>
                    <label className="scope-disabled"><input type="checkbox" disabled /><span>设备视频（不开放）</span></label>
                  </div>
                  <div className="grant-actions"><input value={grantNotes[key] ?? ""} onChange={(event) => setGrantNotes((current) => ({ ...current, [key]: event.target.value }))} placeholder={grant.isActive ? "撤销授权时填写原因" : "重新启用时填写核验说明"} /><button className="secondary" disabled={!grant.isActive || grantBusy === key || JSON.stringify([...draft].sort()) === JSON.stringify([...grant.scopes].sort())} onClick={() => { void runGrantAction(grant, "update_scopes"); }}>保存范围</button><button className={grant.isActive ? "danger-button" : "primary"} disabled={grantBusy === key} onClick={() => { void runGrantAction(grant, grant.isActive ? "revoke" : "reactivate"); }}>{grantBusy === key ? "提交中…" : grant.isActive ? "撤销授权" : "重新启用"}</button></div>
                </article>;
              })}
            </div>
          </section>
        ) : activeView === "notifications" ? (
          <section className="notification-console panel">
            <div className="notification-toolbar">
              <div>
                <p>个人消息箱</p>
                <h2>业务通知</h2>
                <small>仅展示当前账号的通知；接收人和可见范围由后端授权决定。</small>
              </div>
              <div className="notification-controls" aria-label="通知筛选">
                <button className={!notificationUnreadOnly ? "active" : ""} onClick={() => { setNotificationUnreadOnly(false); void loadNotifications(1, false); }}>全部</button>
                <button className={notificationUnreadOnly ? "active" : ""} onClick={() => { setNotificationUnreadOnly(true); void loadNotifications(1, true); }}>仅未读</button>
                <button className="secondary" disabled={notificationLoading} onClick={() => void loadNotifications(notifications.page, notificationUnreadOnly)}>{notificationLoading ? "刷新中…" : "刷新"}</button>
              </div>
            </div>
            <div className="notification-summary">
              <span><strong>{notifications.unreadCount}</strong> 未读</span>
              <span><strong>{notifications.total}</strong> {notificationUnreadOnly ? "条未读结果" : "条通知"} · 本页 {groupedNotifications.length} 组事项</span>
              <small>第 {notifications.page}/{notificationPageCount} 页</small>
            </div>
            <div className="notification-list" aria-live="polite">
              {notificationLoading && <div className="empty">正在读取通知…</div>}
              {!notificationLoading && notifications.items.length === 0 && <div className="empty">{notificationUnreadOnly ? "当前没有未读通知" : "当前没有业务通知"}</div>}
              {!notificationLoading && groupedNotifications.map((group) => {
                const item = group[0];
                const unread = group.some((entry) => !entry.isRead);
                return <article className={`notification-item ${unread ? "unread" : "read"}`} key={`${item.category}:${item.targetType}:${item.targetId}`}>
                  <span className={`notification-category ${item.category}`}>{notificationCategoryLabels[item.category]}</span>
                  <div className="notification-copy">
                    <div><h3>{item.title}</h3>{unread && <b>未读</b>}{group.length > 1 && <b>{group.length} 次更新</b>}</div>
                    <p>{item.body}</p>
                    <small>最近更新 {formatTime(item.createdAt)} · {auditTargetLabels[item.targetType] ?? "业务事项"}</small>
                    {group.length > 1 && <details className="notification-history"><summary>查看全部 {group.length} 次提醒</summary><ul>{group.map((entry) => <li key={entry.id}><time>{formatTime(entry.createdAt)}</time><span>{entry.body}</span></li>)}</ul></details>}
                  </div>
                  <div className="notification-actions">
                    {unread && <button className="secondary" disabled={notificationBusy === item.id} onClick={() => void recordNotificationRead(item, group)}>{notificationBusy === item.id ? "处理中…" : "全部标为已读"}</button>}
                    {actionableNotificationTargets.has(item.targetType) && <button className="primary" disabled={notificationBusy === item.id} onClick={() => void openNotificationTarget(item, group)}>查看相关事项</button>}
                  </div>
                </article>;
              })}
            </div>
            <div className="audit-pagination">
              <button className="secondary" disabled={notificationLoading || notifications.page <= 1} onClick={() => void loadNotifications(notifications.page - 1, notificationUnreadOnly)}>上一页</button>
              <button className="secondary" disabled={notificationLoading || notifications.page >= notificationPageCount} onClick={() => void loadNotifications(notifications.page + 1, notificationUnreadOnly)}>下一页</button>
            </div>
          </section>
        ) : activeView === "audit" ? (
          <section className="audit-console panel">
            <form className="audit-filters" onSubmit={(event) => { event.preventDefault(); void loadAudits({ ...auditFilters, page: 1 }); }}>
              <label>动作类型
                <select value={auditFilters.action} onChange={(event) => setAuditFilters((current) => ({ ...current, action: event.target.value }))}>
                  <option value="">全部动作</option>
                  {Object.entries(auditActionLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label>操作者 ID
                <input value={auditFilters.actorId} onChange={(event) => setAuditFilters((current) => ({ ...current, actorId: event.target.value }))} placeholder="staff-admin-001" />
              </label>
              <label>对象类型
                <select value={auditFilters.targetType} onChange={(event) => setAuditFilters((current) => ({ ...current, targetType: event.target.value }))}>
                  <option value="">全部对象</option>
                  {Object.entries(auditTargetLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label>对象 ID
                <input value={auditFilters.targetId} onChange={(event) => setAuditFilters((current) => ({ ...current, targetId: event.target.value }))} placeholder="risk-demo-001" />
              </label>
              <div className="filter-actions">
                <button className="primary" type="submit" disabled={auditLoading}>{auditLoading ? "查询中…" : "查询"}</button>
                <button className="secondary" type="button" onClick={() => { setAuditFilters(emptyAuditFilters); void loadAudits(emptyAuditFilters); }}>清空</button>
              </div>
            </form>

            <div className="audit-summary"><div><p>查询结果</p><h2>敏感操作留痕</h2><small>记录本身不能证明授权合规，也不能判断老人健康状态；可展开核对原始字段。</small></div><span>{audits.total} 条记录 · 第 {audits.page}/{auditPageCount} 页</span></div>
            <div className="audit-list" aria-label="审计记录">
              {auditLoading && <div className="empty">正在读取审计记录…</div>}
              {!auditLoading && audits.items.length === 0 && <div className="empty">没有符合条件的审计记录</div>}
              {!auditLoading && audits.items.map((item) => (
                <details className="audit-entry" key={item.id}>
                  <summary className="audit-row">
                    <time>{formatTime(item.createdAt)}</time>
                    <span><strong>{item.actorDisplayName ?? "未命名账号"}</strong><small>{auditTargetLabels[item.targetType] ?? "业务对象"}</small></span>
                    <span><strong>{auditActionLabels[item.action] ?? "其他业务操作"}</strong><small>{auditScopeSummary(item.action, item.metadata)}</small></span>
                    <span className="audit-judgment">{auditAssessment(item.action)}</span>
                    <span className="audit-expand">查看原始字段</span>
                  </summary>
                  <div className="audit-detail">
                    <dl><div><dt>记录 ID</dt><dd>{item.id}</dd></div><div><dt>操作者 ID</dt><dd>{item.actorId}</dd></div><div><dt>动作代码</dt><dd>{item.action}</dd></div><div><dt>对象</dt><dd>{item.targetType} · {item.targetId}</dd></div></dl>
                    <div><strong>留存的原始元数据</strong><pre>{Object.keys(item.metadata).length ? JSON.stringify(item.metadata, null, 2) : "无附加元数据"}</pre></div>
                    <p>此处仅展示系统已有留痕。若需判断操作是否符合授权，应结合当时的授权状态和业务证据人工复核。</p>
                  </div>
                </details>
              ))}
            </div>
            <div className="audit-pagination">
              <button className="secondary" disabled={auditLoading || audits.page <= 1} onClick={() => void loadAudits({ ...appliedAuditFilters, page: audits.page - 1 })}>上一页</button>
              <button className="secondary" disabled={auditLoading || audits.page >= auditPageCount} onClick={() => void loadAudits({ ...appliedAuditFilters, page: audits.page + 1 })}>下一页</button>
            </div>
          </section>
        ) : (
          <section className="registration-panel panel">
            <AccountSetup token={token} onCreated={async () => { const result = await getElderAccounts(token); setElderAccounts(result.items); }} />
            <div className="panel-heading"><div><p>待审核</p><h2>家属注册申请</h2></div><span>{applications.length} 项</span></div>
            <p className="registration-intro">仅核验申请人身份与关系信息。密码以安全哈希保存，审核人员无法查看。</p>
            {loading && <div className="empty">正在读取申请队列…</div>}
            {!loading && applications.length === 0 && <div className="empty">当前没有待审核的注册申请</div>}
            <div className="application-list">{applications.map((application) => <article key={application.id} className="application-row"><div><strong>{application.displayName}</strong><p>{application.relationship} · 申请关联：{application.elderName}</p><small>{application.loginIdentifier} · 提交于 {formatTime(application.createdAt)}</small><p className="registration-caution">请在独立渠道核实老人本人意愿与申请人关系；同名、年龄相符不等于已核验。</p></div><div className="registration-actions registration-verification"><label>选择已核验的老人账号<select value={applicationElders[application.id] ?? ""} onChange={(event) => setApplicationElders((current) => ({ ...current, [application.id]: event.target.value }))}><option value="">请选择</option>{elderAccounts.map((elder) => <option key={elder.id} value={elder.id}>{elder.displayName} · {elder.age} 岁 · {elder.id.slice(-8)}</option>)}</select></label><label>身份及关系核验依据（通过前必填）<textarea value={applicationNotes[application.id] ?? ""} maxLength={500} onChange={(event) => setApplicationNotes((current) => ({ ...current, [application.id]: event.target.value }))} placeholder="记录核验方式与本人同意情况，不填写证件号码" /></label><div><button className="secondary" disabled={reviewingId !== null} onClick={() => { void reviewApplication(application, "rejected"); }}>驳回</button><button className="primary" disabled={reviewingId !== null || !applicationElders[application.id] || !applicationNotes[application.id]?.trim()} onClick={() => { void reviewApplication(application, "approved"); }}>{reviewingId === application.id ? "提交中…" : "通过并授权"}</button></div></div></article>)}</div>
          </section>
        )}
      </section>
    </main>
  );
}
