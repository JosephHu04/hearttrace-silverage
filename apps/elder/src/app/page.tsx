"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";

// All three clients configure the API origin. Accept the older /api suffix too.
const API_ORIGIN = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000")
  .replace(/\/api\/?$/, "")
  .replace(/\/$/, "");
const API_BASE = `${API_ORIGIN}/api`;

type ActivePanel = "home" | "chat" | "time" | "weather" | "news" | "checkin";
type ConsentMode = "private" | "care";
type EmergencyState = "idle" | "confirming" | "submitting" | "sent" | "error";
type CompanionVisualState = "idle" | "listening" | "thinking" | "speaking" | "alert" | "offline";
type ChatMessage = { id: string; role: "user" | "assistant"; content: string; at: Date | null };
type Weather = {
  location: string;
  temperature: number;
  apparentTemperature: number;
  description: string;
  high: number | null;
  low: number | null;
  precipitationProbability: number | null;
  stale: boolean;
};
type NewsItem = { title: string; url: string; source: string };
type DailyCheckIn = {
  id: string;
  checkinDate: string;
  mood: number;
  sleep: number;
  socialWillingness: number;
  shareWithFamily: boolean;
  shareWithCareTeam: boolean;
  createdAt: string;
  updatedAt: string;
};
type Persona = {
  id: string;
  name: string;
  role: string;
  style: string;
  scenarios: string[];
  knowledge: string;
};
const DEFAULT_PERSONA: Persona = {
  id: "yaoyao",
  name: "遥遥",
  role: "像一位常来坐坐、愿意把话听完的晚辈",
  style: "自然、克制、尊重长者；先听准确，再决定是否给一步办法",
  scenarios: [],
  knowledge: ""
};
type ServerEvent = {
  type: string;
  text?: string;
  message?: string;
  kind?: string;
  data?: Weather | { items: NewsItem[]; stale: boolean } | { time: string; date: string; weekday: string };
};

function websocketEndpoint(): string {
  const url = new URL(API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `${url.pathname.replace(/\/$/, "")}/realtime/conversation`;
  url.search = "";
  return url.toString();
}

function displayTime(date: Date): string {
  return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
}

function relevantKnowledge(persona: Persona, query: string): string[] {
  const queryChars = new Set([...query.replace(/\s/g, "")]);
  return persona.knowledge
    .split(/\n\s*\n/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => ({ item, score: [...new Set([...item])].filter((char) => queryChars.has(char)).length }))
    .filter(({ score }) => score >= 2)
    .sort((left, right) => right.score - left.score)
    .slice(0, 4)
    .map(({ item }) => item.slice(0, 600));
}

export default function ElderCompanionPage() {
  const router = useRouter();
  const [accessToken, setAccessToken] = useState("");
  const [elderId, setElderId] = useState("");
  const [elderName, setElderName] = useState("");
  const sessionIdRef = useRef("");
  const emergencyRequestIdRef = useRef<string | null>(null);
  const [connectionAttempt, setConnectionAttempt] = useState(0);
  const [activePanel, setActivePanel] = useState<ActivePanel>("home");
  const [consentMode, setConsentMode] = useState<ConsentMode | null>(null);
  const [now, setNow] = useState<Date | null>(null);
  const [status, setStatus] = useState("正在连接");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: "welcome", role: "assistant", content: "我在呢。您今天想说点什么？旧事、新鲜事，我都慢慢听。", at: null }
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("遥遥正在回复");
  const [personas, setPersonas] = useState<Persona[]>([DEFAULT_PERSONA]);
  const [personasLoaded, setPersonasLoaded] = useState(false);
  const [selectedPersonaId, setSelectedPersonaId] = useState(DEFAULT_PERSONA.id);
  const [autoPersona, setAutoPersona] = useState(true);
  const [personaManagerOpen, setPersonaManagerOpen] = useState(false);
  const [personaDraft, setPersonaDraft] = useState({ name: "", role: "", style: "", scenarios: "", knowledge: "" });
  const [weather, setWeather] = useState<Weather | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [emergencyState, setEmergencyState] = useState<EmergencyState>("idle");
  const [emergencyMessage, setEmergencyMessage] = useState("");
  const [checkIn, setCheckIn] = useState<DailyCheckIn | null>(null);
  const [checkInHistory, setCheckInHistory] = useState<DailyCheckIn[]>([]);
  const [checkInMood, setCheckInMood] = useState(3);
  const [checkInSleep, setCheckInSleep] = useState(3);
  const [checkInSocial, setCheckInSocial] = useState(3);
  const [checkInFamily, setCheckInFamily] = useState(false);
  const [checkInCareTeam, setCheckInCareTeam] = useState(false);
  const [checkInBusy, setCheckInBusy] = useState(false);
  const [checkInNotice, setCheckInNotice] = useState("");
  const socketRef = useRef<WebSocket | null>(null);
  const tokenRef = useRef("");
  const assistantIdRef = useRef<string | null>(null);
  const pendingMessageRef = useRef("");
  const hasSentMessageRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    try {
      const session = JSON.parse(sessionStorage.getItem("hearttrace.elder.session") ?? "null");
      if (!session?.accessToken || session.actor?.role !== "elder" || !Number.isFinite(Date.parse(session.expiresAt)) || Date.parse(session.expiresAt) <= Date.now()) throw new Error("expired");
      setAccessToken(session.accessToken);
      tokenRef.current = session.accessToken;
      setElderId(session.actor.id);
      setElderName(session.actor.displayName);
    } catch {
      sessionStorage.removeItem("hearttrace.elder.session");
      router.replace("/account");
    }
  }, [router]);

  useEffect(() => {
    if (!elderId) return;
    setPersonasLoaded(false);
    try {
      const stored = JSON.parse(localStorage.getItem(`hearttrace.personas.${elderId}`) ?? "[]") as Persona[];
      const valid = stored.filter((item) => item?.id && item?.name && item?.role && item?.style && item.id !== DEFAULT_PERSONA.id);
      setPersonas([DEFAULT_PERSONA, ...valid]);
    } catch {
      setPersonas([DEFAULT_PERSONA]);
    }
    setPersonasLoaded(true);
  }, [elderId]);

  useEffect(() => {
    if (!elderId || !personasLoaded) return;
    localStorage.setItem(`hearttrace.personas.${elderId}`, JSON.stringify(personas.filter((item) => item.id !== DEFAULT_PERSONA.id)));
  }, [elderId, personas, personasLoaded]);

  const selectedPersona = personas.find((item) => item.id === selectedPersonaId) ?? DEFAULT_PERSONA;

  function logout() {
    socketRef.current?.close();
    sessionStorage.removeItem("hearttrace.elder.session");
    setAccessToken("");
    tokenRef.current = "";
    router.replace("/account");
  }

  const authorizedFetch = useCallback(async (path: string) => {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { Authorization: `Bearer ${tokenRef.current}` }
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail ?? "服务暂时不可用");
    return data;
  }, []);

  const loadWeather = useCallback(async () => {
    try {
      setWeather(await authorizedFetch("/elder/widgets/weather"));
    } catch {
      setWeather(null);
    }
  }, [authorizedFetch]);

  const loadNews = useCallback(async () => {
    try {
      const data = await authorizedFetch("/elder/widgets/news?limit=3");
      setNews(data.items ?? []);
    } catch {
      setNews([]);
    }
  }, [authorizedFetch]);

  const loadCheckIns = useCallback(async () => {
    try {
      const data = await authorizedFetch("/elder/check-ins?days=7") as { items?: DailyCheckIn[] };
      const items = data.items ?? [];
      setCheckInHistory(items);
      const current = items[0] ?? null;
      setCheckIn(current);
      if (current) {
        setCheckInMood(current.mood);
        setCheckInSleep(current.sleep);
        setCheckInSocial(current.socialWillingness);
        setCheckInFamily(current.shareWithFamily);
        setCheckInCareTeam(current.shareWithCareTeam);
      }
    } catch (error) {
      setCheckInNotice(error instanceof Error ? error.message : "暂时无法读取今日打卡");
    }
  }, [authorizedFetch]);

  useEffect(() => {
    if (accessToken && activePanel === "checkin") void loadCheckIns();
  }, [accessToken, activePanel, loadCheckIns]);

  async function saveCheckIn() {
    if (checkInBusy) return;
    setCheckInBusy(true);
    setCheckInNotice("");
    try {
      const response = await fetch(`${API_BASE}/elder/check-ins`, {
        method: "POST",
        headers: { Authorization: `Bearer ${tokenRef.current}`, "Content-Type": "application/json" },
        body: JSON.stringify({ mood: checkInMood, sleep: checkInSleep, socialWillingness: checkInSocial, shareWithFamily: checkInFamily, shareWithCareTeam: checkInCareTeam })
      });
      const data = await response.json() as DailyCheckIn & { detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "保存打卡失败");
      setCheckIn(data);
      setCheckInHistory((items) => [data, ...items.filter((item) => item.id !== data.id)]);
      setCheckInNotice("今天的自述已保存，分享范围也已按你的选择更新。");
    } catch (error) {
      setCheckInNotice(error instanceof Error ? error.message : "保存打卡失败，请稍后重试");
    } finally {
      setCheckInBusy(false);
    }
  }

  async function updateCheckInSharing(nextFamily: boolean, nextCareTeam: boolean) {
    if (!checkIn || checkInBusy) return;
    setCheckInBusy(true);
    setCheckInFamily(nextFamily);
    setCheckInCareTeam(nextCareTeam);
    try {
      const response = await fetch(`${API_BASE}/elder/check-ins/${checkIn.id}/sharing`, {
        method: "POST",
        headers: { Authorization: `Bearer ${tokenRef.current}`, "Content-Type": "application/json" },
        body: JSON.stringify({ shareWithFamily: nextFamily, shareWithCareTeam: nextCareTeam })
      });
      const data = await response.json() as DailyCheckIn & { detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "分享设置更新失败");
      setCheckIn(data);
      setCheckInHistory((items) => items.map((item) => item.id === data.id ? data : item));
      setCheckInNotice("分享设置已更新。");
    } catch (error) {
      setCheckInFamily(checkIn.shareWithFamily);
      setCheckInCareTeam(checkIn.shareWithCareTeam);
      setCheckInNotice(error instanceof Error ? error.message : "分享设置更新失败");
    } finally {
      setCheckInBusy(false);
    }
  }

  useEffect(() => {
    setNow(new Date());
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (activePanel === "chat") bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activePanel, messages, busy]);

  useEffect(() => {
    if (!consentMode || !accessToken) return;
    let cancelled = false;
    let socket: WebSocket | null = null;

    async function connect() {
      try {
        let session = { id: sessionIdRef.current };
        if (!session.id) {
          const sessionResponse = await fetch(`${API_BASE}/conversations/sessions`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            saveMessages: consentMode === "care",
            allowAnalysis: consentMode === "care",
            persona: {
              id: selectedPersona.id,
              name: selectedPersona.name,
              role: selectedPersona.role,
              style: selectedPersona.style,
              scenarios: selectedPersona.scenarios
            }
          })
        });
          const result = await sessionResponse.json();
          if (sessionResponse.status === 401) {
            sessionStorage.removeItem("hearttrace.elder.session");
            setAccessToken("");
            router.replace("/account");
            return;
          }
          if (!sessionResponse.ok) throw new Error(result.detail ?? "无法创建会话");
          session = result;
        }
        if (cancelled) return;
        sessionIdRef.current = session.id;

        socket = new WebSocket(websocketEndpoint());
        socketRef.current = socket;
        socket.onopen = () => {
          socket?.send(JSON.stringify({
            type: "authenticate",
            accessToken,
            sessionId: session.id,
            persona: {
              id: selectedPersona.id,
              name: selectedPersona.name,
              role: selectedPersona.role,
              style: selectedPersona.style,
              scenarios: selectedPersona.scenarios
            }
          }));
        };
        socket.onmessage = (event) => {
          const update = JSON.parse(event.data) as ServerEvent;
          if (update.type === "ready") {
            setStatus("可以使用");
            void Promise.allSettled([loadWeather(), loadNews()]);
            const pending = pendingMessageRef.current;
            if (pending && socket?.readyState === WebSocket.OPEN) {
              pendingMessageRef.current = "";
              hasSentMessageRef.current = true;
              setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: pending, at: new Date() }]);
              setBusy(true);
              socket.send(JSON.stringify({ type: "message", text: pending, knowledge: relevantKnowledge(selectedPersona, pending) }));
            }
          } else if (update.type === "progress") {
            const labels: Record<string, string> = {
              time: "正在读取时间",
              weather: "正在查看天气",
              news: "正在整理最新资讯"
            };
            setProgress(labels[update.kind ?? ""] ?? `${selectedPersona.name}正在回复`);
          } else if (update.type === "widget" && update.data) {
            if (update.kind === "weather") setWeather(update.data as Weather);
            if (update.kind === "news") setNews((update.data as { items: NewsItem[] }).items ?? []);
          } else if (update.type === "delta" && update.text) {
            let assistantId = assistantIdRef.current;
            if (!assistantId) {
              assistantId = crypto.randomUUID();
              assistantIdRef.current = assistantId;
              setMessages((current) => [...current, { id: assistantId as string, role: "assistant", content: update.text as string, at: new Date() }]);
            } else {
              setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, content: item.content + update.text } : item));
            }
          } else if (update.type === "done") {
            assistantIdRef.current = null;
            setBusy(false);
            setProgress(`${selectedPersona.name}正在回复`);
          } else if (update.type === "error") {
            setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: update.message ?? "刚才没有接住，请再说一次。", at: new Date() }]);
            assistantIdRef.current = null;
            setBusy(false);
          }
        };
        socket.onclose = (event) => {
          if (!cancelled) {
            if (event.code === 4401) {
              sessionStorage.removeItem("hearttrace.elder.session");
              setAccessToken("");
              router.replace("/account");
            }
            setStatus("暂时离线");
            setBusy(false);
            assistantIdRef.current = null;
          }
        };
        socket.onerror = () => setStatus("连接不稳");
      } catch (error) {
        if (!cancelled) setStatus(error instanceof Error ? error.message : "暂时离线");
      }
    }

    void connect();
    return () => {
      cancelled = true;
      socket?.close();
    };
  }, [accessToken, consentMode, connectionAttempt, loadNews, loadWeather, router, selectedPersona]);

  function restartWithPersona(personaId: string, pendingMessage = "", profileOverride?: Persona) {
    socketRef.current?.close();
    socketRef.current = null;
    sessionIdRef.current = "";
    assistantIdRef.current = null;
    pendingMessageRef.current = pendingMessage;
    hasSentMessageRef.current = false;
    const nextPersona = profileOverride ?? personas.find((item) => item.id === personaId) ?? DEFAULT_PERSONA;
    setSelectedPersonaId(nextPersona.id);
    setStatus("正在连接");
    setProgress(`${nextPersona.name}正在回复`);
    setMessages([{ id: "welcome", role: "assistant", content: `${nextPersona.name}在呢。您慢慢说。`, at: null }]);
    setConnectionAttempt((value) => value + 1);
  }

  function sendMessage(event: FormEvent) {
    event.preventDefault();
    const text = input.trim();
    if (!text || busy || socketRef.current?.readyState !== WebSocket.OPEN) return;
    if (autoPersona && !hasSentMessageRef.current) {
      const ranked = personas
        .map((persona) => ({
          persona,
          score: persona.scenarios.reduce((sum, scenario) => sum + (scenario && text.includes(scenario) ? scenario.length : 0), 0)
        }))
        .filter(({ score }) => score > 0)
        .sort((left, right) => right.score - left.score);
      if (ranked.length && ranked[0].persona.id !== selectedPersona.id && (ranked.length === 1 || ranked[0].score > ranked[1].score)) {
        setInput("");
        restartWithPersona(ranked[0].persona.id, text);
        return;
      }
    }
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: text, at: new Date() }]);
    setInput("");
    setBusy(true);
    hasSentMessageRef.current = true;
    assistantIdRef.current = null;
    socketRef.current.send(JSON.stringify({ type: "message", text, knowledge: relevantKnowledge(selectedPersona, text) }));
  }

  function savePersona(event: FormEvent) {
    event.preventDefault();
    const name = personaDraft.name.trim();
    const role = personaDraft.role.trim();
    const style = personaDraft.style.trim();
    if (name.length < 2 || !role || !style) return;
    const scenarios = personaDraft.scenarios.split(/[，,\n]/).map((item) => item.trim()).filter((item) => item.length >= 2 && item.length <= 40).slice(0, 12);
    const persona: Persona = {
      id: `persona-${crypto.randomUUID()}`,
      name: name.slice(0, 40),
      role: role.slice(0, 300),
      style: style.slice(0, 300),
      scenarios,
      knowledge: personaDraft.knowledge.slice(0, 30000)
    };
    setPersonas((current) => [...current, persona]);
    setPersonaDraft({ name: "", role: "", style: "", scenarios: "", knowledge: "" });
    restartWithPersona(persona.id, "", persona);
    setPersonaManagerOpen(false);
  }

  function removePersona(personaId: string) {
    if (personaId === DEFAULT_PERSONA.id) return;
    setPersonas((current) => current.filter((item) => item.id !== personaId));
    if (selectedPersonaId === personaId) restartWithPersona(DEFAULT_PERSONA.id);
  }

  async function submitEmergency() {
    if (emergencyState === "submitting" || emergencyState === "sent") return;
    if (!tokenRef.current) {
      setEmergencyState("error");
      setEmergencyMessage("当前还没有连上求助服务。请立即联系身边工作人员或拨打当地紧急电话。");
      return;
    }
    setEmergencyState("submitting");
    setEmergencyMessage("正在发送求助，请稍候…");
    try {
      const response = await fetch(`${API_BASE}/emergency/events`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${tokenRef.current}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          requestId: emergencyRequestIdRef.current ?? (emergencyRequestIdRef.current = `elder-sos-${crypto.randomUUID()}`),
          source: "elder_button",
          note: "老人通过触控端主动发出求助"
        })
      });
      const result = await response.json().catch(() => ({})) as { detail?: string };
      if (!response.ok) throw new Error(result.detail ?? "求助暂时未发送成功");
      setEmergencyState("sent");
      emergencyRequestIdRef.current = null;
      setEmergencyMessage("求助已经发出，家属和工作人员会收到提醒。请留在安全的位置等待联系。");
    } catch (error) {
      setEmergencyState("error");
      setEmergencyMessage(`${error instanceof Error ? error.message : "求助暂时未发送成功"}。请立即联系身边工作人员或拨打当地紧急电话。`);
    }
  }

  async function resetConversationConsent() {
    if (sessionIdRef.current) {
      try {
        const response = await fetch(`${API_BASE}/conversations/sessions/${sessionIdRef.current}/revoke-analysis`, { method: "POST", headers: { Authorization: `Bearer ${tokenRef.current}` } });
        if (!response.ok) throw new Error("暂时无法停止保存与分析，请稍后重试");
      } catch (cause) {
        setStatus(cause instanceof Error ? cause.message : "操作未完成");
        return;
      }
      sessionIdRef.current = "";
    }
    socketRef.current?.close();
    socketRef.current = null;
    assistantIdRef.current = null;
    pendingMessageRef.current = "";
    hasSentMessageRef.current = false;
    setConsentMode(null);
    setActivePanel("home");
    setStatus("正在连接");
    setBusy(false);
    setInput("");
    setEmergencyState("idle");
    setEmergencyMessage("");
    setMessages([{ id: "welcome", role: "assistant", content: `${selectedPersona.name}在呢。您慢慢说。`, at: null }]);
  }

  const dateText = now ? new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "long", day: "numeric", weekday: "long" }).format(now) : "正在读取日期";
  const dayPeriod = !now ? "" : now.getHours() < 6 ? "凌晨" : now.getHours() < 12 ? "上午" : now.getHours() < 18 ? "下午" : "晚上";
  const latestMessage = messages[messages.length - 1];
  const companionVisualState: CompanionVisualState = emergencyState !== "idle"
    ? "alert"
    : status === "暂时离线" || status === "连接不稳"
      ? "offline"
      : status === "正在连接"
        ? "thinking"
        : busy
          ? latestMessage?.role === "assistant" ? "speaking" : "thinking"
          : activePanel === "chat" ? "listening" : "idle";

  if (!accessToken) return <main className="consent-shell">正在确认登录状态…</main>;

  if (!consentMode) {
    return <main className="consent-shell">
      <section className="consent-card" aria-labelledby="consent-title">
        <p className="consent-brand">心迹银龄 · {selectedPersona.name}</p>
        <button type="button" onClick={logout}>退出账号</button>
        <Link href="/account/security">修改密码</Link>
        <h1 id="consent-title">今天想怎样聊？</h1>
        <p className="consent-intro">请您自己选择。无论选哪一种，都可以正常聊天。</p>
        <div className="persona-picker" aria-label="选择陪伴人格">
          <strong>这次由谁陪您聊</strong>
          <div>{personas.map((persona) => <button className={persona.id === selectedPersona.id ? "selected" : ""} type="button" key={persona.id} onClick={() => setSelectedPersonaId(persona.id)}>{persona.name}</button>)}</div>
          <label><input type="checkbox" checked={autoPersona} onChange={(event) => setAutoPersona(event.target.checked)} /> 首句话明确匹配适用场景时，自动换到对应人格</label>
        </div>
        <div className="consent-options">
          <button type="button" onClick={() => setConsentMode("private")}>
            <strong>只在这次聊天</strong>
            <span>不保存聊天，也不用于健康关怀分析</span>
          </button>
          <button className="consent-care" type="button" onClick={() => setConsentMode("care")}>
            <strong>生成关怀摘要</strong>
            <span>保存本次聊天并用于健康关怀分析；家属看不到聊天全文，只有工作人员确认后的简短摘要</span>
          </button>
        </div>
        <small>这不是疾病诊断。您可以随时停止本次会话后续的保存与分析；已保存内容和已发布摘要不会自动删除。</small>
      </section>
    </main>;
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <button className="brand" type="button" onClick={() => setActivePanel("home")}>{selectedPersona.name}</button>
        <p className="welcome">{elderName}，{dayPeriod ? `${dayPeriod}好` : "您好"}</p>
        <div className="service-state"><span>{status}</span>{(status === "暂时离线" || status === "连接不稳") && <button type="button" onClick={() => { setStatus("正在连接"); setConnectionAttempt((value) => value + 1); }}>重新连接</button>}<small>{consentMode === "care" ? "已同意生成关怀摘要" : "本次对话不保存"}</small><button type="button" onClick={() => { void resetConversationConsent(); }}>停止保存与分析 / 重新选择</button><Link href="/account/security">修改密码</Link><button type="button" onClick={logout}>退出</button></div>
      </header>

      {activePanel === "home" && (
        <section className="feature-grid" aria-label="主要功能">
          <button className="feature-tile feature-chat" type="button" onClick={() => setActivePanel("chat")}>
            <span className="feature-chat-copy">
              <strong>陪我聊聊</strong>
              <span>点一下，说说心里话</span>
            </span>
            <CompanionAvatar name={selectedPersona.name} state={companionVisualState} compact />
          </button>

          <button className="feature-tile feature-time" type="button" onClick={() => setActivePanel("time")}>
            <strong className="tile-clock">{now ? displayTime(now) : "--:--"}</strong>
            <span>现在时间</span>
          </button>

          <button className="feature-tile feature-weather" type="button" onClick={() => setActivePanel("weather")}>
            <strong>{weather ? `${weather.temperature}℃` : "今日天气"}</strong>
            <span>{weather ? `${weather.description} · ${weather.location}` : "点一下查看天气"}</span>
          </button>

          <button className="feature-tile feature-news" type="button" onClick={() => setActivePanel("news")}>
            <strong>最新资讯</strong>
            <span>{news[0]?.title ?? "点一下听听今天的消息"}</span>
          </button>

          <button className="feature-tile feature-checkin" type="button" onClick={() => setActivePanel("checkin")}>
            <strong>每日自述</strong>
            <span>{checkIn ? "今天已记录 · 点一下可修改" : "用三个小问题告诉我今天的状态"}</span>
          </button>

          <Link className="feature-tile feature-screening" href="/screening">
            <strong>关怀小测</strong>
            <span>本人愿意时，完成有国家标准依据的情绪关怀筛查</span>
          </Link>

          <section className="persona-home-card" aria-labelledby="persona-home-title">
            <div className="persona-home-heading">
              <button className="companion-launch" type="button" onClick={() => setActivePanel("chat")} aria-label={`和${selectedPersona.name}聊聊`}>
                <CompanionAvatar name={selectedPersona.name} state={companionVisualState} />
              </button>
              <div>
                <p>当前陪伴者</p>
                <h2 id="persona-home-title">{selectedPersona.name}</h2>
                <span>{selectedPersona.role}</span>
              </div>
              <button type="button" aria-expanded={personaManagerOpen} onClick={() => setPersonaManagerOpen((open) => !open)}>
                {personaManagerOpen ? "收起管理" : "添加或管理陪伴者"}
              </button>
            </div>
            <div className="persona-quick-list" aria-label="在首页选择陪伴者">
              {personas.map((persona) => (
                <button
                  className={persona.id === selectedPersona.id ? "selected" : ""}
                  type="button"
                  key={persona.id}
                  onClick={() => restartWithPersona(persona.id)}
                >
                  <strong>{persona.name}</strong>
                  <span>{persona.style}</span>
                </button>
              ))}
            </div>
            {personaManagerOpen && (
              <div className="persona-manager">
                <section className="persona-list" aria-label="已有人格">
                  {personas.map((persona) => (
                    <article className={persona.id === selectedPersona.id ? "active" : ""} key={persona.id}>
                      <div><h2>{persona.name}</h2><p>{persona.role}</p><small>{persona.style}</small></div>
                      <div className="persona-actions">
                        <button type="button" onClick={() => { restartWithPersona(persona.id); setPersonaManagerOpen(false); }}>选择</button>
                        {persona.id !== DEFAULT_PERSONA.id && <button type="button" onClick={() => removePersona(persona.id)}>删除</button>}
                      </div>
                    </article>
                  ))}
                </section>
                <form className="persona-form" onSubmit={savePersona}>
                  <h2>新增陪伴者</h2>
                  <label>名称<input required minLength={2} maxLength={40} value={personaDraft.name} onChange={(event) => setPersonaDraft((value) => ({ ...value, name: event.target.value }))} placeholder="例如：林老师" /></label>
                  <label>关系定位<textarea required maxLength={300} value={personaDraft.role} onChange={(event) => setPersonaDraft((value) => ({ ...value, role: event.target.value }))} placeholder="例如：理性、可靠的老朋友" /></label>
                  <label>说话风格<textarea required maxLength={300} value={personaDraft.style} onChange={(event) => setPersonaDraft((value) => ({ ...value, style: event.target.value }))} placeholder="例如：清楚直接，一次只说一件事" /></label>
                  <label>适用场景<input value={personaDraft.scenarios} onChange={(event) => setPersonaDraft((value) => ({ ...value, scenarios: event.target.value }))} placeholder="用逗号分隔，例如：工作压力，读新闻" /></label>
                  <label>人格资料<textarea maxLength={30000} value={personaDraft.knowledge} onChange={(event) => setPersonaDraft((value) => ({ ...value, knowledge: event.target.value }))} placeholder="可粘贴背景资料；用空行分段，聊天时只取相关片段" /></label>
                  <button type="submit">保存并选择</button>
                  <small>资料只保存在当前浏览器和当前老人账号下；每位陪伴者使用独立会话，避免记忆混在一起。</small>
                </form>
              </div>
            )}
          </section>

          <button className="feature-tile feature-emergency" type="button" disabled={emergencyState === "submitting" || emergencyState === "sent"} onClick={() => setEmergencyState("confirming")}>
            <strong>{emergencyState === "sent" ? "求助已发出" : "紧急呼救"}</strong>
            <span>{emergencyState === "sent" ? "家属和工作人员正在收到提醒" : "身体不舒服、跌倒或感到危险时点这里"}</span>
          </button>
        </section>
      )}

      {emergencyState !== "idle" && (
        <div className="emergency-overlay" role="presentation">
          <section className={`emergency-dialog emergency-${emergencyState}`} role="alertdialog" aria-modal="true" aria-labelledby="emergency-title">
            <h2 id="emergency-title">{emergencyState === "sent" ? "求助已发出" : emergencyState === "error" ? "发送没有成功" : "确认发出紧急求助？"}</h2>
            <p>{emergencyMessage || "确认后，家属和工作人员都会收到紧急提醒。"}</p>
            <div>
              {emergencyState === "confirming" && <button className="emergency-confirm" type="button" onClick={() => { void submitEmergency(); }}>确认呼救</button>}
              {emergencyState !== "submitting" && emergencyState !== "sent" && <button type="button" onClick={() => { setEmergencyState("idle"); setEmergencyMessage(""); }}>取消</button>}
              {emergencyState === "error" && <button className="emergency-confirm" type="button" onClick={() => { void submitEmergency(); }}>重新发送</button>}
              {emergencyState === "sent" && <button type="button" onClick={() => setEmergencyState("idle")}>我知道了</button>}
            </div>
          </section>
        </div>
      )}

      {activePanel !== "home" && (
        <section className={`panel-view panel-${activePanel}`}>
          <header className="panel-header">
            <button className="back-button" type="button" onClick={() => setActivePanel("home")}>返回首页</button>
            <h1>{activePanel === "chat" ? `和${selectedPersona.name}聊聊` : activePanel === "time" ? "现在时间" : activePanel === "weather" ? "今日天气" : activePanel === "checkin" ? "每日自述" : "最新资讯"}</h1>
          </header>

          {activePanel === "chat" && (
            <div className="chat-layout">
              <div className="chat-companion-bar">
                <CompanionAvatar name={selectedPersona.name} state={companionVisualState} compact />
                <p>您慢慢说，{selectedPersona.name}在听。</p>
              </div>
              <div className="messages" aria-live="polite">
                {messages.map((message) => (
                  <article className={`message message-${message.role}`} key={message.id}>
                    <div>{message.content.split("\n").filter(Boolean).map((line, index) => <p key={index}>{line}</p>)}</div>
                    <time>{message.at ? displayTime(message.at) : "刚刚"}</time>
                  </article>
                ))}
                {busy && <div className="thinking" role="status">{progress}</div>}
                <div ref={bottomRef} />
              </div>
              <form className="composer" onSubmit={sendMessage}>
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                  rows={1}
                  maxLength={8000}
                  placeholder="点这里输入想说的话"
                  aria-label="输入消息"
                  disabled={busy}
                />
                <button type="submit" disabled={busy || status !== "可以使用"}>发送</button>
              </form>
            </div>
          )}

          {activePanel === "time" && (
            <div className="time-view">
              <strong>{now ? displayTime(now) : "--:--"}</strong>
              <p>{dayPeriod}</p>
              <span>{dateText}</span>
            </div>
          )}

          {activePanel === "weather" && (
            <div className="weather-view">
              {weather ? (
                <>
                  <p className="weather-place">{weather.location}</p>
                  <strong>{weather.temperature}℃</strong>
                  <h2>{weather.description}</h2>
                  <div className="weather-facts">
                    <span>体感温度<br /><b>{weather.apparentTemperature}℃</b></span>
                    <span>最高温度<br /><b>{weather.high ?? "--"}℃</b></span>
                    <span>最低温度<br /><b>{weather.low ?? "--"}℃</b></span>
                    <span>降雨可能<br /><b>{weather.precipitationProbability ?? "--"}%</b></span>
                  </div>
                  {weather.stale && <p className="data-note">当前显示最近一次天气信息</p>}
                </>
              ) : (
                <div className="empty-state"><strong>天气暂时没有连接</strong><p>可以稍后再试一次</p></div>
              )}
              <button className="refresh-button" type="button" onClick={() => void loadWeather()}>重新查看天气</button>
            </div>
          )}

          {activePanel === "news" && (
            <div className="news-view">
              {news.length ? (
                <ol>
                  {news.map((item, index) => (
                    <li key={item.url}>
                      <a href={item.url} target="_blank" rel="noreferrer">
                        <span>{index + 1}</span>
                        <strong>{item.title}</strong>
                        <small>{item.source}</small>
                      </a>
                    </li>
                  ))}
                </ol>
              ) : (
                <div className="empty-state"><strong>资讯暂时没有连接</strong><p>可以稍后再试一次</p></div>
              )}
              <button className="refresh-button" type="button" onClick={() => void loadNews()}>重新查看资讯</button>
            </div>
          )}

          {activePanel === "checkin" && (
            <div className="checkin-view">
              <div className="checkin-intro"><strong>花一分钟，记录今天的自己</strong><p>这是你的主观感受，不是考试，也不是疾病诊断。可以随时修改。</p></div>
              <div className="checkin-form">
                <RatingQuestion label="今天的心情怎么样？" value={checkInMood} onChange={setCheckInMood} labels={["很低落", "不太好", "一般", "还不错", "很好"]} />
                <RatingQuestion label="昨晚睡得怎么样？" value={checkInSleep} onChange={setCheckInSleep} labels={["很不好", "不太好", "一般", "还不错", "很好"]} />
                <RatingQuestion label="今天愿意和人聊聊吗？" value={checkInSocial} onChange={setCheckInSocial} labels={["不愿意", "比较少", "看情况", "愿意", "很愿意"]} />
              </div>
              <div className="checkin-sharing"><strong>你想把这次自述分享给谁？</strong><label><input type="checkbox" checked={checkInFamily} disabled={!checkIn || checkInBusy} onChange={(event) => { void updateCheckInSharing(event.target.checked, checkInCareTeam); }} /> 家属（只看到这三个分数和日期）</label><label><input type="checkbox" checked={checkInCareTeam} disabled={!checkIn || checkInBusy} onChange={(event) => { void updateCheckInSharing(checkInFamily, event.target.checked); }} /> 关怀团队（用于人工关注，不代表诊断）</label><small>不分享也可以保存；聊天全文不会因为打卡而开放。</small></div>
              <button className="checkin-submit" type="button" disabled={checkInBusy} onClick={() => { void saveCheckIn(); }}>{checkInBusy ? "保存中…" : checkIn ? "更新今天的自述" : "保存今天的自述"}</button>
              {checkInNotice && <p className="checkin-notice" role="status">{checkInNotice}</p>}
              {checkInHistory.length > 0 && <div className="checkin-history"><h2>最近 7 天</h2>{checkInHistory.map((item) => <div key={item.id}><time>{item.checkinDate}</time><span>心情 {item.mood}/5 · 睡眠 {item.sleep}/5 · 交流 {item.socialWillingness}/5</span><small>{item.shareWithFamily || item.shareWithCareTeam ? "已按选择分享" : "仅自己可见"}</small></div>)}</div>}
            </div>
          )}
        </section>
      )}
    </main>
  );
}

function RatingQuestion({ label, value, onChange, labels }: { label: string; value: number; onChange: (value: number) => void; labels: string[] }) {
  return <fieldset className="rating-question"><legend>{label}</legend><div>{labels.map((text, index) => { const score = index + 1; return <label key={text} className={value === score ? "selected" : ""}><input type="radio" name={label} checked={value === score} onChange={() => onChange(score)} /><span>{score}</span><small>{text}</small></label>; })}</div></fieldset>;
}

const COMPANION_STATE_LABELS: Record<CompanionVisualState, string> = {
  idle: "我在这里",
  listening: "正在听您说",
  thinking: "正在认真想",
  speaking: "正在和您说话",
  alert: "正在处理提醒",
  offline: "正在重新连接"
};

function CompanionAvatar({ name, state, compact = false }: { name: string; state: CompanionVisualState; compact?: boolean }) {
  const label = COMPANION_STATE_LABELS[state];
  return (
    <div className={`companion-avatar companion-${state}${compact ? " companion-compact" : ""}`} role="status" aria-live="polite" aria-atomic="true">
      <div className="companion-portrait" aria-hidden="true">
        <span className="companion-halo" />
        <Image src="/companion/yaoyao-avatar-v1.png" width={246} height={256} sizes={compact ? "92px" : "190px"} alt="" priority />
        <span className="companion-wave companion-wave-one" />
        <span className="companion-wave companion-wave-two" />
        <span className="companion-wave companion-wave-three" />
      </div>
      <span className="companion-caption"><strong>{name}</strong><small>{label}</small></span>
    </div>
  );
}
