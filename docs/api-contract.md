# 初始接口契约

所有涉及老人数据的读取都必须由服务端校验关系、角色与授权范围。

| 接口 | 调用方 | 用途 |
| --- | --- | --- |
| `POST /api/conversations/sessions` | 老人端 | 创建会话并校验保存与分析授权 |
| `WS /api/realtime/conversation` | 老人端 | 流式文本与语音陪伴 |
| `POST /api/emergency/events` | 老人端、设备端 | 创建一键呼救或设备求助事件 |
| `POST /api/video-link/requests` | 老人端 | 交接至已绑定的微信联系人或电话路径 |
| `WS /api/devices/{id}/telemetry` | 硬件端 | 设备心跳、按键状态和跌倒候选事件 |
| `GET /api/family/elders/{id}/today` | 家属端 | 今日摘要、趋势、待办和紧急事件状态 |
| `POST /api/family/risk-events/{id}/actions` | 家属端 | 记录已查看、已联系、已探望或已转介 |
| `GET /api/admin/fall-events` | 管理端 | 审核跌倒候选事件与设备在线状态 |
| `POST /api/auth/registration-applications` | 家属端 | 提交家属关系核验申请；密码仅以哈希保存 |
| `GET /api/auth/registration-applications/{id}` | 家属端 | 查询本人申请的审批状态（正式版应加入短信/邮件校验） |
| `GET /api/admin/registration-applications?status=pending` | 管理端 | 查看待审批家属申请 |
| `POST /api/admin/registration-applications/{id}/review` | 管理端 | 通过或驳回申请；通过时在同一事务中创建家属账号与审计记录 |
| `POST /api/auth/login` | 家属端、管理端 | 密码登录并获得短期访问令牌 |
| `POST /api/auth/password/change` | 已登录用户 | 校验当前密码后修改密码 |
| `POST /api/auth/password-recovery` | 家属端 | 请求向已绑定渠道发送一次性重置说明；响应不泄露账号是否存在 |
| `POST /api/auth/password-recovery/confirm` | 家属端 | 消费 15 分钟的一次性令牌并重置密码 |

接口请求、响应字段、授权 scope 和错误码将在第 2 周冻结为 OpenAPI 文档。

## 家属注册状态机

```text
提交申请 → pending（无法登录） → 管理员通过 → approved + 创建家属账号 → 可以登录
                              └→ 管理员驳回 → rejected（保留审核原因）
```

管理端只可查看申请人、联系方式、关系和授权声明版本，不能读取明文密码或密码哈希。找回密码令牌必须由邮件或短信适配器发送；当前仓库已完成生成、哈希存储、过期与一次性消费机制，但不把令牌暴露给浏览器。

## 已实现：风险复核纵向切片

以下接口已在 `services/api` 实现，字段采用 camelCase：

| 接口 | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/health` | 公开 | 服务健康检查 |
| `POST /api/auth/demo-login` | 比赛开发环境 | 为预置合成账号签发短期 JWT |
| `GET /api/family/me/elders` | family | 只列出当前家属拥有有效授权的老人 |
| `GET /api/family/elders/{id}/today` | family | 返回授权后的结构化今日摘要；访问会审计 |
| `POST /api/family/risk-events/{id}/actions` | family | 幂等记录联系、视频计划或转介请求；写入审计 |
| `GET /api/admin/risk-events` | admin、professional | 风险队列，支持 level、status、page、perPage |
| `GET /api/admin/risk-events/{id}` | admin、professional | 结构化证据、版本和处置时间线；访问会审计 |
| `POST /api/admin/risk-events/{id}/actions` | admin、professional | 按状态机执行复核动作 |
| `GET /api/admin/audit-logs` | admin、professional（暂定） | 按 targetType、targetId 查询审计 |

处置请求示例：

```json
{
  "requestId": "客户端生成的唯一请求 ID",
  "action": "resolve",
  "expectedVersion": 3,
  "note": "已联系家属并建议安排专业评估。"
}
```

- `requestId` 用于幂等，重复请求返回同一条动作，不重复改变状态。
- `expectedVersion` 用于防止两个工作人员覆盖彼此的更新；版本不一致返回 409。
- `request_action`、`escalate`、`resolve`、`mark_false_positive`、`reopen` 必须填写复核说明。
- 状态变更、处置动作和审计日志在同一数据库事务中提交。
- 详情只返回趋势、量表与模型候选信号等结构化证据，不返回原始聊天全文。

家属行动请求示例：

```json
{
  "requestId": "客户端生成的唯一请求 ID",
  "action": "contacted"
}
```

家属接口不会信任前端传入的老人关系或授权 scope。服务端从 JWT 获取家属身份，并在每次读取和写入时校验 `family_elder_grants`；未授权访问返回 403。
