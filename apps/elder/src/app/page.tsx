"use client";

import { FormEvent, useCallback, useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent, type RefObject } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { playWavAudio, startVoiceCapture, stopVoiceCapture, stopVoiceCaptureWithoutSaving, type VoiceCapture } from "@/lib/voice-audio";
import { MASCOT_SKIN_STORAGE_KEY, Mascot3D, type MascotKind, type MascotMood } from "@/components/Mascot3D";
import { HandsFreeCallCapture } from "@/components/HandsFreeCallCapture";
import { startRealtimeAsr, type RealtimeAsrSession } from "@/lib/realtime-asr";
import { splitSpokenText } from "@/lib/speech-chunks";

// All three clients configure the API origin. Accept the older /api suffix too.
const API_ORIGIN = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000")
  .replace(/\/api\/?$/, "")
  .replace(/\/$/, "");
const API_BASE = `${API_ORIGIN}/api`;

type ActivePanel = "home" | "chat" | "weather" | "news" | "checkin" | "voiceCall";
type ConsentMode = "private" | "care";
type EmergencyState = "idle" | "confirming" | "submitting" | "sent" | "error";
type CompanionVisualState = "idle" | "listening" | "thinking" | "speaking" | "alert" | "offline";
type CompanionIdleAction = "none" | "wave" | "bounce" | "peek" | "sparkle";
type VoiceState = "idle" | "recording" | "transcribing";
type VoiceCallPhase = "idle" | "listening" | "hearing" | "processing" | "speaking" | "muted" | "error";
type VoiceHealth = { asr: boolean; tts: boolean; realtimeAsr: boolean; checked: boolean };
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
  model?: string;
  modelReady?: boolean;
  data?: Weather | { items: NewsItem[]; stale: boolean } | { time: string; date: string; weekday: string };
};

function connectionNeedsAttention(value: string): boolean {
  return ["服务未启动", "连接不稳", "暂时离线", "模型未配置", "模型暂时不可用"].includes(value);
}

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
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [voiceHealth, setVoiceHealth] = useState<VoiceHealth>({ asr: false, tts: false, realtimeAsr: false, checked: false });
  const [voiceNotice, setVoiceNotice] = useState("正在检查语音服务");
  const [voiceCallPhase, setVoiceCallPhase] = useState<VoiceCallPhase>("idle");
  const [voiceCallNotice, setVoiceCallNotice] = useState("");
  const [voiceCallMuted, setVoiceCallMuted] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [companionIdleAction, setCompanionIdleAction] = useState<CompanionIdleAction>("none");
  const [companionReaction, setCompanionReaction] = useState("");
  const [mascotKind, setMascotKind] = useState<MascotKind>("moss");
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
  const assistantTextRef = useRef("");
  const pendingMessageRef = useRef("");
  const hasSentMessageRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const voiceCaptureRef = useRef<VoiceCapture | null>(null);
  const realtimeAsrRef = useRef<RealtimeAsrSession | null>(null);
  const voiceCallActiveRef = useRef(false);
  const voiceCallMutedRef = useRef(false);
  const voiceCallGenerationRef = useRef(0);
  const voicePressActiveRef = useRef(false);
  const voiceCaptureStartedAtRef = useRef(0);
  const lastVoiceKeyUpAtRef = useRef(0);
  const voiceTimerRef = useRef<number | null>(null);
  const playbackContextRef = useRef<AudioContext | null>(null);
  const playbackSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const mouthLevelRef = useRef(0);
  const speechRequestSeqRef = useRef(0);
  const speechBufferRef = useRef("");
  const speechQueueRef = useRef<string[]>([]);
  const speechDrainRef = useRef<Promise<void> | null>(null);
  const speechAbortRef = useRef<AbortController | null>(null);
  const characterActionTimerRef = useRef<number | null>(null);
  const voiceHealthRef = useRef(voiceHealth);
  const ttsEnabledRef = useRef(ttsEnabled);

  useEffect(() => { voiceHealthRef.current = voiceHealth; }, [voiceHealth]);
  useEffect(() => { ttsEnabledRef.current = ttsEnabled; }, [ttsEnabled]);

  useEffect(() => {
    const stored = window.localStorage.getItem(MASCOT_SKIN_STORAGE_KEY);
    if (stored === "moss" || stored === "cloud") setMascotKind(stored);
  }, []);

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
    if (!accessToken) return;
    let cancelled = false;
    async function checkVoiceServices() {
      try {
        const response = await fetch(`${API_BASE}/speech/health`, { headers: { Authorization: `Bearer ${tokenRef.current}` } });
        if (!response.ok) throw new Error("语音服务检查失败");
        const result = await response.json() as { asr?: boolean; tts?: boolean; realtimeAsr?: boolean };
        if (cancelled) return;
        const health = { asr: result.asr === true, tts: result.tts === true, realtimeAsr: result.realtimeAsr === true, checked: true };
        setVoiceHealth(health);
        if (voiceState === "idle") setVoiceNotice(health.asr && health.tts ? "语音识别和回复播报已就绪" : health.asr ? "可以语音输入，回复播报暂未连接" : health.tts ? "可以播放回复，语音输入暂未连接" : "语音服务暂未启动");
      } catch {
        if (!cancelled) {
          setVoiceHealth({ asr: false, tts: false, realtimeAsr: false, checked: true });
          if (voiceState === "idle") setVoiceNotice("连接语音服务失败；系统会自动重试");
        }
      }
    }
    void checkVoiceServices();
    const timer = window.setInterval(() => { void checkVoiceServices(); }, 15_000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [accessToken, voiceState]);

  useEffect(() => () => {
    voiceCallActiveRef.current = false;
    voiceCallGenerationRef.current += 1;
    if (voiceTimerRef.current !== null) window.clearTimeout(voiceTimerRef.current);
    if (characterActionTimerRef.current !== null) window.clearTimeout(characterActionTimerRef.current);
    if (voiceCaptureRef.current) stopVoiceCaptureWithoutSaving(voiceCaptureRef.current);
    realtimeAsrRef.current?.cancel();
    speechRequestSeqRef.current += 1;
    speechAbortRef.current?.abort();
    speechQueueRef.current = [];
    speechBufferRef.current = "";
    playbackSourceRef.current?.stop();
    mouthLevelRef.current = 0;
    void playbackContextRef.current?.close();
  }, []);

  useEffect(() => {
    const stopHiddenCall = () => {
      if (!document.hidden || !voiceCallActiveRef.current) return;
      voiceCallActiveRef.current = false;
      voiceCallMutedRef.current = false;
      voiceCallGenerationRef.current += 1;
      realtimeAsrRef.current?.cancel();
      realtimeAsrRef.current = null;
      speechRequestSeqRef.current += 1;
      speechAbortRef.current?.abort();
      speechQueueRef.current = [];
      speechBufferRef.current = "";
      playbackSourceRef.current?.stop();
      playbackSourceRef.current = null;
      mouthLevelRef.current = 0;
      setIsSpeaking(false);
      setVoiceCallMuted(false);
      setVoiceCallPhase("idle");
      setActivePanel("home");
    };
    document.addEventListener("visibilitychange", stopHiddenCall);
    return () => document.removeEventListener("visibilitychange", stopHiddenCall);
  }, []);

  const playCharacterAction = useCallback((action: Exclude<CompanionIdleAction, "none">, reaction: string, duration = 2200) => {
    if (characterActionTimerRef.current !== null) window.clearTimeout(characterActionTimerRef.current);
    setCompanionIdleAction(action);
    setCompanionReaction(reaction);
    characterActionTimerRef.current = window.setTimeout(() => {
      setCompanionIdleAction("none");
      setCompanionReaction("");
      characterActionTimerRef.current = null;
    }, duration);
  }, []);

  const prepareSpeechPlayback = useCallback(() => {
    if (!voiceHealthRef.current.tts || !ttsEnabledRef.current) return;
    if (!playbackContextRef.current || playbackContextRef.current.state === "closed") {
      playbackContextRef.current = new AudioContext({ latencyHint: "interactive" });
    }
    if (playbackContextRef.current.state === "suspended") void playbackContextRef.current.resume();
  }, []);

  const speakAssistantReply = useCallback(async (text: string, requestId: number): Promise<boolean> => {
    const clean = text.replace(/\[[^\]]+\]/g, "").trim().slice(0, 800);
    if (!clean || !voiceHealthRef.current.tts || !ttsEnabledRef.current) return false;
    const controller = new AbortController();
    speechAbortRef.current = controller;
    try {
      prepareSpeechPlayback();
      const response = await fetch(`${API_BASE}/speech/synthesize`, {
        method: "POST",
        headers: { Authorization: `Bearer ${tokenRef.current}`, "Content-Type": "application/json" },
        body: JSON.stringify({ text: clean }),
        signal: controller.signal
      });
      if (!response.ok) throw new Error("回复播报暂时失败");
      const context = playbackContextRef.current;
      if (!context || requestId !== speechRequestSeqRef.current || !ttsEnabledRef.current) return false;
      if (response.headers.get("X-Audio-Format") !== "wav") throw new Error("语音格式不受支持");
      await playWavAudio(context, await response.arrayBuffer(), (source) => {
        if (requestId !== speechRequestSeqRef.current) return;
        playbackSourceRef.current = source;
        setIsSpeaking(Boolean(source));
      }, (level) => {
        if (requestId === speechRequestSeqRef.current) mouthLevelRef.current = level;
      }, () => requestId === speechRequestSeqRef.current && ttsEnabledRef.current);
      return requestId === speechRequestSeqRef.current;
    } catch {
      if (requestId === speechRequestSeqRef.current) setVoiceNotice("这次回复没能播出，文字已正常显示");
      return false;
    } finally {
      if (speechAbortRef.current === controller) speechAbortRef.current = null;
      if (requestId === speechRequestSeqRef.current) {
        mouthLevelRef.current = 0;
        setIsSpeaking(false);
      }
    }
  }, [prepareSpeechPlayback]);

  const drainSpeechQueue = useCallback((): Promise<void> => {
    if (speechDrainRef.current) return speechDrainRef.current;
    const requestId = speechRequestSeqRef.current;
    const running = (async () => {
      while (requestId === speechRequestSeqRef.current && speechQueueRef.current.length) {
        const segment = speechQueueRef.current.shift();
        if (!segment) continue;
        if (voiceCallActiveRef.current) {
          setVoiceCallPhase("speaking");
          setVoiceCallNotice("遥遥正在回答；说完后会继续听您说");
        }
        const played = await speakAssistantReply(segment, requestId);
        if (!played) {
          if (requestId === speechRequestSeqRef.current) speechQueueRef.current = [];
          break;
        }
      }
    })();
    speechDrainRef.current = running;
    void running.finally(() => {
      if (speechDrainRef.current === running) {
        speechDrainRef.current = null;
        if (speechQueueRef.current.length && requestId === speechRequestSeqRef.current) void drainSpeechQueue();
      }
    });
    return running;
  }, [speakAssistantReply]);

  const queueSpokenText = useCallback((delta: string, flush = false): Promise<void> => {
    if (!voiceHealthRef.current.tts || !ttsEnabledRef.current) return Promise.resolve();
    const split = splitSpokenText(speechBufferRef.current + delta, flush);
    speechBufferRef.current = split.remaining;
    speechQueueRef.current.push(...split.segments);
    return drainSpeechQueue();
  }, [drainSpeechQueue]);

  const stopSpeaking = useCallback(() => {
    speechRequestSeqRef.current += 1;
    speechAbortRef.current?.abort();
    speechAbortRef.current = null;
    speechBufferRef.current = "";
    speechQueueRef.current = [];
    speechDrainRef.current = null;
    try { playbackSourceRef.current?.stop(); } catch { /* already stopped */ }
    playbackSourceRef.current = null;
    mouthLevelRef.current = 0;
    setIsSpeaking(false);
  }, []);

  function endVoiceCall() {
    voiceCallActiveRef.current = false;
    voiceCallMutedRef.current = false;
    realtimeAsrRef.current?.cancel();
    realtimeAsrRef.current = null;
    setVoiceCallMuted(false);
    voiceCallGenerationRef.current += 1;
    stopSpeaking();
    setVoiceCallPhase("idle");
    setVoiceCallNotice("");
    setActivePanel("home");
  }

  function startVoiceCall() {
    if (status !== "可以使用" || !voiceHealth.asr || !voiceHealth.tts || busy || voiceState !== "idle") return;
    prepareSpeechPlayback();
    stopSpeaking();
    realtimeAsrRef.current?.cancel();
    realtimeAsrRef.current = null;
    voiceCallActiveRef.current = true;
    voiceCallMutedRef.current = false;
    setVoiceCallMuted(false);
    voiceCallGenerationRef.current += 1;
    ttsEnabledRef.current = true;
    setTtsEnabled(true);
    setVoiceCallNotice("直接说话即可，说完稍停会自动发送。您可以随时结束。");
    setVoiceCallPhase("listening");
    setActivePanel("voiceCall");
  }

  async function sendVoiceCallTurn(wav: Blob) {
    if (!voiceCallActiveRef.current || voiceCallMutedRef.current) return;
    const generation = voiceCallGenerationRef.current;
    const realtime = realtimeAsrRef.current;
    realtimeAsrRef.current = null;
    setVoiceCallPhase("processing");
    setVoiceCallNotice("正在听懂您说的话…");
    try {
      if (realtime) {
        let transcript = "";
        try { transcript = (await realtime.finish()).trim(); }
        catch { /* Fall back to the existing complete-WAV route. */ }
        if (!voiceCallActiveRef.current || voiceCallMutedRef.current || generation !== voiceCallGenerationRef.current) return;
        if (transcript) {
          if (!sendChatText(transcript)) throw new Error("连接暂不可用，请结束后重新连接");
          setVoiceCallNotice("已经收到，正在回答您…");
          return;
        }
      }
      const response = await fetch(`${API_BASE}/speech/transcribe`, {
        method: "POST",
        headers: { Authorization: `Bearer ${tokenRef.current}`, "Content-Type": "audio/wav" },
        body: wav
      });
      const result = await response.json() as { text?: string; detail?: string };
      if (!voiceCallActiveRef.current || voiceCallMutedRef.current || generation !== voiceCallGenerationRef.current) return;
      if (!response.ok) throw new Error(result.detail ?? "这次没听清，请再说一次");
      const transcript = result.text?.trim() ?? "";
      if (!transcript) throw new Error("这次没听清，请再说一次");
      if (!sendChatText(transcript)) throw new Error("连接暂不可用，请结束后重新连接");
      setVoiceCallNotice("已经收到，正在回答您…");
    } catch (error) {
      realtime?.cancel();
      if (!voiceCallActiveRef.current || generation !== voiceCallGenerationRef.current) return;
      setVoiceCallNotice(error instanceof Error ? error.message : "语音识别失败，请再试一次");
      setVoiceCallPhase(socketRef.current?.readyState === WebSocket.OPEN ? "listening" : "error");
    }
  }

  function voiceCallError(message: string) {
    if (!voiceCallActiveRef.current) return;
    realtimeAsrRef.current?.cancel();
    realtimeAsrRef.current = null;
    setVoiceCallNotice(message);
    setVoiceCallPhase("error");
  }

  function toggleVoiceCallMute() {
    const next = !voiceCallMutedRef.current;
    voiceCallMutedRef.current = next;
    setVoiceCallMuted(next);
    if (next) {
      realtimeAsrRef.current?.cancel();
      realtimeAsrRef.current = null;
    }
    if (next && (voiceCallPhase === "listening" || voiceCallPhase === "hearing")) {
      setVoiceCallPhase("muted");
      setVoiceCallNotice("麦克风已暂停，不会发送这一段声音");
    } else if (!next && voiceCallPhase === "muted") {
      setVoiceCallPhase("listening");
      setVoiceCallNotice("我在听，请继续说…");
    }
  }

  async function stopAndTranscribe() {
    const capture = voiceCaptureRef.current;
    if (!capture) return;
    voiceCaptureRef.current = null;
    const realtime = realtimeAsrRef.current;
    realtimeAsrRef.current = null;
    if (voiceTimerRef.current !== null) window.clearTimeout(voiceTimerRef.current);
    voiceTimerRef.current = null;
    setVoiceState("transcribing");
    setVoiceNotice("正在识别您刚才说的话…");
    try {
      const wav = await stopVoiceCapture(capture);
      if (wav.size <= 44) throw new Error("没有录到声音");
      if (realtime) {
        let transcript = "";
        try { transcript = (await realtime.finish()).trim(); }
        catch { /* Fall back to the complete WAV when realtime ASR fails. */ }
        if (transcript) {
          if (!sendChatText(transcript)) throw new Error("连接暂不可用，这次语音没有发送，请重试");
          setVoiceNotice("已发送，遥遥正在回复…");
          return;
        }
      }
      const response = await fetch(`${API_BASE}/speech/transcribe`, {
        method: "POST",
        headers: { Authorization: `Bearer ${tokenRef.current}`, "Content-Type": "audio/wav" },
        body: wav
      });
      const result = await response.json() as { text?: string; detail?: string };
      if (!response.ok) throw new Error(result.detail ?? "语音识别失败");
      const transcript = result.text?.trim() ?? "";
      if (!transcript) throw new Error("这次没有听清，请再说一次");
      if (!sendChatText(transcript)) throw new Error("连接暂不可用，这次语音没有发送，请重试");
      setVoiceNotice("已发送，遥遥正在回复…");
    } catch (error) {
      realtime?.cancel();
      setVoiceNotice(error instanceof Error ? error.message : "语音识别失败，请再试一次");
    } finally {
      setVoiceState("idle");
    }
  }

  async function beginVoiceCapture() {
    if (voicePressActiveRef.current || voiceState !== "idle" || busy || status !== "可以使用" || !voiceHealth.asr) return;
    voicePressActiveRef.current = true;
    setVoiceState("recording");
    setVoiceNotice("正在听，松手后立即发送；移出按钮可取消");
    try {
      prepareSpeechPlayback();
      stopSpeaking();
      if (voiceHealthRef.current.realtimeAsr) realtimeAsrRef.current = startRealtimeAsr(API_ORIGIN, tokenRef.current);
      const capture = await startVoiceCapture((samples, sampleRate) => realtimeAsrRef.current?.push(samples, sampleRate));
      if (!voicePressActiveRef.current) {
        stopVoiceCaptureWithoutSaving(capture);
        realtimeAsrRef.current?.cancel();
        realtimeAsrRef.current = null;
        return;
      }
      voiceCaptureRef.current = capture;
      voiceCaptureStartedAtRef.current = performance.now();
      voiceTimerRef.current = window.setTimeout(() => {
        voicePressActiveRef.current = false;
        void stopAndTranscribe();
      }, 45_000);
    } catch (error) {
      realtimeAsrRef.current?.cancel();
      realtimeAsrRef.current = null;
      voicePressActiveRef.current = false;
      setVoiceState("idle");
      setVoiceNotice(error instanceof Error ? error.message : "无法使用麦克风，请检查浏览器权限");
    }
  }

  function cancelVoiceCapture() {
    if (!voicePressActiveRef.current) return;
    voicePressActiveRef.current = false;
    if (voiceTimerRef.current !== null) window.clearTimeout(voiceTimerRef.current);
    voiceTimerRef.current = null;
    const capture = voiceCaptureRef.current;
    voiceCaptureRef.current = null;
    realtimeAsrRef.current?.cancel();
    realtimeAsrRef.current = null;
    if (capture) stopVoiceCaptureWithoutSaving(capture);
    setVoiceState("idle");
    setVoiceNotice("已取消录音，没有发送");
  }

  function finishVoiceCapture() {
    if (!voicePressActiveRef.current) return;
    if (!voiceCaptureRef.current || performance.now() - voiceCaptureStartedAtRef.current < 250) {
      cancelVoiceCapture();
      setVoiceNotice("请按住说话，松手后会立即发送");
      return;
    }
    voicePressActiveRef.current = false;
    void stopAndTranscribe();
  }

  function toggleAccessibleVoiceCapture() {
    if (voicePressActiveRef.current) finishVoiceCapture();
    else void beginVoiceCapture();
  }

  function onVoicePointerDown(event: ReactPointerEvent<HTMLButtonElement>) {
    if (event.button !== 0 || !event.isPrimary) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    void beginVoiceCapture();
  }

  function onVoicePointerUp(event: ReactPointerEvent<HTMLButtonElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    const bounds = event.currentTarget.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) cancelVoiceCapture();
    else finishVoiceCapture();
  }

  function onVoiceKeyDown(event: ReactKeyboardEvent<HTMLButtonElement>) {
    if ((event.key !== " " && event.key !== "Enter") || event.repeat) return;
    event.preventDefault();
    void beginVoiceCapture();
  }

  function onVoiceKeyUp(event: ReactKeyboardEvent<HTMLButtonElement>) {
    if (event.key !== " " && event.key !== "Enter") return;
    event.preventDefault();
    lastVoiceKeyUpAtRef.current = performance.now();
    finishVoiceCapture();
  }

  function onVoiceClick(event: ReactMouseEvent<HTMLButtonElement>) {
    // Screen-reader activation fires click without pointer/key events.
    if (event.detail === 0 && performance.now() - lastVoiceKeyUpAtRef.current > 400) toggleAccessibleVoiceCapture();
  }

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
    voiceCallActiveRef.current = false;
    voiceCallGenerationRef.current += 1;
    realtimeAsrRef.current?.cancel();
    realtimeAsrRef.current = null;
    socketRef.current?.close();
    if (voiceCaptureRef.current) {
      stopVoiceCaptureWithoutSaving(voiceCaptureRef.current);
      voiceCaptureRef.current = null;
    }
    stopSpeaking();
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
    const canPlayIdleAction = activePanel === "home"
      && status === "可以使用"
      && !busy
      && !isSpeaking
      && voiceState === "idle"
      && emergencyState === "idle";
    if (!canPlayIdleAction) {
      setCompanionIdleAction("none");
      setCompanionReaction("");
      return;
    }
    const actions: Array<{ action: Exclude<CompanionIdleAction, "none">; reaction: string; duration: number }> = [
      { action: "wave", reaction: "嗨，我在这里", duration: 2400 },
      { action: "bounce", reaction: "今天也要好好的", duration: 2100 },
      { action: "peek", reaction: "想说什么都可以", duration: 2500 },
      { action: "sparkle", reaction: "我来陪您啦", duration: 2300 }
    ];
    let idleTimer = window.setTimeout(function scheduleAction() {
      const next = actions[Math.floor(Math.random() * actions.length)];
      playCharacterAction(next.action, next.reaction, next.duration);
      idleTimer = window.setTimeout(scheduleAction, next.duration + 7000 + Math.random() * 7000);
    }, 5000 + Math.random() * 5000);
    return () => window.clearTimeout(idleTimer);
  }, [activePanel, busy, emergencyState, isSpeaking, playCharacterAction, status, voiceState]);

  useEffect(() => {
    if (!consentMode || !accessToken) return;
    let cancelled = false;
    let socket: WebSocket | null = null;
    let retryTimer: number | null = null;
    const retryLater = () => {
      if (cancelled || retryTimer !== null) return;
      retryTimer = window.setTimeout(() => {
        retryTimer = null;
        if (!cancelled) {
          setStatus("正在连接");
          setConnectionAttempt((value) => value + 1);
        }
      }, 5000);
    };

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
            const modelReady = update.modelReady !== false;
            setStatus(modelReady ? "可以使用" : "模型未配置");
            if (voiceCallActiveRef.current && !modelReady) {
              setVoiceCallPhase("error");
              setVoiceCallNotice("聊天模型还没有配置，语音对话暂不可用");
            }
            void Promise.allSettled([loadWeather(), loadNews()]);
            const pending = pendingMessageRef.current;
            if (modelReady && pending && socket?.readyState === WebSocket.OPEN) {
              pendingMessageRef.current = "";
              hasSentMessageRef.current = true;
              setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: pending, at: new Date() }]);
              setBusy(true);
              socket.send(JSON.stringify({ type: "message", text: pending, knowledge: relevantKnowledge(selectedPersona, pending) }));
            }
          } else if (update.type === "meta") {
            if (update.model === "local-model-unconfigured") setStatus("模型未配置");
            else if (update.model === "local-network-fallback") setStatus("模型暂时不可用");
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
            assistantTextRef.current += update.text;
            void queueSpokenText(update.text);
            let assistantId = assistantIdRef.current;
            if (!assistantId) {
              assistantId = crypto.randomUUID();
              assistantIdRef.current = assistantId;
              setMessages((current) => [...current, { id: assistantId as string, role: "assistant", content: update.text as string, at: new Date() }]);
            } else {
              setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, content: item.content + update.text } : item));
            }
          } else if (update.type === "done") {
            const spokenReply = assistantTextRef.current;
            assistantTextRef.current = "";
            assistantIdRef.current = null;
            setBusy(false);
            setProgress(`${selectedPersona.name}正在回复`);
            const playback = (async () => {
              if (spokenReply) await queueSpokenText("", true);
              while (speechQueueRef.current.length || speechDrainRef.current) await drainSpeechQueue();
            })();
            if (voiceCallActiveRef.current) {
              const generation = voiceCallGenerationRef.current;
              setVoiceCallPhase("speaking");
              setVoiceCallNotice("遥遥正在回答；说完后会继续听您说");
              void playback.finally(() => {
                if (voiceCallActiveRef.current && generation === voiceCallGenerationRef.current) {
                  setVoiceCallPhase(voiceCallMutedRef.current ? "muted" : "listening");
                  setVoiceCallNotice(voiceCallMutedRef.current ? "麦克风已暂停" : "我在听，请继续说…");
                }
              });
            }
          } else if (update.type === "error") {
            stopSpeaking();
            setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: update.message ?? "刚才没有接住，请再说一次。", at: new Date() }]);
            assistantIdRef.current = null;
            assistantTextRef.current = "";
            setBusy(false);
            if (voiceCallActiveRef.current) {
              setVoiceCallNotice("这次没能回答，您可以再说一次");
              setVoiceCallPhase(voiceCallMutedRef.current ? "muted" : "listening");
            }
          }
        };
        socket.onclose = (event) => {
          if (!cancelled) {
            stopSpeaking();
            if (event.code === 4401) {
              sessionStorage.removeItem("hearttrace.elder.session");
              setAccessToken("");
              router.replace("/account");
              return;
            }
            setStatus("暂时离线");
            if (voiceCallActiveRef.current) {
              setVoiceCallPhase("error");
              setVoiceCallNotice("语音连接中断，请结束后重新开启");
            }
            setBusy(false);
            assistantIdRef.current = null;
            assistantTextRef.current = "";
            retryLater();
          }
        };
        socket.onerror = () => setStatus("连接不稳");
      } catch (error) {
        if (!cancelled) {
          setStatus(error instanceof TypeError ? "服务未启动" : error instanceof Error ? error.message : "暂时离线");
          retryLater();
        }
      }
    }

    void connect();
    return () => {
      cancelled = true;
      if (retryTimer !== null) window.clearTimeout(retryTimer);
      socket?.close();
    };
  }, [accessToken, consentMode, connectionAttempt, drainSpeechQueue, loadNews, loadWeather, queueSpokenText, router, selectedPersona, stopSpeaking]);

  function restartWithPersona(personaId: string, pendingMessage = "", profileOverride?: Persona) {
    socketRef.current?.close();
    socketRef.current = null;
    sessionIdRef.current = "";
    assistantIdRef.current = null;
    assistantTextRef.current = "";
    pendingMessageRef.current = pendingMessage;
    hasSentMessageRef.current = false;
    const nextPersona = profileOverride ?? personas.find((item) => item.id === personaId) ?? DEFAULT_PERSONA;
    setSelectedPersonaId(nextPersona.id);
    setStatus("正在连接");
    setProgress(`${nextPersona.name}正在回复`);
    setMessages([{ id: "welcome", role: "assistant", content: `${nextPersona.name}在呢。您慢慢说。`, at: null }]);
    setConnectionAttempt((value) => value + 1);
  }

  function sendChatText(rawText: string): boolean {
    const text = rawText.trim();
    const socket = socketRef.current;
    if (!text || busy || status !== "可以使用" || socket?.readyState !== WebSocket.OPEN) return false;
    if (autoPersona && !hasSentMessageRef.current) {
      const ranked = personas
        .map((persona) => ({
          persona,
          score: persona.scenarios.reduce((sum, scenario) => sum + (scenario && text.includes(scenario) ? scenario.length : 0), 0)
        }))
        .filter(({ score }) => score > 0)
        .sort((left, right) => right.score - left.score);
      if (ranked.length && ranked[0].persona.id !== selectedPersona.id && (ranked.length === 1 || ranked[0].score > ranked[1].score)) {
        restartWithPersona(ranked[0].persona.id, text);
        return true;
      }
    }
    prepareSpeechPlayback();
    stopSpeaking();
    try {
      socket.send(JSON.stringify({ type: "message", text, knowledge: relevantKnowledge(selectedPersona, text) }));
    } catch {
      setStatus("连接不稳");
      return false;
    }
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: text, at: new Date() }]);
    setBusy(true);
    hasSentMessageRef.current = true;
    assistantIdRef.current = null;
    assistantTextRef.current = "";
    return true;
  }

  function sendMessage(event: FormEvent) {
    event.preventDefault();
    if (voiceState !== "idle") return;
    if (sendChatText(input)) setInput("");
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
    voiceCallActiveRef.current = false;
    voiceCallGenerationRef.current += 1;
    stopSpeaking();
    setVoiceCallPhase("idle");
    socketRef.current = null;
    assistantIdRef.current = null;
    assistantTextRef.current = "";
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
  const latestAssistantMessage = [...messages].reverse().find((message) => message.role === "assistant");
  const companionVisualState: CompanionVisualState = emergencyState !== "idle"
    ? "alert"
    : connectionNeedsAttention(status)
      ? "offline"
      : status === "正在连接"
        ? "thinking"
        : voiceState === "recording"
          ? "listening"
          : isSpeaking
            ? "speaking"
            : busy
          ? latestMessage?.role === "assistant" ? "speaking" : "thinking"
          : activePanel === "chat" ? "listening" : "idle";
  const mascotMood: MascotMood = companionVisualState === "listening" ? "listen"
    : companionVisualState === "speaking" ? "talk"
    : companionVisualState === "thinking" ? "think"
    : companionVisualState === "alert" ? "alert"
    : companionVisualState === "offline" ? "offline"
    : companionIdleAction === "wave" ? "hello"
    : companionIdleAction === "bounce" || companionIdleAction === "sparkle" ? "happy"
    : companionIdleAction === "peek" ? "listen" : "idle";

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
        <button className="brand" type="button" onClick={() => { if (voiceCallActiveRef.current) endVoiceCall(); else setActivePanel("home"); }}>{selectedPersona.name}</button>
        <p className="welcome">{elderName}，{dayPeriod ? `${dayPeriod}好` : "您好"}</p>
        <div className="service-state">
          <span>{status}</span>
          <small>{consentMode === "care" ? "关怀摘要已开启" : "本次对话不保存"}</small>
          {connectionNeedsAttention(status) && <button type="button" onClick={() => { setStatus("正在连接"); setConnectionAttempt((value) => value + 1); }}>重新连接</button>}
          <details className="session-menu">
            <summary>账户与隐私</summary>
            <div>
              <button type="button" onClick={() => { void resetConversationConsent(); }}>停止保存与分析 / 重新选择</button>
              <Link href="/companion-3d/mascot-preview">精灵造型与表情预览</Link>
              <Link href="/account/security">修改密码</Link>
              <button type="button" onClick={logout}>退出账号</button>
            </div>
          </details>
        </div>
      </header>

      {activePanel === "home" && (
        <section className="companion-lobby" aria-label="遥遥陪伴大厅">
          <div className={`lobby-stage lobby-${companionVisualState}`}>
            <div className="lobby-light lobby-light-one" aria-hidden="true" />
            <div className="lobby-light lobby-light-two" aria-hidden="true" />

            <div className="lobby-glance">
              <span>{dateText}</span>
              <strong>{now ? displayTime(now) : "--:--"}</strong>
              <button type="button" onClick={() => setActivePanel("weather")}>
                {weather ? `${weather.temperature}℃ · ${weather.description}` : "查看今日天气"}
              </button>
            </div>

            <button
              className={`lobby-character lobby-character-${companionVisualState} lobby-action-${companionIdleAction}`}
              type="button"
              onClick={() => {
                if (companionVisualState === "idle") playCharacterAction("wave", "我在呢！想说什么都可以", 2600);
              }}
              onPointerMove={(event) => {
                const rect = event.currentTarget.getBoundingClientRect();
                event.currentTarget.style.setProperty("--look-x", `${((event.clientX - rect.left) / rect.width - 0.5) * 10}px`);
                event.currentTarget.style.setProperty("--look-y", `${((event.clientY - rect.top) / rect.height - 0.5) * 7}px`);
              }}
              onPointerLeave={(event) => {
                event.currentTarget.style.setProperty("--look-x", "0px");
                event.currentTarget.style.setProperty("--look-y", "0px");
              }}
              aria-label={`${mascotKind === "moss" ? "小芽" : "小云"}陪伴精灵，${status === "模型未配置" ? "聊天待配置" : COMPANION_STATE_LABELS[companionVisualState]}，点击打招呼`}
            >
              <span className="lobby-character-ring" aria-hidden="true" />
              <span className="lobby-character-body" aria-hidden="true">
                <Mascot3D kind={mascotKind} mood={mascotMood} mouthLevelRef={mouthLevelRef} transparent lobby />
              </span>
              {companionReaction && <span className="lobby-character-reaction" aria-live="polite">{companionReaction}</span>}
              <span className="lobby-character-sparkles" aria-hidden="true"><i /> <i /> <i /></span>
              <span className="lobby-character-name"><strong>{mascotKind === "moss" ? "小芽" : "小云"} · {selectedPersona.name}</strong><small>{status === "模型未配置" ? "聊天待配置" : COMPANION_STATE_LABELS[companionVisualState]}</small></span>
            </button>

            <section className="lobby-speech" aria-live="polite" aria-atomic="true">
              <span>{connectionNeedsAttention(status) ? "陪伴聊天暂不可用" : busy ? progress : `${selectedPersona.name}想对您说`}</span>
              <p>{connectionNeedsAttention(status) ? status === "模型未配置" ? "聊天模型还没有配置，请联系管理员；紧急情况仍可使用呼救功能。" : "正在尝试重新连接。其他不依赖聊天的功能仍可使用。" : busy && latestMessage?.role !== "assistant" ? "我听到了，正在认真想怎么回答您。" : latestAssistantMessage?.content ?? "我在呢，您今天想聊点什么？"}</p>
              <button type="button" onClick={() => setActivePanel("chat")}>查看对话记录</button>
            </section>

            <nav className="lobby-actions" aria-label="常用功能">
              <button type="button" aria-label="每日自述，记录今天的状态" onClick={() => setActivePanel("checkin")}><span className="lobby-action-mark" aria-hidden="true">记</span><span>每日自述</span></button>
              <Link href="/screening" aria-label="关怀小测，本人愿意时再做"><span className="lobby-action-mark" aria-hidden="true">测</span><span>关怀小测</span></Link>
              <button type="button" aria-label="听听资讯，看看今天的新鲜事" onClick={() => setActivePanel("news")}><span className="lobby-action-mark" aria-hidden="true">听</span><span>听听资讯</span></button>
              <button type="button" aria-label="陪伴设置，选择不同说话风格" aria-expanded={personaManagerOpen} onClick={() => setPersonaManagerOpen((open) => !open)}><span className="lobby-action-mark" aria-hidden="true">伴</span><span>陪伴设置</span></button>
            </nav>

            <button className="lobby-emergency" type="button" disabled={emergencyState === "submitting" || emergencyState === "sent"} onClick={() => setEmergencyState("confirming")}>
              {emergencyState === "sent" ? "求助已发出" : "紧急呼救"}
            </button>

            <div className="lobby-voice-control">
              <button
                className={`voice-button${voiceState === "recording" ? " recording" : ""}`}
                type="button"
                onPointerDown={onVoicePointerDown}
                onPointerUp={onVoicePointerUp}
                onPointerCancel={cancelVoiceCapture}
                onKeyDown={onVoiceKeyDown}
                onKeyUp={onVoiceKeyUp}
                onClick={onVoiceClick}
                disabled={voiceState === "transcribing" || (voiceState !== "recording" && (busy || status !== "可以使用" || !voiceHealth.asr))}
                aria-describedby="lobby-voice-hint"
              >
                {voiceState === "recording" ? "松开发送" : voiceState === "transcribing" ? "识别并发送中…" : "按住说话"}
              </button>
              <p id="lobby-voice-hint" role="status">{voiceNotice === "语音识别和回复播报已就绪" ? "松手自动发送 · 语音由阿里云识别" : voiceNotice}</p>
            </div>
          </div>

          {personaManagerOpen && (
            <section className="persona-home-card lobby-persona-manager" aria-labelledby="persona-home-title">
              <div className="persona-home-heading">
                <div>
                  <p>当前陪伴者</p>
                  <h2 id="persona-home-title">{selectedPersona.name}</h2>
                  <span>{selectedPersona.role}</span>
                </div>
                <button type="button" onClick={() => setPersonaManagerOpen(false)}>收起管理</button>
              </div>
              <div className="persona-quick-list" aria-label="选择陪伴者">
                {personas.map((persona) => (
                  <button className={persona.id === selectedPersona.id ? "selected" : ""} type="button" key={persona.id} onClick={() => restartWithPersona(persona.id)}>
                    <strong>{persona.name}</strong><span>{persona.style}</span>
                  </button>
                ))}
              </div>
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
            </section>
          )}
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
            <button className="back-button" type="button" onClick={() => { if (voiceCallActiveRef.current) endVoiceCall(); else setActivePanel("home"); }}>返回首页</button>
            <h1>{activePanel === "voiceCall" ? `与${selectedPersona.name}语音对话` : activePanel === "chat" ? `和${selectedPersona.name}聊聊` : activePanel === "weather" ? "今日天气" : activePanel === "checkin" ? "每日自述" : "最新资讯"}</h1>
          </header>

          {activePanel === "voiceCall" && (
            <div className="voice-call-layout">
              {(voiceCallPhase === "listening" || voiceCallPhase === "hearing") && !voiceCallMuted && status === "可以使用" && (
                <HandsFreeCallCapture
                  onSpeechStart={(preRoll, sampleRate) => {
                    setVoiceCallPhase("hearing");
                    setVoiceCallNotice("听到您说话了，请继续…");
                    if (voiceHealthRef.current.realtimeAsr) {
                      realtimeAsrRef.current?.cancel();
                      realtimeAsrRef.current = startRealtimeAsr(API_ORIGIN, tokenRef.current);
                      for (const samples of preRoll) realtimeAsrRef.current.push(samples, sampleRate);
                    }
                  }}
                  onAudioChunk={(samples, sampleRate) => realtimeAsrRef.current?.push(samples, sampleRate)}
                  onTurn={(wav) => { void sendVoiceCallTurn(wav); }}
                  onError={voiceCallError}
                />
              )}
              <div className={`voice-call-orb voice-call-${voiceCallPhase}`} aria-hidden="true">
                <Mascot3D kind={mascotKind} mood={voiceCallPhase === "speaking" ? "talk" : voiceCallPhase === "processing" ? "think" : voiceCallPhase === "error" ? "offline" : "listen"} mouthLevelRef={mouthLevelRef} transparent />
              </div>
              <div className="voice-call-copy" role="status" aria-live="polite">
                <strong>{voiceCallPhase === "listening" ? "我在听" : voiceCallPhase === "hearing" ? "请继续说" : voiceCallPhase === "processing" ? "正在想怎么回答" : voiceCallPhase === "speaking" ? "遥遥正在说话" : voiceCallPhase === "muted" ? "麦克风已暂停" : "语音暂不可用"}</strong>
                <p>{voiceCallNotice}</p>
              </div>
              <div className="voice-call-controls">
                {voiceCallPhase === "error" ? <button type="button" onClick={() => { if (status === "可以使用") { setVoiceCallPhase("listening"); setVoiceCallNotice("我在听，请继续说…"); } }} disabled={status !== "可以使用"}>重新收音</button> : <button type="button" onClick={toggleVoiceCallMute} aria-pressed={voiceCallMuted}>{voiceCallMuted ? "恢复麦克风" : "暂停麦克风"}</button>}
                <button className="voice-call-end" type="button" onClick={endVoiceCall}>结束通话</button>
              </div>
              <p className="voice-call-privacy">说完稍停会自动发送；遥遥回答时暂停收音。录音交由阿里云识别，保存与分析遵循您进入时的选择。</p>
            </div>
          )}

          {activePanel === "chat" && (
            <div className="chat-layout">
              <div className="chat-companion-bar">
                <CompanionAvatar name={selectedPersona.name} state={companionVisualState} kind={mascotKind} status={status} mouthLevelRef={mouthLevelRef} compact />
                <p>{connectionNeedsAttention(status) ? status === "模型未配置" ? "聊天模型还没有配置，请联系管理员。" : "连接暂不可用，正在尝试恢复。" : `您慢慢说，${selectedPersona.name}在听。`}</p>
                <button className="chat-call-trigger" type="button" onClick={startVoiceCall} disabled={busy || status !== "可以使用" || !voiceHealth.asr || !voiceHealth.tts || voiceState !== "idle"}>开启连续语音对话</button>
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
                <button
                  className={`voice-button${voiceState === "recording" ? " recording" : ""}`}
                  type="button"
                  onPointerDown={onVoicePointerDown}
                  onPointerUp={onVoicePointerUp}
                  onPointerCancel={cancelVoiceCapture}
                  onKeyDown={onVoiceKeyDown}
                  onKeyUp={onVoiceKeyUp}
                  onClick={onVoiceClick}
                  disabled={voiceState === "transcribing" || (voiceState !== "recording" && (busy || status !== "可以使用" || !voiceHealth.asr))}
                >{voiceState === "recording" ? "松开发送" : voiceState === "transcribing" ? "识别并发送中…" : "按住说话"}</button>
                <button type="submit" disabled={busy || voiceState !== "idle" || status !== "可以使用"}>发送</button>
                <p className="composer-voice-status" aria-live="polite">{voiceNotice}</p>
                <p className="voice-cloud-notice">按住说话，松手立即发送；移出按钮可取消。录音交由阿里云处理。</p>
              </form>
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

function CompanionAvatar({ name, state, kind, status, mouthLevelRef, compact = false }: { name: string; state: CompanionVisualState; kind: MascotKind; status: string; mouthLevelRef?: RefObject<number>; compact?: boolean }) {
  const label = status === "模型未配置" ? "聊天待配置" : COMPANION_STATE_LABELS[state];
  return (
    <div className={`companion-avatar companion-${state}${compact ? " companion-compact" : ""}`} role="status" aria-live="polite" aria-atomic="true">
      <div className="companion-portrait" aria-hidden="true">
        <span className="companion-halo" />
        <Mascot3D kind={kind} mood={state === "listening" ? "listen" : state === "speaking" ? "talk" : state === "thinking" ? "think" : state === "alert" ? "alert" : state === "offline" ? "offline" : "idle"} mouthLevelRef={mouthLevelRef} transparent />
        <span className="companion-wave companion-wave-one" />
        <span className="companion-wave companion-wave-two" />
        <span className="companion-wave companion-wave-three" />
      </div>
      <span className="companion-caption"><strong>{name}</strong><small>{label}</small></span>
    </div>
  );
}
