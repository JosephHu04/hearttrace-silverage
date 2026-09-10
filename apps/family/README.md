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

默认地址为 `http://localhost:3000`。本地预览阶段使用 Mock 数据；实际接入以 `docs/api-contract.md` 为准。

## 接口接入顺序

1. `GET /api/family/elders/{id}/today`
2. `GET /api/family/elders/{id}/insights`
3. `POST /api/family/risk-events/{id}/actions`
4. 授权、审计和紧急事件接口

在任何 API 接入中，前端不得传入或自行决定授权 scope；服务端必须校验当前家属与老人的关系和授权状态。
