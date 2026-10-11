"""Chấm mức quan trọng cho từng tin.

level: 4 = 🔥 cực mạnh, 3 = 🔴 cao, 2 = 🟠 trung bình, 1 = 🟡 thấp, 0 = ⚪ nghỉ lễ / không kinh tế
"""

LEVEL_ICON = {4: "🔥", 3: "🔴", 2: "🟠", 1: "🟡", 0: "⚪"}
LEVEL_NAME = {4: "Cực mạnh", 3: "Cao", 2: "Trung bình", 1: "Thấp", 0: "Nghỉ lễ"}


def _starts(name: str, keywords: list[str]) -> bool:
    n = name.lower()
    return any(n.startswith(k.lower()) for k in keywords)


def vi_name(name: str, cfg: dict) -> str:
    names = cfg.get("vi_names", {})
    if name in names:
        return names[name]
    for en, vi in names.items():
        if name.startswith(en):
            return vi
    return ""


def classify(events: list[dict], cfg: dict) -> list[dict]:
    currencies = set(cfg["watch_currencies"])
    keywords = [k.lower() for k in cfg.get("watch_keywords", [])]
    for e in events:
        level = e["impact"]
        if level > 0:
            if _starts(e["name"], cfg.get("always_top", [])):
                level = 4
            elif _starts(e["name"], cfg.get("force_high", [])):
                level = max(level, 3)
            elif _starts(e["name"], cfg.get("force_medium", [])):
                level = max(level, 2)
        e["level"] = level
        e["vi"] = vi_name(e["name"], cfg)
        e["key"] = f'{e["currency"]}|{e["name"]}|{e["ts"]}'
        e["watch"] = e["currency"] in currencies or any(k in e["name"].lower() for k in keywords)
        # Tin "phát biểu", "họp"... không có số liệu => không chờ actual
        e["has_data"] = bool(e["forecast"] or e["previous"] or e["actual"])
    return events
