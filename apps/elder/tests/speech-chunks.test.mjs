import assert from "node:assert/strict";
import test from "node:test";
import { splitSpokenText } from "../src/lib/speech-chunks.ts";
import { encodePcm16Chunk } from "../src/lib/voice-audio.ts";

test("speaks the first completed sentence before the full reply arrives", () => {
  assert.deepEqual(splitSpokenText("您今天散步了。后面还"), {
    segments: ["您今天散步了。"],
    remaining: "后面还"
  });
});

test("does not read an incomplete opening or lose the last phrase", () => {
  assert.deepEqual(splitSpokenText("您今天散步了十分钟，感觉"), {
    segments: [],
    remaining: "您今天散步了十分钟，感觉"
  });
  assert.deepEqual(splitSpokenText("后面还想再聊", true), {
    segments: ["后面还想再聊"],
    remaining: ""
  });
});

test("splits a longer phrase at a natural comma", () => {
  const result = splitSpokenText("如果您愿意，我们可以慢慢说说今天散步时的见闻，接下来再聊");
  assert.deepEqual(result.segments, ["如果您愿意，我们可以慢慢说说今天散步时的见闻，"]);
  assert.equal(result.remaining, "接下来再聊");
});

test("encodes browser samples as 16 kHz signed PCM for realtime ASR", () => {
  const encoded = encodePcm16Chunk(new Float32Array([-1, 0, 1]), 16000);
  const view = new DataView(encoded);
  assert.equal(encoded.byteLength, 6);
  assert.deepEqual([view.getInt16(0, true), view.getInt16(2, true), view.getInt16(4, true)], [-32768, 0, 32767]);
  assert.equal(encodePcm16Chunk(new Float32Array(4800), 48000).byteLength, 3200);
});
