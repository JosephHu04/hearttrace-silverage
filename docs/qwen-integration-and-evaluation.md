# 阿里云百炼 Qwen 接入与评测说明

## 选择结论

MVP 的文本陪伴与异步关怀分析统一选择 **`qwen-plus`**。

- 中文多轮沟通与结构化 JSON 摘要较稳定，模型别名便于比赛期间复现；
- 在短上下文的非思考模式下，官方列示价格约为输入 ¥0.8 / 百万 Token、输出 ¥2 / 百万 Token；
- 不用最高档模型作为默认，避免每日摘要和多人并发时成本不可控；
- 后续可通过 `DASHSCOPE_MODEL` 对 flash 系列进行非危机场景 A/B 测试，但危机规则和正式量表不依赖模型。

阿里云百炼的新按量付费 API Key 可以 `sk-ws-` 开头；它是 API Key，不是 SSH 私钥。密钥只能保存在本机环境变量或密钥管理服务中，不能提交到 Git 仓库。

## 接入方式

使用百炼 OpenAI 兼容接口：

```text
POST {DASHSCOPE_BASE_URL}/chat/completions
Authorization: Bearer ${DASHSCOPE_API_KEY}
model: qwen-plus
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

## 评测方法与解释

`services/worker/evals/synthetic_cases.json` 使用合成案例覆盖日常平静、孤独、持续低落、明确危机语言和认知担忧。评测会记录 JSON 合法率、紧急场景匹配率、候选信号匹配率、中位延迟和 Token 用量。

这不是临床效度研究。不能将合成案例结果称作真实准确率，也不能据此判断真实老人是否存在抑郁、自伤或认知障碍。真实试用必须使用明确授权的脱敏案例，并由心理/医疗专业人员定义金标准、复核误报与漏报。

## 官方资料

- [阿里云百炼 API Key 获取与安全说明](https://help.aliyun.com/zh/model-studio/get-api-key/)
- [百炼 OpenAI 兼容 Base URL](https://help.aliyun.com/zh/model-studio/base-url)
- [百炼模型价格](https://help.aliyun.com/zh/model-studio/model-pricing)
