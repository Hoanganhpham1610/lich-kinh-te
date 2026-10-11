"""Giá vàng giao ngay XAU/USD theo thời gian thực từ gold-api.com (miễn phí, không cần key).

Bot ghi lại giá ở mỗi vòng chạy quanh giờ ra tin (state["gold"]), từ đó tính giá trước và sau khi ra tin.
"""
import json
import urllib.request

URL = "https://api.gold-api.com/price/XAU"


def spot() -> float | None:
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return float(json.load(r)["price"])
    except Exception as ex:
        print(f"Không lấy được giá vàng: {ex}")
        return None


def reaction(snaps: list[list], release_ts: int, now_ts: int, now_price: float, max_before_age: int = 20 * 60) -> dict | None:
    """snaps: [[ts, price], ...]. Giá trước tin = lần ghi gần nhất trước giờ ra tin (không cũ quá 20 phút)."""
    before = [s for s in snaps if s[0] < release_ts and release_ts - s[0] <= max_before_age]
    if not before or now_price is None:
        return None
    b_ts, p0 = before[-1]
    after = [p for t, p in snaps if t >= release_ts] + [now_price]
    return {
        "before": p0,
        "before_ts": b_ts,
        "now": now_price,
        "change": now_price - p0,
        "pct": (now_price - p0) / p0 * 100,
        "high": max(after),
        "low": min(after),
        "minutes": max(1, round((now_ts - release_ts) / 60)),
    }


def fmt(rx: dict) -> str:
    arrow = "📈" if rx["change"] > 0 else "📉" if rx["change"] < 0 else "➖"
    s = (
        f'{arrow} <b>Vàng XAU/USD</b>: {rx["before"]:,.1f} → <b>{rx["now"]:,.1f}</b> '
        f'({rx["change"]:+,.1f}$ | {rx["pct"]:+.2f}%) sau {rx["minutes"]} phút'
    )
    if rx["high"] != rx["low"]:
        s += f'\n      <i>Biên độ ghi nhận: {rx["low"]:,.1f} – {rx["high"]:,.1f}</i>'
    return s
