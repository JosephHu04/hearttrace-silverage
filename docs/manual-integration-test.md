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

## 自动验证

```bash
cd services/api
pytest
alembic check

cd ../../apps/family
npm run build
```
