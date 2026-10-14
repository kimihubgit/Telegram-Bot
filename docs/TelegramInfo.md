
## 🔍 Inline Bot (Inline Mode)

### "via @Tên_Bot" là gì?

Đây là tính năng **Inline Mode** của Telegram — cho phép người dùng gọi Bot và sử dụng chức năng của nó **trực tiếp ở bất kỳ cuộc trò chuyện nào** (nhóm chat, kênh, hoặc chat riêng) mà **không cần add Bot vào nhóm**.

### 💡 Cơ chế hoạt động

Bình thường, để dùng Bot trong nhóm, bạn phải mời nó vào làm thành viên hoặc Admin. Nhưng với Inline Bot:

1. Bạn gõ: `@Tên_Bot` + Khoảng trắng + Từ khóa (ví dụ: `@SangMata_BOT groupdonate`)
2. Telegram sẽ tự động hiện lên **menu gợi ý kết quả** ngay phía trên bàn phím
3. Khi bạn chọn một kết quả → Bot **thay mặt bạn** gửi tin nhắn vào nhóm
4. Tin nhắn sẽ có dòng chữ nhỏ mờ `via @Tên_Bot` ở trên cùng

### 🛠 Ví dụ Inline Bot phổ biến

| Cách gõ | Chức năng |
|---|---|
| `@gif hello` | Tìm nhanh ảnh GIF chữ "hello" để gửi mà không cần tải về |
| `@vid sntv` | Tìm kiếm và gửi nhanh video YouTube ngay tại khung chat |
| `@pic mèo` | Tìm kiếm hình ảnh nhanh qua Bing |

### 💻 Cách bật Inline Mode cho Bot của bạn

Nếu bạn muốn Bot của mình cũng hỗ trợ Inline Mode (ví dụ: gõ `@BotCuaBan check_violation` để hiện danh sách vi phạm):

1. Mở Telegram, chat với [@BotFather](https://t.me/BotFather)
2. Gửi lệnh `/mybots` → Chọn con Bot của bạn
3. Chọn **Bot Settings** → Tìm mục **Inline Mode**
4. Bấm nút **Turn on** để kích hoạt

Trong code Python (`python-telegram-bot`), cần thêm `InlineQueryHandler` để xử lý từ khóa:

```python
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes, InlineQueryHandler

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    results = [
        InlineQueryResultArticle(
            id="1",
            title="Kết quả tìm kiếm",
            input_message_content=InputTextMessageContent(f"Bạn đã tìm: {query}")
        )
    ]
    await update.inline_query.answer(results)

def get_handlers():
    return [
        InlineQueryHandler(inline_query),
    ]
```

---

## ⚠️ Known Issues & Notes

### `Button_user_invalid` — Lỗi khi tạo nút Profile bằng ID

Telegram **không cho** tạo deep link tới user bằng `tg://user?id=` hoặc `tg://openmessage?user_id=` trong Inline Button nếu user đó không "accessible" từ phía bot.

**Nguyên nhân thường gặp:**

| Trường hợp | Giải thích |
|---|---|
| User chưa từng chat với bot | Bot chưa biết user này |
| Bot không cùng group với user | Không resolve được peer |
| User privacy hạn chế | Cài đặt quyền riêng tư chặn |
| ID không resolve được | Telegram không coi là "accessible peer" |
| Chỉ có raw ID | Không đủ thông tin để tạo link |

**Workaround:** Nếu user có username → dùng `https://t.me/{username}`. Nếu chỉ có ID → không thể tạo nút bấm trực tiếp, chỉ hiển thị ID dạng text.

---