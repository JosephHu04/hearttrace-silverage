import { encodePcm16Chunk } from "@/lib/voice-audio";

export type RealtimeAsrSession = {
  push: (samples: Float32Array, sampleRate: number) => void;
  finish: () => Promise<string>;
  cancel: () => void;
};

export function startRealtimeAsr(apiOrigin: string, accessToken: string): RealtimeAsrSession {
  const url = new URL(`${apiOrigin}/api/realtime/speech`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(url);
  const pending: ArrayBuffer[] = [];
  let pendingBytes = 0;
  let ready = false;
  let finished = false;
  let cancelled = false;
  let failure = "";
  let timeout: number | null = null;
  let resolveFinal: ((text: string) => void) | null = null;
  let rejectFinal: ((reason: Error) => void) | null = null;

  const clearTimer = () => {
    if (timeout !== null) window.clearTimeout(timeout);
    timeout = null;
  };
  const fail = () => {
    failure = "实时识别暂不可用";
    clearTimer();
    rejectFinal?.(new Error(failure));
    resolveFinal = null;
    rejectFinal = null;
    socket.close();
  };
  const sendPending = () => {
    if (!ready || socket.readyState !== WebSocket.OPEN) return;
    for (const bytes of pending) socket.send(bytes);
    pending.length = 0;
    pendingBytes = 0;
    if (finished) socket.send(JSON.stringify({ type: "finish" }));
  };

  socket.onopen = () => socket.send(JSON.stringify({ type: "authenticate", accessToken }));
  socket.onmessage = (event) => {
    if (cancelled) return;
    try {
      const result = JSON.parse(event.data) as { type?: string; text?: string };
      if (result.type === "ready") {
        ready = true;
        sendPending();
      } else if (result.type === "final") {
        clearTimer();
        resolveFinal?.(result.text?.trim() ?? "");
        resolveFinal = null;
        rejectFinal = null;
        socket.close();
      } else if (result.type === "error") fail();
    } catch { fail(); }
  };
  socket.onerror = fail;
  socket.onclose = () => { if (!cancelled && resolveFinal) fail(); };

  return {
    push(samples, sampleRate) {
      if (cancelled || finished || failure) return;
      const bytes = encodePcm16Chunk(samples, sampleRate);
      if (!bytes.byteLength) return;
      if (ready && socket.readyState === WebSocket.OPEN) socket.send(bytes);
      else {
        pending.push(bytes);
        pendingBytes += bytes.byteLength;
        if (pendingBytes > 2_000_000) fail();
      }
    },
    finish() {
      if (cancelled || failure) return Promise.reject(new Error("实时识别暂不可用"));
      finished = true;
      return new Promise<string>((resolve, reject) => {
        resolveFinal = resolve;
        rejectFinal = reject;
        timeout = window.setTimeout(fail, 8000);
        sendPending();
      });
    },
    cancel() {
      cancelled = true;
      clearTimer();
      pending.length = 0;
      rejectFinal?.(new Error("已取消语音识别"));
      resolveFinal = null;
      rejectFinal = null;
      socket.close();
    }
  };
}
