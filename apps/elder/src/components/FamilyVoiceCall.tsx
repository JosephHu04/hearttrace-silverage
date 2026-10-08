"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track } from "livekit-client";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/api\/?$/, "").replace(/\/$/, "");

type Call = { id: string; status: "ringing" | "active"; incoming: boolean; counterpartId: string; counterpartName: string };
type Contact = { id: string; name: string };

export function FamilyVoiceCall({ token, targetId, elder = false, onBusyChange }: {
  token: string;
  targetId?: string | null;
  elder?: boolean;
  onBusyChange?: (active: boolean) => void;
}) {
  const [call, setCall] = useState<Call | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [chosenId, setChosenId] = useState("");
  const [busy, setBusy] = useState(false);
  const [muted, setMuted] = useState(false);
  const [audioBlocked, setAudioBlocked] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [message, setMessage] = useState("");
  const roomRef = useRef<Room | null>(null);
  const joiningRef = useRef(false);
  const joinedCallRef = useRef("");
  const audioHostRef = useRef<HTMLDivElement>(null);
  const onBusyRef = useRef(onBusyChange);
  const callRef = useRef<Call | null>(null);
  onBusyRef.current = onBusyChange;
  callRef.current = call;
  const callId = call?.id;
  const callStatus = call?.status;
  const callBusy = Boolean(callId);

  const request = useCallback(async <T,>(path: string, method = "GET", body?: object): Promise<T> => {
    const response = await fetch(`${API_BASE}/api/voice-calls${path}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store"
    });
    const result = await response.json().catch(() => ({})) as T & { detail?: string };
    if (!response.ok) throw new Error(result.detail ?? `通话服务暂不可用（${response.status}）`);
    return result;
  }, [token]);

  const releaseRoom = useCallback(() => {
    joinedCallRef.current = "";
    joiningRef.current = false;
    const room = roomRef.current;
    roomRef.current = null;
    if (room) void room.disconnect();
    audioHostRef.current?.replaceChildren();
    setMuted(false);
    setAudioBlocked(false);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const result = await request<{ call: Call | null }>("/current");
      if (callRef.current && !result.call) setMessage("本次通话已结束或无人接听，可以稍后再试");
      setCall(result.call);
      if (!result.call) releaseRoom();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "通话状态读取失败");
    }
  }, [request, releaseRoom]);

  useEffect(() => {
    let cancelled = false;
    void request<{ items: Contact[] }>("/contacts")
      .then((result) => { if (!cancelled) { setContacts(result.items); setChosenId((current) => current || result.items[0]?.id || ""); } })
      .catch((error) => { if (!cancelled) setMessage(error instanceof Error ? error.message : "家人列表读取失败"); });
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 1500);
    return () => { cancelled = true; window.clearInterval(timer); releaseRoom(); };
  }, [request, refresh, releaseRoom]);

  useEffect(() => {
    onBusyRef.current?.(callBusy);
  }, [callBusy]);

  useEffect(() => {
    if (!callId || callStatus !== "active" || joinedCallRef.current === callId || joiningRef.current) return;
    const joiningCallId: string = callId;
    let cancelled = false;
    joiningRef.current = true;
    async function join() {
      let room: Room | null = null;
      try {
        const credentials = await request<{ url: string; token: string }>(`/${joiningCallId}/token`, "POST");
        if (cancelled) return;
        room = new Room({ adaptiveStream: true });
        room.on(RoomEvent.TrackSubscribed, (track) => {
          if (track.kind === Track.Kind.Audio) {
            const element = track.attach() as HTMLAudioElement;
            element.autoplay = true;
            audioHostRef.current?.appendChild(element);
            void element.play().catch(() => setAudioBlocked(true));
          }
        });
        room.on(RoomEvent.TrackUnsubscribed, (track) => { track.detach().forEach((element) => element.remove()); });
        await room.connect(credentials.url, credentials.token);
        if (cancelled) { await room.disconnect(); return; }
        roomRef.current = room;
        joinedCallRef.current = joiningCallId;
        await room.localParticipant.setMicrophoneEnabled(true);
        try { await room.startAudio(); } catch { setAudioBlocked(true); }
        setMessage("已接通，可以直接说话");
      } catch (error) {
        if (room) await room.disconnect();
        setMessage(error instanceof Error ? error.message : "加入语音房间失败，请检查麦克风权限");
      } finally {
        joiningRef.current = false;
      }
    }
    void join();
    return () => { cancelled = true; };
  }, [callId, callStatus, request]);

  useEffect(() => {
    const onLeave = () => {
      const current = callRef.current;
      if (current) void fetch(`${API_BASE}/api/voice-calls/${current.id}/end`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` }, keepalive: true
      });
    };
    window.addEventListener("pagehide", onLeave);
    return () => window.removeEventListener("pagehide", onLeave);
  }, [token]);

  async function act(path: string, body?: object) {
    setBusy(true);
    setMessage("");
    try {
      const result = await request<{ call: Call }>(path, "POST", body);
      setCall(result.call.status === "ringing" || result.call.status === "active" ? result.call : null);
      if (result.call.status !== "ringing" && result.call.status !== "active") releaseRoom();
    } catch (error) {
      setExpanded(true);
      setMessage(error instanceof Error ? error.message : "操作失败，请稍后再试");
    } finally {
      setBusy(false);
    }
  }

  async function toggleMute() {
    const next = !muted;
    try { await roomRef.current?.localParticipant.setMicrophoneEnabled(!next); setMuted(next); }
    catch { setMessage("麦克风切换失败，请检查权限"); }
  }

  const target = targetId || chosenId;
  const targetAvailable = contacts.some((contact) => contact.id === target);
  if (elder && !call && !expanded) return <section className="family-voice-call compact" aria-label="家人语音通话">
    <button type="button" disabled={busy || !targetAvailable} onClick={() => {
      if (contacts.length === 1) void act("", { targetId: target });
      else setExpanded(true);
    }}>☎ 家人通话</button>
  </section>;
  return <section className={`family-voice-call${call?.incoming && call.status === "ringing" ? " incoming" : ""}`} aria-label="家人语音通话" aria-live="polite">
    <div ref={audioHostRef} hidden />
    <strong>☎ {call?.incoming && call.status === "ringing" ? `${call.counterpartName}来电` : call?.status === "active" ? `正在与${call.counterpartName}通话` : call ? `正在呼叫${call.counterpartName}…` : "与家人语音通话"}</strong>
    {!call && elder && contacts.length > 1 && <select aria-label="选择要呼叫的家人" value={chosenId} onChange={(event) => setChosenId(event.target.value)}>{contacts.map((contact) => <option key={contact.id} value={contact.id}>{contact.name}</option>)}</select>}
    {!call && <button type="button" disabled={busy || !targetAvailable} onClick={() => void act("", { targetId: target })}>{targetAvailable ? elder ? "呼叫家人" : "呼叫老人" : "暂无已授权家人"}</button>}
    {!call && elder && <button type="button" onClick={() => setExpanded(false)}>收起</button>}
    {call?.incoming && call.status === "ringing" && <><button type="button" disabled={busy} onClick={() => void act(`/${call.id}/answer`)}>接听</button><button type="button" disabled={busy} onClick={() => void act(`/${call.id}/decline`)}>拒绝</button></>}
    {call?.status === "active" && <button type="button" disabled={busy} onClick={() => void toggleMute()}>{muted ? "取消静音" : "静音"}</button>}
    {call && !(call.incoming && call.status === "ringing") && <button type="button" disabled={busy} onClick={() => void act(`/${call.id}/end`)}>{call.status === "active" ? "挂断" : "取消呼叫"}</button>}
    {audioBlocked && <button type="button" onClick={() => { void roomRef.current?.startAudio().then(() => setAudioBlocked(false)); }}>开启声音</button>}
    {message && <small role="status">{message}</small>}
  </section>;
}
