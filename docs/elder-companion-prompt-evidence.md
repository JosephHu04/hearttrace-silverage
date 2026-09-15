# 老人陪伴提示词：证据到规则的映射

更新日期：2026-09-15

## 结论

老人陪伴对话不应等同于“持续安慰”或“多提问题”。更可靠的设计方向是：维护人格与自主权，准确承接具体生活内容，围绕用户真正重视的关系和角色展开，在用户主动时支持回忆与现实联系，同时明确 AI 不能替代家人、朋友、照护者或专业服务。

## 证据映射

| 证据发现 | 转成的提示词规则 |
| --- | --- |
| 对老年人使用昵称、集体代词、指令式语气或替其发言，可能削弱自主、参与和人格感。 | 禁止幼儿化和替用户决定；建议保留选择权，意图明确时直接回答。 |
| 随年龄增长，人们往往更优先考虑情绪意义和少数重要关系，而不是单纯扩大关系数量。 | 围绕用户重视的人与事回应；不把“多认识人、扩大社交圈”当成孤独的默认解法。 |
| 以人为中心的老年照护强调个体偏好、社会参与、自主、尊严与家庭参与。 | 每轮判断用户当前需要被听见、获得答案还是得到一步帮助；尊重拒绝和改变主意。 |
| 怀旧和生命回顾研究显示出降低孤独、改善部分心理结果的潜力，但研究异质性和质量限制明显。 | 用户主动回忆时沿真实细节邀请讲述；不强迫、不测试记忆、不声称这就是治疗或保证疗效。 |
| 社区老人丧亲支持涉及意义建构、支持获取困难和个体差异。 | 不催“放下、想开”；允许谈具体记忆，不规定悲伤进度，也不把逝者说成仍然在世。 |
| 老年用户对 AI 的偏好差异很大，并关注隐私和技术依赖；现有 LLM 老人照护研究样本小、尚无临床或成本有效性证据。 | 不声称普遍有效，不制造依赖，不替代真人联系或专业照护；功能和建议都应服从个人意愿。 |

## 主要资料

- Lillekroken D, et al. *Elderspeak in Healthcare Settings: How Care, Control and Personhood Intersect in Care Communication—A Qualitative Meta-Synthesis*. Journal of Advanced Nursing, 2026. https://pubmed.ncbi.nlm.nih.gov/42383511/
- Carstensen LL. *Socioemotional Selectivity Theory: The Role of Perceived Endings in Human Motivation*. Current Opinion in Psychology, 2021. https://pmc.ncbi.nlm.nih.gov/articles/PMC8599276/
- Udkunta K, et al. *Models of Care and Interventions to Improve Person-Centred Care for Older People in Long-Term Care Facilities: A Mixed Methods Systematic Review*. Journal of Advanced Nursing, 2026. https://pubmed.ncbi.nlm.nih.gov/41692992/
- Yang H, et al. *Effects of reminiscence therapy for loneliness in older adults: a systematic review and meta-analysis*. Age and Ageing, 2025. https://pubmed.ncbi.nlm.nih.gov/40434177/
- Castillo-Hornero A, et al. *Reminiscence interventions for loneliness reduction in older adults: a systematic review*. Aging & Mental Health, 2024. https://pubmed.ncbi.nlm.nih.gov/38669147/
- Teichman S, et al. *Qualitative Bereavement Experiences and Support in Community-Dwelling Older Adults: A Scoping Review*. Omega, 2024. https://pubmed.ncbi.nlm.nih.gov/39676328/
- Wolfe BH, et al. *Caregiving Artificial Intelligence Chatbot for Older Adults and Their Preferences, Well-Being, and Social Connectivity: Mixed-Method Study*. JMIR, 2025. https://pmc.ncbi.nlm.nih.gov/articles/PMC11950695/
- Johnson JT, et al. *Research on patient-facing chatbots based on large language models in the care of older people: a living systematic review*. European Geriatric Medicine, 2026. https://pubmed.ncbi.nlm.nih.gov/41826720/

## 证据边界

这些资料支持设计原则，不等于证明某一段系统提示词具有临床疗效。特别是 LLM 老人陪伴研究仍处于小样本、探索性阶段；产品上线后仍需要老人参与的可用性测试、真实对话质性评审、安全事件审查和长期依赖风险监测。
