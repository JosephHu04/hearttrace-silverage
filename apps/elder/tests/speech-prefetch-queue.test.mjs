import assert from "node:assert/strict";
import test from "node:test";
import { SpeechPrefetchQueue } from "../src/lib/speech-prefetch-queue.ts";

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

test("prepares two speech segments ahead while preserving playback order", async () => {
  const requests = new Map();
  const started = [];
  const queue = new SpeechPrefetchQueue((text) => {
    started.push(text);
    const request = deferred();
    requests.set(text, request);
    return request.promise;
  }, 2);

  queue.push(["第一句", "第二句", "第三句"]);
  assert.deepEqual(started, ["第一句", "第二句"]);
  const first = queue.shift();
  requests.get("第二句").resolve("audio-2");
  await Promise.resolve();
  await Promise.resolve();
  assert.deepEqual(started, ["第一句", "第二句", "第三句"]);
  requests.get("第三句").resolve("audio-3");
  requests.get("第一句").resolve("audio-1");
  assert.equal(await first, "audio-1");
  assert.equal(await queue.shift(), "audio-2");
  assert.equal(await queue.shift(), "audio-3");
  assert.equal(queue.length, 0);
});

test("clearing the queue aborts pending speech and allows a fresh turn", async () => {
  const pending = [];
  const queue = new SpeechPrefetchQueue((text, signal) => new Promise((resolve, reject) => {
    pending.push({ text, resolve });
    signal.addEventListener("abort", () => reject(new Error("cancelled")), { once: true });
  }), 2);

  queue.push(["旧回复", "旧回复后半句"]);
  const old = queue.shift();
  queue.clear();
  assert.equal(await old, null);
  queue.push(["新回复"]);
  assert.deepEqual(pending.map((item) => item.text), ["旧回复", "旧回复后半句", "新回复"]);
  pending.at(-1).resolve("new-audio");
  assert.equal(await queue.shift(), "new-audio");
});
