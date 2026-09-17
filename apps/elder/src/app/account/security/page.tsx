"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const origin = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/api\/?$/, "").replace(/\/$/, "");

export default function SecurityPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const submitting = useRef(false);

  useEffect(() => {
    try {
      const session = JSON.parse(sessionStorage.getItem("hearttrace.elder.session") ?? "null");
      if (!session?.accessToken || session.actor?.role !== "elder" || !Number.isFinite(Date.parse(session.expiresAt)) || Date.parse(session.expiresAt) <= Date.now()) throw new Error("expired");
      setToken(session.accessToken);
    } catch {
      sessionStorage.removeItem("hearttrace.elder.session");
      router.replace("/account");
    }
  }, [router]);

  async function change(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || submitting.current) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    const currentPassword = String(values.get("currentPassword"));
    const newPassword = String(values.get("newPassword"));
    if (newPassword !== values.get("confirmation")) { setNotice("两次输入的新密码不一致。"); return; }
    if (newPassword === currentPassword) { setNotice("请设置一个与原来不同的新密码。"); return; }
    submitting.current = true;
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(`${origin}/api/auth/password/change`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ currentPassword, newPassword }) });
      const result = await response.json().catch(() => null);
      if (response.status === 401) {
        sessionStorage.removeItem("hearttrace.elder.session");
        router.replace("/account");
        return;
      }
      if (!response.ok) throw new Error(typeof result?.detail === "string" ? result.detail : "修改失败，请稍后重试。");
      form.reset();
      sessionStorage.removeItem("hearttrace.elder.session");
      setDone(true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "网络暂时不可用，请稍后重试。");
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  if (!token) return <main className="consent-shell"><p role="status">正在确认您的账号…</p></main>;
  return <main className="consent-shell"><section className="consent-card elder-login">
    <p className="consent-brand">心迹银龄 · 账号安全</p>
    {done ? <><h1>密码已修改</h1><p role="status">旧的登录已失效，请使用新密码重新登录。</p><Link href="/account">前往登录 →</Link></> : <>
      <Link href="/">← 返回首页</Link><h1>修改密码</h1><p>设置 10 至 128 个字符的新密码。请不要把密码告诉他人。</p>
      <form onSubmit={(event) => { void change(event); }}>
        <label>当前密码<input name="currentPassword" type="password" autoComplete="current-password" minLength={10} maxLength={128} required disabled={busy} /></label>
        <label>新密码<input name="newPassword" type="password" autoComplete="new-password" minLength={10} maxLength={128} required disabled={busy} /></label>
        <label>再输入一次新密码<input name="confirmation" type="password" autoComplete="new-password" minLength={10} maxLength={128} required disabled={busy} /></label>
        <button disabled={busy}>{busy ? "正在修改…" : "确认修改"}</button>
      </form>{notice && <p role="alert">{notice}</p>}
    </>}
  </section></main>;
}
