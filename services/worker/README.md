# Worker：Qwen 关怀分析与评测

首发模型为 `qwen-plus`，通过阿里云百炼 OpenAI 兼容接口调用。它只生成候选关怀信号与家属摘要；不用于诊断，也不能直接写入风险等级。

## 本机配置

在本机终端或未提交的 `.env.local` 中设置下列变量，切勿把真实值写进代码、GitHub 或聊天消息：

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
