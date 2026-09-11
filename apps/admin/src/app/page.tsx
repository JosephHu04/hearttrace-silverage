"use client";

import { useEffect, useMemo, useState } from "react";
import { demoLogin, getAuditLogs, getElderCandidates, getRegistrationApplications, getRiskDetail, getRiskQueue, performRiskAction, reviewRegistrationApplication } from "@/lib/admin-api";
import type { Actor, AuditFilters, AuditListResponse, ElderCandidate, RegistrationApplication, RiskAction, RiskDetail, RiskListItem, RiskStatus } from "@/lib/types";

type AdminView = "risk" | "audit" | "registrations";

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
  "family.referral_requested": "家属申请专业转介"
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
  const [elderCandidates, setElderCandidates] = useState<ElderCandidate[]>([]);
  const [selectedElders, setSelectedElders] = useState<Record<string, string>>({});

  useEffect(() => {
    let active = true;
    async function boot() {
      try {
        const login = await demoLogin();
        if (!active) return;
        setActor(login.actor);
        setToken(login.accessToken);
        const queue = await getRiskQueue(login.accessToken);
        if (!active) return;
        setRisks(queue.items);
        const registrationQueue = await getRegistrationApplications(login.accessToken);
        if (!active) return;
        setApplications(registrationQueue.items);
        const eligibleElders = await getElderCandidates(login.accessToken);
        if (!active) return;
        setElderCandidates(eligibleElders);
        if (queue.items[0]) {
          const detail = await getRiskDetail(login.accessToken, queue.items[0].id);
          if (!active) return;
          setSelected(detail);
        }
        setNotice("已连接真实 API · 当前仅展示结构化证据");
      } catch (cause) {
        if (!active) return;
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
  }, []);

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

  const openView = (view: AdminView) => {
    setActiveView(view);
    setError("");
    if (view === "audit" && audits.items.length === 0) void loadAudits(emptyAuditFilters);
    if (view === "registrations") {
      void getRegistrationApplications(token).then((queue) => setApplications(queue.items)).catch(() => setError("读取注册申请失败"));
    }
  };

  const auditPageCount = Math.max(1, Math.ceil(audits.total / audits.perPage));

  const reviewApplication = async (application: RegistrationApplication, decision: "approved" | "rejected") => {
    if (!token) return;
    setReviewingId(application.id);
    setError("");
    try {
      await reviewRegistrationApplication(token, application.id, decision, selectedElders[application.id]);
      setApplications((current) => current.filter((item) => item.id !== application.id));
      setNotice(decision === "approved" ? "申请已通过，家属账户已激活。" : "申请已驳回，结果已写入审计记录。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "审核提交失败");
    } finally {
      setReviewingId(null);
    }
  };

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span>心</span><div><strong>心迹银龄</strong><small>管理工作台</small></div></div>
        <nav aria-label="管理端主导航">
          <button className={`nav-item ${activeView === "risk" ? "active" : ""}`} onClick={() => openView("risk")}><span>01</span>风险复核</button>
          <button className={`nav-item ${activeView === "registrations" ? "active" : ""}`} onClick={() => openView("registrations")}><span>02</span>注册审核{applications.length > 0 && <em>{applications.length} 待办</em>}</button>
          <button className="nav-item" disabled><span>03</span>安全事件<em>待接入</em></button>
          <button className="nav-item" disabled><span>04</span>关系与授权<em>待接入</em></button>
          <button className="nav-item" disabled><span>05</span>设备管理<em>待接入</em></button>
          <button className={`nav-item ${activeView === "audit" ? "active" : ""}`} onClick={() => openView("audit")}><span>06</span>审计查询</button>
        </nav>
        <div className="sidebar-note">
          <span className="connection-dot" />
          {error ? "服务需要检查" : "权限校验正常"}
          <small>浏览器不计算风险等级或授权范围</small>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div><p>{activeView === "risk" ? "风险复核 / 今日工作" : activeView === "audit" ? "审计查询 / 操作留痕" : "账号管理 / 关系核验"}</p><h1>{activeView === "risk" ? "先处理需要人工判断的事项" : activeView === "audit" ? "核对每一次敏感读取与人工操作" : "审核家属账户申请"}</h1></div>
          <div className="actor"><span>{actor?.displayName?.slice(0, 1) ?? "管"}</span><div><strong>{actor?.displayName ?? "正在登录"}</strong><small>{actor?.role ?? "—"}</small></div></div>
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
        </> : activeView === "audit" ? (
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
            <div className="panel-heading"><div><p>待审核</p><h2>家属注册申请</h2></div><span>{applications.length} 项</span></div>
            <p className="registration-intro">核验申请人身份与关系，并在通过前确认对应老人。密码以安全哈希保存，审核人员无法查看。</p>
            {loading && <div className="empty">正在读取申请队列…</div>}
            {!loading && applications.length === 0 && <div className="empty">当前没有待审核的注册申请</div>}
            <div className="application-list">{applications.map((application) => <article key={application.id} className="application-row"><div><strong>{application.displayName}</strong><p>{application.relationship} · 申请关联：{application.elderName}</p><small>{application.loginIdentifier} · 提交于 {formatTime(application.createdAt)}</small></div><div className="registration-actions"><select aria-label={`为${application.displayName}选择对应老人`} value={selectedElders[application.id] ?? ""} onChange={(event) => setSelectedElders((current) => ({ ...current, [application.id]: event.target.value }))}><option value="">确认对应老人</option>{elderCandidates.map((elder) => <option key={elder.id} value={elder.id}>{elder.name} · {elder.age} 岁</option>)}</select><button className="secondary" disabled={reviewingId !== null} onClick={() => { void reviewApplication(application, "rejected"); }}>驳回</button><button className="primary" disabled={reviewingId !== null || !selectedElders[application.id]} onClick={() => { void reviewApplication(application, "approved"); }}>{reviewingId === application.id ? "提交中…" : "通过并授权"}</button></div></article>)}</div>
          </section>
        )}
      </section>
    </main>
  );
}
