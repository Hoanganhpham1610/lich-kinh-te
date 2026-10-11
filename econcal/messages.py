"""Soạn nội dung tin nhắn Telegram (HTML)."""
from datetime import datetime
from html import escape
from itertools import groupby

from . import gold
from .rules import LEVEL_ICON

DISCLAIMER = "<i>⚠️ Nhận định tham khảo, không phải khuyến nghị đầu tư.</i>"

WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
LEGEND = "<i>🔥 Cực mạnh · 🔴 Cao · 🟠 Trung bình — giờ Việt Nam (GMT+7)</i>"


def _dt(e, tz) -> datetime:
    return datetime.fromtimestamp(e["ts"], tz)


def _time(e, tz) -> str:
    return _dt(e, tz).strftime("%H:%M") if e["timed"] else (e["time_label"] or "Cả ngày")


def _title(e) -> str:
    t = f'<b>{escape(e["name"])}</b>'
    if e["vi"]:
        t += f' — {escape(e["vi"])}'
    return t


def _numbers(e) -> str:
    bits = []
    if e["forecast"]:
        bits.append(f'Dự báo {escape(e["forecast"])}')
    if e["previous"]:
        bits.append(f'Trước {escape(e["previous"])}')
    return " | ".join(bits)


def _line(e, tz) -> str:
    s = f'{LEVEL_ICON[e["level"]]} <code>{_time(e, tz)}</code> {e["currency"]} {_title(e)}'
    nums = _numbers(e)
    return s + (f"\n      <i>{nums}</i>" if nums else "")


def _by_day(events, tz) -> str:
    blocks = []
    for day, items in groupby(events, key=lambda e: _dt(e, tz).date()):
        head = f"<b>📌 {WEEKDAYS[day.weekday()]} {day:%d/%m}</b>"
        blocks.append(head + "\n" + "\n".join(_line(e, tz) for e in items))
    return "\n\n".join(blocks)


def _footer(cfg) -> str:
    f = cfg["telegram"].get("footer")
    return f"\n\n{f}" if f else ""


def weekly(events, start, end, tz, cfg) -> str:
    head = f"🗓 <b>LỊCH TIN KINH TẾ TUẦN {start:%d/%m} – {end:%d/%m}</b>\n{LEGEND}"
    if not events:
        return head + "\n\nTuần này không có tin quan trọng." + _footer(cfg)
    top = [e for e in events if e["level"] == 4]
    hot = ""
    if top:
        hot = "\n\n<b>⚡ Tâm điểm tuần:</b> " + ", ".join(
            f'{escape(e["vi"] or e["name"])} ({WEEKDAYS[_dt(e, tz).weekday()]})' for e in top
        )
    return head + hot + "\n\n" + _by_day(events, tz) + _footer(cfg)


def daily(events, day, tz, cfg) -> str:
    head = f"☀️ <b>LỊCH TIN {WEEKDAYS[day.weekday()].upper()} {day:%d/%m}</b>\n{LEGEND}"
    if not events:
        return head + "\n\nHôm nay không có tin quan trọng. Thị trường có thể đi ngang." + _footer(cfg)
    lines = "\n".join(_line(e, tz) for e in events)
    return f"{head}\n\n{lines}{_footer(cfg)}"


def remind(group, minutes, tz, cfg) -> str:
    t = _dt(group[0], tz).strftime("%H:%M")
    head = f"⏰ <b>CÒN {minutes} PHÚT — {t} ra tin</b>"
    body = "\n".join(_line(e, tz) for e in group)
    return f"{head}\n\n{body}\n\n⚠️ Cẩn trọng biến động mạnh, giãn spread.{_footer(cfg)}"


def actual(group, tz, cfg, gold_rx=None, analysis=None) -> str:
    t = _dt(group[0], tz).strftime("%H:%M")
    head = f"📊 <b>KẾT QUẢ TIN {t}</b>"
    rows = []
    score = 0
    for e in group:
        mark = {1: "🟢 tốt hơn dự báo", 2: "🔻 xấu hơn dự báo"}.get(e["better_worse"], "")
        score += {1: 1, 2: -1}.get(e["better_worse"], 0)
        row = f'{LEVEL_ICON[e["level"]]} {e["currency"]} {_title(e)}\n      Thực tế: <b>{escape(e["actual"])}</b>'
        if mark:
            row += f"  {mark}"
        nums = _numbers(e)
        if nums:
            row += f"\n      <i>{nums}</i>"
        rows.append(row)
    out = f"{head}\n\n" + "\n".join(rows)
    if gold_rx:
        out += "\n\n" + gold.fmt(gold_rx)
    if analysis:
        out += f"\n\n🧠 <b>Phân tích tác động lên vàng</b>\n{analysis}"
    else:  # dự phòng khi không có AI: nhận định theo quy tắc
        usd = all(e["currency"] == "USD" for e in group)
        if usd and score > 0:
            out += "\n\n💵 Nhìn chung <b>tích cực cho USD</b> → thường gây áp lực lên vàng."
        elif usd and score < 0:
            out += "\n\n💵 Nhìn chung <b>tiêu cực cho USD</b> → thường hỗ trợ vàng."
    if analysis or score:
        out += "\n\n" + DISCLAIMER
    return out + _footer(cfg)


def followup(group, tz, gold_rx) -> str:
    t = _dt(group[0], tz).strftime("%H:%M")
    names = ", ".join(escape(e["vi"] or e["name"]) for e in group[:3])
    return f"⏱ <b>Vàng {gold_rx['minutes']} phút sau tin {t}</b> ({names})\n\n{gold.fmt(gold_rx)}"
