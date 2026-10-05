/** Split only complete, speakable phrases; keep incomplete model tokens buffered. */
export function splitSpokenText(buffer: string, flush = false): { segments: string[]; remaining: string } {
  const segments: string[] = [];
  let remaining = buffer;
  while (remaining) {
    const sentence = /[。！？!?；;\n]/.exec(remaining);
    const comma = /[，,]/.exec(remaining.slice(20));
    const commaIndex = comma ? comma.index + 20 : -1;
    const boundary = sentence && (commaIndex < 0 || sentence.index <= commaIndex)
      ? sentence.index + 1
      : commaIndex >= 0 ? commaIndex + 1 : -1;
    if (boundary < 0) break;
    const segment = remaining.slice(0, boundary).trim();
    if (segment) segments.push(segment);
    remaining = remaining.slice(boundary);
  }
  if (flush && remaining.trim()) {
    segments.push(remaining.trim());
    remaining = "";
  }
  return { segments, remaining };
}
