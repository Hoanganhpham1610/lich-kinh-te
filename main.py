"""Lịch kinh tế → Dashboard + Telegram.

Cách dùng:
  python main.py tick              # chạy 1 vòng (GitHub Actions gọi mỗi 5 phút)
  python main.py tick --dry-run    # in tin ra màn hình thay vì gửi Telegram
  python main.py preview weekly    # xem trước tin tổng hợp tuần (weekly|daily|remind|actual)
  python main.py test-telegram     # gửi 1 tin thử để kiểm tra token / chat id
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from itertools import groupby
from pathlib import Path
from zoneinfo import ZoneInfo

from econcal import messages
from econcal.fetch import fetch_week
from econcal.rules import classify
from econcal.telegram import send

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "state" / "state.json"
DATA_FILE = ROOT / "docs" / "data.json"

sys.stdout.reconfigure(encoding="utf-8")


def load_dotenv() -> None:
    """Đọc file .env (chỉ dùng khi chạy trên máy; trên GitHub dùng Secrets)."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))


load_dotenv()


def load_cfg() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"sent": {}}


def save_state(state: dict) -> None:
    cutoff = time.time() - 14 * 86400
    state["sent"] = {k: v for k, v in state["sent"].items() if v > cutoff}
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def write_dashboard_data(events: list[dict], source: str, cfg: dict) -> bool:
    """Ghi docs/data.json; chỉ ghi khi dữ liệu đổi để tránh commit thừa. Trả về True nếu có thay đổi."""
    payload = {
        "source": source,
        "timezone": cfg["timezone"],
        "watch_currencies": cfg["watch_currencies"],
        "events": sorted(events, key=lambda e: (e["ts"], -e["level"])),
    }
    old = json.loads(DATA_FILE.read_text(encoding="utf-8")) if DATA_FILE.exists() else {}
    old.pop("updated", None)
    if old == payload:
        return False
    payload["updated"] = int(time.time())
    DATA_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return True


def get_events(cfg: dict) -> tuple[list[dict], str]:
    events, source = fetch_week("this")
    # Chủ nhật VN: lấy luôn tuần sau để tin tổng hợp / dashboard không bị trống
    tz = ZoneInfo(cfg["timezone"])
    if datetime.now(tz).weekday() >= 5:
        try:
            nxt, _ = fetch_week("next")
            seen = {(e["currency"], e["name"], e["ts"]) for e in events}
            events += [e for e in nxt if (e["currency"], e["name"], e["ts"]) not in seen]
        except Exception as ex:
            print(f"Không lấy được tuần sau: {ex}")
    return classify(events, cfg), source


def pick(events, lo: datetime, hi: datetime, min_level: int) -> list[dict]:
    return sorted(
        (e for e in events if e["watch"] and e["level"] >= min_level and lo.timestamp() <= e["ts"] < hi.timestamp()),
        key=lambda e: (e["ts"], -e["level"]),
    )


def tick(dry_run: bool = False, now: datetime | None = None) -> None:
    cfg = load_cfg()
    tz = ZoneInfo(cfg["timezone"])
    now = now or datetime.now(tz)
    tg = cfg["telegram"]
    state = load_state()
    sent = state["sent"]

    events, source = get_events(cfg)
    print(f"[{now:%Y-%m-%d %H:%M}] {len(events)} tin từ {source}")
    # Feed dự phòng không có actual => không ghi đè dashboard
    if source in ("forexfactory", "firecrawl"):
        if write_dashboard_data(events, source, cfg):
            print("Đã cập nhật docs/data.json")

    def mark(key):
        sent[key] = int(time.time())

    today7 = now.replace(hour=tg["daily"]["hour"], minute=0, second=0, microsecond=0)

    # 1) Tổng hợp tuần
    w = tg["weekly"]
    wkey = f"weekly:{now:%G-W%V}"
    if w["enabled"] and now.weekday() == w["weekday"] and w["hour"] <= now.hour < 12 and wkey not in sent:
        start = today7.replace(hour=0)
        end = start + timedelta(days=7)
        send(messages.weekly(pick(events, start, end, w["min_level"]), start, end - timedelta(days=1), tz, cfg), dry_run)
        mark(wkey)

    # 2) Lịch trong ngày (07:00 hôm nay → 07:00 mai, để gồm cả tin đêm như FOMC 01:00)
    d = tg["daily"]
    dkey = f"daily:{now:%Y-%m-%d}"
    if d["enabled"] and d["hour"] <= now.hour < 12 and now.weekday() < 5 and dkey not in sent:
        send(messages.daily(pick(events, today7, today7 + timedelta(days=1), d["min_level"]), now.date(), tz, cfg), dry_run)
        mark(dkey)

    # 3) Nhắc trước giờ ra tin
    r = tg["remind"]
    if r["enabled"]:
        upcoming = [e for e in pick(events, now, now + timedelta(minutes=r["minutes_before"]), r["min_level"])
                    if e["timed"] and f'remind:{e["key"]}' not in sent]
        for ts, group in groupby(upcoming, key=lambda e: e["ts"]):
            group = list(group)
            minutes = max(1, round((ts - now.timestamp()) / 60))
            send(messages.remind(group, minutes, tz, cfg), dry_run)
            for e in group:
                mark(f'remind:{e["key"]}')

    # 4) Kết quả actual
    a = tg["actual"]
    if a["enabled"]:
        released = [e for e in pick(events, now - timedelta(minutes=a["max_minutes_after"]), now, a["min_level"])
                    if e["actual"] and f'actual:{e["key"]}' not in sent]
        for ts, group in groupby(released, key=lambda e: e["ts"]):
            group = list(group)
            send(messages.actual(group, tz, cfg), dry_run)
            for e in group:
                mark(f'actual:{e["key"]}')

    if not dry_run:
        save_state(state)


def preview(kind: str) -> None:
    cfg = load_cfg()
    tz = ZoneInfo(cfg["timezone"])
    tg = cfg["telegram"]
    events, source = get_events(cfg)
    now = datetime.now(tz)
    today7 = now.replace(hour=tg["daily"]["hour"], minute=0, second=0, microsecond=0)
    if kind == "weekly":
        start = (today7 - timedelta(days=now.weekday())).replace(hour=0)
        if now.weekday() >= 5:
            start += timedelta(days=7)
        end = start + timedelta(days=7)
        print(messages.weekly(pick(events, start, end, tg["weekly"]["min_level"]), start, end - timedelta(days=1), tz, cfg))
    elif kind == "daily":
        print(messages.daily(pick(events, today7, today7 + timedelta(days=1), tg["daily"]["min_level"]), now.date(), tz, cfg))
    else:
        watched = [e for e in events if e["watch"] and e["level"] >= 3 and e["timed"]]
        if kind == "actual":
            watched = [e for e in watched if e["has_data"]]
            watched = [e for e in watched if e["actual"]] or watched
        if not watched:
            print("Không có tin phù hợp để xem trước.")
            return
        ts = watched[0]["ts"] if kind == "remind" else watched[-1]["ts"]
        group = [e for e in watched if e["ts"] == ts]
        if kind == "remind":
            print(messages.remind(group, tg["remind"]["minutes_before"], tz, cfg))
        else:
            for e in group:  # dữ liệu giả nếu chưa ra tin
                e["actual"] = e["actual"] or e["forecast"] or "?"
            print(messages.actual(group, tz, cfg))
    print(f"\n(nguồn: {source})")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tick")
    t.add_argument("--dry-run", action="store_true")
    pv = sub.add_parser("preview")
    pv.add_argument("kind", choices=["weekly", "daily", "remind", "actual"])
    sub.add_parser("test-telegram")
    args = p.parse_args()

    if args.cmd == "tick":
        tick(args.dry_run)
    elif args.cmd == "preview":
        preview(args.kind)
    else:
        send("✅ Bot lịch kinh tế đã kết nối thành công!")
        print("Đã gửi tin thử.")
