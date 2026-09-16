"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, changeFamilyGrant, getAuditLogs, getElderAccounts, getEmergencyQueue, getFamilyGrants, getNotifications, getRegistrationApplications, getRiskDetail, getRiskQueue, markNotificationRead, performEmergencyAction, performRiskAction, reviewRegistrationApplication } from "@/lib/admin-api";
import { clearAdminSession, readAdminSession } from "@/lib/admin-session";
import { AccountSetup } from "./account-setup";
import type { Actor, AuditFilters, AuditListResponse, AuthorizationScope, ElderAccount, EmergencyAction, EmergencyEvent, EmergencyStatus, FamilyGrant, GrantAction, NotificationCategory, NotificationItem, NotificationListResponse, RegistrationApplication, RiskAction, RiskDetail, RiskListItem, RiskStatus } from "@/lib/types";

type AdminView = "risk" | "emergency" | "relationships" | "notifications" | "audit" | "registrations";

const emptyAuditFilters: AuditFilters = { actorId: "", action: "", targetType: "", targetId: "", page: 1, perPage: 25 };

const auditActionLabels: Record<string, string> = {
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
  "family.contacted": "家属记录已联系",
  "family.video_planned": "家属安排视频联络",
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
  "analysis.completed": "完成结构化关怀分析",
  "analysis.skipped": "因授权变化跳过分析",
  "analysis.failed": "关怀分析任务失败",
  "analysis.summary_published": "发布已复核家属摘要",
  "notification.read": "读取站内通知",
  "notification.delivered": "确认通知投递",
  "notification.delivery_failed": "通知投递失败"
};

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

const actionableNotificationTargets = new Set(["risk_event", "emergency_event", "registration_application", "family_elder_grant"]);

const viewHeadings: Record<AdminView, { eyebrow: string; title: string }> = {
  risk: { eyebrow: "风险复核 / 今日工作", title: "先处理需要人工判断的事项" },
  emergency: { eyebrow: "安全事件 / 紧急求助", title: "确认每一条求助都得到人工响应" },
  relationships: { eyebrow: "关系管理 / 授权范围", title: "让每一次访问都有明确授权依据" },
  notifications: { eyebrow: "通知中心 / 个人待办", title: "从业务提醒直接进入处置闭环" },
  audit: { eyebrow: "审计查询 / 操作留痕", title: "核对每一次敏感读取与人工操作" },
  registrations: { eyebrow: "账号管理 / 关系核验", title: "审核家属账户申请" }
};

function formatTime(value: string | null) {
  if (!value) return "未设置";
  return new Intl.DateTimeFormat("zh-CN", {
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
  const [selectedEmergency, setSelectedEmergency] = useState<EmergencyEvent | null>(null);
  const [emergencyNote, setEmergencyNote] = useState("");
  const [emergencyBusy, setEmergencyBusy] = useState<EmergencyAction | null>(null);
  const [elderAccounts, setElderAccounts] = useState<ElderAccount[]>([]);
  const [applicationElders, setApplicationElders] = useState<Record<string, string>>({});
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
        const queue = await getRiskQueue(session.accessToken);
        if (!active) return;
        setRisks(queue.items);
        const emergencyQueue = await getEmergencyQueue(session.accessToken);
        if (!active) return;
        setEmergencies(emergencyQueue.items);
        setSelectedEmergency(emergencyQueue.items[0] ?? null);
        const elders = await getElderAccounts(session.accessToken);
        if (!active) return;
        setElderAccounts(elders.items);
        const grantQueue = await getFamilyGrants(session.accessToken);
        if (!active) return;
        setGrants(grantQueue.items);
        setGrantDrafts(Object.fromEntries(grantQueue.items.map((grant) => [`${grant.familyId}:${grant.elderId}`, grant.scopes])));
        const notificationQueue = await getNotifications(session.accessToken);
        if (!active) return;
        setNotifications(notificationQueue);
        if (queue.items[0]) {
          const detail = await getRiskDetail(session.accessToken, queue.items[0].id);
          if (!active) return;
          setSelected(detail);
        }
        setNotice("已连接真实 API · 当前仅展示结构化证据");
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
      setNotice(`已读取 ${result.total} 条审计记录`);
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

  const recordNotificationRead = async (item: NotificationItem) => {
    if (!token || item.isRead) return;
    setNotificationBusy(item.id);
    setError("");
    try {
      await markNotificationRead(token, item.id);
      await loadNotifications(notifications.page, notificationUnreadOnly);
      setNotice("通知已标记为已读，操作已写入审计日志");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "更新通知状态失败");
    } finally {
      setNotificationBusy(null);
    }
  };

  const openNotificationTarget = async (item: NotificationItem) => {
    if (!token) return;
    if (!item.isRead) await recordNotificationRead(item);
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
    if (view === "audit" && audits.items.length === 0) void loadAudits(emptyAuditFilters);
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
  };

  const auditPageCount = Math.max(1, Math.ceil(audits.total / audits.perPage));
  const notificationPageCount = Math.max(1, Math.ceil(notifications.total / notifications.perPage));

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
    setReviewingId(application.id);
    setError("");
    try {
      await reviewRegistrationApplication(token, application.id, decision, elderId);
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
          <button className={`nav-item ${activeView === "registrations" ? "active" : ""}`} onClick={() => openView("registrations")}><span>02</span>注册审核{applications.length > 0 && <em>{applications.length} 待办</em>}</button>
          <button className={`nav-item ${activeView === "emergency" ? "active" : ""}`} onClick={() => openView("emergency")}><span>03</span>安全事件{emergencies.filter((item) => ["open", "acknowledged"].includes(item.status)).length > 0 && <em>{emergencies.filter((item) => ["open", "acknowledged"].includes(item.status)).length} 待办</em>}</button>
          <button className={`nav-item ${activeView === "relationships" ? "active" : ""}`} onClick={() => openView("relationships")}><span>04</span>关系与授权<em>{grants.filter((grant) => grant.isActive).length} 生效</em></button>
          <button className={`nav-item ${activeView === "notifications" ? "active" : ""}`} onClick={() => openView("notifications")}><span>05</span>通知中心{notifications.unreadCount > 0 && <em>{notifications.unreadCount} 未读</em>}</button>
          <button className="nav-item" disabled><span>06</span>设备管理<em>待接入</em></button>
          <button className={`nav-item ${activeView === "audit" ? "active" : ""}`} onClick={() => openView("audit")}><span>07</span>审计查询</button>
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
          <div className="actor"><span>{actor?.displayName?.slice(0, 1) ?? "管"}</span><div><strong>{actor?.displayName ?? "管理员"}</strong><small>管理员</small></div><button className="actor-logout" onClick={logout}>退出</button></div>
        </header>

        <div className={error ? "notice error" : "notice"} role="status">
          <b>{error ? "!" : "i"}</b>{error || notice}
        </div>

        {activeView === "risk" ? <>
        <section className="metrics" aria-label="风险概览">
          <article><p>开放事项</p><strong>{loading ? "—" : activeCount}</strong><small>等待认领或处置</small></article>
          <article className="urgent"><p>橙红风险</p><strong>{loading ? "—" : urgentCount}</strong><small>优先完成复核</small></article>
          <article><p>当前队列</p><strong>{loading ? "—" : risks.length}</strong><small>已按创建时间排序</small></article>
          <article><p>证据策略</p><strong className="text-value">结构化</strong><small>默认不返回聊天全文</small></article>
        </section>

        <section className="review-layout">
          <div className="queue-panel panel">
            <div className="panel-heading"><div><p>待办队列</p><h2>风险事件</h2></div><span>{risks.length} 项</span></div>
            <div className="queue-list">
              {loading && <div className="empty">正在读取风险队列…</div>}
              {!loading && risks.length === 0 && <div className="empty">当前没有待复核事件</div>}
              {risks.map((risk) => (
                <button
                  key={risk.id}
                  className={`queue-item ${selected?.id === risk.id ? "selected" : ""}`}
                  onClick={() => { void selectRisk(risk); }}
                >
                  <div className="queue-top"><span className={`level ${risk.level}`}>{risk.level === "red" ? "红色" : risk.level === "orange" ? "橙色" : "关注"}</span><time>{formatTime(risk.slaDueAt)}</time></div>
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
                  <div><div className="detail-meta"><span className={`level ${selected.level}`}>{selected.level.toUpperCase()}</span><span>{statusLabels[selected.status]}</span><span>版本 {selected.version}</span></div><h2>{selected.title}</h2><p>{selected.summary}</p></div>
                  <div className="elder-card"><small>服务对象</small><strong>{selected.elderName}</strong><span>{selected.elderId}</span></div>
                </div>

                <div className="detail-columns">
                  <section>
                    <div className="section-title"><div><p>可解释证据</p><h3>三类来源共同支持复核</h3></div><span>不含聊天全文</span></div>
                    <div className="evidence-list">
                      {selected.evidence.map((item, index) => (
                        <article key={item.id}>
                          <span>{String(index + 1).padStart(2, "0")}</span>
                          <div><small>{item.label}</small><strong>{item.detail}</strong><p>引用：{item.evidenceRef}</p></div>
                        </article>
                      ))}
                    </div>
                    <div className="versions"><span>模型 {selected.modelVersion ?? "未使用"}</span><span>规则 {selected.ruleVersion}</span></div>
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
        </> : activeView === "emergency" ? (
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
              <span><strong>{notifications.total}</strong> {notificationUnreadOnly ? "条未读结果" : "条通知"}</span>
              <small>第 {notifications.page}/{notificationPageCount} 页</small>
            </div>
            <div className="notification-list" aria-live="polite">
              {notificationLoading && <div className="empty">正在读取通知…</div>}
              {!notificationLoading && notifications.items.length === 0 && <div className="empty">{notificationUnreadOnly ? "当前没有未读通知" : "当前没有业务通知"}</div>}
              {!notificationLoading && notifications.items.map((item) => (
                <article className={`notification-item ${item.isRead ? "read" : "unread"}`} key={item.id}>
                  <span className={`notification-category ${item.category}`}>{notificationCategoryLabels[item.category]}</span>
                  <div className="notification-copy">
                    <div><h3>{item.title}</h3>{!item.isRead && <b>未读</b>}</div>
                    <p>{item.body}</p>
                    <small>{formatTime(item.createdAt)} · {item.targetType} · {item.targetId}</small>
                  </div>
                  <div className="notification-actions">
                    {!item.isRead && <button className="secondary" disabled={notificationBusy === item.id} onClick={() => void recordNotificationRead(item)}>{notificationBusy === item.id ? "处理中…" : "标为已读"}</button>}
                    {actionableNotificationTargets.has(item.targetType) && <button className="primary" disabled={notificationBusy === item.id} onClick={() => void openNotificationTarget(item)}>查看相关事项</button>}
                  </div>
                </article>
              ))}
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
                  <option value="risk.viewed">查看风险详情</option>
                  <option value="risk.claim">认领风险事件</option>
                  <option value="risk.begin_review">开始人工复核</option>
                  <option value="risk.request_action">要求跟进</option>
                  <option value="risk.escalate">升级处置</option>
                  <option value="risk.resolve">记录已解决</option>
                  <option value="risk.mark_false_positive">标记误报</option>
                  <option value="risk.close">关闭风险事件</option>
                  <option value="risk.reopen">重新打开</option>
                  <option value="family.today_viewed">家属查看摘要</option>
                  <option value="family.contacted">家属记录已联系</option>
                  <option value="family.video_planned">家属安排视频联络</option>
                  <option value="family.referral_requested">家属申请专业转介</option>
                  <option value="emergency.created">发起紧急求助</option>
                  <option value="emergency.acknowledge">确认收到求助</option>
                  <option value="emergency.resolve">解除紧急事件</option>
                  <option value="emergency.cancel">取消紧急事件</option>
                  <option value="emergency.reopen">重新打开紧急事件</option>
                  <option value="grant.created">创建家属授权</option>
                  <option value="grant.update_scopes">调整授权范围</option>
                  <option value="grant.revoke">撤销家属授权</option>
                  <option value="grant.reactivate">重新启用授权</option>
                  <option value="conversation.analysis_queued">提交授权会话分析</option>
                  <option value="analysis.completed">完成结构化关怀分析</option>
                  <option value="analysis.skipped">因授权变化跳过分析</option>
                  <option value="analysis.failed">关怀分析任务失败</option>
                  <option value="analysis.summary_published">发布已复核家属摘要</option>
                  <option value="notification.read">读取站内通知</option>
                  <option value="notification.delivered">确认通知投递</option>
                  <option value="notification.delivery_failed">通知投递失败</option>
                </select>
              </label>
              <label>操作者 ID
                <input value={auditFilters.actorId} onChange={(event) => setAuditFilters((current) => ({ ...current, actorId: event.target.value }))} placeholder="staff-admin-001" />
              </label>
              <label>对象类型
                <select value={auditFilters.targetType} onChange={(event) => setAuditFilters((current) => ({ ...current, targetType: event.target.value }))}>
                  <option value="">全部对象</option>
                  <option value="risk_event">风险事件</option>
                  <option value="elder">老人账号</option>
                  <option value="emergency_event">紧急事件</option>
                  <option value="family_elder_grant">家属授权关系</option>
                  <option value="conversation_session">陪伴会话</option>
                  <option value="conversation_analysis">结构化关怀分析</option>
                  <option value="daily_insight">家属每日摘要</option>
                  <option value="outbox_event">异步任务事件</option>
                  <option value="notification">站内通知</option>
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

            <div className="audit-summary"><div><p>查询结果</p><h2>敏感操作留痕</h2></div><span>{audits.total} 条记录 · 第 {audits.page}/{auditPageCount} 页</span></div>
            <div className="audit-table" role="table" aria-label="审计记录">
              <div className="audit-row audit-header" role="row"><span>时间</span><span>操作者</span><span>动作</span><span>对象</span><span>元数据</span></div>
              {auditLoading && <div className="empty">正在读取审计记录…</div>}
              {!auditLoading && audits.items.length === 0 && <div className="empty">没有符合条件的审计记录</div>}
              {!auditLoading && audits.items.map((item) => (
                <article className="audit-row" role="row" key={item.id}>
                  <time>{formatTime(item.createdAt)}</time>
                  <span><strong>{item.actorDisplayName ?? item.actorId}</strong><small>{item.actorId}</small></span>
                  <span><strong>{auditActionLabels[item.action] ?? item.action}</strong><small>{item.action}</small></span>
                  <span><strong>{item.targetType}</strong><small>{item.targetId}</small></span>
                  <code>{Object.keys(item.metadata).length ? JSON.stringify(item.metadata) : "—"}</code>
                </article>
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
            <div className="application-list">{applications.map((application) => <article key={application.id} className="application-row"><div><strong>{application.displayName}</strong><p>{application.relationship} · 申请关联：{application.elderName}</p><small>{application.loginIdentifier} · 提交于 {formatTime(application.createdAt)}</small></div><div className="registration-actions registration-verification"><label>核验老人账号<select value={applicationElders[application.id] ?? ""} onChange={(event) => setApplicationElders((current) => ({ ...current, [application.id]: event.target.value }))}><option value="">请选择</option>{elderAccounts.map((elder) => <option key={elder.id} value={elder.id}>{elder.displayName} · {elder.age} 岁</option>)}</select></label><div><button className="secondary" disabled={reviewingId !== null} onClick={() => { void reviewApplication(application, "rejected"); }}>驳回</button><button className="primary" disabled={reviewingId !== null || !applicationElders[application.id]} onClick={() => { void reviewApplication(application, "approved"); }}>{reviewingId === application.id ? "提交中…" : "通过并授权"}</button></div></div></article>)}</div>
          </section>
        )}
      </section>
    </main>
  );
}
