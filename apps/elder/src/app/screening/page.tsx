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
type AnsweredQuestion = Question & { selectedValue: string };
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
  answeredQuestions: AnsweredQuestion[];
  shareWithFamily: boolean;
  shareWithCareTeam: boolean;
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
  const [recentScreenings, setRecentScreenings] = useState<ScreeningSession[]>([]);
  const [reviewIndex, setReviewIndex] = useState<number | null>(null);
  const [draftAnswers, setDraftAnswers] = useState<Record<string, string>>({});
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
      void fetch(`${API_BASE}/elder/screenings?limit=10`, {
        headers: { Authorization: `Bearer ${stored.accessToken}` }
      }).then(async (response) => {
        if (!response.ok) return;
        const body = await response.json();
        setRecentScreenings(body.items ?? []);
      }).catch(() => {});
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
      setRecentScreenings((previous) => [body, ...previous].slice(0, 10));
      setReviewIndex(null);
      setDraftAnswers({});
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "暂时无法开始测评");
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswer() {
    if (!token || !screening?.currentQuestion) return;
    const value = draftAnswers[screening.currentQuestion.itemCode];
    if (!value) return;
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
      setRecentScreenings((previous) => previous.map((item) => item.id === body.id ? body : item));
      setReviewIndex(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "答案暂时没有保存成功");
    } finally {
      setBusy(false);
    }
  }

  async function saveReviewedAnswer() {
    if (!token || !screening || reviewIndex === null) return;
    const answered = screening.answeredQuestions[reviewIndex];
    if (!answered) return;
    const value = draftAnswers[answered.itemCode] ?? answered.selectedValue;
    if (value !== answered.selectedValue) {
      setBusy(true);
      setError("");
      try {
        const response = await fetch(`${API_BASE}/elder/screenings/${screening.id}/answers/${answered.itemCode}`, {
          method: "PATCH",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          body: JSON.stringify({ value })
        });
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "修改暂时没有保存成功");
        setScreening(body);
        setRecentScreenings((previous) => previous.map((item) => item.id === body.id ? body : item));
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "修改暂时没有保存成功");
        setBusy(false);
        return;
      }
      setBusy(false);
    }
    setReviewIndex(reviewIndex + 1 < screening.progressAnswered ? reviewIndex + 1 : null);
  }

  const shownQuestion = reviewIndex === null
    ? screening?.currentQuestion
    : screening?.answeredQuestions[reviewIndex];
  const selectedValue = shownQuestion
    ? draftAnswers[shownQuestion.itemCode] ?? (reviewIndex === null ? "" : screening?.answeredQuestions[reviewIndex]?.selectedValue ?? "")
    : "";
  const isReviewing = reviewIndex !== null;
  const unfinishedScreening = recentScreenings.find((item) => item.status === "in_progress");
  const completedScreenings = recentScreenings.filter((item) => item.status === "completed").slice(0, 5);

  if (!token) return <main className={styles.shell}>正在确认登录状态…</main>;

  return <main className={styles.shell}>
    <header className={styles.header}>
      <Link href="/">返回首页</Link>
      <div><p>心迹银龄 · 标准关怀筛查</p><h1>慢慢回答，没有对错</h1></div>
    </header>

    {!screening && <section className={styles.card}>
      <p className={styles.notice}>这是本人自愿完成的标准化筛查，不是疾病诊断。题目与计分由固定程序处理，大模型不会替您回答。</p>
      {(unfinishedScreening || completedScreenings.length > 0) && <div className={styles.recentActions}>
        {unfinishedScreening && <button type="button" onClick={() => { setScreening(unfinishedScreening); setReviewIndex(null); setDraftAnswers({}); setError(""); }}>继续未完成的{unfinishedScreening.instrument.name}</button>}
        {completedScreenings.map((item) => <button key={item.id} type="button" onClick={() => { setScreening(item); setReviewIndex(null); setError(""); }}>查看{item.instrument.name}结果 · {item.result?.totalScore}分</button>)}
      </div>}
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

    {screening?.status === "in_progress" && shownQuestion && <section className={styles.card}>
      <div className={styles.progress}><span>第 {shownQuestion.number} 题{isReviewing ? " · 检查已答内容" : ""}</span><span>共 {screening.instrument.itemCount} 题</span></div>
      <div className={styles.progressTrack}><i style={{ width: `${(screening.progressAnswered / screening.instrument.itemCount) * 100}%` }} /></div>
      <p className={styles.timeframe}>{screening.instrument.timeframe}</p>
      <h2 className={styles.question}>{shownQuestion.text}</h2>
      <div className={styles.choices}>
        {shownQuestion.choices.map((choice) => <button
          key={choice.value}
          type="button"
          disabled={busy}
          aria-pressed={selectedValue === choice.value}
          className={selectedValue === choice.value ? styles.chosen : ""}
          onClick={() => setDraftAnswers((previous) => ({ ...previous, [shownQuestion.itemCode]: choice.value }))}
        >{choice.label}</button>)}
      </div>
      <div className={styles.questionActions}>
        <button type="button" disabled={busy || (isReviewing ? reviewIndex === 0 : screening.progressAnswered === 0)} onClick={() => setReviewIndex(isReviewing ? reviewIndex - 1 : screening.progressAnswered - 1)}>上一题</button>
        {isReviewing && <button type="button" disabled={busy} onClick={() => {
          setDraftAnswers((previous) => {
            const next = { ...previous };
            screening.answeredQuestions.forEach((answer) => { delete next[answer.itemCode]; });
            return next;
          });
          setReviewIndex(null);
        }}>不保存，返回未完成题</button>}
        <button type="button" className={styles.next} disabled={busy || !selectedValue} onClick={() => { void (isReviewing ? saveReviewedAnswer() : submitAnswer()); }}>
          {busy ? "正在保存…" : isReviewing ? "保存并继续" : shownQuestion.number === screening.instrument.itemCount ? "提交并查看结果" : "确认，下一题"}
        </button>
      </div>
      {error && <p className={styles.error} role="alert">{error}</p>}
      <small className={styles.source}>{screening.instrument.standardReference} · 题目保持标准原文，不由模型改写。</small>
    </section>}

    {screening?.status === "completed" && screening.result && <section className={styles.card}>
      <p className={styles.complete}>筛查已完成 · 本人可见</p>
      <h2>本次筛查结果</h2>
      <div className={styles.resultHero}>
        <div><strong>{screening.result.totalScore}</strong><span> / {screening.instrument.code === "gds15" ? 15 : 21} 分</span></div>
        <p>{screening.result.band === "normal" ? "本次分数未达到量表的人工关注范围" : screening.result.label}</p>
      </div>
      <p className={styles.resultExplanation}>您回答的是{screening.instrument.name}，题目回顾{screening.instrument.code === "gds15" ? "过去一周" : "过去两周"}的情况。按本项目采用的固定计分规则，您的分数落在 <strong>{screening.result.scoreRange}</strong> 这一档。它反映的是这次量表回答，不能代表您今天一定开心或难过，也不能单独判断是否患病。</p>
      <h3 className={styles.subheading}>接下来可以怎么做</h3>
      <p className={styles.recommendation}>{screening.result.recommendation}</p>
      <div className={styles.resultMeta}><span>家属：{screening.shareWithFamily ? "已同意分享简要建议" : "未分享"}</span><span>关怀团队：{screening.shareWithCareTeam ? "已同意分享筛查摘要" : "未分享"}</span></div>
      <p className={styles.notice}>{screening.result.notice}</p>
      <p className={styles.source}>计分依据：{screening.instrument.standardReference} · <a href="https://www.nhc.gov.cn/fzs/c100048/202211/ff72fed5f73c48838458fb353c99509d/files/1746697544163_41758.pdf" target="_blank" rel="noopener noreferrer">查看国家卫健委原文</a></p>
      <details className={styles.answerReview}><summary>核对我的作答（仅本人可见）</summary><ol>{screening.answeredQuestions.map((question) => <li key={question.itemCode}><span>{question.text}</span><strong>{question.choices.find((choice) => choice.value === question.selectedValue)?.label ?? "—"}</strong></li>)}</ol><p>本次筛查已完成，结果不会被悄悄改写；如需重新作答，请开始新的一次筛查。</p></details>
      <div className={styles.doneActions}><Link href="/">返回首页</Link><button type="button" onClick={() => { setScreening(null); setConsent(false); setReviewIndex(null); setDraftAnswers({}); }}>完成另一项筛查</button></div>
    </section>}
  </main>;
}
