export type VoiceCapture = {
  context: AudioContext;
  stream: MediaStream;
  source: MediaStreamAudioSourceNode;
  processor: ScriptProcessorNode;
  silentGain: GainNode;
  chunks: Float32Array[];
};

const TARGET_SAMPLE_RATE = 16000;

function joinSamples(chunks: Float32Array[]): Float32Array {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const samples = new Float32Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    samples.set(chunk, offset);
    offset += chunk.length;
  }
  return samples;
}

function resample(samples: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return samples;
  const length = Math.max(1, Math.round(samples.length * toRate / fromRate));
  const output = new Float32Array(length);
  const ratio = fromRate / toRate;
  for (let index = 0; index < length; index += 1) {
    const position = index * ratio;
    const left = Math.floor(position);
    const right = Math.min(left + 1, samples.length - 1);
    const fraction = position - left;
    output[index] = samples[left] * (1 - fraction) + samples[right] * fraction;
  }
  return output;
}

function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeText = (offset: number, text: string) => {
    for (let index = 0; index < text.length; index += 1) view.setUint8(offset + index, text.charCodeAt(index));
  };
  writeText(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let index = 0; index < samples.length; index += 1) {
    const value = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(44 + index * 2, value < 0 ? value * 32768 : value * 32767, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export async function startVoiceCapture(): Promise<VoiceCapture> {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error("当前设备不支持麦克风录音");
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
  });
  const context = new AudioContext({ latencyHint: "interactive" });
  await context.resume();
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(4096, 1, 1);
  const silentGain = context.createGain();
  silentGain.gain.value = 0;
  const capture: VoiceCapture = { context, stream, source, processor, silentGain, chunks: [] };
  processor.onaudioprocess = (event) => capture.chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
  source.connect(processor);
  processor.connect(silentGain);
  silentGain.connect(context.destination);
  return capture;
}

export async function stopVoiceCapture(capture: VoiceCapture): Promise<Blob> {
  capture.processor.onaudioprocess = null;
  capture.source.disconnect();
  capture.processor.disconnect();
  capture.silentGain.disconnect();
  capture.stream.getTracks().forEach((track) => track.stop());
  const sourceRate = capture.context.sampleRate;
  await capture.context.close();
  return encodeWav(resample(joinSamples(capture.chunks), sourceRate, TARGET_SAMPLE_RATE), TARGET_SAMPLE_RATE);
}

export function stopVoiceCaptureWithoutSaving(capture: VoiceCapture): void {
  capture.processor.onaudioprocess = null;
  capture.source.disconnect();
  capture.processor.disconnect();
  capture.silentGain.disconnect();
  capture.stream.getTracks().forEach((track) => track.stop());
  void capture.context.close();
}

export async function playPcmS16le(
  context: AudioContext,
  bytes: ArrayBuffer,
  sampleRate: number,
  onSource: (source: AudioBufferSourceNode | null) => void
): Promise<void> {
  if (bytes.byteLength < 2) throw new Error("语音内容为空");
  if (context.state === "suspended") await context.resume();
  const evenLength = bytes.byteLength - (bytes.byteLength % 2);
  const pcm = new DataView(bytes, 0, evenLength);
  const samples = new Float32Array(evenLength / 2);
  for (let index = 0; index < samples.length; index += 1) samples[index] = pcm.getInt16(index * 2, true) / 32768;
  const audioBuffer = context.createBuffer(1, samples.length, sampleRate);
  audioBuffer.copyToChannel(samples, 0);
  const source = context.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(context.destination);
  onSource(source);
  await new Promise<void>((resolve) => {
    source.onended = () => {
      onSource(null);
      resolve();
    };
    source.start();
  });
}
