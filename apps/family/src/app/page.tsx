"use client";

import { useEffect, useMemo, useState } from "react";
import { getFamilyElders, getFamilyToday, recordFamilyAction } from "@/lib/family-api";
import { mockFamilyToday } from "@/lib/mock-family-data";
import type { FamilyAction, FamilyElder, FamilyToday } from "@/lib/types";

type PageKey = "today" | "report" | "trend" | "risk" | "plan" | "privacy";

const navigation: { key: PageKey; label: string; icon: string }[] = [
  { key: "today", label: "今日关怀", icon: "☀" },
  { key: "report", label: "每日关怀报告", icon: "✦" },
  { key: "trend", label: "心境趋势", icon: "⌁" },
  { key: "risk", label: "风险提醒", icon: "◉" },
  { key: "plan", label: "陪伴计划", icon: "□" },
  { key: "privacy", label: "隐私与授权", icon: "⌘" }
];

const pageTitles: Record<PageKey, string> = {
  today: "今天，适合轻轻问候一下",
  report: "每日关怀报告",
  trend: "心境趋势",
  risk: "风险提醒与行动",
  plan: "陪伴计划",
  privacy: "隐私与授权"
};

function Tag({ children, tone = "calm" }: { children: React.ReactNode; tone?: "calm" | "warm" | "alert" | "safe" }) {
  return <span className={`tag tag-${tone}`}>{children}</span>;
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

export default function FamilyDashboard() {
  const [page, setPage] = useState<PageKey>("today");
  const [action, setAction] = useState("尚未记录行动");
  const [notice, setNotice] = useState("正在读取已授权的摘要、趋势和安全事件状态。");
  const [today, setToday] = useState<FamilyToday>(mockFamilyToday);
  const [elders, setElders] = useState<FamilyElder[]>([]);
  const [selectedElderId, setSelectedElderId] = useState<string | null>(null);
  const [apiState, setApiState] = useState<"loading" | "connected" | "unavailable" | "denied" | "signed_out">("loading");
  const [actorName, setActorName] = useState("—");
  const [token, setToken] = useState<string | null>(null);

  const greeting = useMemo(() => new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date()), []);

  useEffect(() => {
    let active = true;

    const stored = sessionStorage.getItem("hearttrace.family.session");
    if (!stored) {
      setApiState("signed_out");
      setNotice("请先登录已获批的家属账号，再查看授权范围内的信息。");
      return () => { active = false; };
    }
    let session: { accessToken: string; actor: { displayName: string; role: string } };
    try {
      session = JSON.parse(stored) as { accessToken: string; actor: { displayName: string; role: string } };
      if (!session.accessToken || session.actor.role !== "family") throw new Error("invalid family session");
    } catch {
      sessionStorage.removeItem("hearttrace.family.session");
      setApiState("signed_out");
      setNotice("登录状态无效，请重新登录。");
      return () => { active = false; };
    }

    setApiState("loading");
    setNotice("正在读取已授权的老人关系。");
    void getFamilyElders(session.accessToken)
      .then((result) => {
        if (result.items.length === 0) {
          if (!active) return;
          setActorName(session.actor.displayName);
          setToken(session.accessToken);
          setApiState("denied");
          setNotice("该账号暂未获得任何老人的有效授权，服务端未返回老人数据。");
          return;
        }
        if (!active) return;
        setActorName(session.actor.displayName);
        setToken(session.accessToken);
        setElders(result.items);
        setSelectedElderId(result.items[0].id);
      })
      .catch(() => {
        if (!active) return;
        setToken(null);
        setApiState("unavailable");
        setNotice("暂时无法连接核心 API，未展示任何老人数据。请稍后重试。");
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!token || !selectedElderId) return;
    let active = true;
    setApiState("loading");
    setAction("尚未记录行动");
    setNotice("正在读取当前老人的授权摘要、关怀行动与安全状态。");
    void getFamilyToday(token, selectedElderId)
      .then((data) => {
        if (!active) return;
        setToday(data);
        setApiState("connected");
        setNotice(`已读取授权摘要，当前老人：${data.elder.name}。`);
      })
      .catch(() => {
        if (!active) return;
        setApiState("unavailable");
        setNotice("暂时无法读取该老人的授权数据，未展示任何模拟或缓存信息。请稍后重试。");
      });
    return () => { active = false; };
  }, [token, selectedElderId]);

  const logout = () => {
    sessionStorage.removeItem("hearttrace.family.session");
    setToken(null);
    setApiState("signed_out");
    setNotice("你已退出登录。");
  };

  const recordAction = async (nextAction: FamilyAction, label: string) => {
    try {
      if (!today.riskEventId) throw new Error("当前没有可关联的风险事件");
      if (!today.access.careActionsAllowed) throw new Error("当前授权不包含关怀行动");
      const recorded = await recordFamilyAction(token, today.riskEventId, nextAction);
      setAction(`已记录：${label}`);
      setToday((current) => ({
        ...current,
        recentActions: [{ action: nextAction, recordedAt: recorded.recordedAt }, ...current.recentActions].slice(0, 5)
      }));
      setNotice(`关怀行动“${label}”已提交。该记录会进入家属端的后续审计与跟进流程。`);
    } catch {
      setAction(`待同步：${label}`);
      setNotice("行动暂未同步到服务端，请在网络恢复后重试。演示数据没有被视为正式记录。");
    }
  };

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">心</div>
          <div><strong>心迹银龄</strong><span>家属关怀台</span></div>
        </div>

        <div className="elder-switcher">
          <div className="elder-avatar">{apiState === "denied" || elders.length === 0 ? "—" : (elders.find((elder) => elder.id === selectedElderId)?.name ?? today.elder.name).slice(0, 1)}</div>
          <div><strong>{apiState === "denied" ? "无授权老人" : elders.find((elder) => elder.id === selectedElderId)?.name ?? today.elder.name}</strong><span>{apiState === "denied" ? "服务端未返回数据" : `${elders.find((elder) => elder.id === selectedElderId)?.age ?? today.elder.age} 岁 · 已授权`}</span></div>
          {elders.length > 1 && <select aria-label="切换老人" className="elder-select" value={selectedElderId ?? ""} onChange={(event) => setSelectedElderId(event.target.value)}>{elders.map((elder) => <option key={elder.id} value={elder.id}>{elder.name}</option>)}</select>}
        </div>

        <nav aria-label="家属端导航">
          {navigation.map((item) => (
            <button key={item.key} className={`nav-item ${page === item.key ? "active" : ""}`} onClick={() => setPage(item.key)}>
              <span>{item.icon}</span>{item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span className="live-dot" /> {apiState === "connected" ? "授权状态正常" : "访问受限"}
          <small>{apiState === "connected" ? "已连接核心业务 API" : apiState === "loading" ? "正在连接数据服务" : apiState === "denied" ? "无有效老人授权" : apiState === "signed_out" ? "需要登录" : "服务暂不可用"}</small>
        </div>
      </aside>

      <div className="content-shell">
        <header className="topbar">
          <div><p>{greeting}</p><h1>{pageTitles[page]}</h1></div>
          <div className="top-actions">
            <Tag tone={apiState === "connected" ? "safe" : "alert"}>{apiState === "connected" ? "已授权查看" : "暂不可查看"}</Tag>
            {apiState === "connected" ? <button className="profile" onClick={logout}>{actorName} · 退出</button> : <a className="profile" href="/account">登录家属账号</a>}
          </div>
        </header>

        <div className="notice" role="status"><span>i</span>{notice}</div>

        {apiState !== "connected" ? (
          <Card className="access-denied"><Tag tone="alert">{apiState === "signed_out" ? "需要登录" : apiState === "denied" ? "暂未授权" : "服务不可用"}</Tag><h2>{apiState === "signed_out" ? "登录后才能查看关怀信息" : apiState === "denied" ? "当前账号暂未获得老人授权" : "暂时无法读取关怀数据"}</h2><p>{apiState === "signed_out" ? "仅已获管理端批准的家属账号可登录。" : "为保护老人隐私，页面不会在异常状态下展示任何模拟或缓存的老人数据。"}</p>{apiState === "signed_out" && <a className="primary" href="/account">前往登录</a>}</Card>
        ) : (
          <>
            {page === "today" && <TodayView today={today} action={action} onAction={recordAction} onNavigate={() => setPage("report")} />}
            {page === "report" && <ReportView today={today} />}
            {page === "trend" && <TrendView today={today} />}
            {page === "risk" && <RiskView today={today} action={action} onAction={recordAction} />}
            {page === "plan" && <PlanView today={today} onAction={recordAction} />}
            {page === "privacy" && <PrivacyView today={today} />}
          </>
        )}
      </div>
    </main>
  );
}

function TodayView({ today, action, onAction, onNavigate }: { today: FamilyToday; action: string; onAction: (action: FamilyAction, label: string) => Promise<void>; onNavigate: () => void }) {
  const baselineDescription = today.status.baselineDelta < 0 ? `下降 ${Math.abs(today.status.baselineDelta)} 分` : today.status.baselineDelta > 0 ? `上升 ${today.status.baselineDelta} 分` : "持平";

  return <div className="page-grid today-grid">
    <Card className="hero-card">
      <div className="eyebrow">今日状态 <Tag tone="warm">{today.status.label}</Tag></div>
      <h2>{today.status.headline}</h2>
      <p>{today.status.summary}</p>
      <div className="hero-actions"><button className="primary" disabled={!today.access.careActionsAllowed || !today.riskEventId} onClick={() => { void onAction("contacted", "已电话联系"); }}>我已联系</button><button className="secondary" disabled={!today.access.careActionsAllowed || !today.riskEventId} onClick={() => { void onAction("video_planned", "计划晚间视频联络"); }}>安排视频联络</button></div>
      <small>{action}</small>
    </Card>

    <Card className="score-card">
      <p className="muted">今日关怀指数</p><div className="score-row"><strong>{today.status.score}</strong><span>/ 100</span></div>
      <div className="meter"><i style={{ width: `${today.status.score}%` }} /></div><p className="score-caption">较个人近 7 天基线 <b>{baselineDescription}</b></p>
    </Card>

    <Card className="summary-card">
      <div className="card-heading"><div><p className="muted">今日摘要</p><h3>今日授权主题</h3></div><button className="text-button" onClick={onNavigate}>查看报告 →</button></div>
      <div className="topic-list">{today.topics.map((topic) => <div key={topic.name}><span className={`topic-dot ${topic.tone}`} />{topic.name} <b>{topic.note}</b></div>)}</div>
    </Card>

    <Card className="timeline-card">
      <p className="muted">建议的关怀节奏</p><h3>把关心变成一件具体的小事</h3>
      <div className="timeline"><div><span>现在</span><b>发一句语音或打个电话</b><small>问问昨晚睡得怎么样</small></div><div><span>今晚</span><b>安排 10 分钟视频联络</b><small>尊重本人意愿，可让家人一起问候</small></div><div><span>本周</span><b>确定一次线下探望</b><small>不强制，由家人共同商量</small></div></div>
    </Card>
  </div>;
}

function ReportView({ today }: { today: FamilyToday }) {
  return <div className="page-grid report-grid">
    <Card className="report-head"><div><Tag tone="calm">今日</Tag><h2>{today.status.headline}</h2><p>{today.status.summary} 这是一份辅助关怀摘要，不是心理疾病诊断。</p></div><div className="report-score"><span>关怀指数</span><strong>{today.status.score}</strong><small>个人基线对比</small></div></Card>
    <Card><p className="muted">授权主题</p><h3>今天值得留意的事</h3><ul className="clean-list">{today.topics.map((topic) => <li key={topic.name}>{topic.name}：{topic.note}</li>)}</ul></Card>
    <Card><p className="muted">关怀建议</p><h3>从倾听开始</h3><ol className="number-list"><li>先问睡眠，不急着给建议。</li><li>邀请她决定视频通话时间。</li><li>若低落持续，建议完成一次标准筛查。</li></ol></Card>
    <Card className="evidence-card"><div className="card-heading"><div><p className="muted">可追溯线索</p><h3>仅展示授权后的结构化摘要</h3></div><Tag tone="safe">授权有效</Tag></div><div className="evidence-row"><span>主题</span><b>{today.topics[0]?.name ?? "暂无"}</b><em>{today.topics[0]?.note ?? "暂无摘要"}</em></div><div className="evidence-row"><span>趋势</span><b>较个人基线 {today.status.baselineDelta >= 0 ? "+" : ""}{today.status.baselineDelta} 分</b><em>仅作关怀参考</em></div></Card>
  </div>;
}

function TrendView({ today }: { today: FamilyToday }) {
  const points = "0,74 55,62 110,66 165,45 220,52 275,38 330,47 385,41 440,58";
  return <div className="page-grid trend-grid">
    <Card className="trend-card"><div className="card-heading"><div><p className="muted">近 7 天</p><h2>只与{today.elder.name}自己的基线比较</h2></div><div className="segmented"><button className="selected">7 天</button><button>30 天</button></div></div><div className="chart-wrap"><div className="chart-y"><span>90</span><span>70</span><span>50</span><span>30</span></div><svg viewBox="0 0 450 120" role="img" aria-label="近七日心境趋势图"><defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#c9c6f4" stopOpacity=".55"/><stop offset="1" stopColor="#c9c6f4" stopOpacity="0"/></linearGradient></defs><path d={`M0,120 L${points} L440,120 Z`} fill="url(#fill)"/><polyline points={points} fill="none" stroke="#6f6ab5" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>{points.split(" ").map((point) => { const [cx, cy] = point.split(","); return <circle key={point} cx={cx} cy={cy} r="4" fill="#fff" stroke="#6f6ab5" strokeWidth="2"/>; })}</svg></div><div className="chart-labels"><span>周四</span><span>周五</span><span>周六</span><span>周日</span><span>周一</span><span>周二</span><span>今天</span></div></Card>
    <Card className="baseline-card"><p className="muted">趋势说明</p><h3>今天较个人基线 {today.status.baselineDelta >= 0 ? `高 ${today.status.baselineDelta}` : `低 ${Math.abs(today.status.baselineDelta)}`} 分</h3><p>变化仅用于安排关怀节奏，不直接推断疾病。</p><Tag tone={today.status.level === "green" ? "safe" : "warm"}>{today.status.label}</Tag></Card>
    <Card className="screening-card"><p className="muted">标准化筛查</p><h3>最近一次：尚未完成</h3><p>如本人愿意，可由老人端完成固定题目的自评量表；结果仅作为进一步关怀的参考。</p><button className="secondary">查看授权说明</button></Card>
  </div>;
}

function actionLabel(action: FamilyAction) {
  return { contacted: "已联系", video_planned: "安排视频联络", referral_requested: "申请专业转介" }[action];
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function RiskView({ today, action, onAction }: { today: FamilyToday; action: string; onAction: (action: FamilyAction, label: string) => Promise<void> }) {
  const levelLabel = { green: "绿色 · 状态平稳", yellow: "黄色 · 待观察", orange: "橙色 · 需要关注", red: "红色 · 紧急" }[today.status.level];
  const urgency = { green: "低", yellow: "低", orange: "中", red: "高" }[today.status.level];
  return <div className="page-grid risk-grid">
    <Card className="risk-overview"><div><Tag tone={today.status.level === "red" ? "alert" : today.status.level === "green" ? "safe" : "warm"}>{levelLabel}</Tag><h2>{today.safety.message}</h2><p>系统提示以温和联系为主。若出现一键呼救、确认跌倒或明确生命安全危机，系统将升级为红色事件。</p></div><div className="risk-ring"><b>{urgency}</b><span>紧急程度</span></div></Card>
    <Card className="action-card"><p className="muted">本次待办</p><h3>完成一项关怀行动</h3><button className="primary full" disabled={!today.access.careActionsAllowed || !today.riskEventId} onClick={() => { void onAction("contacted", "已电话联系"); }}>记录已联系</button><button className="secondary full" disabled={!today.access.careActionsAllowed || !today.riskEventId} onClick={() => { void onAction("referral_requested", "申请专业转介"); }}>申请专业转介</button><small>{today.access.careActionsAllowed ? action : "当前授权仅允许查看摘要，不能提交关怀行动。"}</small></Card>
    <Card className="event-card"><div className="card-heading"><div><p className="muted">安全事件</p><h3>一键呼救与设备事件</h3></div><Tag tone={today.safety.hasActiveEmergency ? "alert" : "safe"}>{today.safety.hasActiveEmergency ? "处理中" : "暂无事件"}</Tag></div><p>{today.safety.message}</p>{today.safety.hasActiveEmergency && <div className="event-meta"><span>{today.safety.source === "device_button" ? "设备实体求助键" : "老人端一键呼救"}</span>{today.safety.triggeredAt && <span>发起于 {formatDateTime(today.safety.triggeredAt)}</span>}</div>}<small>家属端只显示事件状态和必要说明；不默认开放摄像头画面或日常视频。</small></Card>
  </div>;
}

function PlanView({ today, onAction }: { today: FamilyToday; onAction: (action: FamilyAction, label: string) => Promise<void> }) {
  return <div className="page-grid plan-grid"><Card className="plan-hero"><p className="muted">下一次陪伴</p><h2>今晚 19:30 · 视频问候</h2><p>由{today.elder.name}决定是否接通。系统只负责打开已绑定的联络路径，不保存微信通话内容。</p><button className="primary" disabled={!today.access.careActionsAllowed || !today.riskEventId} onClick={() => { void onAction("video_planned", "已确认今晚视频问候"); }}>确认安排</button></Card><Card><p className="muted">本周清单</p><div className="task-list"><label><input type="checkbox" defaultChecked /> 发一条轻松的早安语音</label><label><input type="checkbox" /> 询问是否愿意视频聊天</label><label><input type="checkbox" /> 与家人协调周末探望</label></div></Card><Card><p className="muted">最近关怀记录</p><h3>已同步到服务端</h3>{today.recentActions.length === 0 ? <p>尚未记录关怀行动。</p> : <div className="action-history">{today.recentActions.map((item, index) => <div key={`${item.action}-${item.recordedAt}-${index}`}><b>{actionLabel(item.action)}</b><span>{formatDateTime(item.recordedAt)}</span></div>)}</div>}</Card><Card><p className="muted">关怀话题</p><h3>避免“盘问式”关心</h3><div className="prompt-chips"><span>今天阳光好吗？</span><span>昨晚睡得还好吗？</span><span>最近有什么开心的事？</span></div></Card></div>;
}

function PrivacyView({ today }: { today: FamilyToday }) {
  const hasScope = (scope: string) => today.access.scopes.includes(scope);
  return <div className="page-grid privacy-grid"><Card className="privacy-head"><Tag tone="safe">授权状态有效</Tag><h2>{today.elder.name}始终可以查看、调整或撤回授权。</h2><p>家属可访问的范围以本人确认的授权为准。撤回后，服务端将立即停止对应接口返回。</p></Card><Card className="permission-card"><p className="muted">当前授权范围</p><div className="permission-row"><span>每日关怀摘要</span><Tag tone={hasScope("daily_summary") ? "safe" : "calm"}>{hasScope("daily_summary") ? "已授权" : "未授权"}</Tag></div><div className="permission-row"><span>提交关怀行动</span><Tag tone={hasScope("care_actions") ? "safe" : "calm"}>{hasScope("care_actions") ? "已授权" : "未授权"}</Tag></div><div className="permission-row"><span>完整聊天全文</span><Tag tone="calm">未授权</Tag></div><div className="permission-row"><span>设备事件短片段</span><Tag tone="calm">未授权</Tag></div></Card><Card className="audit-card"><p className="muted">访问记录</p><h3>透明且可追溯</h3><p>通过核心 API 的摘要查看与关怀行动均写入审计日志，可由管理端核对。</p></Card></div>;
}
