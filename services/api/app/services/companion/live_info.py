from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import Settings
from app.services.companion.widgets import WidgetUnavailable, get_news, get_weather


_WEATHER = re.compile(r"天气|气温|温度|下雨|带伞|冷不冷|热不热")
_TIME = re.compile(r"几点|现在时间|什么时间|今天几号|日期|星期几|周几")
_NEWS = re.compile(r"新闻|资讯|今天发生了什么|有什么新鲜事")
_BEIJING_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")


@dataclass(frozen=True)
class LiveInfoResult:
    reply: str
    widget: dict[str, Any]


def detect_live_info_kind(message: str) -> str | None:
    if _WEATHER.search(message):
        return "weather"
    if _TIME.search(message):
        return "time"
    if _NEWS.search(message):
        return "news"
    return None


def build_live_info_result(message: str, settings: Settings) -> LiveInfoResult | None:
    kind = detect_live_info_kind(message)
    if kind == "weather":
        try:
            weather = get_weather(
                settings.elder_default_latitude,
                settings.elder_default_longitude,
                location=settings.elder_default_location,
            )
        except WidgetUnavailable:
            return None
        rain = weather.get("precipitationProbability")
        rain_text = f"，今天最高降雨概率约 {rain}%" if rain is not None else ""
        stale_text = "（这是最近一次取到的数据）" if weather.get("stale") else ""
        return LiveInfoResult(
            reply=(
                f"{weather['location']}现在约 {weather['temperature']}℃，{weather['description']}，"
                f"体感约 {weather['apparentTemperature']}℃。今天最高约 {weather.get('high')}℃，"
                f"最低约 {weather.get('low')}℃{rain_text}{stale_text}。"
            ),
            widget={"kind": "weather", "data": weather},
        )
    if kind == "time":
        now = datetime.now(_BEIJING_TIMEZONE)
        weekday = f"星期{'一二三四五六日'[now.weekday()]}"
        return LiveInfoResult(
            reply=f"现在是北京时间 {now:%H:%M}，{now.month}月{now.day}日，{weekday}。",
            widget={"kind": "time", "data": {"time": now.strftime("%H:%M"), "date": f"{now.month}月{now.day}日", "weekday": weekday}},
        )
    if kind == "news":
        try:
            news = get_news(3)
        except WidgetUnavailable:
            return None
        items = news.get("items") or []
        if not items:
            return None
        lines = ["我刚看到这几条最新资讯："]
        for index, item in enumerate(items, start=1):
            lines.append(f"{index}、{item['title']}（{item['source']}）")
        lines.append("您想听哪一条，我再陪您细看。")
        return LiveInfoResult("\n".join(lines), {"kind": "news", "data": news})
    return None
