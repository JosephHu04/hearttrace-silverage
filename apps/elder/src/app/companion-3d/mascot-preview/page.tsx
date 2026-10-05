"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { MASCOT_SKIN_STORAGE_KEY, Mascot3D, type MascotKind, type MascotMood } from "../../../components/Mascot3D";
import styles from "./page.module.css";

type Mascot = MascotKind;
type Mood = Extract<MascotMood, "idle" | "hello" | "listen" | "happy" | "wink" | "curious" | "talk">;

const mascots: Record<Mascot, { name: string; role: string; color: string }> = {
  moss: { name: "小芽", role: "叶耳 · 温暖活泼", color: "#b7e9ba" },
  cloud: { name: "小云", role: "云冠 · 安静柔和", color: "#e6eef4" }
};

const moods: { id: Mood; label: string; detail: string }[] = [
  { id: "idle", label: "自然待机", detail: "呼吸、双眨眼、偶尔探头" },
  { id: "hello", label: "打招呼", detail: "先点头，再靠近问好" },
  { id: "listen", label: "认真倾听", detail: "轻轻前倾，眼神跟随" },
  { id: "happy", label: "开心回应", detail: "笑眼、鼓脸和两次轻跳" },
  { id: "wink", label: "俏皮眨眼", detail: "单眼眨动、偏头、耳朵回应" },
  { id: "curious", label: "好奇探头", detail: "歪头看您，眉毛一高一低" },
  { id: "talk", label: "开口回应", detail: "轻点头，嘴巴有节奏地动" }
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
        <Link className={styles.brand} href="/"><span>✦</span> 心迹银龄 <i>/</i> 精灵试镜室</Link>
        <Link className={styles.back} href="/">返回老人端 ↗</Link>
      </header>
      <section className={styles.layout}>
        <div className={styles.copy}>
          <span className={styles.eyebrow}>NEW COMPANION DIRECTION / 01</span>
          <h1>让陪伴，<br /><em>有一点灵气。</em></h1>
          <p className={styles.intro}>给小精灵一点自己的性格。选择皮肤后点点它，看看招呼、开心、眨眼和好奇探头；回到老人端也会沿用您选的皮肤。</p>
          <div className={styles.selector} aria-label="选择精灵造型">
            {(Object.keys(mascots) as Mascot[]).map((item) => (
              <button className={kind === item ? styles.selected : ""} key={item} onClick={() => chooseSkin(item)} type="button" aria-pressed={kind === item}>
                <span className={styles.swatch} style={{ background: mascots[item].color }} />
                <strong>{mascots[item].name}</strong><small>{mascots[item].role}</small>
              </button>
            ))}
          </div>
          <div className={styles.status}><span className={styles.statusDot} /> 正在试镜 · {mascots[kind].name} · {moods.find((item) => item.id === mood)?.label}</div>
        </div>

        <div className={styles.preview}>
          <div className={styles.stage}><Mascot3D kind={kind} mood={mood} trigger={trigger} onInteract={interact} /><span className={styles.stageTag}>点精灵，有回应 ✦</span><button className={styles.stageHint} type="button" onClick={interact}>再互动一下 ✦</button><span className={styles.bubble} aria-live="polite">{mood === "hello" ? "您好呀，我在这里！" : mood === "listen" ? "我听着呢，您慢慢说。" : mood === "happy" ? "见到您，我也很开心！" : mood === "wink" ? "嘿，给您眨个眼。" : mood === "curious" ? "今天有什么新鲜事吗？" : mood === "talk" ? "想聊什么？我陪您说说。" : "点我一下，看看我的反应"}</span></div>
          <div className={styles.actions}>
            {moods.map((item) => <button className={mood === item.id ? styles.active : ""} key={item.id} onClick={() => selectMood(item.id)} type="button"><strong>{item.label}</strong><small>{item.detail}</small></button>)}
          </div>
        </div>
      </section>
      <aside className={styles.note}>
        <div><span>01 / 素材来源</span><p>两款试镜模型来自 3DAssets.dev，标注为 CC0，可作为可修改的造型底座。</p></div>
        <div><span>02 / 现阶段边界</span><p>这是真实 3D 模型的节点表情。老人端播报时，嘴巴随实际音频响度开合；试镜室的“开口回应”只演示动作节奏，尚未达到逐音素口型。</p></div>
        <div><span>03 / 后续制作</span><p>确定造型后，可在 Blender 补充不同元音的嘴形与材质，再接入语音时间戳，进一步提高对口型精度。</p></div>
      </aside>
    </main>
  );
}
