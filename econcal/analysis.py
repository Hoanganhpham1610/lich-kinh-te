"""Phân tích tác động của tin lên giá vàng bằng Claude.

Cần biến môi trường ANTHROPIC_API_KEY. Lỗi bất kỳ => trả về None để bot dùng nhận định theo quy tắc.
"""
import os
import re
from datetime import datetime
from html import escape

SYSTEM = """Bạn là chuyên viên phân tích vĩ mô viết cho một kênh Telegram tiếng Việt về tin kinh tế và giá vàng.
Nhiệm vụ: ngay sau khi số liệu kinh tế được công bố, viết nhận định ngắn về tác động lên vàng (XAU/USD).

Nội dung cần có, theo thứ tự:
1. Đánh giá số liệu: nóng/nguội, mạnh/yếu so với dự báo và kỳ trước. Nếu các tin cùng giờ trái chiều nhau, nói rõ tin nào quan trọng hơn.
2. Hệ quả với kỳ vọng lãi suất Fed, đồng USD và lợi suất trái phiếu Mỹ.
3. Kịch bản cho vàng: thiên tăng hay thiên giảm, mức độ (mạnh/vừa/nhẹ).
4. Nếu có dữ liệu giá vàng thực tế sau khi ra tin: nhận xét thị trường đang phản ứng thuận hay ngược kỳ vọng.
5. Một lưu ý rủi ro ngắn (ví dụ tin quan trọng sắp tới, khả năng đảo chiều).

Quy tắc trình bày:
- Tối đa 5 dòng, mỗi dòng bắt đầu bằng một emoji phù hợp, tổng dưới 700 ký tự.
- Chỉ dùng thẻ <b> và <i> để nhấn mạnh; không dùng Markdown, không dùng thẻ khác.
- Viết tiếng Việt tự nhiên, gọn, dành cho nhà đầu tư cá nhân.
- Không đưa điểm vào lệnh, cắt lỗ, chốt lời hay khuyến nghị mua/bán cụ thể; chỉ phân tích kịch bản.
- Không bịa số liệu ngoài dữ liệu được cung cấp."""


def _describe(e, tz) -> str:
    t = datetime.fromtimestamp(e["ts"], tz).strftime("%a %d/%m %H:%M")
    bw = {1: "tốt hơn dự báo (theo ForexFactory, tốt cho đồng tiền)", 2: "xấu hơn dự báo"}.get(e["better_worse"], "")
    parts = [f'{t} | {e["currency"]} | {e["name"]}' + (f' ({e["vi"]})' if e["vi"] else "")]
    parts.append(f'  Thực tế: {e["actual"] or "-"} | Dự báo: {e["forecast"] or "-"} | Kỳ trước: {e["previous"] or "-"}')
    if bw:
        parts.append(f"  Đánh giá: {bw}")
    return "\n".join(parts)


def _sanitize(text: str) -> str:
    """Escape mọi thứ rồi chỉ cho phép lại <b>, <i> để Telegram HTML không lỗi."""
    s = escape(text.strip())
    return re.sub(r"&lt;(/?)(b|i)&gt;", r"<\1\2>", s)


def analyze(group: list[dict], context: list[dict], gold_rx: dict | None, tz, cfg: dict) -> str | None:
    ai = cfg.get("ai", {})
    if not ai.get("enabled") or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic

    prompt = "TIN VỪA CÔNG BỐ:\n" + "\n".join(_describe(e, tz) for e in group)
    if gold_rx:
        prompt += (
            f'\n\nGIÁ VÀNG GIAO NGAY XAU/USD: trước tin {gold_rx["before"]:.1f}, hiện tại {gold_rx["now"]:.1f} '
            f'({gold_rx["pct"]:+.2f}%) sau {gold_rx["minutes"]} phút; biên độ {gold_rx["low"]:.1f}–{gold_rx["high"]:.1f}.'
        )
    else:
        prompt += "\n\nGIÁ VÀNG: chưa có dữ liệu phản ứng."
    if context:
        prompt += "\n\nBỐI CẢNH TRONG TUẦN (tin quan trọng khác):\n" + "\n".join(_describe(e, tz) for e in context)

    try:
        client = anthropic.Anthropic(timeout=120, max_retries=2)
        resp = client.beta.messages.create(
            model=ai.get("model", "claude-opus-5-5"),
            max_tokens=16000,
            system=SYSTEM,
            output_config={"effort": ai.get("effort", "medium")},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as ex:
        print(f"Claude lỗi: {ex}")
        return None
    if resp.stop_reason == "refusal":
        print(f"Claude từ chối: {resp.stop_details}")
        return None
    text = "".join(b.text for b in resp.content if b.type == "text")
    return _sanitize(text) if text.strip() else None
