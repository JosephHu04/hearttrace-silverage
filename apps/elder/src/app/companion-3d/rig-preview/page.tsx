"use client";

import Link from "next/link";
import { useState } from "react";
import {
  RIG_ACTION_META,
  RIG_ACTIONS,
  type RigAction,
  XiaoheRigPreview
} from "../../../components/XiaoheRigPreview";
import styles from "./page.module.css";

export default function RigPreviewPage() {
  const [requestedAction, setRequestedAction] = useState<RigAction>("Idle_Base");
  const [playingAction, setPlayingAction] = useState<RigAction>("Idle_Base");

  const requestAction = (action: RigAction) => {
    if (action === requestedAction) {
      setRequestedAction("Idle_Base");
      window.setTimeout(() => setRequestedAction(action), 30);
      return;
    }
    setRequestedAction(action);
  };

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <p><i aria-hidden="true" /> INTERNAL MOTION REVIEW</p>
          <h1>骨骼动作验收台</h1>
          <span>当前只判断动作质量，不代表最终人物外观。</span>
        </div>
        <Link href="/companion-3d">返回正式视觉方案</Link>
      </header>

      <section className={styles.workspace}>
        <div className={styles.stage}>
          <XiaoheRigPreview action={requestedAction} onPlaying={setPlayingAction} />
          <div className={styles.liveBadge}><i aria-hidden="true" /> 动作实时预览</div>
          <div className={styles.nowPlaying}>
            <small>正在执行</small>
            <strong>{RIG_ACTION_META[playingAction].label}</strong>
            <span>{RIG_ACTION_META[playingAction].hint}</span>
          </div>
          <p className={styles.dragHint}>拖动可旋转 · 滚轮可缩放</p>
        </div>

        <aside className={styles.panel}>
          <div className={styles.warning}>
            <span aria-hidden="true">!</span>
            <div>
              <strong>这是动作底座，不是正式小禾</strong>
              <p>当前外套和裤装仍是工程版型，脸型、孩童比例、表情与中文口型还需按视觉稿制作。请重点看肩、肘、腕、手指、脊柱与重心的联动。</p>
            </div>
          </div>

          <div className={styles.actionHeading}>
            <div><p>5 种可体验动作</p><h2>点一下亲自验收</h2></div>
            <span>招手结束后会自动回到自然待机。</span>
          </div>

          <div className={styles.actionList}>
            {RIG_ACTIONS.map((action, index) => (
              <button
                className={playingAction === action ? styles.active : ""}
                key={action}
                onClick={() => requestAction(action)}
                type="button"
              >
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div><strong>{RIG_ACTION_META[action].label}</strong><small>{RIG_ACTION_META[action].hint}</small></div>
                <b aria-hidden="true">▶</b>
              </button>
            ))}
          </div>

          <dl className={styles.specs}>
            <div><dt>骨骼</dt><dd>65 根</dd></div>
            <div><dt>手部</dt><dd>完整手指链</dd></div>
            <div><dt>动作</dt><dd>5 种已接入</dd></div>
            <div><dt>用途</dt><dd>内部动作验收</dd></div>
          </dl>
        </aside>
      </section>
    </main>
  );
}
