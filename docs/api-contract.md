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
