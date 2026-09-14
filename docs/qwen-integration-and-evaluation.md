# 阿里云百炼 Qwen 接入与评测说明

## 选择结论

MVP 将低延迟实时陪伴与异步关怀分析分开配置：

- 实时陪伴默认 **`qwen3.8-flash`**，关闭思考模式、限制历史和输出长度，并使用流式返回；
- 异步关怀分析继续使用 **`qwen-plus`**，保持结构化 JSON 验证和合成案例评测；
- 急症、跌倒、自伤语言等危机场景使用服务端确定性规则，不依赖任一模型；
- 两种用途共享百炼 API Key，但使用不同模型环境变量，避免实时成本选择影响分析任务。

阿里云百炼的新按量付费 API Key 可以 `sk-ws-` 开头；它是 API Key，不是 SSH 私钥。密钥只能保存在本机环境变量或密钥管理服务中，不能提交到 Git 仓库。

开发时可在被 `.gitignore` 排除的本地环境文件中配置 `DASHSCOPE_API_KEY` 与 `DASHSCOPE_BASE_URL`。`DASHSCOPE_MODEL` 控制异步分析，`DASHSCOPE_COMPANION_MODEL` 控制实时陪伴；任何脚本和日志都不能打印或保存密钥。

## 接入方式

使用百炼 OpenAI 兼容接口：

```text
POST {DASHSCOPE_BASE_URL}/chat/completions
Authorization: Bearer ${DASHSCOPE_API_KEY}
model: qwen-plus（异步分析）或 qwen3.8-flash（实时陪伴）
```

开发默认使用北京地域 `https://dashscope.aliyuncs.com/compatible-mode/v1`。生产环境应使用业务空间专属 API Host，且 API Key、业务空间和地域必须匹配。

## 运行时边界

```text
已授权对话摘要
       ↓
Qwen：候选信号 + 证据下标 + 家属摘要（JSON）
       ↓
服务端规则引擎：量表 / 趋势 / 安全事件 / 人工跟进
       ↓
家属端：授权后的摘要、建议行动、事件状态
```

Qwen 输出不包含疾病诊断、风险等级或关闭安全事件的权限。它只能建议日常关怀、邀请标准筛查、人工跟进或紧急流程。

接入层同时启用百炼的 `json_object` 结构化输出，并在服务端校验字段、枚举值、证据下标和紧急流程一致性；不合格输出必须进入失败队列或人工复核，不能静默当作有效结果。[百炼结构化输出说明](https://help.aliyun.com/zh/model-studio/qwen-structured-output)

对于网络或 TLS 的瞬时连接错误，接入层最多额外重试 2 次（间隔 0.5 秒、1 秒）；HTTP 业务错误与模型结构化输出错误不会重试，避免把配置或提示词问题伪装成网络问题。

## 评测方法与解释

`services/worker/evals/synthetic_cases.json` 使用合成案例覆盖日常平静、孤独、持续低落、明确危机语言和认知担忧。评测会记录 JSON 合法率、紧急场景匹配率、候选信号匹配率、中位延迟和 Token 用量。

实时陪伴另有 `services/api/evals/synthetic_companion_cases.json`，覆盖成年人式日常回应、具体情绪承接、回忆细节、单步操作、误解修复、非紧急健康边界和耐心重复。先校验语料，再使用本机密钥运行 Flash：

```bash
cd services/api
python companion_evaluate.py --dry-run
python companion_evaluate.py
```

报告只写入被 Git 忽略的 `data/evaluations/`，记录逐例回复、场景路由、长度、问题数、禁用表达以及首字和总耗时。离线评测为区分网络抖动和内容失败，会对单个合成案例最多重试一次；这不改变线上会话的零重试、8 秒快速降级策略。合成检查通过不等于真实老人体验通过；进入真实试用前，仍需由老人用户和照护专业人员共同复核失败案例。

## 实时陪伴的设计依据

- 回复默认 35 至 90 个汉字、最多一个问题，办事时只给一个可确认步骤；这是为了降低多轮任务负担，同时保留自然交流，而不是把老人当成儿童。
- 系统按“直接办事、情绪陪伴、回忆、重复、认知安全、误解修复”等方式切换。研究表明，老年用户对直接或礼貌表达的偏好与任务和互动取向有关，不能统一堆叠客套话；多会话陪伴则应重点检查自然、切题、鼓励、理解、相关和礼貌。
- 发生误解时，系统先采用用户的纠正，再给最多两个具体选项。仅重复“请再说一次”会把修复负担留给用户；多种错误修复策略对老年用户的完成效果和满意度更好。
- `qwen3.8-flash` 保持流式输出，并显式设置 `enable_thinking=false` 与 `preserve_thinking=false`。日常陪伴不需要推理过程，减少思考 Token 能降低等待和费用。

设计参考：

- [阿里云百炼：思考模式和延迟](https://www.alibabacloud.com/help/en/model-studio/deep-thinking)
- [老年人智能屏的直接与礼貌对话设计](https://arxiv.org/abs/2203.15767)
- [面向老年人的多会话闲聊设计与质量维度](https://arxiv.org/abs/1901.06620)
- [老年用户与聊天机器人的多策略错误修复实验](https://pmc.ncbi.nlm.nih.gov/articles/PMC8692264/)
- [老年用户在真实家庭环境中的 AI 对话中断与修复](https://arxiv.org/abs/2510.06690)

## 微调门槛

现阶段先稳定提示词、确定性安全路由和回归评测，不直接拿零散真实对话微调。阿里云建议监督微调准备至少约 1000 条高质量问答，偏好优化准备至少约 100 组偏好数据；团队还需要逐条确认授权、脱敏、标注一致性和人工验收。达到这些条件后再比较 LoRA/SFT 与当前 Flash 基线，只有质量提升且延迟、成本和安全回归均达标才切换。

- [阿里云百炼：模型调优方法与数据规模](https://www.alibabacloud.com/help/en/model-studio/model-training-overview)
- [阿里云百炼：训练集与评测集要求](https://www.alibabacloud.com/help/en/model-studio/training-set-and-evaluation-set)

这不是临床效度研究。不能将合成案例结果称作真实准确率，也不能据此判断真实老人是否存在抑郁、自伤或认知障碍。真实试用必须使用明确授权的脱敏案例，并由心理/医疗专业人员定义金标准、复核误报与漏报。

## 官方资料

- [阿里云百炼 API Key 获取与安全说明](https://help.aliyun.com/zh/model-studio/get-api-key/)
- [百炼 OpenAI 兼容 Base URL](https://help.aliyun.com/zh/model-studio/base-url)
- [百炼模型价格](https://help.aliyun.com/zh/model-studio/model-pricing)
