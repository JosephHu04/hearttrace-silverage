"use client";

import { FormEvent, useState } from "react";
import { changePassword, confirmPasswordRecovery, loginWithPassword, requestPasswordRecovery } from "@/lib/family-api";

export default function AccountPage() {
  const [token, setToken] = useState("");
  const [name, setName] = useState("");
  const [notice, setNotice] = useState("");

  const login = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    try {
      const result = await loginWithPassword(String(values.get("loginIdentifier")), String(values.get("password")));
      setToken(result.accessToken);
      setName(result.actor.displayName);
      setNotice("登录验证通过。此演示页不会把令牌保存到浏览器；正式版将使用安全 Cookie 会话。");
    } catch (error) { setNotice(error instanceof Error ? error.message : "登录失败"); }
  };
  const change = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    if (values.get("newPassword") !== values.get("newPasswordConfirm")) { setNotice("两次新密码不一致"); return; }
    try { setNotice((await changePassword(token, String(values.get("currentPassword")), String(values.get("newPassword")))).message); event.currentTarget.reset(); }
    catch (error) { setNotice(error instanceof Error ? error.message : "修改失败"); }
  };
  const recover = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    try { setNotice((await requestPasswordRecovery(String(values.get("loginIdentifier")))).message); }
    catch (error) { setNotice(error instanceof Error ? error.message : "请求失败"); }
  };
  const confirm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    try { setNotice((await confirmPasswordRecovery(String(values.get("recoveryToken")), String(values.get("newPassword")))).message); }
    catch (error) { setNotice(error instanceof Error ? error.message : "重置失败"); }
  };
  return <main className="auth-page">
    <div className="auth-brand"><span>心</span><div><strong>心迹银龄</strong><small>账户与安全</small></div></div>
    <section className="auth-card"><p className="eyebrow">获批后登录</p><h1>家属账户</h1><form className="auth-form" onSubmit={(event) => { void login(event); }}><label>手机号或邮箱<input name="loginIdentifier" required /></label><label>密码<input name="password" type="password" required minLength={10} /></label><button className="primary">登录</button></form></section>
    <section className="auth-card"><p className="eyebrow">忘记密码</p><h2>申请重置</h2><form className="auth-form" onSubmit={(event) => { void recover(event); }}><label>手机号或邮箱<input name="loginIdentifier" required /></label><button className="secondary">发送重置说明</button></form><small>无论账号是否存在，页面都会显示相同提示，避免泄露账户信息。</small></section>
    <section className="auth-card"><p className="eyebrow">收到重置说明后</p><h2>设置新密码</h2><form className="auth-form" onSubmit={(event) => { void confirm(event); }}><label>重置令牌<input name="recoveryToken" required /></label><label>新密码<input name="newPassword" type="password" required minLength={10} /></label><button className="secondary">确认重置</button></form></section>
    {token && <section className="auth-card"><p className="eyebrow">已验证 · {name}</p><h2>修改密码</h2><form className="auth-form" onSubmit={(event) => { void change(event); }}><label>当前密码<input name="currentPassword" type="password" required minLength={10} /></label><label>新密码<input name="newPassword" type="password" required minLength={10} /></label><label>确认新密码<input name="newPasswordConfirm" type="password" required minLength={10} /></label><button className="primary">更新密码</button></form></section>}
    {notice && <p className="auth-notice" role="status">{notice}</p>}<a className="text-button" href="/register">还没有账号？提交申请 →</a>
  </main>;
}
