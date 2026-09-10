# 核心业务 API

当前实现的是首条后端纵向切片：演示身份认证、服务端 RBAC、风险队列与详情、风险状态机、幂等处置和审计。

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

## 演示登录

向 `POST /api/auth/demo-login` 提交：

```json
{"actorId":"staff-admin-001"}
```

返回的 Bearer token 可调用管理端接口。`family-demo-001` 用于验证非工作人员无法访问管理端。

## 测试

```bash
pytest
```

测试覆盖角色越权、风险状态机、幂等写入、版本冲突和审计留痕。
