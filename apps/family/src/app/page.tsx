"use client";

import { useEffect, useMemo, useState } from "react";
import { getFamilyToday, recordFamilyAction } from "@/lib/family-api";
import { mockFamilyToday } from "@/lib/mock-family-data";
import type { FamilyAction, FamilyToday } from "@/lib/types";

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
  const elderId = "elder-demo-001";
  const [page, setPage] = useState<PageKey>("today");
  const [action, setAction] = useState("尚未记录行动");
  const [notice, setNotice] = useState("正在读取已授权的摘要、趋势和安全事件状态。");
  const [today, setToday] = useState<FamilyToday>(mockFamilyToday);
  const [apiState, setApiState] = useState<"loading" | "connected" | "fallback">("loading");

  const greeting = useMemo(() => new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date()), []);

  useEffect(() => {
    let active = true;

    void getFamilyToday(elderId)
      .then((data) => {
        if (!active) return;
        setToday(data);
        setApiState("connected");
        setNotice("已读取家属端 Mock API。正式联调时只需配置 NEXT_PUBLIC_API_BASE_URL。");
      })
      .catch(() => {
        if (!active) return;
        setApiState("fallback");
        setNotice("暂时无法连接 API，正在使用本地演示数据。");
      });

    return () => {
      active = false;
    };
  }, [elderId]);

  const recordAction = async (nextAction: FamilyAction, label: string) => {
    try {
      await recordFamilyAction("risk-demo-001", nextAction);
      setAction(`已记录：${label}`);
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
          <div className="elder-avatar">陈</div>
          <div><strong>{today.elder.name}</strong><span>{today.elder.age} 岁 · 已授权</span></div>
          <button aria-label="切换老人" className="icon-button">⌄</button>
        </div>

        <nav aria-label="家属端导航">
          {navigation.map((item) => (
            <button key={item.key} className={`nav-item ${page === item.key ? "active" : ""}`} onClick={() => setPage(item.key)}>
              <span>{item.icon}</span>{item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span className="live-dot" /> 授权状态正常
          <small>{apiState === "connected" ? "已连接家属端 Mock API" : apiState === "loading" ? "正在连接数据服务" : "本地演示数据模式"}</small>
        </div>
      </aside>

      <div className="content-shell">
        <header className="topbar">
          <div><p>{greeting}</p><h1>{pageTitles[page]}</h1></div>
          <div className="top-actions"><Tag tone="safe">已授权查看</Tag><button className="profile">林女士 <span>⌄</span></button></div>
        </header>

        <div className="notice" role="status"><span>i</span>{notice}</div>

        {page === "today" && <TodayView today={today} action={action} onAction={recordAction} onNavigate={() => setPage("report")} />}
        {page === "report" && <ReportView />}
        {page === "trend" && <TrendView />}
        {page === "risk" && <RiskView today={today} action={action} onAction={recordAction} />}
        {page === "plan" && <PlanView onAction={recordAction} />}
        {page === "privacy" && <PrivacyView />}
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
      <div className="hero-actions"><button className="primary" onClick={() => { void onAction("contacted", "已电话联系"); }}>我已联系她</button><button className="secondary" onClick={() => { void onAction("video_planned", "计划晚间视频联络"); }}>安排视频联络</button></div>
      <small>{action}</small>
    </Card>

    <Card className="score-card">
      <p className="muted">今日关怀指数</p><div className="score-row"><strong>{today.status.score}</strong><span>/ 100</span></div>
      <div className="meter"><i style={{ width: `${today.status.score}%` }} /></div><p className="score-caption">较个人近 7 天基线 <b>{baselineDescription}</b></p>
    </Card>

    <Card className="summary-card">
      <div className="card-heading"><div><p className="muted">今日摘要</p><h3>她谈到了什么</h3></div><button className="text-button" onClick={onNavigate}>查看报告 →</button></div>
      <div className="topic-list">{today.topics.map((topic) => <div key={topic.name}><span className={`topic-dot ${topic.tone}`} />{topic.name} <b>{topic.note}</b></div>)}</div>
    </Card>

    <Card className="timeline-card">
      <p className="muted">建议的关怀节奏</p><h3>把关心变成一件具体的小事</h3>
      <div className="timeline"><div><span>现在</span><b>发一句语音或打个电话</b><small>问问她昨晚睡得怎么样</small></div><div><span>今晚</span><b>安排 10 分钟视频联络</b><small>如她愿意，可让家人一起问候</small></div><div><span>本周</span><b>确定一次线下探望</b><small>不强制，由家人共同商量</small></div></div>
    </Card>
  </div>;
}

function ReportView() {
  return <div className="page-grid report-grid">
    <Card className="report-head"><div><Tag tone="calm">9 月 10 日</Tag><h2>情绪整体平稳，夜间睡眠话题值得温和跟进。</h2><p>这是一份辅助关怀摘要，不是心理疾病诊断。每项结论均由授权对话的主题、趋势或量表结果支持。</p></div><div className="report-score"><span>心境</span><strong>72</strong><small>个人基线 78</small></div></Card>
    <Card><p className="muted">积极片段</p><h3>值得延续的事</h3><ul className="clean-list"><li>午后晒太阳并和邻居聊了几句</li><li>主动提到想给孙女讲年轻时的故事</li><li>愿意尝试明晚和家人视频聊天</li></ul></Card>
    <Card><p className="muted">关怀建议</p><h3>从倾听开始</h3><ol className="number-list"><li>先问睡眠，不急着给建议。</li><li>邀请她决定视频通话时间。</li><li>若低落持续，建议完成一次标准筛查。</li></ol></Card>
    <Card className="evidence-card"><div className="card-heading"><div><p className="muted">可追溯线索</p><h3>仅展示授权后的主题摘要</h3></div><Tag tone="safe">授权有效</Tag></div><div className="evidence-row"><span>主题</span><b>睡眠变浅</b><em>来自今日 2 个会话摘要</em></div><div className="evidence-row"><span>趋势</span><b>近 3 天晚间心境略降</b><em>个人基线对比</em></div></Card>
  </div>;
}

function TrendView() {
  const points = "0,74 55,62 110,66 165,45 220,52 275,38 330,47 385,41 440,58";
  return <div className="page-grid trend-grid">
    <Card className="trend-card"><div className="card-heading"><div><p className="muted">近 7 天</p><h2>只与她自己的基线比较</h2></div><div className="segmented"><button className="selected">7 天</button><button>30 天</button></div></div><div className="chart-wrap"><div className="chart-y"><span>90</span><span>70</span><span>50</span><span>30</span></div><svg viewBox="0 0 450 120" role="img" aria-label="近七日心境趋势图"><defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#c9c6f4" stopOpacity=".55"/><stop offset="1" stopColor="#c9c6f4" stopOpacity="0"/></linearGradient></defs><path d={`M0,120 L${points} L440,120 Z`} fill="url(#fill)"/><polyline points={points} fill="none" stroke="#6f6ab5" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>{points.split(" ").map((point) => { const [cx, cy] = point.split(","); return <circle key={point} cx={cx} cy={cy} r="4" fill="#fff" stroke="#6f6ab5" strokeWidth="2"/>; })}</svg></div><div className="chart-labels"><span>周四</span><span>周五</span><span>周六</span><span>周日</span><span>周一</span><span>周二</span><span>今天</span></div></Card>
    <Card className="baseline-card"><p className="muted">趋势说明</p><h3>今天比个人基线低 6 分</h3><p>变化仍处于轻度观察区间。建议以联系、陪伴和作息关怀为先，不直接推断疾病。</p><Tag tone="warm">连续观察 3 天</Tag></Card>
    <Card className="screening-card"><p className="muted">标准化筛查</p><h3>最近一次：尚未完成</h3><p>如本人愿意，可由老人端完成固定题目的自评量表；结果仅作为进一步关怀的参考。</p><button className="secondary">查看授权说明</button></Card>
  </div>;
}

function RiskView({ today, action, onAction }: { today: FamilyToday; action: string; onAction: (action: FamilyAction, label: string) => Promise<void> }) {
  return <div className="page-grid risk-grid">
    <Card className="risk-overview"><div><Tag tone="warm">黄色 · 待观察</Tag><h2>{today.safety.message}</h2><p>系统提示以温和联系为主。若出现一键呼救、确认跌倒或明确生命安全危机，系统将升级为红色事件。</p></div><div className="risk-ring"><b>低</b><span>紧急程度</span></div></Card>
    <Card className="action-card"><p className="muted">本次待办</p><h3>完成一项关怀行动</h3><button className="primary full" onClick={() => { void onAction("contacted", "已电话联系"); }}>记录已联系</button><button className="secondary full" onClick={() => { void onAction("referral_requested", "申请专业转介"); }}>申请专业转介</button><small>{action}</small></Card>
    <Card className="event-card"><div className="card-heading"><div><p className="muted">安全事件</p><h3>一键呼救与设备事件</h3></div><Tag tone={today.safety.hasActiveEmergency ? "alert" : "safe"}>{today.safety.hasActiveEmergency ? "处理中" : "暂无事件"}</Tag></div><p>家属端只显示事件状态、处置时限和必要说明；不默认开放摄像头画面或日常视频。</p></Card>
  </div>;
}

function PlanView({ onAction }: { onAction: (action: FamilyAction, label: string) => Promise<void> }) {
  return <div className="page-grid plan-grid"><Card className="plan-hero"><p className="muted">下一次陪伴</p><h2>今晚 19:30 · 视频问候</h2><p>由陈奶奶决定是否接通。系统只负责打开已绑定的联络路径，不保存微信通话内容。</p><button className="primary" onClick={() => { void onAction("video_planned", "已确认今晚视频问候"); }}>确认安排</button></Card><Card><p className="muted">本周清单</p><div className="task-list"><label><input type="checkbox" defaultChecked /> 发一条轻松的早安语音</label><label><input type="checkbox" /> 询问是否愿意视频聊天</label><label><input type="checkbox" /> 与家人协调周末探望</label></div></Card><Card><p className="muted">关怀话题</p><h3>避免“盘问式”关心</h3><div className="prompt-chips"><span>今天阳光好吗？</span><span>昨晚睡得还好吗？</span><span>想不想听孙女说说学校？</span></div></Card></div>;
}

function PrivacyView() {
  return <div className="page-grid privacy-grid"><Card className="privacy-head"><Tag tone="safe">授权状态有效</Tag><h2>陈奶奶始终可以查看、调整或撤回授权。</h2><p>家属可访问的范围以她本人确认的授权为准。撤回后，服务端将立即停止对应接口返回。</p></Card><Card className="permission-card"><p className="muted">当前授权范围</p><div className="permission-row"><span>每日关怀摘要</span><Tag tone="safe">已授权</Tag></div><div className="permission-row"><span>心境趋势与量表结果</span><Tag tone="safe">已授权</Tag></div><div className="permission-row"><span>风险相关片段</span><Tag tone="safe">已授权</Tag></div><div className="permission-row"><span>完整聊天全文</span><Tag tone="calm">未授权</Tag></div><div className="permission-row"><span>设备事件短片段</span><Tag tone="calm">未授权</Tag></div></Card><Card className="audit-card"><p className="muted">最近访问记录</p><h3>透明且可追溯</h3><div className="audit-line"><b>今天 09:24</b><span>林女士查看今日关怀摘要</span></div><div className="audit-line"><b>昨天 20:16</b><span>林女士记录“已电话联系”</span></div><button className="text-button">导出我的访问记录 →</button></Card></div>;
}
