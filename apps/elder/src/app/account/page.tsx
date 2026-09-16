"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

const origin = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/api\/?$/, "").replace(/\/$/, "");

export default function ElderLogin() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${origin}/api/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ loginIdentifier: form.get("identifier"), password: form.get("password") }) });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "账号或密码不正确");
      if (result.actor.role !== "elder") throw new Error("请使用老人自己的账号登录");
      sessionStorage.setItem("hearttrace.elder.session", JSON.stringify(result));
      router.replace("/");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "暂时连不上，请稍后再试");
    } finally { setBusy(false); }
  }
  return <main className="consent-shell"><section className="consent-card elder-login"><p className="consent-brand">心迹银龄 · 遥遥</p><h1>欢迎回来</h1><p className="consent-intro">输入工作人员为您开通的账号，开始聊天。</p><form onSubmit={(event) => { void login(event); }}><label>账号<input name="identifier" required autoComplete="username" placeholder="手机号或邮箱" /></label><label>密码<input name="password" type="password" required minLength={10} autoComplete="current-password" /></label><button disabled={busy}>{busy ? "正在登录…" : "登录"}</button></form>{error && <p role="alert">{error}</p>}<small>还没有账号或忘记密码，请联系工作人员协助核验。</small></section></main>;
}
