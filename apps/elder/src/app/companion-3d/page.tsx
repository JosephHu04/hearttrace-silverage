"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { actionLabel, Yaoyao3D, YAOYAO_ACTIONS, type YaoyaoAction } from "@/components/Yaoyao3D";
import styles from "./page.module.css";

const AUTO_ACTIONS: YaoyaoAction[] = ["Idle_Wave", "Nod", "Think", "Cheer"];

export default function Companion3DPage() {
  const [requestedAction, setRequestedAction] = useState<YaoyaoAction>("Idle_Base");
  const [playingAction, setPlayingAction] = useState<YaoyaoAction>("Idle_Base");
  const [autoMotion, setAutoMotion] = useState(true);

  const requestAction = useCallback((action: YaoyaoAction) => {
    setRequestedAction((current) => current === action ? "Idle_Base" : action);
    if (action === "Idle_Base") setPlayingAction("Idle_Base");
  }, []);

  useEffect(() => {
    if (!autoMotion) return;
    const timer = window.setInterval(() => {
      const next = AUTO_ACTIONS[Math.floor(Math.random() * AUTO_ACTIONS.length)];
      requestAction(next);
    }, 9000);
    return () => window.clearInterval(timer);
  }, [autoMotion, requestAction]);

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <p>遥遥 · Blender 动作样机</p>
          <h1>她不再只是一张会平移的图片</h1>
          <span>手臂、前臂、手掌、头部、身体和腿部已经接入独立骨骼动作。</span>
        </div>
        <Link href="/">返回老人端</Link>
      </header>

      <section className={styles.workspace} aria-label="三维角色动作验证区">
        <div className={styles.stage}>
          <Yaoyao3D action={requestedAction} onPlaying={setPlayingAction} />
          <div className={styles.status} aria-live="polite">
            <span>正在执行</span>
            <strong>{actionLabel(playingAction)}</strong>
          </div>
          <p className={styles.hint}>拖动可转动视角 · 滚轮或双指可缩放</p>
        </div>

        <aside className={styles.controls}>
          <div className={styles.controlHeading}>
            <div><p>动作控制台</p><h2>逐个检查骨骼动作</h2></div>
            <label><input type="checkbox" checked={autoMotion} onChange={(event) => setAutoMotion(event.target.checked)} /> 自动待机</label>
          </div>
          <div className={styles.actionGrid}>
            {YAOYAO_ACTIONS.map((action) => (
              <button
                className={playingAction === action ? styles.active : ""}
                type="button"
                key={action}
                onClick={() => requestAction(action)}
              >
                <strong>{actionLabel(action)}</strong>
                <small>{action}</small>
              </button>
            ))}
          </div>
          <article className={styles.notice}>
            <strong>目前是骨架验证版</strong>
            <p>这一版先证明 Blender → GLB → 网页动作链路可行。最终版仍需精修手指、脸部表情、头发和服装，并补充眨眼与中文口型。</p>
          </article>
        </aside>
      </section>
    </main>
  );
}
