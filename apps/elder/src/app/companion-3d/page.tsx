import Image from "next/image";
import Link from "next/link";
import styles from "./page.module.css";

const concepts = [
  {
    id: "xiaohe",
    name: "小禾",
    role: "可爱孩童陪伴者",
    palette: "橘杏 · 薄荷绿",
    image: "/companion/concepts/xiaohe-turnaround-v1.png",
    priority: true
  },
  {
    id: "tuantuan",
    name: "团团",
    role: "阳光少年陪伴者",
    palette: "天空蓝 · 暖黄",
    image: "/companion/concepts/tuantuan-turnaround-v1.png",
    priority: false
  },
  {
    id: "nuannuan",
    name: "暖暖",
    role: "温柔成年女性陪伴者",
    palette: "珊瑚粉 · 浆果紫",
    image: "/companion/concepts/nuannuan-turnaround-v1.png",
    priority: false
  },
  {
    id: "yaoyao",
    name: "遥遥",
    role: "温和青年陪伴者",
    palette: "鼠尾草绿 · 淡薰衣草",
    image: "/companion/concepts/yaoyao-turnaround-v1.png",
    priority: false
  }
] as const;

export default function Companion3DPage() {
  return (
    <main className={styles.conceptShell}>
      <header className={styles.conceptHeader}>
        <div>
          <p>心迹银龄 · 正式角色视觉方向</p>
          <h1>从角色设计出发，不再展示技术灰模</h1>
          <span>人物必须具备完整轮廓、自然五官、清晰双手、服装细节和可信的表情，达到比赛演示和老人长期使用的观感标准。</span>
        </div>
        <Link href="/">返回老人端</Link>
      </header>

      <section className={styles.conceptLead}>
        <div>
          <p>第一优先级</p>
          <h2>小禾 · 可爱孩童主皮肤</h2>
          <span>以她作为第一个正式 3D 角色，进入高质量基模、Humanoid 骨骼、蒙皮权重、眨眼和中文口型制作流程。</span>
        </div>
        <strong>正式建模优先</strong>
      </section>

      <section className={styles.conceptGrid} aria-label="陪伴角色美术方案">
        {concepts.map((concept) => (
          <article className={concept.priority ? styles.conceptPrimary : ""} key={concept.id}>
            <div className={styles.conceptImage}>
              <Image
                src={concept.image}
                alt={`${concept.name}角色正面、侧面和背面设计稿`}
                width={1536}
                height={1024}
                sizes="(max-width: 760px) 100vw, 50vw"
                priority={concept.priority}
              />
            </div>
            <div className={styles.conceptMeta}>
              <div>
                <p>{concept.palette}</p>
                <h2>{concept.name}</h2>
                <span>{concept.role}</span>
              </div>
              {concept.priority ? <strong>首个落地角色</strong> : <span>后续共用骨骼皮肤</span>}
            </div>
          </article>
        ))}
      </section>

      <footer className={styles.conceptFooter}>
        <strong>正式验收线</strong>
        <p>不再用球体、方块拼角色。最终模型必须通过轮廓、面部、手部、服装、权重、表情和动作七项验收后，才会进入老人端主页面。</p>
      </footer>
    </main>
  );
}
