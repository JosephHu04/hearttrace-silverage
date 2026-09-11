# 家属端与业务后端手动联调

所有账号和数据均为合成演示数据。不要替换为真实老人、聊天、电话或健康资料。

## 测试账号

| 账号 | 角色 | 授权关系 | 用途 |
| --- | --- | --- | --- |
| `family-demo-001` | 家属（林女士） | 陈奶奶 `elder-demo-001` | 黄色关注摘要、提交关怀行动 |
| `family-demo-002` | 家属（王先生） | 李爷爷 `elder-demo-002` | 绿色平稳摘要、多账号隔离 |
| `family-no-access-001` | 家属 | 无 | 验证无授权时不泄露老人数据 |
| `staff-admin-001` | 管理员（周老师） | 不适用 | 在管理端核对风险队列和审计 |
| `staff-professional-001` | 专业人员（许老师） | 不适用 | 验证工作人员角色 |
| `elder-demo-001` | 老人（陈奶奶） | 本人 | 验证老人端一键求助 |
| `device-demo-001` | 设备（客厅求助键） | 陈奶奶 `elder-demo-001` | 验证绑定设备求助和设备越权隔离 |

## 启动

终端一：

```bash
cd services/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

终端二：

```bash
cd apps/family
printf 'NEXT_PUBLIC_API_BASE_URL=http://localhost:8000\n' > .env.local
npm install
npm run dev
```

打开 `http://localhost:3000`，通过右上角下拉框切换测试账号。

## 手动验收路径

1. 选择林女士，应显示陈奶奶、72 分和黄色轻度关怀；记录“已电话联系”应成功。
2. 选择王先生，应只显示李爷爷、84 分和绿色平稳；不得看到陈奶奶的数据。
3. 选择无授权账号，应显示访问被拒绝页，不得回退展示任何老人的 Mock 数据。
4. 使用管理员令牌查询审计日志：`targetType=elder&targetId=elder-demo-001` 应看到 `family.today_viewed`；`targetType=risk_event&targetId=risk-demo-001` 应看到 `family.contacted`。
5. 停止后端后刷新家属端，应明确显示“本地演示数据模式”，用于验证降级提示，不应把 Mock 行动视为正式记录。

## 紧急求助接口联调

1. 使用 `elder-demo-001` 登录并调用 `POST /api/emergency/events`，传入唯一 `requestId` 和 `source=elder_button`；重复提交应返回同一事件并标记 `duplicate=true`。
2. 家属端刷新陈奶奶今日摘要，应显示活动紧急事件；无授权家属仍不得读取该摘要。
3. 管理员通过 `GET /api/admin/emergency-events?status=open` 找到事件，依次提交 `acknowledge` 和带说明的 `resolve`。
4. 家属端在确认后应显示“正在持续跟进”，解除后应恢复“暂无紧急安全事件”。
5. 管理员在审计台按对象类型 `emergency_event` 和对象 ID 查询，应看到 `emergency.created`、`emergency.acknowledge`、`emergency.resolve`。
6. 使用 `device-demo-001` 可为陈奶奶创建 `device_button` 求助，但为 `elder-demo-002` 创建必须返回 403。

## 家属注册与授权联调

1. 在家属注册页提交合成申请；审核前使用申请密码登录应返回 401。
2. 管理端“注册审核”必须先从系统老人账号中选择核验对象，未选择时不能通过。
3. 选择 `elder-demo-001` 并通过后，新家属应能登录且只能看到陈奶奶，不能访问李爷爷。
4. 在“关系与授权”取消“关怀行动记录”并保存；新家属仍可查看摘要，但提交关怀行动应返回 403。
5. 填写原因并撤销授权；无需重新登录，家属老人列表应立即为空，摘要访问返回 403。
6. 填写重新核验说明并启用授权；访问恢复，审计台应显示 `grant.created`、`grant.update_scopes`、`grant.revoke` 和 `grant.reactivate`。

## 自动验证

```bash
cd services/api
pytest
alembic check

cd ../../apps/family
npm run build
```

## 授权分析闭环联调

1. 使用老人账号创建 `saveMessages=true`、`allowAnalysis=true` 的会话并完成一轮合成对话；数据库应新增 `conversation.analysis.requested` Outbox，payload 只含会话和消息 ID。
2. 设置与 API 相同的 `DATABASE_URL` 以及本机 `DASHSCOPE_API_KEY`，运行 `python3 services/worker/analysis_worker.py --once`。
3. 输出应包含 `analysisId`；若候选需要人工跟进，还应包含 `riskEventId`。管理端风险详情只显示候选标签，不显示对话原文。
4. 管理员依次执行“认领”“开始复核”“要求跟进”，并填写人工判断说明。
5. 林女士刷新陈奶奶页面后，应看到工作人员确认过的新摘要；审计台应出现 `conversation.analysis_queued`、`analysis.completed` 和 `analysis.summary_published`。
6. 在 Worker 处理前撤回该会话的分析授权，任务应标记为 skipped，模型不得被调用，也不得产生分析记录。

无需真实模型即可运行自动闭环回归：

```bash
cd services/api
pytest tests/test_analysis_pipeline.py
```
