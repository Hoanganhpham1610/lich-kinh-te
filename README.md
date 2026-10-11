# 📅 Lịch Kinh Tế → Dashboard + Telegram

Tự động lấy lịch tin kinh tế từ ForexFactory, chấm mức quan trọng theo quy tắc riêng, rồi:

- **Dashboard** (GitHub Pages): lịch theo giờ VN, lọc theo mức độ, đếm ngược tin quan trọng tiếp theo, đánh dấu ⭐ thủ công, tô xanh/đỏ số thực tế so với dự báo.
- **Bot Telegram** đăng lên kênh:
  | Loại tin | Khi nào |
  |---|---|
  | 🗓 Tổng hợp tuần | Thứ Hai 07:00 |
  | ☀️ Lịch trong ngày | 07:00 thứ Hai–Sáu (gồm cả tin đêm như FOMC 01:00) |
  | ⏰ Nhắc trước | 30 phút trước tin 🔴/🔥 |
  | 📊 Kết quả actual | Ngay khi ForexFactory cập nhật số thực tế |

## Mức quan trọng

| | Mức | Nguồn |
|---|---|---|
| 🔥 | Cực mạnh | `always_top` trong `config.json` (NFP, CPI, lãi suất Fed, họp báo FOMC, Chủ tịch Fed…) |
| 🔴 | Cao | High của ForexFactory + `force_high` |
| 🟠 | Trung bình | Medium của ForexFactory + `force_medium` (tồn kho dầu, OPEC…) |
| 🟡 | Thấp | Low |
| ⚪ | Nghỉ lễ | Holiday |

Muốn nâng/hạ tin nào thì thêm **phần đầu tên tin** (đúng như trên ForexFactory) vào danh sách tương ứng.
`watch_currencies` = các đồng tiền theo dõi; `watch_keywords` = tin của nước khác vẫn lấy nếu tên có chứa từ khoá (OPEC, Crude Oil…).

## Cài đặt (khoảng 10 phút)

### 1. Tạo bot Telegram
1. Chat với [@BotFather](https://t.me/BotFather) → `/newbot` → lấy **token**.
2. Thêm bot vào kênh làm **Admin** (quyền *Post messages*).
3. **Chat ID**: kênh công khai dùng `@ten_kenh`; kênh riêng tư dùng dạng `-100xxxxxxxxxx`.

Thử trên máy (PowerShell):
```powershell
pip install -r requirements.txt
$env:TELEGRAM_BOT_TOKEN="123:ABC..."; $env:TELEGRAM_CHAT_ID="@ten_kenh"; python main.py test-telegram
```

### 2. Đưa lên GitHub
1. Tạo repo mới trên github.com — **nên để Public**: Actions miễn phí không giới hạn. Repo Private chỉ có 2.000 phút/tháng, không đủ cho chạy 5 phút/lần.
2. Đẩy code lên:
   ```bash
   git init && git add . && git commit -m "init" && git branch -M main
   git remote add origin https://github.com/<user>/<repo>.git && git push -u origin main
   ```
3. **Settings → Secrets and variables → Actions → New repository secret**:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `FIRECRAWL_API_KEY` *(tuỳ chọn — dự phòng khi ForexFactory chặn máy chủ GitHub)*
4. **Settings → Pages** → Source: *Deploy from a branch* → `main` / `/docs` → Save.
   Dashboard sẽ ở `https://<user>.github.io/<repo>/` — ghim link này lên kênh.
5. Tab **Actions** → chọn *Lich kinh te* → **Run workflow** để chạy lần đầu.

## Lệnh hữu ích

```bash
python main.py preview weekly     # xem trước tin tổng hợp tuần (weekly|daily|remind|actual)
python main.py tick --dry-run     # chạy 1 vòng nhưng chỉ in ra, không gửi
```

## Lưu ý

- **Mạng VNPT/Viettel có thể chặn DNS forexfactory.com** khi chạy trên máy ở VN. Đặt `$env:FF_IP="104.18.7.7"` hoặc đổi DNS sang 1.1.1.1. Trên GitHub không bị ảnh hưởng.
- **Lịch chạy của GitHub có thể trễ 5–15 phút** lúc cao điểm. Nếu cần nhắc đúng giờ, tạo job miễn phí trên [cron-job.org](https://cron-job.org) gọi API `workflow_dispatch` mỗi 5 phút (cần GitHub token quyền *Actions: write*).
- Trạng thái "đã gửi" lưu ở `state/state.json` để không gửi trùng; `docs/data.json` chỉ commit khi dữ liệu thay đổi.
- Muốn thêm chữ ký/kênh cuối mỗi tin: sửa `telegram.footer` trong `config.json`, ví dụ `"📢 @ten_kenh"`.
