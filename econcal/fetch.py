"""Lấy lịch kinh tế từ ForexFactory.

Nguồn chính: trang https://www.forexfactory.com/calendar (có nhúng JSON đầy đủ, kể cả số Actual).
Dự phòng 1: Firecrawl API (nếu đặt FIRECRAWL_API_KEY) khi bị Cloudflare chặn.
Dự phòng 2: feed JSON nfs.faireconomy.media (không có Actual, chỉ có lịch).
"""
import json
import os
import re
import time
import urllib.request
from datetime import datetime

FF_URL = "https://www.forexfactory.com/calendar?week={week}"
FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

IMPACT = {"high": 3, "medium": 2, "low": 1, "holiday": 0, "non-economic": 0}


def _fetch_html_direct(url: str) -> str:
    from curl_cffi import requests, CurlOpt

    opts = {}
    # Một số nhà mạng VN (VNPT...) chặn DNS forexfactory.com — đặt FF_IP=104.18.7.7 để chạy local.
    if os.environ.get("FF_IP"):
        opts[CurlOpt.RESOLVE] = [f"www.forexfactory.com:443:{os.environ['FF_IP']}"]
    s = requests.Session(impersonate="chrome", curl_options=opts)
    err = None
    for attempt in range(3):
        try:
            r = s.get(url, timeout=40)
            if r.status_code == 200 and "days:" in r.text:
                return r.text
            err = RuntimeError(f"HTTP {r.status_code}, có thể bị Cloudflare chặn")
        except Exception as ex:
            err = ex
        time.sleep(3 * (attempt + 1))
    raise err


def _fetch_html_firecrawl(url: str) -> str:
    key = os.environ.get("FIRECRAWL_API_KEY")
    if not key:
        raise RuntimeError("Không có FIRECRAWL_API_KEY")
    req = urllib.request.Request(
        "https://api.firecrawl.dev/v2/scrape",
        data=json.dumps({"url": url, "formats": ["rawHtml"], "maxAge": 0}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)["data"]["rawHtml"]


def _parse_html(html: str) -> list[dict]:
    m = re.search(r"days:\s*(\[.*?\]),\s*\n\s*time:", html, re.S)
    if not m:
        raise RuntimeError("Không tìm thấy dữ liệu lịch trong trang")
    events = []
    for day in json.loads(m.group(1)):
        for e in day["events"]:
            time_label = e.get("timeLabel") or ""
            events.append({
                "name": e["name"],
                "currency": e["currency"],
                "impact": IMPACT.get((e.get("impactName") or "").lower(), 1),
                "ts": int(e["dateline"]),
                # "All Day", "Tentative", "Day 1"... => không có giờ cụ thể
                "timed": bool(re.match(r"^\d{1,2}:\d{2}(am|pm)$", time_label)),
                "time_label": time_label,
                "actual": e.get("actual") or "",
                "forecast": e.get("forecast") or "",
                "previous": e.get("previous") or "",
                # ForexFactory: 1 = tốt hơn dự báo, 2 = xấu hơn (đối với đồng tiền)
                "better_worse": int(e.get("actualBetterWorse") or 0),
                "url": "https://www.forexfactory.com" + e["url"] if e.get("url") else "",
            })
    return events


def _fetch_feed() -> list[dict]:
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        raw = json.load(r)
    events = []
    for e in raw:
        dt = datetime.fromisoformat(e["date"])
        events.append({
            "name": e["title"],
            "currency": e["country"],
            "impact": IMPACT.get(e["impact"].lower(), 1),
            "ts": int(dt.timestamp()),
            "timed": not (dt.hour == 0 and dt.minute == 0),
            "time_label": "",
            "actual": "",
            "forecast": e.get("forecast") or "",
            "previous": e.get("previous") or "",
            "better_worse": 0,
            "url": "",
        })
    return events


def fetch_week(week: str = "this") -> tuple[list[dict], str]:
    """Trả về (events, tên nguồn đã dùng)."""
    url = FF_URL.format(week=week)
    errors = []
    for name, fn in (("forexfactory", _fetch_html_direct), ("firecrawl", _fetch_html_firecrawl)):
        try:
            return _parse_html(fn(url)), name
        except Exception as ex:  # thử nguồn tiếp theo
            errors.append(f"{name}: {ex}")
            print(f"Lỗi nguồn {name}: {ex}")
    if week == "this":
        try:
            return _fetch_feed(), "faireconomy-feed (không có actual)"
        except Exception as ex:
            errors.append(f"feed: {ex}")
    raise RuntimeError("Không lấy được lịch:\n  " + "\n  ".join(errors))
