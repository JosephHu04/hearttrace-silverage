# 心迹银龄 HeartTrace SilverAge

面向老年人的情感陪伴与家庭关怀系统。项目由老人用户端、家属端、管理端、后端服务和后续硬件终端组成。

## MVP 范围

- 老人端：文字和语音陪伴、心情记录、标准化筛查、一键呼救、视频联络交接。
- 家属端：每日关怀、趋势、风险提醒、紧急事件跟进、陪伴计划与授权查看。
- 管理端：关系与授权、风险复核、审计，以及设备事件审核。
- 平台：陪伴 Agent、关怀分析 Agent、风险规则引擎、授权和审计。

系统不作心理疾病诊断。聊天全文和日常视频均不对家属默认开放。

文本陪伴与异步关怀分析的首发模型为阿里云百炼 `qwen-plus`；密钥仅从本机环境变量读取。接入方式和合成案例评测说明见 [Qwen 接入与评测](docs/qwen-integration-and-evaluation.md)。

## 仓库结构

```text
apps/
  elder/            老人用户端
  family/           家属端
  admin/            管理端
services/
  api/              核心业务 API
  worker/           异步分析与通知任务
  device-gateway/   后续硬件设备接入
docs/               架构、接口与决策文档
infra/              本地开发与部署配置
```

## 本地开发原则

1. 前端先使用 API Mock 并行开发，接口冻结后统一联调。
2. 权限、授权范围和风险等级仅由服务端定义。
3. 禁止提交 API 密钥、真实聊天、真实视频、真实联系方式或未授权样本。
4. 紧急联络和防跌倒仅使用合成测试数据进行演示。

硬件采购与终端验收规格见 [老人端触控终端与安全设备采购规格](docs/hardware-terminal-procurement.md)。

## 团队协作

所有改动通过功能分支和 Pull Request 合并；CI 会校验仓库基础文档，构建家属端和管理端，并测试核心 API。分支命名、冲突处理与审查要求见 [协作规则](CONTRIBUTING.md)。

详细规划见 [总体技术规划书](docs/心迹银龄独立版总体技术规划书.docx)、[架构说明](docs/architecture.md)、[接口契约](docs/api-contract.md) 与 [决策记录](docs/decision-log.md)。

## 当前实现进度

- 家属端：六个关怀页面、演示账号切换，以及授权摘要和关怀行动的核心 API 联调。
- 管理端：风险队列、结构化证据、状态机处置和操作时间线。
- 核心 API：演示 JWT、服务端 RBAC、风险复核、幂等与乐观版本、审计日志、SQLite/PostgreSQL 配置及 Alembic 初始迁移。

本地运行方式见 [管理端说明](apps/admin/README.md) 和 [核心 API 说明](services/api/README.md)。
