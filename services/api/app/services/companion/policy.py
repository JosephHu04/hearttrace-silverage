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
_NEGATIONS = ("没有", "没", "并无", "未出现", "不会", "不是")
_PAST = ("昨天", "前天", "上次", "以前", "刚才", "之前")
_RESOLVED = ("现在好了", "已经好了", "现在没事", "没事了", "缓过来了")
_CURRENT_AGAIN = ("现在又", "这会儿又", "刚刚又", "又开始")
_THIRD_PARTY = ("我妈", "我爸", "我老伴", "我爱人", "我丈夫", "我妻子", "我儿子", "我女儿", "他", "她")
_PRACTICAL_OBJECTS = ("手机", "微信", "视频", "电话", "电视", "遥控器", "挂号", "缴费", "付款", "二维码", "密码", "软件", "app", "按钮", "屏幕", "登录", "网络")
_PRACTICAL_CUES = ("怎么", "如何", "不会", "点哪里", "打不开", "弄不了", "帮我")
_HEALTH_TERMS = ("疼", "痛", "难受", "头晕", "恶心", "咳嗽", "发烧", "血压", "血糖", "睡不着", "失眠", "胸闷", "呼吸", "药", "医生", "医院")
_EMOTIONAL_TERMS = ("孤单", "孤独", "寂寞", "难过", "伤心", "害怕", "担心", "累赘", "没用", "没人管", "被忘了", "想孙子", "想女儿", "想儿子", "想老伴")
_REMINISCENCE_TERMS = ("我以前", "年轻那会", "年轻时候", "当年", "小时候", "从前", "老家")
_COGNITIVE_PHRASES = ("我要回家", "这不是我家", "有人偷了我的", "有人要害我", "我要找妈妈", "我要找爸爸")
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


def _safety_reply(message: str) -> tuple[str, str, str] | None:
    compact = _compact(message)
    resolved_past = (
        any(item in compact for item in _PAST)
        and any(item in compact for item in _RESOLVED)
        and not any(item in compact for item in _CURRENT_AGAIN)
    )
    if resolved_past:
        return None
    if _active_phrase(compact, _SELF_HARM):
        if _third_party(compact, _SELF_HARM):
            return (
                "urgent_safety", "emotional_support",
                "我很重视您说的情况。请先陪着这位家人，不要让对方独处，并马上联系可信任的人；如果对方已经准备伤害自己或不能保证安全，请立即拨打120或110。您现在和对方在一起吗？",
            )
        return (
            "urgent_safety", "emotional_support",
            "我很重视您刚才这句话。请先不要独处，马上联系身边可信任的人；如果您已经准备伤害自己或不能保证安全，请立即拨打120或110。您现在身边有人吗？",
        )
    if _active_phrase(compact, _URGENT_FALL):
        if _third_party(compact, _URGENT_FALL):
            return ("urgent_safety", "health_support", "先不要勉强扶这位家人起身，也不要让对方独自走动。请马上拨打120或叫身边的人来帮忙。您现在和对方在一起吗？")
        return ("urgent_safety", "health_support", "先不要勉强起身，也不要独自走动。请马上拨打120或大声叫身边的人来帮忙。您现在够得到电话吗？")
    if _active_phrase(compact, _URGENT_HEALTH):
        if _third_party(compact, _URGENT_HEALTH):
            return ("urgent_health", "health_support", "这位家人的情况可能很危险，请马上拨打120，并让对方坐下，不要自行走动或开车。您现在和对方在一起吗？")
        return ("urgent_health", "health_support", "您现在说的情况可能很危险，请马上拨打120，或者立刻叫身边的人来帮您。先坐下，别自己走动或开车。您身边现在有人吗？")
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
) -> CarePlan:
    compact = _compact(message)
    familiarity = "first_meeting" if turn_count < 4 else "getting_familiar" if turn_count < 24 else "long_term"
    repeated = len(compact) >= 2 and any(compact == _compact(item) for item in recent_user_messages[:4])
    signals: list[str] = []
    if repeated:
        signals.append("用户近几轮说过相同的话；耐心重新回应，不指出重复。")
    cognitive = any(item in compact for item in _COGNITIVE_PHRASES)
    if cognitive:
        signals.append("可能包含方位或人物混乱；不要诊断、争辩或附和未经证实的内容。")
    if "想孙子" in compact:
        signals.append("先陪用户停留在想念里，再问一个真实片段；不能猜孙子的称呼或动作。")
    if "膝盖" in compact and any(item in compact for item in ("疼", "痛")):
        signals.append("只承接膝盖疼，不断言已经影响走路；最多问一个会改变建议的细节。")

    if cognitive:
        care_mode = "cognitive_support"
    elif repeated:
        care_mode = "repeat_support"
    elif any(item in compact for item in _PRACTICAL_OBJECTS) and any(item in compact for item in _PRACTICAL_CUES):
        care_mode = "practical_help"
    elif any(item in compact for item in _HEALTH_TERMS):
        care_mode = "health_support"
    elif any(item in compact for item in _EMOTIONAL_TERMS):
        care_mode = "emotional_support"
    elif any(item in compact for item in _REMINISCENCE_TERMS):
        care_mode = "reminiscence"
    else:
        care_mode = "natural_adult"

    context = ElderContext(familiarity, care_mode, signals, recent_openings)
    memories = _requested_memories(message)
    safety = _safety_reply(message)
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
