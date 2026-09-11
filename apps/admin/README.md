# 管理端

当前纵向切片实现风险队列、结构化证据、状态机处置、操作时间线和审计查询，数据来自 `services/api`。

## 启动

先启动核心 API：

```bash
cd services/api
.venv/bin/uvicorn app.main:app --reload --port 8000
```

再启动管理端：

```bash
cd apps/admin
pnpm install
pnpm run dev
```

管理端默认地址为 `http://localhost:3001`。若 API 不在本机 8000 端口，通过 `NEXT_PUBLIC_API_BASE_URL` 配置。

演示界面会以 `staff-admin-001` 登录。此入口仅用于比赛开发，正式身份接入后必须关闭。

左侧“审计查询”可按动作类型、操作者、对象类型和对象 ID 组合筛选。家属端联调分支合并后，家属读取摘要和提交关怀行动的记录也会显示在同一审计台。
