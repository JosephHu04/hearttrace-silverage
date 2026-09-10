# 初始接口契约

所有涉及老人数据的读取都必须由服务端校验关系、角色与授权范围。

| 接口 | 调用方 | 用途 |
| --- | --- | --- |
| `POST /api/conversations/sessions` | 老人端 | 创建会话并校验保存与分析授权 |
| `WS /api/realtime/conversation` | 老人端 | 流式文本与语音陪伴 |
| `POST /api/daily-check-ins` | 老人端 | 记录每日自述心情、睡眠和联络意愿；不是标准量表 |
| `POST /api/screening-sessions` | 老人端 | 按服务端下发的版本化模板创建 PHQ-9、GAD-7、AD8 等筛查会话 |
| `POST /api/screening-sessions/{id}/answers` | 老人端 | 提交固定题目答案；服务端负责计分、结果分层与审计 |
| `GET /api/family/elders/{id}/screening-summary` | 家属端 | 在授权范围内读取量表完成状态、结果级别和建议，不返回逐题答案 |
| `POST /api/safety-checks` | 老人端、分析服务 | 记录危机线索后的安全确认；不能由模型自行关闭或降级事件 |
| `POST /api/emergency/events` | 老人端、设备端 | 创建一键呼救或设备求助事件 |
| `POST /api/video-link/requests` | 老人端 | 交接至已绑定的微信联系人或电话路径 |
| `WS /api/devices/{id}/telemetry` | 硬件端 | 设备心跳、按键状态和跌倒候选事件 |
| `GET /api/family/elders/{id}/today` | 家属端 | 今日摘要、趋势、待办和紧急事件状态 |
| `POST /api/family/risk-events/{id}/actions` | 家属端 | 记录已查看、已联系、已探望或已转介 |
| `GET /api/admin/fall-events` | 管理端 | 审核跌倒候选事件与设备在线状态 |

### 筛查与安全约束

- `daily-check-ins` 与 `screening-sessions` 必须分表、分接口、分授权；每日心情不得伪装为医疗量表结果。
- 筛查模板必须由服务端按 `instrument` 和 `instrument_version` 下发，前端不能本地计分。
- 家属端默认只可读取经授权的汇总结果；原始答案、完整聊天与风险片段需要独立 scope。
- 模型只能向 `POST /api/safety-checks` 提交可追溯候选线索，不能提交或覆盖 `risk_level`。
- PHQ-9 第 9 题非零、明确危机线索、一键呼救和确认跌倒均应创建不可由模型关闭的安全事件。

接口请求、响应字段、授权 scope 和错误码将在第 2 周冻结为 OpenAPI 文档。详细规则见 [筛查标准](screening-standard.md)。
