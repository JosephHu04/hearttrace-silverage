# 核心业务 API

当前实现老人陪伴、授权会话分析、风险复核、家属关怀、账号审批、关系授权和紧急求助纵向切片：身份认证、服务端 RBAC、会话授权、事务 Outbox、授权关系、幂等处置、乐观锁和审计共用同一业务后端。

## 本地启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

默认使用仓库内被忽略的 `hearttrace.db`，并写入合成演示数据。生产或联调环境通过 `DATABASE_URL` 切换 PostgreSQL，并设置足够长的 `JWT_SECRET`。

正式数据库初始化使用：

```bash
alembic upgrade head
```

OpenAPI 地址为 `http://localhost:8000/docs`，健康检查为 `GET /api/health`。

实时陪伴使用 `DASHSCOPE_COMPANION_MODEL`（默认 `qwen3.8-flash`）和 8 秒截止时间；异步分析使用 `DASHSCOPE_MODEL`（默认 `qwen-plus`）。只有 `saveMessages=true` 与 `allowAnalysis=true` 同时成立时，助手回复落库事务才会创建只含 ID 引用的分析事件；Outbox 不保存对话原文。真实 API Key 只能放在本机环境或密钥管理服务中。

## 演示登录

向 `POST /api/auth/demo-login` 提交：

```json
{"actorId":"staff-admin-001"}
```

返回的 Bearer token 可调用对应角色接口。完整的合成测试账号、联调步骤和预期结果见 `docs/manual-integration-test.md`。

## 测试

```bash
pytest
```

测试覆盖老人会话所有权与保存授权、分析授权双门槛、Outbox 原文隔离、Worker 重试、人工确认后摘要发布、WebSocket 组件回复、角色越权、注册后授权可用性、授权即时撤销、家属与设备绑定隔离、风险及紧急事件状态机、幂等写入、版本冲突和审计留痕。
