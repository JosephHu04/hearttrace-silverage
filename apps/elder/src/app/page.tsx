"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api";
const DEMO_ACTOR = process.env.NEXT_PUBLIC_ELDER_DEMO_ACTOR_ID ?? "elder-demo-001";

type ChatMessage = { id: string; role: "user" | "assistant"; content: string; at: Date };
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
  const [now, setNow] = useState(new Date());
  const [status, setStatus] = useState("正在连接");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: "welcome", role: "assistant", content: "我在呢。您今天想说点什么？旧事、新鲜事，我都慢慢听。", at: new Date() }
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("遥遥正在回复");
  const [weather, setWeather] = useState<Weather | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const socketRef = useRef<WebSocket | null>(null);
  const tokenRef = useRef("");
  const assistantIdRef = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

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
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;

    async function connect() {
      try {
        const loginResponse = await fetch(`${API_BASE}/auth/demo-login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ actorId: DEMO_ACTOR })
        });
        const login = await loginResponse.json();
        if (!loginResponse.ok) throw new Error(login.detail ?? "演示账号登录失败");
        tokenRef.current = login.accessToken;

        const sessionResponse = await fetch(`${API_BASE}/conversations/sessions`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${login.accessToken}`,
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ saveMessages: false, allowAnalysis: false })
        });
        const session = await sessionResponse.json();
        if (!sessionResponse.ok) throw new Error(session.detail ?? "无法创建会话");
        if (cancelled) return;

        socket = new WebSocket(websocketEndpoint());
        socketRef.current = socket;
        socket.onopen = () => {
          socket?.send(JSON.stringify({
            type: "authenticate",
            accessToken: login.accessToken,
            sessionId: session.id
          }));
        };
        socket.onmessage = (event) => {
          const update = JSON.parse(event.data) as ServerEvent;
          if (update.type === "ready") {
            setStatus("在这里");
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
        socket.onclose = () => {
          if (!cancelled) {
            setStatus("暂时离线");
            setBusy(false);
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
  }, [loadNews, loadWeather]);

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

  const dateText = new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" }).format(now);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="identity">
          <span className="avatar" aria-hidden="true">遥</span>
          <div><h1>遥遥</h1><p><span className="status-dot" />{status}</p></div>
        </div>
        <div className="privacy-badge">本次对话不保存</div>
      </header>

      <section className="daily-glance" aria-label="今日信息">
        <article className="glance-card time-card">
          <p>现在时间</p><strong>{displayTime(now)}</strong><span>{dateText}</span>
        </article>
        <article className="glance-card weather-card">
          <div className="card-heading"><p>今日天气</p><button onClick={() => void loadWeather()} aria-label="刷新天气">↻</button></div>
          {weather ? (
            <><div className="weather-main"><strong>{weather.temperature}°</strong><div><span>{weather.description}</span><small>最高 {weather.high}° · 最低 {weather.low}°</small></div></div><footer>{weather.location}{weather.stale ? " · 缓存天气" : ""}</footer></>
          ) : <div className="empty-card">天气暂时未连接</div>}
        </article>
        <article className="glance-card news-card">
          <div className="card-heading"><p>最新资讯</p><button onClick={() => void loadNews()} aria-label="刷新资讯">↻</button></div>
          <ol>{news.length ? news.map((item) => <li key={item.url}><a href={item.url} target="_blank" rel="noreferrer">{item.title}<small>{item.source}</small></a></li>) : <li>资讯暂时未连接</li>}</ol>
        </article>
      </section>

      <section className="conversation" aria-label="对话">
        <div className="day-divider"><span>今天</span></div>
        <div className="messages" aria-live="polite">
          {messages.map((message) => (
            <article className={`message message-${message.role}`} key={message.id}>
              <div>{message.content.split("\n").filter(Boolean).map((line, index) => <p key={index}>{line}</p>)}</div>
              <time>{displayTime(message.at)}</time>
            </article>
          ))}
          {busy && <div className="thinking"><i /><i /><i /><em>{progress}</em></div>}
          <div ref={bottomRef} />
        </div>
      </section>

      <form className="composer" onSubmit={sendMessage}>
        <textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} rows={1} maxLength={8000} placeholder="想说什么都可以……" aria-label="输入消息" disabled={busy} />
        <button type="submit" disabled={busy || status !== "在这里"} aria-label="发送消息">→</button>
        <p>Enter 发送 · Shift + Enter 换行</p>
      </form>
    </main>
  );
}
