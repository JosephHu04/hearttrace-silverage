# 核心业务 API

当前实现老人陪伴、授权会话分析、风险复核、家属关怀、账号审批、关系授权、紧急求助和站内通知纵向切片：身份认证、服务端 RBAC、会话授权、事务 Outbox、授权关系、幂等处置、乐观锁和审计共用同一业务后端。

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

实时陪伴使用 `DASHSCOPE_COMPANION_MODEL`（默认 `qwen3.8-flash`，显式关闭思考模式）和 30 秒截止时间；异步分析使用 `DASHSCOPE_MODEL`（默认 `qwen-plus`）。后端记录随机追踪号、准备/首字/总耗时及上游错误类别，不记录聊天原文、语音或密钥。只有 `saveMessages=true` 与 `allowAnalysis=true` 同时成立时，助手回复落库事务才会创建只含 ID 引用的分析事件；Outbox 不保存对话原文。真实 API Key 只能放在本机环境或密钥管理服务中。

## 老人端语音

默认语音链路使用独立的阿里云百炼语音密钥：ASR 为 `qwen3-asr-flash`，TTS 为 `qwen-audio-3.0-tts-flash`（普通话音色 `longanfengyue`）。将 `SPEECH_DASHSCOPE_API_KEY` 仅配置在服务端 `.env.speech` 或部署环境变量中；聊天模型继续单独使用 `.env` 中的 `DASHSCOPE_API_KEY`。两个文件均被 Git 忽略。没有语音密钥时只保留打字聊天，不会回退到未配置的服务。

- `GET /api/speech/health`：查看语音密钥配置状态（不是付费的实时推理健康探测）。
- `WS /api/realtime/speech`：老人身份认证后，把 16 kHz 单声道 PCM16 小段音频经后端转送 `qwen3-asr-flash-realtime`；发送 `finish` 后仅返回最终识别文本。网页无法接触语音密钥，失败时回退到下方 WAV 接口。
- `POST /api/speech/transcribe`：仅接受老人身份的 WAV，转发给百炼 ASR；录音不写入数据库或日志。
- `POST /api/speech/synthesize`：仅接受老人身份，调用百炼 TTS 并返回标准 WAV；老人端在模型生成完整短句后即按顺序合成和播报，不再等待整段回答完成，并按实际播放波形驱动精灵嘴型。

原型的 FunASR + Fish Speech 仍可通过 `SPEECH_PROVIDER=local` 启用；此时用 `FUNASR_URL`、`FISH_SPEECH_URL` 和 `FISH_SPEECH_REFERENCE_ID` 配置内网服务。克隆音色的参考音频需要另行确认配音者授权，本仓库不保存生物特征样本。云端模式下，用户主动提交的录音和助手回复文字会发送至阿里云百炼处理；正式使用前需完成知情同意与隐私评估。

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

## 通知接口

- `GET /api/notifications/me`：返回当前账号的通知、未读总数与分页结果；可用 `unreadOnly=true` 只查未读。
- `POST /api/notifications/{id}/read`：仅通知接收人可标记已读；重复提交幂等返回。

站内通知与对应业务变化在同一事务中写入，外部投递事件只包含通知 ID、接收人 ID 和渠道，不复制通知正文、联系方式或对话内容。持续运行 `python3 services/worker/notification_worker.py` 可消费投递事件；当前适配器确认站内投递，后续可替换为短信或邮件实现。
