"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { MASCOT_SKIN_STORAGE_KEY, Mascot3D, type MascotKind, type MascotMood } from "../../../components/Mascot3D";
import styles from "./page.module.css";

type Mascot = MascotKind;
type Mood = Extract<MascotMood, "idle" | "hello" | "listen" | "happy" | "wink" | "curious" | "talk">;

const mascots: Record<Mascot, { name: string; color: string }> = {
  moss: { name: "小芽", color: "#b7e9ba" },
  cloud: { name: "小云", color: "#e6eef4" }
};

const moods: { id: Mood; label: string }[] = [
  { id: "idle", label: "自然待机" },
  { id: "hello", label: "打招呼" },
  { id: "listen", label: "认真倾听" },
  { id: "happy", label: "开心回应" },
  { id: "wink", label: "俏皮眨眼" },
  { id: "curious", label: "好奇探头" },
  { id: "talk", label: "开口回应" }
];

const ONE_SHOT_MOODS: Mood[] = ["hello", "happy", "wink", "curious"];
const INTERACTIONS: Mood[] = ["hello", "happy", "wink", "curious"];

export default function MascotPreviewPage() {
  const [kind, setKind] = useState<Mascot>("moss");
  const [mood, setMood] = useState<Mood>("idle");
  const [trigger, setTrigger] = useState(0);
  const nextInteraction = useRef(0);
  const selectMood = (next: Mood) => { setMood(next); setTrigger((value) => value + 1); };
  const chooseSkin = (next: Mascot) => {
    setKind(next);
    window.localStorage.setItem(MASCOT_SKIN_STORAGE_KEY, next);
    selectMood("hello");
  };
  const interact = () => {
    selectMood(INTERACTIONS[nextInteraction.current % INTERACTIONS.length]);
    nextInteraction.current += 1;
  };

  useEffect(() => {
    const stored = window.localStorage.getItem(MASCOT_SKIN_STORAGE_KEY);
    if (stored === "moss" || stored === "cloud") setKind(stored);
  }, []);
  useEffect(() => {
    if (!ONE_SHOT_MOODS.includes(mood)) return;
    const timer = window.setTimeout(() => setMood("idle"), mood === "happy" ? 2500 : 2000);
    return () => window.clearTimeout(timer);
  }, [mood, trigger]);

  return (
    <main className={styles.shell}>
      <header className={styles.topbar}>
        <Link className={styles.brand} href="/">心迹银龄 <span>· 精灵造型</span></Link>
        <Link className={styles.back} href="/">返回陪伴首页</Link>
      </header>
      <section className={styles.layout} aria-labelledby="mascot-title">
        <div className={styles.selectorRow}>
          <h1 id="mascot-title">选择精灵</h1>
          <div className={styles.selector} aria-label="选择精灵造型">
            {(Object.keys(mascots) as Mascot[]).map((item) => (
              <button className={kind === item ? styles.selected : ""} key={item} onClick={() => chooseSkin(item)} type="button" aria-pressed={kind === item}>
                <span className={styles.swatch} style={{ background: mascots[item].color }} />
                <strong>{mascots[item].name}</strong>
              </button>
            ))}
          </div>
        </div>
        <div className={styles.preview}>
          <div className={styles.stage}>
            <Mascot3D kind={kind} mood={mood} trigger={trigger} onInteract={interact} />
            <button className={styles.stageHint} type="button" onClick={interact}>互动一下 ✦</button>
            {mood !== "idle" && <span className={styles.bubble} aria-live="polite">{mood === "hello" ? "您好呀，我在这里！" : mood === "listen" ? "我听着呢，您慢慢说。" : mood === "happy" ? "见到您，我也很开心！" : mood === "wink" ? "嘿，给您眨个眼。" : mood === "curious" ? "今天有什么新鲜事吗？" : "想聊什么？我陪您说说。"}</span>}
          </div>
          <div className={styles.actions} aria-label="体验精灵动作">
            {moods.map((item) => <button className={mood === item.id ? styles.active : ""} key={item.id} onClick={() => selectMood(item.id)} type="button" aria-pressed={mood === item.id}>{item.label}</button>)}
          </div>
        </div>
      </section>
    </main>
  );
}
