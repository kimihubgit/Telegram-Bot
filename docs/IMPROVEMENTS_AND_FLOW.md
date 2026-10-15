# 🛡️ BÁO CÁO CẢI TIẾN HỆ THỐNG VÀ LUỒNG XỬ LÝ (FLOW ARCHITECTURE)
> **Dự án:** KiGuard Telegram Bot — Chặn Quảng Cáo & Bảo Vệ Nhóm  
> **Ngày cập nhật:** 15/10/2026  
> **Trạng thái:** Đã kiểm thử và chạy thử nghiệm thành công (15/15 module loaded)

---

## 📑 MỤC LỤC
1. [Tổng quan vấn đề trước khi sửa (Before vs After)](#1-tổng-quan-vấn-đề-trước-khi-sửa)
2. [Sơ đồ luồng xử lý tin nhắn (Message Flow Diagram)](#2-sơ-đồ-luồng-xử-lý-tin-nhắn)
3. [Chi tiết các lỗi đã khắc phục & Nâng cấp chất lượng](#3-chi-tiết-các-lỗi-đã-khắc-phục--nâng-cấp)
   - [A. Chặn triệt để QC/Spam qua ảnh, video & tin nhắn sửa](#a-chặn-triệt-để-qcspam-qua-ảnh-video--tin-nhắn-sửa)
   - [B. Bổ sung bộ quy tắc nhận diện link rác & kéo nhóm](#b-bổ-sung-bộ-quy-tắc-nhận-diện-link-rác--kéo-nhóm)
   - [C. Quản trị động theo từng nhóm (Dynamic Group Config)](#c-quản-trị-động-theo-từng-nhóm)
   - [D. Kiến trúc lưu trữ Hybrid Database (MongoDB + JSON Fallback)](#d-kiến-trúc-lưu-trữ-hybrid-database)
   - [E. Khắc phục lỗi font Unicode Console (Windows CP1252)](#e-khắc-phục-lỗi-font-unicode-console-windows-cp1252)
   - [F. Cập nhật thư viện trong requirements.txt](#f-cập-nhật-thư-viện-trong-requirementstxt)
4. [Bảng tổng hợp lệnh quản trị mới](#4-bảng-tổng-hợp-lệnh-quản-trị-mới)
5. [Định hướng giai đoạn tiếp theo: Phân hệ Ngân Hàng](#5-định-hướng-giai-đoạn-tiếp-theo-phân-hệ-ngân-hàng)

---

## 1. TỔNG QUAN VẤN ĐỀ TRƯỚC KHI SỬA

| Điểm kiểm tra | Trước khi sửa (Before) | Sau khi cải tiến (After) |
|---|---|---|
| **Lọc QC qua ảnh / media** | ❌ Bỏ lọt hoàn toàn nếu người bán gửi ảnh đính kèm bài viết (`caption`). | ✅ Trích xuất đồng thời `text` và `caption`, quét AI toàn diện mọi định dạng media. |
| **Lách luật bằng cách Sửa tin** | ❌ Không bắt tin nhắn bị chỉnh sửa (`edited_message`). | ✅ Bắt và kiểm duyệt ngay lập tức khi kẻ spam cố tình sửa lại nội dung tin nhắn. |
| **Phát hiện kéo nhóm Telegram** | ❌ Chưa có quy tắc lọc link mời (`t.me/+...`, `joinchat`). | ✅ Nhận diện lập tức các mẫu link kéo mem, contact spam (Zalo, SĐT, kéo tele). |
| **Cấu hình nhóm** | ❌ Hashtag và số bài rao bán bị fix cứng trong code. | ✅ Tùy chỉnh linh hoạt theo từng nhóm qua lệnh (`/marketguard`, `/sethashtag`, `/setmaxsales`). |
| **Thống kê kiểm duyệt** | ❌ Không có số liệu báo cáo hôm nay bot làm được gì. | ✅ Lệnh `/stats` / `/marketstats` báo cáo số tin đã quét, bài rao bán, nhắc nhở và lượt mute. |
| **Sự phụ thuộc MongoDB** | ❌ Sập bot (`AttributeError`) nếu MongoDB chưa bật. | ✅ Cơ chế **Hybrid DB**: Tự động chuyển đổi mượt mà giữa MongoDB và File JSON an toàn. |
| **Xung đột đọc/ghi File** | ❌ Dễ hỏng file JSON khi nhóm đông người gửi tin cùng lúc. | ✅ Khóa luồng `threading.Lock` + Cơ chế **Atomic Write** (ghi file tạm `.tmp` rồi đổi tên). |
| **Chạy trên Windows** | ❌ Lỗi sập `UnicodeEncodeError` vì emoji trong terminal. | ✅ Tự động cấu hình `sys.stdout` UTF-8 chống lỗi font trên Windows. |
| **Dependencies** | ❌ Thiếu `scikit-learn`, `joblib`, `numpy` trong `requirements.txt`. | ✅ Đã bổ sung đầy đủ, cài 1 lệnh `pip install -r requirements.txt` là chạy ngay. |

---

## 2. SƠ ĐỒ LUỒNG XỬ LÝ TIN NHẮN (MESSAGE FLOW DIAGRAM)

```mermaid
flowchart TD
    UpdateMsg[Tin nhắn mới hoặc Tin nhắn chỉnh sửa trong nhóm] --> CheckNull{Có text hoặc caption không?}
    CheckNull -- Không --> EndIgnore[Bỏ qua]
    CheckNull -- Có --> ExtractText[Trích xuất text = msg.text or msg.caption]

    ExtractText --> Pipeline4[Tầng 1: Tracker (Group -4)<br/>Ghi nhận hồ sơ & biến động user]
    Pipeline4 --> Pipeline3[Tầng 2: Ban Guard (Group -3)<br/>Kiểm tra Blacklist & Forward từ kênh lừa đảo]
    
    Pipeline3 -- Vi phạm Blacklist --> BanAction[Cảnh báo Admin / Mute / Xóa tin]
    Pipeline3 -- An toàn --> Pipeline2[Tầng 3: Badwords Filter (Group -2)<br/>Quét từ ngữ tục tĩu, độc hại]

    Pipeline2 -- Chứa từ cấm --> BadWordAction{Số lần vi phạm?}
    BadWordAction -- 1 đến 3 lần --> DeleteSilent[Xóa tin nhắn âm thầm + Ghi log]
    BadWordAction -- Lần 4 --> MuteAction[Mute 5 phút + Gửi cảnh báo + Nút Hứa gỡ Mute]
    
    Pipeline2 -- Không có từ cấm --> Pipeline1[Tầng 4: Market Guard AI (Group -1)<br/>Kiểm duyệt Quảng Cáo & Rao Vặt]

    Pipeline1 -- Kiểm tra Group --> MG_Enabled{Nhóm có bật MarketGuard?}
    MG_Enabled -- Tắt --> Pipeline0[Tầng 5: Lệnh thông thường (Group 0)]
    MG_Enabled -- Bật --> CheckAdmin{Người gửi là Admin?}
    CheckAdmin -- Đúng --> Pipeline0
    CheckAdmin -- Không --> RunAI[Chạy KiGuard AI Sales Detector]

    RunAI --> ResultAI{AI: Bán hàng hay Tin thường?}
    ResultAI -- Tin thường / Hỏi mua --> Pipeline0
    ResultAI -- Bán hàng / Dịch vụ --> CheckLimit{Đã đăng >= Max bài/ngày?}

    CheckLimit -- Vượt hạn mức --> OverLimitAction[Xóa bài + Mute 12 giờ + Thông báo nhóm]
    CheckLimit -- Chưa vượt hạn mức --> CheckTag{Có gắn Hashtag yêu cầu?}
    
    CheckTag -- Đã có Hashtag --> AcceptPost[Tăng biến đếm bài hôm nay + Cho phép gửi]
    CheckTag -- Thiếu Hashtag --> WarnTag[Gửi nhắc nhở thành viên + Tự xóa cảnh báo sau 60s]
```

---

## 3. CHI TIẾT CÁC LỖI ĐÃ KHẮC PHỤC & NÂNG CẤP

### A. Chặn triệt để QC/Spam qua ảnh, video & tin nhắn sửa
- **Vấn đề cũ:** Spammer thường đăng ảnh bảng giá/sản phẩm kèm chú thích trong `caption`, hoặc gửi tin bình thường rồi **chỉnh sửa (edit)** lại thành tin rao bán. Cả 2 trường hợp này trước đây đều bị bot bỏ lọt vì chỉ đọc `msg.text`.
- **Cách xử lý:**
  - Lấy nội dung: `text = (msg.text or msg.caption or "").strip()`.
  - Bộ lọc handler mở rộng:
    ```python
    group_filter = (filters.TEXT | filters.CAPTION) & filters.ChatType.GROUPS & ~filters.COMMAND
    ```
  - Trong Telegram Bot API, cấu hình `Update.ALL_TYPES` đảm bảo nhận cả `edited_message`, và `update.effective_message` nhận diện đồng bộ cho cả tin gốc và tin sửa.

---

### B. Bổ sung bộ quy tắc nhận diện link rác & kéo nhóm
- **Vấn đề cũ:** Kẻ spam kéo thành viên sang nhóm đối thủ bằng link `t.me/+...` hoặc `t.me/joinchat/...`, hoặc kêu gọi inbox Zalo, mua bán clone, via, tài xỉu.
- **Cách xử lý tại `LLM Ai/sales_detector.py`:**
  - Bổ sung regex nhận diện link mời nhóm Telegram:
    ```python
    re.compile(r'(?:https?://)?(?:t\.me|telegram\.me)/(?:\+[a-zA-Z0-9_-]+|joinchat/[a-zA-Z0-9_-]+)', re.IGNORECASE)
    ```
  - Bổ sung các từ khóa kéo tương tác, bán tài khoản, cờ bạc:
    ```python
    re.compile(r'\b(?:ib\s+tele|inbox\s+tele|kéo\s+sub|bán\s+sub|tăng\s+view|bán\s+clone|bán\s+via|bán\s+group|thu\s+mua\s+acc|bán\s+xu|bán\s+sao|nạp\s+sao|tele\s+pre|telegram\s+premium|sỉ\s+lẻ|sẵn\s+kho|chốt\s+đơn|bảng\s+giá\s+chi\s+tiết|liên\s+hệ\s+zalo|kèo\s+thơm|cơm\s+gạo|tài\s+xỉu|kéo\s+về\s+bờ)\b', re.IGNORECASE)
    ```

---

### C. Quản trị động theo từng nhóm
- Trước đây cấu hình hashtag `#NghienPlusMarket` và hạn mức `6 bài/ngày` bị fix cứng vào code, khiến bot không thể dùng chung cho nhiều nhóm khác nhau.
- **Giải pháp:** Xây dựng hệ thống cấu hình động lưu tại `data/market_guard_settings.json`:
  - Mỗi nhóm có cấu hình độc lập: Trạng thái (Bật/Tắt), Hashtag bắt buộc, Giới hạn bài đăng mỗi ngày.
  - Cung cấp lệnh trực quan cho Admin: `/marketguard on|off`, `/sethashtag <#tag>`, `/setmaxsales <số>`.
  - Thêm báo cáo thống kê qua lệnh `/stats` hoặc `/marketstats`:
    ```text
    📊 Báo Cáo Kiểm Duyệt Hôm Nay (2026-10-15)
    ━━━━━━━━━━━━━━━━━━━━
    🔍 Tổng tin nhắn đã quét: 1,420
    🛒 Phát hiện rao bán/QC: 35
    ⚠️ Nhắc nhở thiếu hashtag: 12
    🚫 Mute thành viên quá hạn: 3
    ```

---

### D. Kiến trúc lưu trữ Hybrid Database
- **Vấn đề cũ:** Các module như `payment_verifier.py`, `group_member_tracker.py`, `banlist_service.py`, `user_tracker.py` gọi trực tiếp vào `db.collection` mà không kiểm tra xem MongoDB có đang chạy không. Khi chạy trên môi trường không có MongoDB, bot sẽ crash ngay lập tức.
- **Giải pháp:**
  1. Kiểm tra trạng thái `if db is not None`. Nếu MongoDB sẵn sàng, thực hiện truy vấn và cập nhật trên database.
  2. Nếu MongoDB offline hoặc xảy ra lỗi kết nối, hệ thống tự động đọc/ghi vào các file JSON tương ứng trong thư mục `data/` (`members.json`, `banlist.json`, `known_users.json`, `claimed_payments.json`).
  3. Áp dụng cơ chế **Atomic Write**: Khi ghi file, dữ liệu được ghi vào file `.tmp` trước rồi mới thay thế file chính bằng `os.replace`. Điều này ngăn ngừa hoàn toàn tình trạng file bị rỗng hoặc lỗi cú pháp JSON khi mất điện hoặc có nhiều người gửi tin cùng một tích tắc.

---

### E. Khắc phục lỗi font Unicode Console (Windows CP1252)
- Môi trường Windows thường đặt mặc định bảng mã console là `cp1252` thay vì `utf-8`. Khi bot in các biểu tượng emoji (`🤖`, `✅`, `❌`, `🔌`) ra terminal, chương trình sẽ báo lỗi `UnicodeEncodeError` và dừng chạy.
- **Giải pháp:** Tự động cấu hình lại bộ đệm stdout/stderr ngay khi khởi động tại `main.py`, `loader.py` và `mongo.py`:
  ```python
  import sys
  if hasattr(sys.stdout, "reconfigure"):
      sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  if hasattr(sys.stderr, "reconfigure"):
      sys.stderr.reconfigure(encoding="utf-8", errors="replace")
  ```

---

### F. Cập nhật thư viện trong requirements.txt
File `requirements.txt` đã được đồng bộ chuẩn với các thư viện Machine Learning mà mã nguồn đang sử dụng:
```text
python-telegram-bot[job-queue]>=21.0
python-dotenv>=1.0.0
telethon>=1.36.0
pandas>=2.2.0
requests>=2.31.0
pymongo>=4.6.0
scikit-learn>=1.4.0
joblib>=1.3.0
numpy>=1.26.0
```

---

## 4. BẢNG TỔNG HỢP LỆNH QUẢN TRỊ MỚI

| Lệnh | Đối tượng | Mô tả chức năng |
|---|---|---|
| `/marketguard [on\|off]` | Admin Nhóm | Bật, tắt hoặc xem trạng thái kiểm duyệt bán hàng/quảng cáo của nhóm. |
| `/sethashtag <#tag>` | Admin Nhóm | Thiết lập hashtag bắt buộc khi đăng bài bán hàng (ví dụ: `/sethashtag #ChoCongNghe`). |
| `/setmaxsales <số>` | Admin Nhóm | Cài đặt giới hạn số lượng bài đăng bán tối đa mỗi ngày của thành viên. |
| `/resetsales [id\|reply]` | Admin Nhóm | Xóa lượt đếm bài đăng bán trong ngày của 1 thành viên vi phạm. |
| `/stats` hoặc `/marketstats` | Admin Nhóm | Hiển thị bảng tổng hợp số tin nhắn quét, bài QC phát hiện và lượt phạt trong ngày. |
| `/checksales [text\|reply]` | Mọi người | Kiểm tra xem tin nhắn (text hoặc ảnh có caption) có bị AI đánh giá là bài bán hàng không. |
| `/datastats` | Mọi người | Xem số lượng mẫu dữ liệu đã tự động thu thập để phục vụ việc huấn luyện model AI. |
| `/addbadword <từ>` | Admin Nhóm | Thêm từ cấm vào bộ lọc, cập nhật Regex ngay lập tức không cần restart bot. |
| `/delbadword <từ>` | Admin Nhóm | Gỡ bỏ từ khỏi danh sách từ cấm. |
| `/badwords` | Admin Nhóm | Xem số lượng từ cấm đang được kích hoạt trong hệ thống. |
| `/resetwarn [id\|reply]` | Admin Nhóm | Reset số lần vi phạm chửi tục của thành viên về 0. |

---

## 5. ĐỊNH HƯỚNG GIAI ĐOẠN TIẾP THEO: PHÂN HỆ NGÂN HÀNG

Theo kế hoạch ưu tiên độ ổn định và chất lượng kiểm duyệt trước, phân hệ ngân hàng ([`autobank/bank/mbbank.py`](file:///d:/code/khai/bottele%20chan%20qc/autobank/bank/mbbank.py)) sẽ được hoàn thiện ở giai đoạn sau:
1. **Lựa chọn giải pháp cổng thanh toán:**
   - **Lựa chọn 1 (Khuyên dùng):** Tận dụng Server Webhook Sepay / Casso đã có sẵn trong [`payment_verifier.py`](file:///d:/code/khai/bottele%20chan%20qc/bot/services/payment_verifier.py) (chạy ngầm cổng 8080). Giải pháp này không cần cào web, không sợ bị ngân hàng khóa tài khoản và độ trễ dưới 2 giây.
   - **Lựa chọn 2:** Tích hợp bộ Scraper MBBank với cơ chế quản lý Token / Session và giải Captcha tự động.
2. **Kích hoạt tự động quyền lợi khi Donate:**
   - Cấp huy hiệu VIP / Miễn trừ kiểm duyệt số bài đăng cho các thành viên đã donate ủng hộ cộng đồng.
