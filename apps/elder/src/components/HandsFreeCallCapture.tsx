"use client";

import { useEffect, useRef } from "react";
import { startVoiceCapture, stopVoiceCapture, stopVoiceCaptureWithoutSaving, type VoiceCapture } from "@/lib/voice-audio";

type Props = {
  onSpeechStart: (preRoll: Float32Array[], sampleRate: number) => void;
  onAudioChunk?: (samples: Float32Array, sampleRate: number) => void;
  onTurn: (wav: Blob) => void;
  onError: (message: string) => void;
};

// Capture one utterance at a time. The parent unmounts this while ASR, the
// conversation model, and TTS run, so the speaker cannot retrigger the mic.
export function HandsFreeCallCapture({ onSpeechStart, onAudioChunk, onTurn, onError }: Props) {
  const callbacks = useRef({ onSpeechStart, onAudioChunk, onTurn, onError });
  callbacks.current = { onSpeechStart, onAudioChunk, onTurn, onError };
  useEffect(() => {
    let cancelled = false;
    let finishing = false;
    let capture: VoiceCapture | null = null;
    let voiceStartedAt = 0;
    let silenceMs = 0;
    let loudFrames = 0;
    let noiseFloor = 0.006;

    async function finish() {
      if (finishing || !capture) return;
      finishing = true;
      const current = capture;
      capture = null;
      try {
        const wav = await stopVoiceCapture(current);
        if (!cancelled) callbacks.current.onTurn(wav);
      } catch {
        if (!cancelled) callbacks.current.onError("这次录音没有完成，请重新开启语音对话");
      }
    }

    async function start() {
      try {
        const acquired = await startVoiceCapture((samples, sampleRate) => {
          if (cancelled || finishing) return;
          let power = 0;
          for (const sample of samples) power += sample * sample;
          const rms = Math.sqrt(power / samples.length);
          const frameMs = samples.length * 1000 / sampleRate;
          const threshold = Math.max(0.016, noiseFloor * 2.7);
          if (!voiceStartedAt) {
            if (rms > threshold) loudFrames += 1;
            else {
              loudFrames = 0;
              noiseFloor = noiseFloor * 0.98 + Math.min(rms, 0.03) * 0.02;
            }
            // Keep only a short pre-roll while waiting, rather than retaining
            // minutes of silence in memory or sending it to speech recognition.
            if (capture && capture.chunks.length > 12) capture.chunks.splice(0, capture.chunks.length - 12);
            if (loudFrames >= 2) {
              voiceStartedAt = performance.now();
              silenceMs = 0;
              callbacks.current.onSpeechStart(capture?.chunks.slice() ?? [], sampleRate);
            }
            return;
          }
          callbacks.current.onAudioChunk?.(samples, sampleRate);
          silenceMs = rms < threshold * 0.75 ? silenceMs + frameMs : 0;
          const speakingMs = performance.now() - voiceStartedAt;
          if ((speakingMs >= 350 && silenceMs >= 650) || speakingMs >= 20_000) void finish();
        });
        if (cancelled) stopVoiceCaptureWithoutSaving(acquired);
        else capture = acquired;
      } catch (error) {
        if (!cancelled) callbacks.current.onError(error instanceof DOMException && error.name === "NotAllowedError"
          ? "请允许麦克风后重新开启语音对话"
          : "麦克风无法启动，请检查设备或浏览器权限");
      }
    }

    void start();
    return () => {
      cancelled = true;
      if (capture) stopVoiceCaptureWithoutSaving(capture);
    };
  }, []);

  return null;
}
