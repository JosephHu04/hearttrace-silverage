"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, completeFamilyCarePlanItem, createFamilyCarePlanItem, getFamilyCarePlan, getFamilyElders, getFamilyToday, getFamilyTrend, getNotifications, markNotificationRead, recordFamilyAction } from "@/lib/family-api";
import type { FamilyAction, FamilyCarePlanItem, FamilyElder, FamilyToday, FamilyTrend, NotificationCategory, NotificationItem, NotificationList } from "@/lib/types";

type PageKey = "today" | "report" | "trend" | "risk" | "notifications" | "plan" | "privacy";

const navigation: { key: PageKey; label: string; icon: string }[] = [
  { key: "today", label: "今日关怀", icon: "☀" },
  { key: "report", label: "每日关怀报告", icon: "✦" },
  { key: "trend", label: "心境趋势", icon: "⌁" },
  { key: "risk", label: "风险提醒", icon: "◉" },
  { key: "notifications", label: "消息通知", icon: "●" },
  { key: "plan", label: "陪伴计划", icon: "□" },
  { key: "privacy", label: "隐私与授权", icon: "⌘" }
];

const pageTitles: Record<PageKey, string> = {
  today: "今天，适合轻轻问候一下",
  report: "每日关怀报告",
  trend: "心境趋势",
  risk: "风险提醒与行动",
  notifications: "消息通知",
  plan: "陪伴计划",
  privacy: "隐私与授权"
};

const notificationLabels: Record<NotificationCategory, string> = {
  emergency: "安全事件",
  risk_follow_up: "关怀跟进",
  registration: "注册审核",
  authorization: "授权变更",
  analysis_summary: "关怀摘要"
};

function Tag({ children, tone = "calm" }: { children: React.ReactNode; tone?: "calm" | "warm" | "alert" | "safe" }) {
  return <span className={`tag tag-${tone}`}>{children}</span>;
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

export default function FamilyDashboard() {
  const router = useRouter();
  const [page, setPage] = useState<PageKey>("today");
  const [action, setAction] = useState("尚未记录行动");
  const [notice, setNotice] = useState("正在读取已授权的摘要、趋势和安全事件状态。");
  const [today, setToday] = useState<FamilyToday | null>(null);
  const [trend, setTrend] = useState<FamilyTrend | null>(null);
  const [trendDays, setTrendDays] = useState<7 | 30>(7);
  const [carePlan, setCarePlan] = useState<FamilyCarePlanItem[]>([]);
  const [elders, setElders] = useState<FamilyElder[]>([]);
  const [selectedElderId, setSelectedElderId] = useState<string | null>(null);
  const [apiState, setApiState] = useState<"loading" | "connected" | "unavailable" | "denied" | "signed_out">("loading");
  const [actorName, setActorName] = useState("—");
  const [token, setToken] = useState<string | null>(null);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [greeting, setGreeting] = useState("");
  const [notifications, setNotifications] = useState<NotificationList>({ items: [], unreadCount: 0, page: 1, perPage: 25, total: 0 });
  const [notificationLoading, setNotificationLoading] = useState(false);
  const [notificationBusy, setNotificationBusy] = useState<string | null>(null);

  useEffect(() => {
    setGreeting(new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date()));
  }, []);

  useEffect(() => {
    let active = true;

    const stored = sessionStorage.getItem("hearttrace.family.session");
    if (!stored) {
      setSessionChecked(true);
      setApiState("signed_out");
      router.replace("/account");
      return () => { active = false; };
    }
    let session: { accessToken: string; actor: { displayName: string; role: string } };
    try {
      session = JSON.parse(stored) as { accessToken: string; actor: { displayName: string; role: string } };
      if (!session.accessToken || session.actor.role !== "family") throw new Error("invalid family session");
    } catch {
      sessionStorage.removeItem("hearttrace.family.session");
      setSessionChecked(true);
      setApiState("signed_out");
      router.replace("/account");
      return () => { active = false; };
    }

    setSessionChecked(true);
    setApiState("loading");
    setActorName(session.actor.displayName);
    setToken(session.accessToken);
    setNotice("正在读取已授权的老人关系。");
    setNotificationLoading(true);
    void getNotifications(session.accessToken)
      .then((result) => {
        if (active) setNotifications(result);
      })
      .catch(() => {
        if (active) setNotice("老人授权数据已连接，但消息通知暂时无法读取。");
      })
      .finally(() => {
        if (active) setNotificationLoading(false);
      });
    void getFamilyElders(session.accessToken)
      .then((result) => {
        if (result.items.length === 0) {
          if (!active) return;
          setToday(null);
          setSelectedElderId(null);
          setElders([]);
          setApiState("denied");
          setPage("notifications");
          setNotice("该账号暂无有效老人授权，仍可查看本人账号与授权变更通知。");
          return;
        }
        if (!active) return;
        setElders(result.items);
        setSelectedElderId(result.items[0].id);
      })
      .catch((cause) => {
        if (!active) return;
        if (cause instanceof ApiError && cause.status === 401) {
          sessionStorage.removeItem("hearttrace.family.session");
          setToken(null);
          setToday(null);
          setApiState("signed_out");
          setNotice("登录状态已过期，请重新登录。");
          router.replace("/account");
          return;
        }
        setToken(null);
        setToday(null);
        setApiState("unavailable");
        setNotice("暂时无法连接核心 API，未展示任何老人数据。请稍后重试。");
      });

    return () => {
      active = false;
    };
  }, [router]);

  useEffect(() => {
    if (!token || !selectedElderId) return;
    let active = true;
    setApiState("loading");
    setAction("尚未记录行动");
    setNotice("正在读取当前老人的授权摘要、趋势、计划与安全状态。");
    void Promise.all([
      getFamilyToday(token, selectedElderId),
      getFamilyTrend(token, selectedElderId, trendDays),
      getFamilyCarePlan(token, selectedElderId)
    ])
      .then(([todayData, trendData, planData]) => {
        if (!active) return;
        setToday(todayData);
        setTrend(trendData);
        setCarePlan(planData);
        setApiState("connected");
        setNotice(`已读取授权摘要、${trendData.items.length} 条趋势记录与私人关怀计划，当前老人：${todayData.elder.name}。`);
      })
      .catch((cause) => {
        if (!active) return;
        setToday(null);
        setTrend(null);
        setCarePlan([]);
        if (cause instanceof ApiError && cause.status === 401) {
          sessionStorage.removeItem("hearttrace.family.session");
          setToken(null);
          setApiState("signed_out");
          router.replace("/account");
          return;
        }
        if (cause instanceof ApiError && cause.status === 403) {
          setApiState("denied");
          setNotice("老人授权已撤回或当前关系未生效，未展示任何关怀数据。");
          return;
        }
        setApiState("unavailable");
        setNotice("暂时无法读取该老人的授权数据，未展示任何模拟或缓存信息。请稍后重试。");
      });
    return () => { active = false; };
  }, [token, selectedElderId, trendDays, router]);

  const logout = () => {
    sessionStorage.removeItem("hearttrace.family.session");
    setToken(null);
    setApiState("signed_out");
    router.replace("/account");
  };

  const loadNotifications = async () => {
    if (!token) return;
    setNotificationLoading(true);
    try {
      setNotifications(await getNotifications(token));
    } catch {
      setNotice("消息通知暂时无法读取，请稍后重试。");
    } finally {
      setNotificationLoading(false);
    }
  };

  const readNotification = async (item: NotificationItem) => {
    if (!token || item.isRead) return;
    setNotificationBusy(item.id);
    try {
      const result = await markNotificationRead(token, item.id);
      setNotifications((current) => ({
        ...current,
        unreadCount: Math.max(0, current.unreadCount - 1),
        items: current.items.map((entry) => entry.id === item.id ? result.notification : entry)
      }));
      setNotice("消息已标记为已读。");
    } catch {
      setNotice("消息状态暂未更新，请稍后重试。");
    } finally {
      setNotificationBusy(null);
    }
  };

  const openNotification = async (item: NotificationItem) => {
    if (!item.isRead) await readNotification(item);
    if (!token || apiState !== "connected" || !selectedElderId) {
      setNotice("当前授权未生效，只能查看通知内容，不能打开老人关怀数据。");
      return;
    }
    const destination: Partial<Record<NotificationCategory, PageKey>> = {
      emergency: "risk",
      risk_follow_up: "risk",
      analysis_summary: "report",
      authorization: "privacy"
    };
    try {
      setToday(await getFamilyToday(token, selectedElderId));
      setPage(destination[item.category] ?? "notifications");
      setNotice("已从消息刷新当前授权数据。");
    } catch {
      setApiState("denied");
      setPage("notifications");
      setNotice("授权状态已经变化，通知仍可查看，但老人关怀数据已停止返回。");
    }
  };

  const recordAction = async (nextAction: FamilyAction, label: string) => {
    try {
      if (!token || !today) throw new Error("当前登录或摘要不可用");
      if (!today.riskEventId) throw new Error("当前没有可关联的风险事件");
      if (!today.access.careActionsAllowed) throw new Error("当前授权不包含关怀行动");
      const recorded = await recordFamilyAction(token, today.riskEventId, nextAction);
      setAction(`已记录：${label}`);
      setToday((current) => current ? ({
        ...current,
        recentActions: [{ action: nextAction, recordedAt: recorded.recordedAt }, ...current.recentActions].slice(0, 5)
      }) : current);
      setNotice(`关怀行动“${label}”已提交。该记录会进入家属端的后续审计与跟进流程。`);
    } catch {
      setAction(`待同步：${label}`);
      setNotice("行动暂未同步到服务端，请在网络恢复后重试。演示数据没有被视为正式记录。");
    }
  };

  const addCarePlan = async (title: string, scheduledFor?: string) => {
    if (!token || !selectedElderId || !today?.access.careActionsAllowed) return;
    const normalizedTitle = title.trim();
    if (normalizedTitle.length < 2) {
      setNotice("请至少填写两个字的关怀计划内容。");
      return;
    }
    try {
      const item = await createFamilyCarePlanItem(token, selectedElderId, normalizedTitle, scheduledFor);
      setCarePlan((items) => [...items, item]);
      setNotice("关怀计划已保存，只有当前已授权家属可查看和完成它。");
    } catch {
      setNotice("关怀计划暂未保存，请检查网络和授权后重试。");
      throw new Error("care plan save failed");
    }
  };

  const completeCarePlan = async (itemId: string) => {
    if (!token || !selectedElderId || !today?.access.careActionsAllowed) return;
    try {
      const completed = await completeFamilyCarePlanItem(token, selectedElderId, itemId);
      setCarePlan((items) => items.map((item) => item.id === itemId ? completed : item));
      setNotice("已完成的关怀计划已保存，并已写入审计记录。");
    } catch {
      setNotice("计划状态暂未更新，请稍后重试。");
    }
  };

  if (!sessionChecked) {
    return <main className="auth-loading" aria-live="polite"><div><span className="auth-loading-mark">心</span><p>正在验证登录状态…</p></div></main>;
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">心</div>
          <div><strong>心迹银龄</strong><span>家属关怀台</span></div>
        </div>

        <div className="elder-switcher">
          <div className="elder-avatar">{apiState === "denied" || elders.length === 0 ? "—" : (elders.find((elder) => elder.id === selectedElderId)?.name ?? "—").slice(0, 1)}</div>
          <div><strong>{apiState === "denied" ? "无授权老人" : elders.find((elder) => elder.id === selectedElderId)?.name ?? "正在读取"}</strong><span>{apiState === "denied" ? "服务端未返回数据" : elders.find((elder) => elder.id === selectedElderId) ? `${elders.find((elder) => elder.id === selectedElderId)?.age} 岁 · 已授权` : "正在核对授权"}</span></div>
          {elders.length > 1 && <select aria-label="切换老人" className="elder-select" value={selectedElderId ?? ""} onChange={(event) => setSelectedElderId(event.target.value)}>{elders.map((elder) => <option key={elder.id} value={elder.id}>{elder.name}</option>)}</select>}
        </div>

        <nav aria-label="家属端导航">
          {navigation.map((item) => (
            <button key={item.key} className={`nav-item ${page === item.key ? "active" : ""}`} onClick={() => { setPage(item.key); if (item.key === "notifications") void loadNotifications(); }}>
              <span>{item.icon}</span>{item.label}{item.key === "notifications" && notifications.unreadCount > 0 && <b>{notifications.unreadCount}</b>}
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
          <div><p suppressHydrationWarning>{greeting || "今日关怀"}</p><h1>{pageTitles[page]}</h1></div>
          <div className="top-actions">
            <Tag tone={page === "notifications" && token ? "calm" : apiState === "connected" ? "safe" : "alert"}>{page === "notifications" && token ? "本人消息" : apiState === "connected" ? "已授权查看" : "暂不可查看"}</Tag>
            {token ? <><a className="profile" href="/account/security">账户安全</a><button className="profile" onClick={logout}>{actorName} · 退出</button></> : <a className="profile" href="/account">登录家属账号</a>}
          </div>
        </header>

        <div className="notice" role="status"><span>i</span>{notice}</div>

        {page === "notifications" && token ? (
          <NotificationView notifications={notifications} loading={notificationLoading} busyId={notificationBusy} canOpenCare={apiState === "connected"} onRefresh={loadNotifications} onRead={readNotification} onOpen={openNotification} />
        ) : apiState !== "connected" || !today ? (
          <Card className="access-denied"><Tag tone="alert">{apiState === "signed_out" ? "需要登录" : apiState === "denied" ? "暂未授权" : "服务不可用"}</Tag><h2>{apiState === "signed_out" ? "登录后才能查看关怀信息" : apiState === "denied" ? "当前账号暂未获得老人授权" : "暂时无法读取关怀数据"}</h2><p>{apiState === "signed_out" ? "仅已获管理端批准的家属账号可登录。" : "为保护老人隐私，页面不会在异常状态下展示任何模拟或缓存的老人数据。"}</p>{apiState === "signed_out" && <a className="primary" href="/account">前往登录</a>}</Card>
        ) : (
          <>
            {page === "today" && <TodayView today={today} action={action} onAction={recordAction} onNavigate={() => setPage("report")} />}
            {page === "report" && <ReportView today={today} />}
            {page === "trend" && <TrendView today={today} trend={trend} selectedDays={trendDays} onSelectDays={setTrendDays} />}
            {page === "risk" && <RiskView today={today} action={action} onAction={recordAction} />}
            {page === "plan" && <PlanView today={today} items={carePlan} onAction={recordAction} onAddItem={addCarePlan} onCompleteItem={completeCarePlan} />}
            {page === "privacy" && <PrivacyView today={today} />}
          </>
        )}
      </div>
    </main>
  );
}

function NotificationView({ notifications, loading, busyId, canOpenCare, onRefresh, onRead, onOpen }: { notifications: NotificationList; loading: boolean; busyId: string | null; canOpenCare: boolean; onRefresh: () => Promise<void>; onRead: (item: NotificationItem) => Promise<void>; onOpen: (item: NotificationItem) => Promise<void> }) {
  return <Card className="family-notifications">
    <div className="card-heading notification-heading"><div><p className="muted">只属于当前账号</p><h2>业务消息</h2><small>授权撤销后仍可查看本人收到的授权结果，但不能继续读取老人数据。</small></div><div><Tag tone={notifications.unreadCount > 0 ? "warm" : "safe"}>{notifications.unreadCount} 条未读</Tag><button className="secondary" disabled={loading} onClick={() => { void onRefresh(); }}>{loading ? "刷新中…" : "刷新"}</button></div></div>
    <div className="family-notification-list">
      {loading && <div className="notification-empty">正在读取消息…</div>}
      {!loading && notifications.items.length === 0 && <div className="notification-empty">暂时没有业务消息</div>}
      {!loading && notifications.items.map((item) => {
        const hasCareDestination = ["emergency", "risk_follow_up", "analysis_summary", "authorization"].includes(item.category);
        return <article className={item.isRead ? "read" : "unread"} key={item.id}>
          <span className={`family-notification-kind ${item.category}`}>{notificationLabels[item.category]}</span>
          <div><div className="family-notification-title"><h3>{item.title}</h3>{!item.isRead && <b>未读</b>}</div><p>{item.body}</p><small>{formatDateTime(item.createdAt)}</small></div>
          <div className="family-notification-actions">
            {!item.isRead && <button className="secondary" disabled={busyId === item.id} onClick={() => { void onRead(item); }}>{busyId === item.id ? "处理中…" : "标为已读"}</button>}
            {hasCareDestination && <button className="primary" disabled={busyId === item.id || !canOpenCare} title={canOpenCare ? undefined : "当前无有效老人授权"} onClick={() => { void onOpen(item); }}>查看关怀</button>}
          </div>
        </article>;
      })}
    </div>
  </Card>;
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

function TrendView({ today, trend, selectedDays, onSelectDays }: { today: FamilyToday; trend: FamilyTrend | null; selectedDays: 7 | 30; onSelectDays: (days: 7 | 30) => void }) {
  const points = trend?.items ?? [];
  const chartPoints = points.map((item, index) => {
    const x = points.length === 1 ? 220 : (440 / (points.length - 1)) * index;
    const y = 108 - (Math.max(0, Math.min(100, item.score)) * 0.9);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const dateLabel = (value: string) => new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(new Date(value));
  return <div className="page-grid trend-grid">
    <Card className="trend-card"><div className="card-heading"><div><p className="muted">近 {selectedDays} 天</p><h2>只与{today.elder.name}自己的基线比较</h2></div><div className="segmented"><button className={selectedDays === 7 ? "selected" : ""} onClick={() => onSelectDays(7)}>7 天</button><button className={selectedDays === 30 ? "selected" : ""} onClick={() => onSelectDays(30)}>30 天</button></div></div>{points.length === 0 ? <div className="empty-chart"><b>暂无足够的趋势记录</b><span>后续经人工确认的每日摘要会在这里按天展示。</span></div> : <><div className="chart-wrap"><div className="chart-y"><span>100</span><span>75</span><span>50</span><span>25</span></div><svg viewBox="0 0 450 120" role="img" aria-label={`近${selectedDays}天关怀趋势图`}><defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#c9c6f4" stopOpacity=".55"/><stop offset="1" stopColor="#c9c6f4" stopOpacity="0"/></linearGradient></defs>{points.length > 1 && <path d={`M0,120 L${chartPoints} L440,120 Z`} fill="url(#fill)"/>}<polyline points={chartPoints} fill="none" stroke="#6f6ab5" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>{chartPoints.split(" ").map((point, index) => { const [cx, cy] = point.split(","); return <circle key={`${points[index].recordedAt}-${point}`} cx={cx} cy={cy} r="4" fill="#fff" stroke="#6f6ab5" strokeWidth="2"><title>{`${dateLabel(points[index].recordedAt)} · ${points[index].score} 分 · ${points[index].label}`}</title></circle>; })}</svg></div><div className="chart-labels">{points.map((item) => <span key={item.recordedAt}>{dateLabel(item.recordedAt)}</span>)}</div></>}</Card>
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

function PlanView({ today, items, onAction, onAddItem, onCompleteItem }: { today: FamilyToday; items: FamilyCarePlanItem[]; onAction: (action: FamilyAction, label: string) => Promise<void>; onAddItem: (title: string, scheduledFor?: string) => Promise<void>; onCompleteItem: (itemId: string) => Promise<void> }) {
  const [title, setTitle] = useState("");
  const [scheduledFor, setScheduledFor] = useState("");
  const [saving, setSaving] = useState(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    try {
      await onAddItem(title, scheduledFor ? new Date(scheduledFor).toISOString() : undefined);
      setTitle("");
      setScheduledFor("");
    } catch {
      // The parent keeps the actionable error message in the shared status area.
    } finally {
      setSaving(false);
    }
  };
  return <div className="page-grid plan-grid"><Card className="plan-hero"><p className="muted">下一次陪伴</p><h2>和{today.elder.name}约一个舒服的时间</h2><p>由本人决定是否接通。视频功能接入后，只会打开已绑定的联络路径，不保存通话内容。</p><button className="primary" disabled={!today.access.careActionsAllowed || !today.riskEventId} onClick={() => { void onAction("video_planned", "已确认视频问候安排"); }}>记录视频安排</button></Card><Card><p className="muted">新增计划</p><form className="plan-form" onSubmit={submit}><label>关怀事项<input value={title} maxLength={140} disabled={!today.access.careActionsAllowed || saving} onChange={(event) => setTitle(event.target.value)} placeholder="例如：周末一起整理相册" /></label><label>计划时间（可选）<input type="datetime-local" value={scheduledFor} disabled={!today.access.careActionsAllowed || saving} onChange={(event) => setScheduledFor(event.target.value)} /></label><button className="secondary" disabled={!today.access.careActionsAllowed || saving}>{saving ? "正在保存…" : "保存关怀计划"}</button></form></Card><Card><p className="muted">本周清单</p><h3>只属于当前家属的计划</h3>{items.length === 0 ? <p>还没有计划。可以从一句问候或一次短通话开始。</p> : <div className="task-list">{items.map((item) => <label key={item.id} className={item.completedAt ? "task-done" : ""}><input type="checkbox" checked={Boolean(item.completedAt)} disabled={Boolean(item.completedAt) || !today.access.careActionsAllowed} onChange={() => { void onCompleteItem(item.id); }} /> <span>{item.title}</span>{item.scheduledFor && <small>{formatDateTime(item.scheduledFor)}</small>}</label>)}</div>}</Card><Card><p className="muted">最近关怀记录</p><h3>已同步到服务端</h3>{today.recentActions.length === 0 ? <p>尚未记录关怀行动。</p> : <div className="action-history">{today.recentActions.map((item, index) => <div key={`${item.action}-${item.recordedAt}-${index}`}><b>{actionLabel(item.action)}</b><span>{formatDateTime(item.recordedAt)}</span></div>)}</div>}</Card><Card><p className="muted">关怀话题</p><h3>避免“盘问式”关心</h3><div className="prompt-chips"><span>今天阳光好吗？</span><span>昨晚睡得还好吗？</span><span>最近有什么开心的事？</span></div></Card></div>;
}

function PrivacyView({ today }: { today: FamilyToday }) {
  const hasScope = (scope: string) => today.access.scopes.includes(scope);
  return <div className="page-grid privacy-grid"><Card className="privacy-head"><Tag tone="safe">授权状态有效</Tag><h2>{today.elder.name}始终可以查看、调整或撤回授权。</h2><p>家属可访问的范围以本人确认的授权为准。撤回后，服务端将立即停止对应接口返回。</p></Card><Card className="permission-card"><p className="muted">当前授权范围</p><div className="permission-row"><span>每日关怀摘要</span><Tag tone={hasScope("daily_summary") ? "safe" : "calm"}>{hasScope("daily_summary") ? "已授权" : "未授权"}</Tag></div><div className="permission-row"><span>提交关怀行动</span><Tag tone={hasScope("care_actions") ? "safe" : "calm"}>{hasScope("care_actions") ? "已授权" : "未授权"}</Tag></div><div className="permission-row"><span>完整聊天全文</span><Tag tone="calm">未授权</Tag></div><div className="permission-row"><span>设备事件短片段</span><Tag tone="calm">未授权</Tag></div></Card><Card className="audit-card"><p className="muted">访问记录</p><h3>透明且可追溯</h3><p>通过核心 API 的摘要查看与关怀行动均写入审计日志，可由管理端核对。</p></Card></div>;
}
