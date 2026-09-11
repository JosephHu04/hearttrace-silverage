from __future__ import annotations

import html
import json
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any


WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
NEWS_FEEDS = (
    ("综合新闻", "https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("国家统计局", "https://www.stats.gov.cn/sj/zxfb/rss.xml"),
    ("领事安全提醒", "https://cs.mfa.gov.cn/gyls/lsgz/lsyj/rss_57447.xml"),
)
REQUEST_TIMEOUT_SECONDS = 5
_WEATHER_CACHE_SECONDS = 600
_NEWS_CACHE_SECONDS = 900

_WEATHER_CODES = {
    0: "晴朗", 1: "大致晴朗", 2: "局部多云", 3: "阴天", 45: "有雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "较强毛毛雨", 56: "轻微冻雨", 57: "较强冻雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "轻微冻雨", 67: "较强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "米雪", 80: "阵雨", 81: "较强阵雨",
    82: "强阵雨", 85: "阵雪", 86: "强阵雪", 95: "雷雨", 96: "雷雨伴小冰雹", 99: "雷雨伴冰雹",
}

_cache_lock = threading.Lock()
_weather_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_news_cache: tuple[float, list[dict[str, str]]] | None = None


class WidgetUnavailable(RuntimeError):
    pass


def _read_url(url: str, *, max_bytes: int | None = None) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "HeartTrace-SilverAge/0.1",
            "Accept": "application/json, application/rss+xml, application/xml, text/xml",
        },
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read() if max_bytes is None else response.read(max_bytes)


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else None


def _round_optional(value: Any) -> int | None:
    return None if value is None else round(float(value))


def _parse_weather(payload: bytes, *, location: str) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8"))
    current = data.get("current") or {}
    daily = data.get("daily") or {}
    temperature = current.get("temperature_2m")
    if temperature is None:
        raise WidgetUnavailable("天气服务没有返回当前温度。")
    return {
        "location": location,
        "temperature": round(float(temperature)),
        "apparentTemperature": round(float(current.get("apparent_temperature", temperature))),
        "description": _WEATHER_CODES.get(int(current.get("weather_code", -1)), "天气变化中"),
        "high": _round_optional(_first(daily.get("temperature_2m_max"))),
        "low": _round_optional(_first(daily.get("temperature_2m_min"))),
        "precipitationProbability": _round_optional(_first(daily.get("precipitation_probability_max"))),
        "observedAt": str(current.get("time") or ""),
        "stale": False,
    }


def get_weather(latitude: float, longitude: float, *, location: str) -> dict[str, Any]:
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("经纬度超出有效范围。")
    cache_key = f"{latitude:.2f},{longitude:.2f}"
    now = time.monotonic()
    with _cache_lock:
        cached = _weather_cache.get(cache_key)
        if cached and now - cached[0] < _WEATHER_CACHE_SECONDS:
            return dict(cached[1])
    query = urllib.parse.urlencode(
        {
            "latitude": f"{latitude:.4f}",
            "longitude": f"{longitude:.4f}",
            "current": "temperature_2m,apparent_temperature,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": 1,
            "timezone": "auto",
        }
    )
    try:
        result = _parse_weather(_read_url(f"{WEATHER_URL}?{query}"), location=location)
    except Exception as exc:
        if cached:
            stale = dict(cached[1])
            stale["stale"] = True
            return stale
        raise WidgetUnavailable("暂时没有取到天气，请稍后再试。") from exc
    with _cache_lock:
        _weather_cache[cache_key] = (now, result)
    return dict(result)


def _element_text(element: ET.Element, names: tuple[str, ...]) -> str:
    for child in element.iter():
        if child.tag.rsplit("}", 1)[-1].lower() in names and child.text:
            return child.text.strip()
    return ""


def _entry_link(element: ET.Element) -> str:
    for child in element.iter():
        if child.tag.rsplit("}", 1)[-1].lower() != "link":
            continue
        href = child.attrib.get("href", "").strip()
        if href:
            return href
        if child.text:
            return child.text.strip()
    return ""


def _published_timestamp(value: str) -> float:
    if not value:
        return 0.0
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _parse_feed(payload: bytes, *, source: str) -> list[dict[str, str]]:
    root = ET.fromstring(payload)
    entries = [item for item in root.iter() if item.tag.rsplit("}", 1)[-1].lower() in {"item", "entry"}]
    items: list[dict[str, str]] = []
    for entry in entries:
        title = html.unescape(re.sub(r"<[^>]+>", "", _element_text(entry, ("title",))))
        title = re.sub(r"\s+", " ", title).strip()
        url = _entry_link(entry)
        published = _element_text(entry, ("pubdate", "published", "updated", "date"))
        entry_source = _element_text(entry, ("source",)) or source
        if title and url.startswith(("http://", "https://")):
            items.append({"title": title, "url": url, "source": entry_source, "published": published, "_timestamp": str(_published_timestamp(published))})
    return items


def _fetch_feed(source: str, url: str) -> list[dict[str, str]]:
    return _parse_feed(_read_url(url, max_bytes=512_000), source=source)


def get_news(limit: int = 3) -> dict[str, Any]:
    global _news_cache
    limit = max(1, min(limit, 8))
    now = time.monotonic()
    with _cache_lock:
        cached = _news_cache
        if cached and now - cached[0] < _NEWS_CACHE_SECONDS:
            return {"items": [dict(item) for item in cached[1][:limit]], "stale": False}
    fetched: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=len(NEWS_FEEDS)) as executor:
        futures = [executor.submit(_fetch_feed, source, url) for source, url in NEWS_FEEDS]
        for future in as_completed(futures):
            try:
                fetched.extend(future.result())
            except Exception:
                continue
    if not fetched:
        if cached:
            return {"items": [dict(item) for item in cached[1][:limit]], "stale": True}
        raise WidgetUnavailable("暂时没有取到资讯，请稍后再试。")
    deduplicated = {item["title"]: item for item in fetched}
    items = sorted(deduplicated.values(), key=lambda item: float(item.pop("_timestamp", "0") or 0), reverse=True)
    with _cache_lock:
        _news_cache = (now, items)
    return {"items": [dict(item) for item in items[:limit]], "stale": False}
