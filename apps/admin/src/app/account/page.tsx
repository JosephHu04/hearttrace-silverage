"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { loginWithPassword } from "@/lib/admin-api";
import { readAdminSession, saveAdminSession } from "@/lib/admin-session";

export default function AdminAccountPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (readAdminSession()) router.replace("/");
  }, [router]);

  const login = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    const values = new FormData(event.currentTarget);
    try {
      const result = await loginWithPassword(String(values.get("loginIdentifier") ?? ""), String(values.get("password") ?? ""));
      if (result.actor.role !== "admin") {
        setNotice("该账号不是管理员，请使用管理端账号登录。");
        return;
      }
      saveAdminSession(result);
      router.replace("/");
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : "登录失败，请稍后再试。");
    } finally {
      setBusy(false);
    }
  };

  return <main className="admin-auth-page">
    <div className="admin-auth-brand"><span>心</span><div><strong>心迹银龄</strong><small>管理工作台</small></div></div>
    <section className="admin-auth-layout">
      <div className="admin-auth-intro">
        <p>人工复核 · 明确授权 · 全程留痕</p>
        <h1>先确认身份，<br />再处理每一份关怀。</h1>
        <span>风险事件、注册审批与老人授权属于敏感业务。登录后才能进入管理工作台，所有操作均由共享后端核验权限。</span>
      </div>
      <section className="admin-auth-card" aria-labelledby="admin-login-title">
        <p className="admin-auth-eyebrow">管理人员入口</p>
        <h2 id="admin-login-title">登录管理工作台</h2>
        <p>请输入由团队管理员分配的管理账号和密码。</p>
        <form onSubmit={(event) => { void login(event); }}>
          <label>手机号或邮箱<input name="loginIdentifier" required autoComplete="username" placeholder="请输入管理账号" /></label>
          <label>密码<input name="password" type="password" required minLength={10} autoComplete="current-password" placeholder="请输入密码" /></label>
          <button type="submit" disabled={busy}>{busy ? "正在验证…" : "登录"}</button>
        </form>
        {notice && <p className="admin-auth-notice" role="status">{notice}</p>}
        <small>忘记密码？请联系团队管理员核验身份。请勿发送密码或验证码。</small>
      </section>
    </section>
  </main>;
}
