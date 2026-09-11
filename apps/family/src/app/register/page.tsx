"use client";

import { FormEvent, useState } from "react";
import { createRegistrationApplication, getRegistrationApplication } from "@/lib/family-api";
import type { RegistrationApplication } from "@/lib/types";

const statusText = { pending: "等待管理端审核", approved: "审核已通过，可以登录", rejected: "申请未通过" } as const;

export default function RegisterPage() {
  const [application, setApplication] = useState<RegistrationApplication | null>(null);
  const [lookupId, setLookupId] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const password = String(values.get("password") ?? "");
    if (password !== values.get("passwordConfirm")) {
      setNotice("两次输入的密码不一致");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const next = await createRegistrationApplication({
        displayName: String(values.get("displayName") ?? ""),
        loginIdentifier: String(values.get("loginIdentifier") ?? ""),
        relationship: String(values.get("relationship") ?? ""),
        elderName: String(values.get("elderName") ?? ""),
        password,
        consentVersion: "family-registration-v1"
      });
      setApplication(next);
      setLookupId(next.id);
      setNotice("申请已提交。请保存申请编号，管理端审核通过后即可使用该联系方式和密码登录。");
      event.currentTarget.reset();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "提交失败，请稍后再试");
    } finally {
      setBusy(false);
    }
  };

  const lookup = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!lookupId.trim()) return;
    try {
      setApplication(await getRegistrationApplication(lookupId.trim()));
      setNotice("");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "查询失败");
    }
  };

  return <main className="auth-page">
    <div className="auth-brand"><span>心</span><div><strong>心迹银龄</strong><small>家属账户申请</small></div></div>
    <section className="auth-card wide">
      <p className="eyebrow">第一步 · 提交关系核验</p>
      <h1>申请家属关怀台账号</h1>
      <p>提交后由管理端核验关系与授权。审核通过前无法访问任何老人信息。</p>
      <form className="auth-form" onSubmit={(event) => { void submit(event); }}>
        <label>您的称呼<input name="displayName" required minLength={2} placeholder="例如：林女士" /></label>
        <label>手机号或邮箱<input name="loginIdentifier" required minLength={3} placeholder="用于登录与找回密码" /></label>
        <label>与老人的关系<select name="relationship" defaultValue=""><option value="" disabled>请选择</option><option value="子女">子女</option><option value="配偶">配偶</option><option value="孙辈">孙辈</option><option value="其他监护人">其他监护人</option></select></label>
        <label>老人称呼<input name="elderName" required placeholder="例如：陈奶奶" /></label>
        <label>设置密码<input name="password" type="password" required minLength={10} autoComplete="new-password" placeholder="至少 10 位" /></label>
        <label>确认密码<input name="passwordConfirm" type="password" required minLength={10} autoComplete="new-password" /></label>
        <label className="auth-consent"><input name="consent" type="checkbox" required />我确认已获得老人知情同意，并同意将申请交由管理端审核。</label>
        <button className="primary" disabled={busy}>{busy ? "正在提交…" : "提交审核申请"}</button>
      </form>
      {notice && <p className="auth-notice" role="status">{notice}</p>}
    </section>
    <section className="auth-card status-card">
      <div><p className="eyebrow">查询进度</p><h2>管理端审核状态</h2></div>
      <form className="lookup-form" onSubmit={(event) => { void lookup(event); }}><input value={lookupId} onChange={(event) => setLookupId(event.target.value)} placeholder="输入申请编号" /><button className="secondary">查询</button></form>
      {application && <div className={`application-status ${application.status}`}><strong>{statusText[application.status]}</strong><span>申请编号：{application.id}</span>{application.reviewNote && <small>审核说明：{application.reviewNote}</small>}</div>}
      <a className="text-button" href="/account">已有获批账号？登录或管理密码 →</a>
    </section>
  </main>;
}
