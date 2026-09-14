# 家属端

家属端通过核心 API 展示已获授权的结构化关怀信息：

- 今日关怀和下一步建议
- 每日关怀报告与可追溯主题摘要
- 只与个人基线比较的 7/30 天心境趋势
- 风险、紧急联络与设备事件处置状态
- 仅当前家属可见、可完成的陪伴计划
- 授权范围与访问审计

## 启动

```bash
npm install
npm run dev
```

默认地址为 `http://localhost:3000`，并默认连接本机 `http://localhost:8000` 的核心 API。先在 `services/api` 启动 API；若 API 不在本机 8000 端口，再创建 `.env.local`：

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

未登录、未获授权或 API 不可用时，页面不会展示任何老人模拟数据。

开发环境已预置两名已授权家属，密码均为 `FamilyDemo2026!`：

- `lin.demo@hearttrace.local` → 陈奶奶
- `wang.demo@hearttrace.local` → 李爷爷

`noaccess.demo@hearttrace.local` 的密码为 `NoAccessDemo2026!`，用于验证未授权账号不会读取任何老人数据。以上仅限本地合成数据，不能用于部署环境。

## 接口接入顺序

1. `POST /api/auth/demo-login`
2. `GET /api/family/me/elders`
3. `GET /api/family/elders/{id}/today`
4. `GET /api/family/elders/{id}/trend?days=7|30`
5. `GET/POST /api/family/elders/{id}/care-plan`
6. `POST /api/family/elders/{id}/care-plan/{itemId}/complete`
7. `POST /api/family/risk-events/{id}/actions`

在任何 API 接入中，前端不得传入或自行决定授权 scope；服务端必须校验当前家属与老人的关系和授权状态。
