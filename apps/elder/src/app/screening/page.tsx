"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import styles from "./screening.module.css";

const API_ORIGIN = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000")
  .replace(/\/api\/?$/, "")
  .replace(/\/$/, "");
const API_BASE = `${API_ORIGIN}/api`;

type InstrumentCode = "gds15" | "gad7";
type Choice = { value: string; label: string };
type Question = { itemCode: string; number: number; text: string; choices: Choice[] };
type Instrument = {
  code: InstrumentCode;
  version: string;
  name: string;
  purpose: string;
  timeframe: string;
  standardReference: string;
  itemCount: number;
};
type ScreeningSession = {
  id: string;
  instrument: Instrument;
  status: "in_progress" | "completed";
  progressAnswered: number;
  currentQuestion: Question | null;
  result: null | {
    totalScore: number;
    scoreRange: string;
    band: "normal" | "moderate" | "high";
    label: string;
    recommendation: string;
    notice: string;
  };
};

export default function ScreeningPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [selected, setSelected] = useState<InstrumentCode>("gds15");
  const [consent, setConsent] = useState(false);
  const [shareFamily, setShareFamily] = useState(false);
  const [shareCareTeam, setShareCareTeam] = useState(false);
  const [screening, setScreening] = useState<ScreeningSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    try {
      const stored = JSON.parse(sessionStorage.getItem("hearttrace.elder.session") ?? "null");
      if (!stored?.accessToken || stored.actor?.role !== "elder" || Date.parse(stored.expiresAt) <= Date.now()) throw new Error("expired");
      setToken(stored.accessToken);
      void fetch(`${API_BASE}/screenings/instruments`, {
        headers: { Authorization: `Bearer ${stored.accessToken}` }
      }).then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "暂时无法读取量表");
        setInstruments(body.items ?? []);
      }).catch((cause) => setError(cause instanceof Error ? cause.message : "暂时无法读取量表"));
    } catch {
      sessionStorage.removeItem("hearttrace.elder.session");
      router.replace("/account");
    }
  }, [router]);

  async function startScreening() {
    if (!token || !consent) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/elder/screenings`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          instrumentCode: selected,
          consentConfirmed: consent,
          shareWithFamily: shareFamily,
          shareWithCareTeam: shareCareTeam
        })
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "暂时无法开始测评");
      setScreening(body);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "暂时无法开始测评");
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswer(value: string) {
    if (!token || !screening?.currentQuestion) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/elder/screenings/${screening.id}/answers`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ itemCode: screening.currentQuestion.itemCode, value })
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "答案暂时没有保存成功");
      setScreening(body);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "答案暂时没有保存成功");
    } finally {
      setBusy(false);
    }
  }

  if (!token) return <main className={styles.shell}>正在确认登录状态…</main>;

  return <main className={styles.shell}>
    <header className={styles.header}>
      <Link href="/">返回首页</Link>
      <div><p>心迹银龄 · 标准关怀筛查</p><h1>慢慢回答，没有对错</h1></div>
    </header>

    {!screening && <section className={styles.card}>
      <p className={styles.notice}>这是本人自愿完成的标准化筛查，不是疾病诊断。题目与计分由固定程序处理，大模型不会替您回答。</p>
      <div className={styles.instruments}>
        {instruments.map((instrument) => <button
          type="button"
          key={instrument.code}
          className={selected === instrument.code ? styles.selected : ""}
          onClick={() => setSelected(instrument.code)}
        >
          <strong>{instrument.name}</strong>
          <span>{instrument.purpose}</span>
          <small>{instrument.timeframe} · 共 {instrument.itemCount} 题</small>
        </button>)}
      </div>
      <div className={styles.permissions}>
        <label><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /><span><b>我愿意现在完成这次筛查</b><small>可以随时返回；只有本人作答才会计分。</small></span></label>
        <label><input type="checkbox" checked={shareCareTeam} onChange={(event) => setShareCareTeam(event.target.checked)} /><span><b>完成后分享给关怀团队</b><small>工作人员只查看量表名称、分层和建议，不查看聊天全文。</small></span></label>
        <label><input type="checkbox" checked={shareFamily} onChange={(event) => setShareFamily(event.target.checked)} /><span><b>完成后分享给已授权家属</b><small>家属只看到完成状态和关怀建议，不看到逐题答案和总分。</small></span></label>
      </div>
      {error && <p className={styles.error} role="alert">{error}</p>}
      <button className={styles.primary} type="button" disabled={!consent || busy || instruments.length === 0} onClick={() => { void startScreening(); }}>{busy ? "正在准备…" : "开始答题"}</button>
      <small className={styles.source}>依据：WS/T 802—2022《中国健康老年人标准》附录B.3、B.4。</small>
    </section>}

    {screening?.status === "in_progress" && screening.currentQuestion && <section className={styles.card}>
      <div className={styles.progress}><span>第 {screening.currentQuestion.number} 题</span><span>共 {screening.instrument.itemCount} 题</span></div>
      <div className={styles.progressTrack}><i style={{ width: `${(screening.progressAnswered / screening.instrument.itemCount) * 100}%` }} /></div>
      <p className={styles.timeframe}>{screening.instrument.timeframe}</p>
      <h2 className={styles.question}>{screening.currentQuestion.text}</h2>
      <div className={styles.choices}>
        {screening.currentQuestion.choices.map((choice) => <button key={choice.value} type="button" disabled={busy} onClick={() => { void submitAnswer(choice.value); }}>{choice.label}</button>)}
      </div>
      {error && <p className={styles.error} role="alert">{error}</p>}
      <small className={styles.source}>{screening.instrument.standardReference} · 题目保持标准原文，不由模型改写。</small>
    </section>}

    {screening?.status === "completed" && screening.result && <section className={styles.card}>
      <p className={styles.complete}>已完成</p>
      <h2>{screening.result.label}</h2>
      <p className={styles.recommendation}>{screening.result.recommendation}</p>
      <div className={styles.resultMeta}><span>{screening.instrument.name}</span><span>{screening.result.totalScore} 分 · {screening.result.scoreRange}</span></div>
      <p className={styles.notice}>{screening.result.notice}</p>
      <div className={styles.doneActions}><Link href="/">返回首页</Link><button type="button" onClick={() => { setScreening(null); setConsent(false); }}>完成另一项筛查</button></div>
    </section>}
  </main>;
}
