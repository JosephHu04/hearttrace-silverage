"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { changePassword } from "@/lib/family-api";

export default function SecurityPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    try {
      const session = JSON.parse(sessionStorage.getItem("hearttrace.family.session") ?? "null") as { accessToken?: string; actor?: { role?: string } } | null;
      if (!session?.accessToken || session.actor?.role !== "family") throw new Error("missing session");
      setToken(session.accessToken);
    } catch {
      router.replace("/account");
    }
  }, [router]);

  const change = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) return;
    const values = new FormData(event.currentTarget);
    if (values.get("newPassword") !== values.get("newPasswordConfirm")) { setNotice("两次输入的新密码不一致。"); return; }
    setBusy(true);
    setNotice("");
    try {
      setNotice((await changePassword(token, String(values.get("currentPassword")), String(values.get("newPassword")))).message);
      event.currentTarget.reset();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "修改失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  };

  if (!token) return <main className="auth-loading" aria-live="polite"><div><span className="auth-loading-mark">心</span><p>正在验证登录状态…</p></div></main>;
  return <main className="auth-page auth-flow-page"><div className="auth-brand"><span>心</span><div><strong>心迹银龄</strong><small>账户与安全</small></div></div><section className="flow-card"><a className="back-link" href="/">← 返回关怀台</a><p className="eyebrow">账户安全</p><h1>修改登录密码</h1><p>修改后请使用新密码登录。此操作不会改变你的老人授权范围。</p><form className="login-form" onSubmit={(event) => { void change(event); }}><label>当前密码<input name="currentPassword" type="password" required minLength={10} autoComplete="current-password" /></label><label>新密码<input name="newPassword" type="password" required minLength={10} autoComplete="new-password" /></label><label>确认新密码<input name="newPasswordConfirm" type="password" required minLength={10} autoComplete="new-password" /></label><button className="primary login-submit" disabled={busy}>{busy ? "正在更新…" : "更新密码"}</button></form>{notice && <p className="auth-notice" role="status">{notice}</p>}</section></main>;
}
