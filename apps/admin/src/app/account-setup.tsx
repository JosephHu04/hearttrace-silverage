"use client";
import { FormEvent, useState } from "react";
import { createElderAccount, getTaskOverview, retryTask, type TaskOverview } from "@/lib/admin-api";

export function AccountSetup({ token, onCreated }: { token: string; onCreated: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [tasks, setTasks] = useState<TaskOverview | null>(null);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setNotice("");
    try {
      const elder = await createElderAccount(token, { displayName: String(data.get("name")), age: Number(data.get("age")), loginIdentifier: String(data.get("identifier")), password: String(data.get("password")) });
      form.reset();
      setNotice(`${elder.displayName}的账号已创建，可在老人端登录。`);
      await onCreated();
    } catch (cause) { setNotice(cause instanceof Error ? cause.message : "创建失败"); }
    finally { setBusy(false); }
  }
  async function refresh() {
    try { setTasks(await getTaskOverview(token)); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : "读取任务失败"); }
  }
  async function retry(id: string) {
    setBusy(true);
    try { await retryTask(token, id); await refresh(); setNotice("任务已重新排队，需要后台处理服务运行后执行。"); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : "重试失败"); }
    finally { setBusy(false); }
  }
  return <section className="account-setup">
    <details><summary>为新老人开通账号</summary><p>请先核验老人身份，将初始账号和密码通过约定的安全方式交给本人。</p><form onSubmit={(event) => { void create(event); }}>
      <label>姓名<input name="name" required minLength={2} maxLength={100} /></label>
      <label>年龄<input name="age" type="number" required min={0} max={120} /></label>
      <label>手机号或邮箱<input name="identifier" required minLength={3} maxLength={120} autoComplete="off" /></label>
      <label>初始密码<input name="password" type="password" required minLength={10} maxLength={128} autoComplete="new-password" /></label>
      <button className="primary" disabled={busy}>{busy ? "正在处理…" : "创建老人账号"}</button>
    </form></details>
    <details onToggle={(event) => { if (event.currentTarget.open) void refresh(); }}><summary>后台分析与通知任务</summary><p>待处理任务持续增加时，请检查后台处理服务。重试不会绕过老人授权。</p><button className="secondary" onClick={() => { void refresh(); }}>刷新状态</button>
      {tasks && <><ul>{tasks.counts.map((item) => <li key={`${item.eventType}:${item.status}`}>{item.eventType === "conversation.analysis.requested" ? "聊天分析" : "通知投递"} · {({ pending: "等待处理", processing: "处理中", failed: "失败", processed: "已完成" } as Record<string, string>)[item.status] ?? item.status}：{item.count}</li>)}</ul>{tasks.counts.length === 0 && <p>暂无任务</p>}{tasks.failed.map((item) => <p key={item.id}>{item.eventType === "conversation.analysis.requested" ? "聊天分析失败" : "通知投递失败"}（尝试 {item.attempts} 次） <button disabled={busy} onClick={() => { void retry(item.id); }}>重新排队</button></p>)}</>}
    </details>{notice && <p role="status">{notice}</p>}
  </section>;
}
