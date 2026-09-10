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

接口请求、响应字段、授权 scope 和错误码将在第 2 周冻结为 OpenAPI 文档。

## 已实现：风险复核纵向切片

以下接口已在 `services/api` 实现，字段采用 camelCase：

| 接口 | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/health` | 公开 | 服务健康检查 |
| `POST /api/auth/demo-login` | 比赛开发环境 | 为预置合成账号签发短期 JWT |
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
