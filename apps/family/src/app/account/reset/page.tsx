"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { confirmPasswordRecovery } from "@/lib/family-api";

export default function ResetPage() {
  const router = useRouter();
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const confirm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    if (values.get("newPassword") !== values.get("newPasswordConfirm")) { setNotice("两次输入的新密码不一致。"); return; }
    setBusy(true);
    setNotice("");
    try {
      setNotice((await confirmPasswordRecovery(String(values.get("recoveryToken")), String(values.get("newPassword")))).message);
      window.setTimeout(() => router.replace("/account"), 1200);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "重置失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  };

  return <main className="auth-page auth-flow-page"><div className="auth-brand"><span>心</span><div><strong>心迹银龄</strong><small>账户与安全</small></div></div><section className="flow-card"><a className="back-link" href="/account/recovery">← 返回账户恢复</a><p className="eyebrow">账户恢复</p><h1>设置新密码</h1><p>输入收到的重置令牌。新密码至少 10 位，建议同时包含字母、数字和符号。</p><form className="login-form" onSubmit={(event) => { void confirm(event); }}><label>重置令牌<input name="recoveryToken" required autoComplete="one-time-code" placeholder="请输入重置令牌" /></label><label>新密码<input name="newPassword" type="password" required minLength={10} autoComplete="new-password" placeholder="至少 10 位" /></label><label>确认新密码<input name="newPasswordConfirm" type="password" required minLength={10} autoComplete="new-password" placeholder="再次输入新密码" /></label><button className="primary login-submit" disabled={busy}>{busy ? "正在重置…" : "确认重置"}</button></form>{notice && <p className="auth-notice" role="status">{notice}</p>}</section></main>;
}
