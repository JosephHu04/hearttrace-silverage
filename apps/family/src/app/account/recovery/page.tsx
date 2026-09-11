"use client";

import { FormEvent, useState } from "react";
import { requestPasswordRecovery } from "@/lib/family-api";

export default function RecoveryPage() {
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const recover = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    try {
      const values = new FormData(event.currentTarget);
      setNotice((await requestPasswordRecovery(String(values.get("loginIdentifier")))).message);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "请求失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  };

  return <main className="auth-page auth-flow-page"><div className="auth-brand"><span>心</span><div><strong>心迹银龄</strong><small>账户与安全</small></div></div><section className="flow-card"><a className="back-link" href="/account">← 返回登录</a><p className="eyebrow">账户恢复</p><h1>忘记密码</h1><p>填写登录手机号或邮箱。为避免泄露账号是否存在，系统会返回相同提示。</p><form className="login-form" onSubmit={(event) => { void recover(event); }}><label>手机号或邮箱<input name="loginIdentifier" required autoComplete="username" placeholder="请输入手机号或邮箱" /></label><button className="primary login-submit" disabled={busy}>{busy ? "正在提交…" : "发送重置说明"}</button></form>{notice && <p className="auth-notice" role="status">{notice}</p>}<p className="flow-next">已经收到重置令牌？ <a href="/account/reset">设置新密码</a></p></section></main>;
}
