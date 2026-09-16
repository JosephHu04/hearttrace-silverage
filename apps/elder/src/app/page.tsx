"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

// All three clients configure the API origin. Accept the older /api suffix too.
const API_ORIGIN = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000")
  .replace(/\/api\/?$/, "")
  .replace(/\/$/, "");
const API_BASE = `${API_ORIGIN}/api`;

type ActivePanel = "home" | "chat" | "time" | "weather" | "news";
type ConsentMode = "private" | "care";
type EmergencyState = "idle" | "confirming" | "submitting" | "sent" | "error";
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

export default function ElderCompanionPage() {
  const router = useRouter();
  const [accessToken, setAccessToken] = useState("");
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
  const [weather, setWeather] = useState<Weather | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [emergencyState, setEmergencyState] = useState<EmergencyState>("idle");
  const [emergencyMessage, setEmergencyMessage] = useState("");
  const socketRef = useRef<WebSocket | null>(null);
  const tokenRef = useRef("");
  const assistantIdRef = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    try {
      const session = JSON.parse(sessionStorage.getItem("hearttrace.elder.session") ?? "null");
      if (!session?.accessToken || session.actor?.role !== "elder" || !Number.isFinite(Date.parse(session.expiresAt)) || Date.parse(session.expiresAt) <= Date.now()) throw new Error("expired");
      setAccessToken(session.accessToken);
      tokenRef.current = session.accessToken;
      setElderName(session.actor.displayName);
    } catch {
      sessionStorage.removeItem("hearttrace.elder.session");
      router.replace("/account");
    }
  }, [router]);

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
            allowAnalysis: consentMode === "care"
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
            sessionId: session.id
          }));
        };
        socket.onmessage = (event) => {
          const update = JSON.parse(event.data) as ServerEvent;
          if (update.type === "ready") {
            setStatus("可以使用");
            void Promise.allSettled([loadWeather(), loadNews()]);
          } else if (update.type === "progress") {
            const labels: Record<string, string> = {
              time: "正在读取时间",
              weather: "正在查看天气",
              news: "正在整理最新资讯"
            };
            setProgress(labels[update.kind ?? ""] ?? "遥遥正在回复");
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
            setProgress("遥遥正在回复");
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
  }, [accessToken, consentMode, connectionAttempt, loadNews, loadWeather, router]);

  function sendMessage(event: FormEvent) {
    event.preventDefault();
    const text = input.trim();
    if (!text || busy || socketRef.current?.readyState !== WebSocket.OPEN) return;
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: text, at: new Date() }]);
    setInput("");
    setBusy(true);
    assistantIdRef.current = null;
    socketRef.current.send(JSON.stringify({ type: "message", text }));
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
    setConsentMode(null);
    setActivePanel("home");
    setStatus("正在连接");
    setBusy(false);
    setInput("");
    setEmergencyState("idle");
    setEmergencyMessage("");
    setMessages([{ id: "welcome", role: "assistant", content: "我在呢。您今天想说点什么？旧事、新鲜事，我都慢慢听。", at: null }]);
  }

  const dateText = now ? new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "long", day: "numeric", weekday: "long" }).format(now) : "正在读取日期";
  const dayPeriod = !now ? "" : now.getHours() < 6 ? "凌晨" : now.getHours() < 12 ? "上午" : now.getHours() < 18 ? "下午" : "晚上";

  if (!accessToken) return <main className="consent-shell">正在确认登录状态…</main>;

  if (!consentMode) {
    return <main className="consent-shell">
      <section className="consent-card" aria-labelledby="consent-title">
        <p className="consent-brand">心迹银龄 · 遥遥</p>
        <button type="button" onClick={logout}>退出账号</button>
        <Link href="/account/security">修改密码</Link>
        <h1 id="consent-title">今天想怎样聊？</h1>
        <p className="consent-intro">请您自己选择。无论选哪一种，都可以正常聊天。</p>
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
        <button className="brand" type="button" onClick={() => setActivePanel("home")}>遥遥</button>
        <p className="welcome">{elderName}，{dayPeriod ? `${dayPeriod}好` : "您好"}</p>
        <div className="service-state"><span>{status}</span>{(status === "暂时离线" || status === "连接不稳") && <button type="button" onClick={() => { setStatus("正在连接"); setConnectionAttempt((value) => value + 1); }}>重新连接</button>}<small>{consentMode === "care" ? "已同意生成关怀摘要" : "本次对话不保存"}</small><button type="button" onClick={() => { void resetConversationConsent(); }}>停止保存与分析 / 重新选择</button><Link href="/account/security">修改密码</Link><button type="button" onClick={logout}>退出</button></div>
      </header>

      {activePanel === "home" && (
        <section className="feature-grid" aria-label="主要功能">
          <button className="feature-tile feature-chat" type="button" onClick={() => setActivePanel("chat")}>
            <strong>陪我聊聊</strong>
            <span>点一下，说说心里话</span>
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
            <h1>{activePanel === "chat" ? "陪我聊聊" : activePanel === "time" ? "现在时间" : activePanel === "weather" ? "今日天气" : "最新资讯"}</h1>
          </header>

          {activePanel === "chat" && (
            <div className="chat-layout">
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
        </section>
      )}
    </main>
  );
}
