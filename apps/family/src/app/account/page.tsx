"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { loginWithPassword } from "@/lib/family-api";

export default function AccountPage() {
  const router = useRouter();
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const login = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    setBusy(true);
    setNotice("");
    try {
      const result = await loginWithPassword(String(values.get("loginIdentifier")), String(values.get("password")));
      sessionStorage.setItem("hearttrace.family.session", JSON.stringify({ accessToken: result.accessToken, actor: result.actor }));
      router.replace("/");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "登录失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  };

  return <main className="auth-page auth-login-page">
    <div className="auth-brand"><span>心</span><div><strong>心迹银龄</strong><small>家属关怀台</small></div></div>
    <section className="login-layout">
      <div className="login-intro">
        <p className="eyebrow">安心陪伴 · 授权可见</p>
        <h1>把关心，变成恰到好处的陪伴。</h1>
        <p>家属仅能在老人本人确认的范围内，查看每日关怀摘要、风险状态和自己提交的关怀行动。</p>
        <ul><li>不默认展示聊天全文或视频内容</li><li>每次查看和跟进均有访问留痕</li><li>紧急事件优先进入人工处置流程</li></ul>
      </div>
      <section className="login-card">
        <p className="eyebrow">获批后登录</p>
        <h2>登录家属账户</h2>
        <p className="login-caption">请输入已通过管理端核验的手机号或邮箱。</p>
        <form className="login-form" onSubmit={(event) => { void login(event); }}>
          <label>手机号或邮箱<input name="loginIdentifier" required autoComplete="username" placeholder="请输入手机号或邮箱" /></label>
          <label>密码<input name="password" type="password" required minLength={10} autoComplete="current-password" placeholder="请输入密码" /></label>
          <div className="login-links"><a href="/account/recovery">忘记密码？</a></div>
          <button className="primary login-submit" disabled={busy}>{busy ? "正在登录…" : "登录"}</button>
        </form>
        {notice && <p className="auth-notice" role="status">{notice}</p>}
        <div className="login-divider"><span>还没有账号？</span></div>
        <a className="secondary login-register" href="/register">提交家属关系申请</a>
      </section>
    </section>
    <p className="auth-footnote">登录即表示你会遵守老人授权范围及平台隐私规范。</p>
  </main>;
}
