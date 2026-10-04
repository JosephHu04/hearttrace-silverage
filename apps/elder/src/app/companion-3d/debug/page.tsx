"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  actionLabel,
  COMPANION_SKINS,
  Yaoyao3D,
  YAOYAO_ACTIONS,
  type CompanionSkin,
  type YaoyaoAction
} from "@/components/Yaoyao3D";
import styles from "../page.module.css";

const AUTO_ACTIONS: YaoyaoAction[] = ["Idle_Wave", "Nod", "Think", "Cheer"];

export default function CompanionRigDebugPage() {
  const [requestedAction, setRequestedAction] = useState<YaoyaoAction>("Idle_Base");
  const [playingAction, setPlayingAction] = useState<YaoyaoAction>("Idle_Base");
  const [autoMotion, setAutoMotion] = useState(true);
  const [selectedSkin, setSelectedSkin] = useState<CompanionSkin>("yaoyao");
  const selectedSkinInfo = COMPANION_SKINS.find((skin) => skin.id === selectedSkin) ?? COMPANION_SKINS[0];

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

  const chooseSkin = useCallback((skin: CompanionSkin) => {
    setSelectedSkin(skin);
    setRequestedAction("Idle_Base");
    setPlayingAction("Idle_Base");
  }, []);

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <p>内部工程页 · 禁止展示或参赛</p>
          <h1>骨骼与 GLB 管线调试灰模</h1>
          <span>本页只检查关节、动作和加载性能，不代表正式视觉质量。</span>
        </div>
        <Link href="/companion-3d">查看正式视觉方向</Link>
      </header>

      <section className={styles.workspace} aria-label="三维角色骨骼调试区">
        <div className={styles.stage}>
          <Yaoyao3D skin={selectedSkin} action={requestedAction} onPlaying={setPlayingAction} />
          <div className={styles.status} aria-live="polite">
            <span>{selectedSkinInfo.name} · 正在执行</span>
            <strong>{actionLabel(playingAction)}</strong>
          </div>
          <p className={styles.hint}>拖动可转动视角 · 滚轮或双指可缩放</p>
        </div>

        <aside className={styles.controls}>
          <section className={styles.skinPanel} aria-labelledby="skin-title">
            <div><p>调试占位皮肤</p><h2 id="skin-title">检查共用骨骼</h2></div>
            <div className={styles.skinGrid}>
              {COMPANION_SKINS.map((skin) => (
                <button
                  className={selectedSkin === skin.id ? styles.skinActive : ""}
                  type="button"
                  aria-pressed={selectedSkin === skin.id}
                  key={skin.id}
                  onClick={() => chooseSkin(skin.id)}
                >
                  <i style={{ backgroundColor: skin.swatch }} aria-hidden="true" />
                  <span><strong>{skin.name}</strong><small>{skin.description}</small></span>
                </button>
              ))}
            </div>
          </section>
          <div className={styles.controlHeading}>
            <div><p>动作调试</p><h2>逐个检查骨骼动作</h2></div>
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
            <strong>灰模不是产品角色</strong>
            <p>它只验证 Blender → GLB → 网页动作链路。任何正式展示必须换成完成建模、材质、表情和权重验收的角色资产。</p>
          </article>
        </aside>
      </section>
    </main>
  );
}
