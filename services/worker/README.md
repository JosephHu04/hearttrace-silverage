# Worker：Qwen 关怀分析与评测

首发模型为 `qwen-plus`，通过阿里云百炼 OpenAI 兼容接口调用。它只生成候选关怀信号与家属摘要；不用于诊断，也不能直接写入风险等级。

## 运行分析 Worker

先启动 API 并确认同一个 `DATABASE_URL` 已执行 `alembic upgrade head`。会话必须同时声明 `saveMessages=true` 与 `allowAnalysis=true`；每次助手回复会在保存消息的同一事务中写入只含会话和消息 ID 的 Outbox 事件。

```bash
python3 services/worker/analysis_worker.py --once
python3 services/worker/analysis_worker.py
```

第一条命令处理至多一个可用事件，适合联调；第二条持续轮询。Worker 在调用模型前重新校验授权，只把老人消息发送给分析模型，持久化结构化候选信号和证据引用，不把原始对话复制到 Outbox、风险证据、家属摘要或审计元数据。需要人工跟进的候选会进入管理端风险队列；工作人员执行“要求跟进”后，确认过的家属摘要才会发布。

失败任务最多尝试三次并指数退避；耗尽重试后写入 `analysis.failed` 审计记录。生产部署可继续以同一 Outbox 契约替换为 Redis 队列唤醒，数据库仍是业务事实来源。

## 本机配置

在仓库根目录新建未提交的 `.env.local`，或在本机终端设置下列变量。程序会读取 `.env.local` 中尚未设置的变量；切勿把真实值写进代码、GitHub 或聊天消息：

```text
DASHSCOPE_API_KEY=<轮换后的百炼按量付费 API Key>
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen-plus
```

北京地域公共兼容地址适合开发验证；生产环境应改用阿里云控制台提供的业务空间专属 API Host，且 API Key 与地域必须匹配。

## 运行评测

```bash
python3 services/worker/qwen_evaluate.py --dry-run
python3 services/worker/qwen_evaluate.py
```

第二条命令仅运行合成、非临床案例，输出到被 Git 忽略的 `data/evaluations/`。报告包含请求耗时、JSON 合法率、紧急场景匹配率、候选信号匹配率与 Token 用量。

通过合成案例只表示接口与提示词没有回归，**不代表临床准确率或可用于医疗诊断**。真实试用前需要心理/医疗专业顾问确认量表、危机话术、转介流程和人工值守。
