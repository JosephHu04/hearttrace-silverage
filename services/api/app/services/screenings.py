"""Versioned WS/T 802-2022 screening templates and deterministic scoring.

The companion model may invite an elder to start a screening, but it must not
rewrite items, answer on the elder's behalf, or calculate a score.  This module
is the only scoring source used by the API.
"""

from __future__ import annotations

from dataclasses import dataclass


INSTRUMENT_VERSION = "wst802-2022-v1"
SCREENING_NOTICE = "该结果仅用于标准化筛查和关怀参考，不构成精神疾病诊断。"


@dataclass(frozen=True)
class Item:
    code: str
    text: str
    choices: tuple[tuple[str, str, int], ...]


@dataclass(frozen=True)
class Instrument:
    code: str
    name: str
    purpose: str
    timeframe: str
    standard_reference: str
    items: tuple[Item, ...]


YES_NO = (("yes", "是", 1), ("no", "否", 0))
YES_NO_REVERSED = (("yes", "是", 0), ("no", "否", 1))
GAD_CHOICES = (
    ("0", "无", 0),
    ("1", "7天以内", 1),
    ("2", "一半以上日子", 2),
    ("3", "几乎每天", 3),
)


GDS15 = Instrument(
    code="gds15",
    name="简版老年抑郁量表（GDS-15）",
    purpose="观察近一周与情绪低落、兴趣、幸福感和无助感相关的自述情况",
    timeframe="请根据过去一周内的感受回答。",
    standard_reference="WS/T 802-2022 附录 B.4",
    items=(
        Item("gds15_1", "您对生活基本上满意吗？", YES_NO_REVERSED),
        Item("gds15_2", "您是否放弃了许多爱好和兴趣？", YES_NO),
        Item("gds15_3", "您是否觉得生活空虚？", YES_NO),
        Item("gds15_4", "您是否常感到厌倦？", YES_NO),
        Item("gds15_5", "您是否大部分时间精力充沛？", YES_NO_REVERSED),
        Item("gds15_6", "您是否害怕会有不幸的事落到您头上？", YES_NO),
        Item("gds15_7", "您是否大部分时间感到幸福？", YES_NO_REVERSED),
        Item("gds15_8", "您是否常感到孤立无援？", YES_NO),
        Item("gds15_9", "您是否愿意待在家里而不愿去室外做些新鲜事？", YES_NO),
        Item("gds15_10", "您是否觉得记忆力比以前差？", YES_NO),
        Item("gds15_11", "您觉得现在活着很开心吗？", YES_NO_REVERSED),
        Item("gds15_12", "您是否觉得像现在这样活着毫无意义？", YES_NO),
        Item("gds15_13", "您觉得生活充满活力吗？", YES_NO_REVERSED),
        Item("gds15_14", "您是否觉得您的处境已毫无希望？", YES_NO),
        Item("gds15_15", "您是否觉得大多数人比您强得多？", YES_NO),
    ),
)


GAD7 = Instrument(
    code="gad7",
    name="广泛性焦虑障碍量表（GAD-7）",
    purpose="观察近两周紧张、担忧、放松困难和不安等自述情况",
    timeframe="请根据过去两星期内的情况回答。",
    standard_reference="WS/T 802-2022 附录 B.3",
    items=(
        Item("gad7_1", "感觉紧张、焦虑或急切？", GAD_CHOICES),
        Item("gad7_2", "不能够停止或控制担忧？", GAD_CHOICES),
        Item("gad7_3", "对各种各样的事情担忧过多？", GAD_CHOICES),
        Item("gad7_4", "很难放松下来？", GAD_CHOICES),
        Item("gad7_5", "由于不安而无法静坐？", GAD_CHOICES),
        Item("gad7_6", "变得容易烦恼或急躁？", GAD_CHOICES),
        Item("gad7_7", "感到似乎将有可怕的事情发生而害怕？", GAD_CHOICES),
    ),
)


INSTRUMENTS = {instrument.code: instrument for instrument in (GDS15, GAD7)}


def get_instrument(code: str) -> Instrument:
    try:
        return INSTRUMENTS[code]
    except KeyError as exc:
        raise ValueError("不支持的筛查量表") from exc


def instrument_payload(instrument: Instrument) -> dict[str, object]:
    return {
        "code": instrument.code,
        "version": INSTRUMENT_VERSION,
        "name": instrument.name,
        "purpose": instrument.purpose,
        "timeframe": instrument.timeframe,
        "standardReference": instrument.standard_reference,
        "itemCount": len(instrument.items),
    }


def question_payload(instrument: Instrument, index: int) -> dict[str, object] | None:
    if index >= len(instrument.items):
        return None
    item = instrument.items[index]
    return {
        "itemCode": item.code,
        "number": index + 1,
        "text": item.text,
        "choices": [{"value": value, "label": label} for value, label, _ in item.choices],
    }


def score_response(instrument: Instrument, item_code: str, value: str) -> int:
    item = next((candidate for candidate in instrument.items if candidate.code == item_code), None)
    if item is None:
        raise ValueError("量表题目不匹配")
    for choice_value, _, score in item.choices:
        if value == choice_value:
            return score
    raise ValueError("答案选项无效")


def result_payload(instrument_code: str, total_score: int) -> dict[str, object]:
    if instrument_code == "gds15":
        if total_score <= 8:
            band, label, score_range = "normal", "未见量表提示", "0-8分"
        elif total_score <= 11:
            band, label, score_range = "moderate", "需要人工关注", "9-11分"
        else:
            band, label, score_range = "high", "需要尽快人工评估", "12-15分"
    elif instrument_code == "gad7":
        if total_score <= 9:
            band, label, score_range = "normal", "未见量表提示", "0-9分"
        elif total_score <= 14:
            band, label, score_range = "moderate", "需要人工关注", "10-14分"
        else:
            band, label, score_range = "high", "需要尽快人工评估", "15-21分"
    else:
        raise ValueError("不支持的筛查量表")

    recommendation = {
        "normal": "继续保持日常交流和规律生活；如本人仍感到明显不适，可主动联系专业人员。",
        "moderate": "建议由受过培训的工作人员结合近期状态进行复核，并安排后续关怀。",
        "high": "建议尽快由医疗、护理或心理专业人员进一步评估；如存在现实安全危险，应立即启动紧急求助流程。",
    }[band]
    return {
        "totalScore": total_score,
        "scoreRange": score_range,
        "band": band,
        "label": label,
        "recommendation": recommendation,
        "notice": SCREENING_NOTICE,
    }
