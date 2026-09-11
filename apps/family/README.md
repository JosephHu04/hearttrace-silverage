# 家属端

家属端的第一版使用合成数据演示以下能力：

- 今日关怀和下一步建议
- 每日关怀报告与可追溯主题摘要
- 只与个人基线比较的心境趋势
- 风险、紧急联络与设备事件处置状态
- 陪伴计划
- 授权范围与访问审计

## 启动

```bash
npm install
npm run dev
```

默认地址为 `http://localhost:3000`。不配置后端时使用 Mock 数据；联调时创建 `.env.local`：

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

页面右上角可切换两组已授权账号和一组无授权负向测试账号。

## 接口接入顺序

1. `POST /api/auth/demo-login`
2. `GET /api/family/me/elders`
3. `GET /api/family/elders/{id}/today`
4. `POST /api/family/risk-events/{id}/actions`

在任何 API 接入中，前端不得传入或自行决定授权 scope；服务端必须校验当前家属与老人的关系和授权状态。
