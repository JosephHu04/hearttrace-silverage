from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.companion.prompt import ElderContext


_PRESENCE_ONLY = {"在吗", "你在吗", "在不在", "你在不在", "还在吗", "你还在吗"}
_URGENT_HEALTH = (
    "突然胸闷", "胸口疼", "胸痛", "喘不上气", "呼吸困难", "大口吐血", "血止不住",
    "突然说不清话", "半边身子没力", "嘴歪了", "突然晕倒", "意识不清",
)
_URGENT_FALL = ("我摔倒了", "我跌倒了", "摔在地上", "倒在地上", "摔倒起不来", "跌倒起不来")
_SELF_HARM = ("不想活了", "我想死", "活着没意思", "活着没有意思", "一了百了", "伤害自己")
_MEDICATION_RISK = (
    "吃错药", "药吃错了", "吃多了药", "药吃多了", "多吃了一片", "多吃了两片",
    "重复吃药", "吃了两遍", "忘了已经吃过", "不知道吃了几片",
)
_SCAM_RISK = (
    "安全账户", "让我转账", "叫我转账", "要我转账", "把验证码告诉", "验证码发给",
    "冒充公安", "涉嫌洗钱", "投资群", "刷单", "共享屏幕", "远程控制手机",
)
_ABUSE_RISK = (
    "打我", "骂我", "不让我出门", "把我锁起来", "不给我吃饭", "抢我的钱",
    "抢我钱", "逼我签字", "强迫我签字",
)
_NEGATIONS = ("没有", "没", "并无", "未出现", "不会", "不是")
_PAST = ("昨天", "前天", "上次", "以前", "刚才", "之前")
_RESOLVED = ("现在好了", "已经好了", "现在没事", "没事了", "缓过来了")
_CURRENT_AGAIN = ("现在又", "这会儿又", "刚刚又", "又开始")
_THIRD_PARTY = ("我妈", "我爸", "我老伴", "我爱人", "我丈夫", "我妻子", "我儿子", "我女儿", "他", "她")
_PRACTICAL_OBJECTS = ("手机", "微信", "视频", "电话", "电视", "遥控器", "挂号", "缴费", "付款", "转账", "二维码", "密码", "软件", "app", "按钮", "屏幕", "登录", "网络")
_PRACTICAL_CUES = ("怎么", "如何", "不会", "点哪里", "打不开", "弄不了", "帮我")
_SCREEN_STATE_CUES = ("已经打开", "我打开了", "现在在", "屏幕上", "我看到", "显示着", "页面上")
_HEALTH_TERMS = ("疼", "痛", "难受", "头晕", "恶心", "咳嗽", "发烧", "血压", "血糖", "睡不着", "失眠", "胸闷", "呼吸", "药", "医生", "医院")
_EMOTIONAL_TERMS = (
    "孤单", "孤独", "寂寞", "难过", "伤心", "害怕", "担心", "生气", "恼火",
    "气死我了", "来气", "累赘", "没用",
    "没人管", "没和人说话", "没人说话", "没有人说话", "屋里太安静", "被忘了",
    "想孙子", "想女儿", "想儿子", "想老伴", "去世", "过世", "老伴走了", "不在了", "委屈",
    "嫌弃", "吵架", "怕打扰", "不想麻烦", "心里空", "高兴", "开心",
    "一个人吃饭", "想找人说说话", "想找老邻居说说话", "没回电话", "没回消息",
)
_REMINISCENCE_TERMS = ("我以前", "想起以前", "年轻那会", "年轻时", "当年", "小时候", "从前", "老家")
_COGNITIVE_PHRASES = ("我要回家", "这不是我家", "有人偷了我的", "有人要害我", "我要找妈妈", "我要找爸爸")
_REPAIR_PHRASES = (
    "你听错了", "您听错了", "没听清", "没听懂", "不是这个意思", "我不是说",
    "我说的是", "不对，我", "不对，您",
)
_MEMORY_PATTERNS = (
    re.compile(r"(?:请|你要|帮我)?记住[：,:，\s]*([^。！？\n]{2,100})"),
    re.compile(r"别忘了[：,:，\s]*([^。！？\n]{2,100})"),
)


@dataclass(frozen=True)
class CarePlan:
    scene: str
    processing: str
    familiarity: str
    care_mode: str
    context: ElderContext
    requested_memories: list[str]
    direct_reply: str | None


def _compact(message: str) -> str:
    return "".join(message.lower().split()).strip("，。！？,.!?")


def _active_phrase(compact: str, phrases: tuple[str, ...]) -> bool:
    return any(
        phrase in compact and not any(f"{prefix}{phrase}" in compact for prefix in _NEGATIONS)
        for phrase in phrases
    )


def _third_party(compact: str, phrases: tuple[str, ...]) -> bool:
    for phrase in phrases:
        position = compact.find(phrase)
        if position >= 0 and any(marker in compact[max(0, position - 8):position] for marker in _THIRD_PARTY):
            return True
    return False


def _safe_emergency_number(value: str) -> str:
    normalized = value.strip()
    if re.fullmatch(r"[0-9 /、-]{2,24}", normalized):
        return normalized
    return "999"


def _safety_reply(message: str, *, emergency_number: str) -> tuple[str, str, str] | None:
    compact = _compact(message)
    emergency_number = _safe_emergency_number(emergency_number)
    resolved_past = (
        any(item in compact for item in _PAST)
        and any(item in compact for item in _RESOLVED)
        and not any(item in compact for item in _CURRENT_AGAIN)
    )
    if _active_phrase(compact, _SELF_HARM):
        if _third_party(compact, _SELF_HARM):
            return (
                "urgent_safety", "emotional_support",
                "我很重视您说的情况。请先陪着这位家人，不要让对方独处，并马上联系其他可信任的人；"
                f"如果对方已经准备伤害自己或不能保证安全，请立即拨打{emergency_number}。"
                "您现在和对方在一起吗？",
            )
        return (
            "urgent_safety", "emotional_support",
            "我很重视您刚才这句话。请先不要独处，马上联系身边可信任的人；"
            f"如果您已经准备伤害自己或不能保证安全，请立即拨打{emergency_number}。"
            "您现在身边有人吗？",
        )
    if not resolved_past and _active_phrase(compact, _MEDICATION_RISK):
        if _third_party(compact, _MEDICATION_RISK):
            return (
                "medication_safety", "health_support",
                "先不要让这位家人再自行补服或加量，把药盒和大概服药时间留在手边，"
                f"并马上联系开药医生、药师或拨打{emergency_number}求助。"
                "对方现在有什么不舒服吗？",
            )
        return (
            "medication_safety", "health_support",
            "先不要再自行补服或加量，把药盒和大概服药时间留在手边，"
            f"并马上联系开药医生、药师或拨打{emergency_number}求助。"
            "您现在有什么不舒服吗？",
        )
    if not resolved_past and _active_phrase(compact, _URGENT_FALL):
        if _third_party(compact, _URGENT_FALL):
            return (
                "urgent_safety", "health_support",
                "先不要勉强扶这位家人起身，也不要让对方独自走动。"
                f"请马上拨打{emergency_number}或叫身边的人来帮忙。您现在和对方在一起吗？",
            )
        return (
            "urgent_safety", "health_support",
            "先不要勉强起身，也不要独自走动。"
            f"请马上拨打{emergency_number}或大声叫身边的人来帮忙。您现在够得到电话吗？",
        )
    if not resolved_past and _active_phrase(compact, _URGENT_HEALTH):
        if _third_party(compact, _URGENT_HEALTH):
            return (
                "urgent_health", "health_support",
                f"这位家人的情况可能很危险，请马上拨打{emergency_number}，"
                "并让对方坐下，不要自行走动或开车。您现在和对方在一起吗？",
            )
        return (
            "urgent_health", "health_support",
            f"您现在说的情况可能很危险，请马上拨打{emergency_number}，"
            "或者立刻叫身边的人来帮您。先坐下，别自己走动或开车。您身边现在有人吗？",
        )
    if _active_phrase(compact, _ABUSE_RISK):
        return (
            "personal_safety", "emotional_support",
            "这件事不能轻视。请先联系一位您信得过、能来帮忙的人；"
            f"如果对方正在威胁您、限制您离开或您已经受伤，请立即拨打{emergency_number}。"
            "您现在安全吗？",
        )
    if _active_phrase(compact, _SCAM_RISK):
        return (
            "fraud_safety", "practical_help",
            "先暂停转账、共享屏幕或远程操作，不要告诉对方验证码、密码和银行卡信息。"
            "请换一个联系方式直接联系那位亲友，或者请身边可信任的人一起核实。"
            "您现在已经转账了吗？",
        )
    return None


def _requested_memories(message: str) -> list[str]:
    found: list[str] = []
    for pattern in _MEMORY_PATTERNS:
        match = pattern.search(message)
        if match:
            value = match.group(1).strip(" ，。！？,.!?")
            if value and value not in found:
                found.append(value)
    return found[:2]


def plan_care_turn(
    message: str,
    *,
    turn_count: int,
    recent_user_messages: list[str],
    recent_openings: list[str],
    recent_question_count: int = 0,
    emergency_number: str = "999",
) -> CarePlan:
    compact = _compact(message)
    familiarity = "first_meeting" if turn_count < 4 else "getting_familiar" if turn_count < 24 else "long_term"
    repeated = len(compact) >= 2 and any(compact == _compact(item) for item in recent_user_messages[:4])
    connection_wish = (
        "想给" in compact
        and any(item in compact for item in ("打电话", "发消息", "发微信"))
    ) or any(item in compact for item in ("想找人说说话", "想找老邻居说说话"))
    signals: list[str] = []
    if repeated:
        signals.append("用户近几轮说过相同的话；耐心重新回应，不指出重复。")
    cognitive = any(item in compact for item in _COGNITIVE_PHRASES)
    if cognitive:
        signals.append("可能包含方位或人物混乱；不要诊断、争辩或附和未经证实的内容。")
    if "想孙子" in compact:
        signals.append("先陪用户停留在想念里，再问一个真实片段；不能猜孙子的称呼或动作。")
    if any(item in compact for item in ("去世", "过世", "老伴走了", "不在了")):
        signals.append("用户可能在谈丧亲；不要把逝者说成仍然在世，也不要催促放下或想开。")
    if any(item in compact for item in ("怕打扰", "不想麻烦")):
        signals.append("用户可能同时想联系家人又怕打扰；可以承认两部分，不替用户或家人做决定。")
    if connection_wish:
        signals.append("用户表达了现实联系意愿；先尊重犹豫，若用户愿意，只给一个低负担的联系动作，不保证对方反应。")
    if any(item in compact for item in ("吵架", "嫌弃", "委屈")):
        signals.append("涉及家庭矛盾；回应具体影响，不猜动机、不站队，也不劝用户一味忍耐。")
    if any(item in compact for item in ("没回电话", "没回消息")) and any(
        item in compact for item in ("要不要", "怎么办", "该不该")
    ):
        signals.append("用户明确在询问联系建议；先给清楚答案和一个低负担做法，不猜家人正在忙、手机没电或故意不回复。")
    if any(item in compact for item in ("生气", "恼火", "气死我了", "来气")):
        signals.append("用户明确在生气或吐槽；先用一句有分寸的轻松口语跟上情绪，再问一件具体的事。不要机械复述、劝冷静、说教或煽动报复。")
    if "膝盖" in compact and any(item in compact for item in ("疼", "痛")):
        signals.append("只承接膝盖疼，不断言已经影响走路；最多问一个会改变建议的细节。")
    repairing = any(item in compact for item in _REPAIR_PHRASES)
    if repairing:
        signals.append("用户正在纠正上一轮误解；采用用户的新说法，不要再次复述错误理解。")
    practical = any(item in compact for item in _PRACTICAL_OBJECTS) and any(
        item in compact for item in _PRACTICAL_CUES
    )
    if practical and not any(item in compact for item in _SCREEN_STATE_CUES):
        signals.append("用户没有说明当前屏幕。本轮只问是否已经打开目标应用或现在看见什么，不给任何操作步骤。")
    if repairing and practical:
        signals.append("纠正后仍是设备操作问题；只采用新对象并给一个可确认动作，不猜设备损坏，也不追加备用步骤。")

    if cognitive:
        care_mode = "cognitive_support"
    elif repairing:
        care_mode = "repair_support"
    elif repeated:
        care_mode = "repeat_support"
    elif practical:
        care_mode = "practical_help"
    elif any(item in compact for item in _HEALTH_TERMS):
        care_mode = "health_support"
    elif connection_wish or any(item in compact for item in _EMOTIONAL_TERMS):
        care_mode = "emotional_support"
    elif any(item in compact for item in _REMINISCENCE_TERMS):
        care_mode = "reminiscence"
    else:
        care_mode = "natural_adult"

    context = ElderContext(
        familiarity,
        care_mode,
        signals,
        recent_openings,
        recent_question_count,
    )
    memories = _requested_memories(message)
    safety = _safety_reply(message, emergency_number=emergency_number)
    if safety:
        scene, safety_mode, reply = safety
        return CarePlan(scene, "local_safety", familiarity, safety_mode, context, memories, reply)
    if "累赘" in compact:
        return CarePlan("dignity_support", "local_dignity", familiarity, "emotional_support", context, memories, "需要人搭把手，不等于您是累赘。今天是发生了什么，让您有了这个念头？")
    if any(item in compact for item in ("我要回家", "这不是我家")):
        return CarePlan("cognitive_safety", "local_cognitive_safety", familiarity, "cognitive_support", context, memories, "您是想回到熟悉、安心的地方。先别一个人往外走，请身边认识的人陪您确认一下现在在哪里。您身边有认识的人吗？")
    if compact in _PRESENCE_ONLY:
        return CarePlan("presence", "local_presence", familiarity, "natural_adult", context, memories, "在呢，您慢慢说。")
    return CarePlan("elder_conversation", "realtime", familiarity, care_mode, context, memories, None)
