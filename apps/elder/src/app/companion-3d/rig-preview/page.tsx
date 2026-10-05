"use client";

import Image from "next/image";
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
          <span>动作可验证；人物外观尚未达到小禾的上线标准。</span>
        </div>
        <Link href="/companion-3d">返回正式视觉方案</Link>
      </header>

      <section className={styles.workspace}>
        <div className={styles.comparison}>
          <div className={styles.stage}>
            <XiaoheRigPreview action={requestedAction} onPlaying={setPlayingAction} />
            <div className={styles.liveBadge}><i aria-hidden="true" /> 可动样机 · 外观未通过</div>
            <div className={styles.nowPlaying}>
              <small>正在执行</small>
              <strong>{RIG_ACTION_META[playingAction].label}</strong>
              <span>{RIG_ACTION_META[playingAction].hint}</span>
            </div>
            <p className={styles.dragHint}>拖动可旋转 · 滚轮可缩放</p>
          </div>
          <div className={styles.target}>
            <div className={styles.targetImage}>
              <Image
                src="/companion/concepts/xiaohe-hero-idle-v2.png"
                alt="小禾角色正式视觉目标，双丸子头、圆润的孩童脸型、杏色外套和薄荷绿裤装"
                fill
                sizes="(max-width: 980px) 100vw, 34vw"
              />
              <span>目标造型 · 并非实时模型</span>
            </div>
            <div className={styles.targetCaption}>
              <div><small>对照参考</small><strong>角色小禾</strong></div>
              <p>大眼与圆润脸型、孩童头身比、自然发束、针织衣料和柔和表情，缺一项都不进入正式首页。</p>
            </div>
          </div>
        </div>

        <aside className={styles.panel}>
          <div className={styles.warning}>
            <span aria-hidden="true">!</span>
            <div>
              <strong>视觉验收：未通过</strong>
              <p>当前底座偏成年，衣服仍是工程网格，缺少眨眼、情绪表情和中文口型。此页只用于判断骨骼动作，不可用于老人端首页或比赛正式演示。</p>
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
            <div><dt>外观</dt><dd>未通过验收</dd></div>
          </dl>
        </aside>
      </section>
    </main>
  );
}
