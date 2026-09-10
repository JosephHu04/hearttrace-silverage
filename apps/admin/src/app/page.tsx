"use client";

import { useEffect, useMemo, useState } from "react";
import { demoLogin, getRiskDetail, getRiskQueue, performRiskAction } from "@/lib/admin-api";
import type { Actor, RiskAction, RiskDetail, RiskListItem, RiskStatus } from "@/lib/types";

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
  const [actor, setActor] = useState<Actor | null>(null);
  const [token, setToken] = useState("");
  const [risks, setRisks] = useState<RiskListItem[]>([]);
  const [selected, setSelected] = useState<RiskDetail | null>(null);
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<RiskAction | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("正在连接共享业务后端");

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

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span>心</span><div><strong>心迹银龄</strong><small>管理工作台</small></div></div>
        <nav aria-label="管理端主导航">
          <button className="nav-item active"><span>01</span>风险复核</button>
          <button className="nav-item" disabled><span>02</span>安全事件<em>待接入</em></button>
          <button className="nav-item" disabled><span>03</span>关系与授权<em>待接入</em></button>
          <button className="nav-item" disabled><span>04</span>设备管理<em>待接入</em></button>
          <button className="nav-item" disabled><span>05</span>审计查询<em>已开放 API</em></button>
        </nav>
        <div className="sidebar-note">
          <span className="connection-dot" />
          {error ? "服务需要检查" : "权限校验正常"}
          <small>浏览器不计算风险等级或授权范围</small>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div><p>风险复核 / 今日工作</p><h1>先处理需要人工判断的事项</h1></div>
          <div className="actor"><span>{actor?.displayName?.slice(0, 1) ?? "管"}</span><div><strong>{actor?.displayName ?? "正在登录"}</strong><small>{actor?.role ?? "—"}</small></div></div>
        </header>

        <div className={error ? "notice error" : "notice"} role="status">
          <b>{error ? "!" : "i"}</b>{error || notice}
        </div>

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
      </section>
    </main>
  );
}
