# 初始接口契约

所有涉及老人数据的读取都必须由服务端校验关系、角色与授权范围。

| 接口 | 调用方 | 用途 |
| --- | --- | --- |
| `POST /api/conversations/sessions` | 老人端 | 创建会话并校验保存与分析授权 |
| `GET/POST /api/elder/check-ins` | 老人端 | 查看或保存本人每日自述与独立分享选择 |
| `POST /api/elder/check-ins/{id}/sharing` | 老人端 | 修改本人历史打卡的分享选择 |
| `GET /api/screenings/instruments` | 三端登录用户 | 获取固定版本的 GDS-15/GAD-7 元数据 |
| `GET/POST /api/elder/screenings` | 老人端 | 本人知情同意后发起筛查或查看本人记录 |
| `POST /api/elder/screenings/{id}/answers` | 老人端 | 按固定顺序提交本人答案并由服务端计分 |
| `GET /api/family/elders/{id}/screenings` | 家属端 | 只读取本人主动分享的分层与建议，不返回逐题答案和总分 |
| `GET /api/admin/screenings` | 管理端 | 只读取本人分享给关怀团队的结构化结果 |
| `WS /api/realtime/conversation` | 老人端 | 流式文本与语音陪伴 |
| `POST /api/emergency/events` | 老人端、绑定设备 | 创建一键呼救或设备求助事件；使用 requestId 幂等防重 |
| `POST /api/video-link/requests` | 老人端 | 交接至已绑定的微信联系人或电话路径 |
| `WS /api/devices/{id}/telemetry` | 硬件端 | 设备心跳、按键状态和跌倒候选事件 |
| `GET /api/family/elders/{id}/today` | 家属端 | 今日摘要、趋势、待办和紧急事件状态 |
| `GET /api/family/elders/{id}/trend?days=7|30` | 家属端 | 只返回已发布摘要的等级、标签和日期；未施测时数值为空 |
| `GET /api/family/elders/{id}/check-ins?days=7` | 家属端 | 仅在有效授权及本人分享后读取自述趋势 |
| `GET/POST /api/family/elders/{id}/care-plan` | 家属端 | 查看或新增仅当前家属可见的关怀计划 |
| `POST /api/family/elders/{id}/care-plan/{itemId}/complete` | 家属端 | 完成一项私人关怀计划 |
| `POST /api/family/risk-events/{id}/actions` | 家属端 | 记录已查看、已联系、已探望或已转介 |
| `GET /api/admin/fall-events` | 管理端 | 审核跌倒候选事件与设备在线状态 |
| `GET /api/admin/check-ins?attentionOnly=true` | 管理端 | 查看本人同意分享给关怀团队的自述与非诊断性关注标记 |
| `POST /api/auth/registration-applications` | 家属端 | 提交家属关系核验申请；密码仅以哈希保存 |
| `GET /api/auth/registration-applications/{id}` | 家属端 | 查询本人申请的审批状态（正式版应加入短信/邮件校验） |
| `GET /api/admin/registration-applications?status=pending` | 管理端 | 查看待审批家属申请 |
| `POST /api/admin/registration-applications/{id}/review` | 管理端 | 通过或驳回申请；通过时必须选择已核验老人，并在同一事务中创建家属账号、授权与审计记录 |
| `GET /api/admin/elders` | 管理端 | 列出可供人工核验选择的有效老人账号 |
| `GET /api/admin/family-grants` | 管理端 | 查看生效与已撤销的家属授权关系 |
| `POST /api/admin/family-grants/{familyId}/{elderId}/actions` | 管理端 | 调整范围、撤销或重新启用授权，使用 expectedVersion 防并发覆盖 |
| `POST /api/auth/login` | 家属端、管理端 | 密码登录并获得短期访问令牌 |
| `POST /api/auth/password/change` | 已登录用户 | 校验当前密码后修改密码 |
| `POST /api/auth/password-recovery` | 家属端 | 当前发送渠道未接入，统一返回 503（不泄露账号是否存在）；接入短信/邮件、限流与失败重试后才开放令牌签发 |
| `POST /api/auth/password-recovery/confirm` | 家属端 | 消费 15 分钟的一次性令牌并重置密码 |
| `GET /api/notifications/me` | 已登录用户 | 获取自己的站内通知、未读数量和分页结果 |
| `POST /api/notifications/{id}/read` | 通知接收人 | 幂等标记自己的通知为已读 |

## 已实现：老人端陪伴会话

`POST /api/conversations/sessions` 仅允许 `elder` 角色调用。请求体：

```json
{
  "saveMessages": false,
  "allowAnalysis": false,
  "persona": {
    "id": "yaoyao",
    "name": "遥遥",
    "role": "像一位常来坐坐、愿意把话听完的晚辈",
    "style": "自然、克制、尊重长者",
    "scenarios": []
  }
}
```

两个授权字段互相独立，默认均为 `false`。`persona` 经过服务端长度和字段校验；审计记录只保存人格 ID、名称和配置指纹，WebSocket 认证时必须提交相同人格卡并通过指纹校验，不在审计中保存完整角色描述或资料。同一会话不能在连接后换成另一个人格。老人端切换人格时必须创建新会话，因此历史、自动记忆和上下文不会跨人格混用。服务端始终保存会话 ID、所属老人、授权选择和审计记录；仅在 `saveMessages=true` 时保存聊天内容并从这些已保存消息重建人格记忆。老人只能读取自己的已保存会话，家属与工作人员没有聊天原文或人格记忆接口。

`WS /api/realtime/conversation` 不在 URL 中传递访问令牌。连接后的第一帧必须是：

```json
{
  "type": "authenticate",
  "accessToken": "Bearer 令牌本体",
  "sessionId": "会话 ID",
  "persona": "与创建会话时完全相同的人格卡"
}
```

认证成功后，客户端发送 `{"type":"message","text":"..."}`。服务端事件包括：

客户端可以同时发送最多 4 条、每条最多 600 字的 `knowledge` 片段。老人端只从当前人格资料中按本轮文字相关度选取片段；服务端不保存这些片段，也不会把一个人格的资料用于另一个会话。资料只能补充表达背景，不能覆盖服务端的安全路由、危机处理和授权规则。

| `type` | 用途 |
| --- | --- |
| `ready` | 会话和老人身份校验完成 |
| `progress` | 正在读取时间、天气或资讯 |
| `meta` | 本轮场景、处理路径和模型 |
| `widget` | 与本轮回复共用的组件数据 |
| `delta` | 可直接朗读的流式文本片段 |
| `done` | 完整回复与首字、总耗时 |
| `error` | 可向用户说明的连接错误 |

时间、天气和新闻使用服务端快速路由，不增加第二次模型调用。非紧急普通对话由 `DASHSCOPE_COMPANION_MODEL` 处理；急症、跌倒、自伤语言等安全场景不交给生成模型决定。

### 多人格记忆边界

- 默认人格为“遥遥”。自定义人格卡和资料保存在当前老人账号的浏览器本地空间，服务端只绑定会话所选的人格卡；当前版本不提供家属或工作人员的人格管理入口。
- 首次消息可以依据用户自己填写的“适用场景”做一次确定性选择；只有唯一最高匹配时才切换，模糊匹配保持当前人格。切换会先创建独立会话，不在同一历史里改身份。
- 明确出现“记住／别忘了”的内容可直接进入本人格上下文。普通稳定事实至少在两个用户回合重复出现后才会被当作已确认记忆；临时内容、健康／用药、安全事件、财务信息和口令不会通过自动重复机制升级。
- 更正内容在提示上下文中取代旧事实，但已保存的原始消息不会被静默改写。称呼偏好、交流边界和“下次再聊”话题从原消息重建，并只对当前人格会话生效。
- `saveMessages=false` 时不保存原文、不形成跨轮持久记忆；自定义人格资料即使由客户端送入本轮，也不落入消息、分析任务或家属摘要。

`GET /api/elder/widgets/weather` 和 `GET /api/elder/widgets/news` 仅允许老人角色读取。定位参数只用于当次天气请求，本纵向切片不保存精确位置。

### 会话后分析约束

- 服务端只有在 `saveMessages=true` 和 `allowAnalysis=true` 同时成立时创建持久化分析任务，两项授权均不互相推导。
- Outbox payload 只含 `sessionId` 与 `sourceMessageId`，不复制对话内容；Worker 调用模型前再次读取并校验会话授权。
- 模型只返回候选信号、是否需要安全确认、建议下一步、家属摘要和证据下标；API 再做枚举、长度和证据范围校验。
- 需要人工跟进的候选以结构化证据进入现有风险队列。模型不会自动发起紧急事件，也不会直接发布家属摘要。
- 工作人员按风险状态机执行 `request_action` 后，后端才把该分析的结构化摘要发布为最新 `DailyInsight`；授权家属随后可从今日摘要读取。
- 风险详情、家属接口和审计日志均不返回原始对话或模型提示词。

## 站内通知与外部投递

注册通过、家属授权变更、工作人员要求风险跟进、授权分析摘要发布、紧急求助创建与状态变化会生成站内通知。接收人由服务端依据当前账号、角色和有效授权关系确定，客户端不能指定接收人。

通知业务记录与 `notification.delivery.requested` Outbox 在同一事务中写入。投递事件只包含 `notificationId`、`recipientId` 和 `channels`，不含通知正文、联系方式、对话原文或模型提示词。事件使用确定性幂等键，同一业务动作重试不会创建重复通知。

其他接口请求、响应字段、授权 scope 和错误码将在后续继续冻结为 OpenAPI 文档。

## 已实现：每日自述打卡（后端）

`POST /api/elder/check-ins` 仅允许登录的老人本人调用。请求体采用 camelCase；三个数值都是本人主观感受的 1–5 级，5 表示较好，1 表示较差，**不是量表、诊断、风险等级或“心理健康分”**：

```json
{
  "mood": 3,
  "sleep": 4,
  "socialWillingness": 2,
  "shareWithFamily": false,
  "shareWithCareTeam": false
}
```

两个分享开关互相独立且默认 `false`；前端应分别解释用途，不可预勾选。服务端以 `Asia/Shanghai` 自然日为准，每位老人每天只保留一条；当日再次提交会更新本人记录，返回同一个 `id`。回复包含 `id`、`checkinDate`、三个自述数值、两个分享开关、`createdAt` 和 `updatedAt`。`GET /api/elder/check-ins?days=7` 仅返回本人最近 1–30 天记录（默认 7 天，按日期倒序）。`POST /api/elder/check-ins/{id}/sharing` 提交 `{"shareWithFamily":false,"shareWithCareTeam":false}` 可随时撤回本人任意历史记录的分享，不改动自述值；非本人记录返回 404。撤回后家属／工作人员的后续读取立即不可见；审计只记录分享选择和日期，不记录具体自述值。

`GET /api/family/elders/{elderId}/check-ins?days=7` 同时要求有效 `daily_summary` 家属授权和该条记录的 `shareWithFamily=true`。返回 `items`，每项仅含 `checkinDate`、`mood`、`sleep`、`socialWillingness`，按日期升序；未获授权返回 403，已获授权但未分享返回空列表。此接口与现有分析摘要 `/trend` 分开，不会把自述值换算成旧的“健康分”。

`GET /api/admin/check-ins?days=7&attentionOnly=false&page=1&perPage=20` 仅允许 `admin`／`professional`，只读取 `shareWithCareTeam=true` 的记录。`attentionNeeded` 仅表示任一自述项不高于 2，供人工决定是否进一步关怀；它不创建风险事件、不自动通知家属，也不代表疾病或危机判断。`attentionOnly=true` 可筛出此类记录。家属和工作人员的查询均写入审计。三个列表的 `days` 均限 1–30，工作人员 `perPage` 限 1–100。

前端联调需确认：三个 1–5 级的中文选项文案、两个分享开关的知情说明，以及工作人员是否需要在管理台展示原始自述值。未确认前，不应将此接口接入自动风险定级。

## 已实现：标准化老年心理关怀筛查

比赛版本采用 `WS/T 802-2022` 附录 B.3 的 GAD-7 和附录 B.4 的 GDS-15。题目、选项、计分方向、阈值和量表版本均由后端固定；大模型只能建议本人自愿开始，不能改写题目、代替作答或计算分数。

老人发起筛查时必须提交 `consentConfirmed=true`，并分别选择 `shareWithFamily` 与 `shareWithCareTeam`。两个分享选项默认关闭且互不推导。每题必须按服务端返回的 `itemCode` 顺序提交；相同答案的网络重试幂等，不允许利用重试改写已提交答案。

GDS-15 按 0-8、9-11、12-15 分为一般、中度关注和高度关注；GAD-7 按 0-9、10-14、15-21 分层。本人分享给关怀团队的中高关注结果进入人工风险复核；量表高分本身不会创建紧急事件。家属只读取本人分享的量表名称、分层、时间和关怀建议，不读取逐题答案或总分。详细边界见 [筛查标准](screening-standard.md)。

## 家属注册状态机

```text
提交申请 → pending（无法登录） → 管理员通过 → approved + 创建家属账号 → 可以登录
                              └→ 管理员驳回 → rejected（保留审核原因）
```

管理端只可查看申请人、联系方式、关系和授权声明版本，不能读取明文密码或密码哈希。找回密码令牌必须由邮件或短信适配器发送；当前仓库已完成生成、哈希存储、过期与一次性消费机制，但不把令牌暴露给浏览器。

申请中的老人姓名只用于人工比对，不能直接作为授权依据。管理员通过申请时必须提交系统内的 `elderId` 和身份、关系核验说明；服务端同事务创建家属账号和 `family_elder_grants`。当前允许的授权范围仅为 `daily_summary` 与 `care_actions`，不提供聊天全文或设备视频范围。撤销后家属列表立即移除该老人，已有令牌再次访问也返回 403。

## 已实现：风险复核纵向切片

以下接口已在 `services/api` 实现，字段采用 camelCase：

| 接口 | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/health` | 公开 | 服务健康检查 |
| `POST /api/auth/demo-login` | 比赛开发环境 | 为预置合成账号签发短期 JWT |
| `GET /api/family/me/elders` | family | 只列出当前家属拥有有效授权的老人 |
| `GET /api/family/elders/{id}/today` | family | 返回授权后的结构化今日摘要；访问会审计 |
| `GET /api/family/elders/{id}/trend?days=7|30` | family | 返回授权后的按日趋势点；不含摘要或聊天内容，访问会审计 |
| `GET /api/family/elders/{id}/care-plan` | family | 只返回当前家属自己的关怀计划，访问会审计 |
| `POST /api/family/elders/{id}/care-plan` | family | 新增私人关怀计划，需要 `care_actions` 授权并写入审计 |
| `POST /api/family/elders/{id}/care-plan/{itemId}/complete` | family | 完成自己的计划，重复完成保持幂等并写入审计 |
| `POST /api/family/risk-events/{id}/actions` | family | 幂等记录联系、视频计划或转介请求；写入审计 |
| `GET /api/admin/risk-events` | admin、professional | 风险队列，支持 level、status、page、perPage |
| `GET /api/admin/risk-events/{id}` | admin、professional | 结构化证据、版本和处置时间线；访问会审计 |
| `POST /api/admin/risk-events/{id}/actions` | admin、professional | 按状态机执行复核动作 |
| `GET /api/admin/audit-logs` | admin | 按 actorId、action、targetType、targetId 查询全局审计，支持分页；专业人员不具备全局审计权限 |
| `GET /api/admin/emergency-events` | admin、professional | 查询紧急事件队列，支持 status、elderId 和分页 |
| `POST /api/admin/emergency-events/{id}/actions` | admin、professional | 确认、解除、取消或重新打开紧急事件 |

处置请求示例：

```json
{
  "requestId": "客户端生成的唯一请求 ID",
  "action": "resolve",
  "expectedVersion": 3,
  "note": "已联系家属并建议安排专业评估。"
}
```

- `requestId` 用于幂等，重复请求返回同一条动作，不重复改变状态。
- `expectedVersion` 用于防止两个工作人员覆盖彼此的更新；版本不一致返回 409。
- `request_action`、`escalate`、`resolve`、`mark_false_positive`、`reopen` 必须填写复核说明。
- 状态变更、处置动作和审计日志在同一数据库事务中提交。
- 详情只返回趋势、量表与模型候选信号等结构化证据，不返回原始聊天全文。

家属行动请求示例：

```json
{
  "requestId": "客户端生成的唯一请求 ID",
  "action": "contacted"
}
```

家属接口不会信任前端传入的老人关系或授权 scope。服务端从 JWT 获取家属身份，并在每次读取和写入时校验 `family_elder_grants`；未授权访问返回 403。

## 已实现：紧急求助纵向切片

老人账号只能为本人创建 `elder_button` 求助；设备账号只能为已绑定老人创建 `device_button` 求助。创建请求必须包含 8 至 100 字符的 `requestId`，重复提交返回原事件且不会重复写入审计。

管理端处置状态机为：

- `open -> acknowledged`：工作人员确认已收到；
- `open/acknowledged -> resolved/cancelled`：解除或取消，必须填写处置说明；
- `resolved/cancelled -> open`：重新打开，必须填写说明。

管理端操作必须携带 `expectedVersion`，过期版本返回 409。创建与每次状态变化都会写入审计；家属今日摘要会基于活动事件实时返回安全状态，不依赖静态演示字段。接口不接收精确位置、聊天原文或健康原文。
