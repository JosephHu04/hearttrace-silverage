# 老人端陪伴应用

老人端使用 Next.js 运行在 `3002` 端口，通过核心 API 创建隐私授权明确的会话，并使用 WebSocket 接收流式陪伴回复。时间、天气和新闻采用后端快速路由，同一份数据同时更新回复和页面卡片，不额外调用大模型。

## 本地运行

先启动 `services/api`，再执行：

```bash
cd apps/elder
npm ci
npm run dev
```

访问 `http://localhost:3002`。默认使用合成老人账号 `elder-demo-001` 进行比赛联调，可通过本地 `.env.local` 覆盖 `.env.example` 中的地址和账号。

当前界面以隐私优先方式创建 `saveMessages=false`、`allowAnalysis=false` 的会话：服务端只保存会话授权元数据和审计记录，聊天内容只在当前 WebSocket 连接的内存中保留。正式认证接入后应移除演示登录流程。

## 接口

- `POST /api/conversations/sessions`：老人角色创建会话并声明保存、分析授权。
- `WS /api/realtime/conversation`：第一帧发送 `authenticate`，之后发送 `message`。
- `GET /api/elder/widgets/weather`：天气卡片。
- `GET /api/elder/widgets/news`：资讯卡片。

访问令牌通过 WebSocket 第一帧传递，不放在 URL 查询参数中。
