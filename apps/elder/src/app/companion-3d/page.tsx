import Image from "next/image";
import Link from "next/link";
import styles from "./page.module.css";

const motionStates = [
  {
    index: "01",
    name: "自然呼吸",
    timing: "持续循环 · 4 秒",
    description: "胸腔、脊柱、肩部和前臂共同参与，保持非常轻的呼吸节奏。",
    tone: "mint"
  },
  {
    index: "02",
    name: "环顾观察",
    timing: "随机触发 · 6–10 秒",
    description: "目光先移动，头部随后转向，肩胸最后跟随，避免机械式转头。",
    tone: "apricot"
  },
  {
    index: "03",
    name: "重心换腿",
    timing: "随机触发 · 8–14 秒",
    description: "髋部轻移、膝盖放松，脊柱与双臂做反向平衡，不做整体平移。",
    tone: "violet"
  },
  {
    index: "04",
    name: "轻声回应",
    timing: "语音驱动 · 实时",
    description: "点头、手势和中文口型随语音状态切换，结束后自然回到呼吸待机。",
    tone: "rose"
  }
] as const;

const concepts = [
  { name: "小禾", role: "可爱孩童陪伴者", image: "/companion/concepts/xiaohe-turnaround-v1.png", primary: true },
  { name: "团团", role: "阳光少年陪伴者", image: "/companion/concepts/tuantuan-turnaround-v1.png", primary: false },
  { name: "暖暖", role: "温柔成年女性陪伴者", image: "/companion/concepts/nuannuan-turnaround-v1.png", primary: false },
  { name: "遥遥", role: "温和青年陪伴者", image: "/companion/concepts/yaoyao-turnaround-v1.png", primary: false }
] as const;

export default function Companion3DPage() {
  return (
    <main className={styles.showcaseShell}>
      <header className={styles.showcaseNav}>
        <Link className={styles.brand} href="/">
          <span aria-hidden="true">心</span>
          <div><strong>心迹银龄</strong><small>角色研发室</small></div>
        </Link>
        <nav aria-label="角色页面导航">
          <a href="#motion-system">待机动作</a>
          <a href="#character-lineup">角色方案</a>
          <Link href="/">返回老人端</Link>
        </nav>
      </header>

      <section className={styles.heroShowcase}>
        <div className={styles.heroCopy}>
          <div className={styles.heroEyebrow}><i aria-hidden="true" /> 主角色视觉 V2 · 小禾</div>
          <h1><span>让陪伴，先从</span><span><em>自然的眼神</em>开始。</span></h1>
          <p>她不是悬浮在页面上的装饰，而是会呼吸、会观察、会倾听，也会在老人需要时给出温和回应的数字陪伴者。</p>
          <div className={styles.heroActions}>
            <a href="#motion-system">查看待机设计 <span aria-hidden="true">→</span></a>
            <a href="#character-lineup">查看四套皮肤</a>
          </div>
          <ul className={styles.qualityList} aria-label="角色视觉质量特征">
            <li>完整五指</li><li>多层发丝</li><li>服装织物</li><li>柔和表情</li>
          </ul>
        </div>

        <div className={styles.heroPortrait}>
          <div className={styles.heroHalo} aria-hidden="true" />
          <Image
            src="/companion/concepts/xiaohe-hero-idle-v2.png"
            alt="小禾自然重心站立并轻轻招手的高质量角色视觉目标稿"
            width={1024}
            height={1536}
            sizes="(max-width: 840px) 92vw, 48vw"
            priority
          />
          <div className={styles.heroStatus}>
            <i aria-hidden="true" />
            <div><small>视觉目标状态</small><strong>自然待机 · 轻声问候</strong></div>
          </div>
          <span className={styles.heroLabel}>正式模型品质基准</span>
        </div>
      </section>

      <section className={styles.motionSection} id="motion-system">
        <div className={styles.sectionHeading}>
          <div><p>AMBIENT MOTION SYSTEM</p><h2>站着，也要像在陪伴</h2></div>
          <span>待机不是单一循环，而是一组低频、自然、不打扰老人的行为组合。<br /><Link className={styles.motionPreviewLink} href="/companion-3d/rig-preview">体验当前动作工程预览 →</Link></span>
        </div>
        <div className={styles.motionGrid}>
          {motionStates.map((motion) => (
            <article className={styles[motion.tone]} key={motion.name}>
              <div className={styles.motionTop}><span>{motion.index}</span><i aria-hidden="true" /></div>
              <h3>{motion.name}</h3>
              <small>{motion.timing}</small>
              <p>{motion.description}</p>
              <div className={styles.motionTrack} aria-hidden="true"><span /></div>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.pipelineSection} aria-label="角色制作进度">
        <div className={styles.pipelineTitle}><span>01</span><div><strong>视觉与比例</strong><small>已确定</small></div></div>
        <i aria-hidden="true" />
        <div className={styles.pipelineTitle}><span>02</span><div><strong>骨骼底座与动作</strong><small>已验证</small></div></div>
        <i aria-hidden="true" />
        <div className={styles.pipelineTitle}><span>03</span><div><strong>正式建模、表情与口型</strong><small>进行中</small></div></div>
      </section>

      <section className={styles.lineupSection} id="character-lineup">
        <div className={styles.sectionHeading}>
          <div><p>SHARED RIG · FOUR IDENTITIES</p><h2>一套骨骼，四种陪伴性格</h2></div>
          <span>先完成“小禾”，其他角色沿用同一动作合同，再分别调整体型、表情与服装权重。</span>
        </div>
        <div className={styles.lineupGrid}>
          {concepts.map((concept) => (
            <article className={concept.primary ? styles.lineupPrimary : ""} key={concept.name}>
              <div>
                <Image src={concept.image} alt={`${concept.name}角色三视图`} width={1536} height={1024} sizes="(max-width: 760px) 100vw, 50vw" />
              </div>
              <footer>
                <span><strong>{concept.name}</strong><small>{concept.role}</small></span>
                <b>{concept.primary ? "首位落地" : "共用骨骼"}</b>
              </footer>
            </article>
          ))}
        </div>
      </section>

      <footer className={styles.showcaseFooter}>
        <div><strong>心迹银龄 · 角色质量门槛</strong><p>正式模型通过脸部、五指、服装、权重、表情、动作与性能七项验收后，才进入老人端主页面。</p></div>
        <Link href="/">回到老人端 <span aria-hidden="true">→</span></Link>
      </footer>
    </main>
  );
}
