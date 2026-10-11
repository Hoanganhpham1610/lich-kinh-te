import json
import os
import urllib.request

MAX_LEN = 4000  # Telegram giới hạn 4096 ký tự / tin


def _split(text: str) -> list[str]:
    """Cắt tin dài theo đoạn (dòng trống) để không vượt giới hạn."""
    parts, cur = [], ""
    for block in text.split("\n\n"):
        if cur and len(cur) + len(block) + 2 > MAX_LEN:
            parts.append(cur)
            cur = block
        else:
            cur = f"{cur}\n\n{block}" if cur else block
    if cur:
        parts.append(cur)
    return parts


def send(text: str, dry_run: bool = False, reply_to: int | None = None) -> list[int]:
    """Gửi tin (tự cắt nếu dài), trả về danh sách message_id."""
    if dry_run:
        print("=" * 60 + (f" (trả lời tin {reply_to})" if reply_to else "") + "\n" + text + "\n")
        return [0]
    ids = []
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    for part in _split(text):
        payload = {
            "chat_id": chat_id,
            "text": part,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_to:
            payload["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.load(r)
            if not res.get("ok"):
                raise RuntimeError(f"Telegram lỗi: {res}")
            ids.append(res["result"]["message_id"])
    return ids
