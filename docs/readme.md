# 🤖 Telegram Bot — Kimidev Community

Hệ thống bot Telegram đa chức năng: giám sát nhóm, OSINT, kiểm tra tài khoản, quản lý ban list, lọc từ tục, và nhiều tiện ích khác.

> Được phát triển bởi **Cộng Đồng Kimidev**

---

## ✨ Tính Năng

### 👤 Kiểm Tra Người Dùng
| Lệnh | Mô tả |
|---|---|
| `/check` | Xem thông tin chi tiết (bio, last seen, DC, premium, ...) — hỗ trợ ID, @username, reply |
| `/checkinfo` | Tra cứu sâu qua Rose Bot + Star Gift — phân hạng tài khoản theo chỉ số X/Y/Z |
| `/myid` | Hiển thị User ID và Chat ID |

### 🛡️ Quản Lý Nhóm
| Lệnh / Tính năng | Mô tả |
|---|---|
| **Group Monitor** | Tự động thông báo admin khi có người vào/rời nhóm |
| **Auto-ban** | Tự rời nhóm → blacklist + ban tự động |
| **Ban Guard** | Chặn user trong danh sách cấm ngay khi vào nhóm (ban hoặc mute) |
| `/banlist` | Quản lý danh sách cấm: `add`, `remove`, `check`, `list` *(chỉ admin)* |
| `/resetwarn` | Reset số lần vi phạm chửi tục của user *(chỉ admin)* |

### 🔇 Lọc Từ Tục (Bad Words)
- Tự động xóa tin nhắn chứa từ cấm
- Vi phạm 1-2 lần: xóa âm thầm
- Vi phạm lần 3: mute 5 phút + cảnh báo trong nhóm + nút "Gỡ Mute"
- Sau khi nhắc nhở: reset về 0

### 📢 Broadcast
| Lệnh | Mô tả |
|---|---|
| `/notification` | Gửi thông báo (text, ảnh, video, ...) đến tất cả user đã tương tác với bot *(chỉ admin)* |

### 🔧 Tiện Ích
| Lệnh | Mô tả |
|---|---|
| `/bin <6 số>` | Tra cứu thông tin BIN thẻ ngân hàng (Brand, Type, Issuer, Country) |
| `/token <bot_token>` | Kiểm tra bot token Telegram còn LIVE hay DIE |
| `/tv <8 ký tự>` | Nhập code Netflix cho TV bằng cookie có sẵn |
| `/scribd <url>` | Lấy link tải tài liệu Scribd + link xem không quảng cáo |

---

## 🏗️ Kiến Trúc

Hệ thống modular — mỗi command là một module riêng biệt, được auto-load khi khởi động.

### Dual API
- **Bot API** (`python-telegram-bot`) — Xử lý lệnh, gửi tin nhắn, quản lý nhóm
- **MTProto API** (`Telethon`) — Truy cập thông tin sâu (bio, last seen, DC, resolve username, Star Gift)

### Cấu Trúc Thư Mục

```
Telegram Bot/
├── main.py                          ← Entry point
├── .env.example                     ← Mẫu cấu hình
├── requirements.txt                 ← Dependencies
│
├── bot/
│   ├── config.py                    ← Load cấu hình từ .env
│   ├── connection.py                ← Kết nối Telethon (start, stop, get_client)
│   │
│   ├── commands/                    ← Các lệnh bot (auto-load)
│   │   ├── start.py                 ← /start, /help, /myid
│   │   ├── check.py                 ← /check (thông tin user chi tiết)
│   │   ├── checkinfo.py             ← /checkinfo (OSINT qua Rose + Gift)
│   │   ├── bin.py                   ← /bin (tra cứu BIN thẻ)
│   │   ├── token.py                 ← /token (check bot token)
│   │   ├── tv.py                    ← /tv (Netflix TV code)
│   │   ├── scribd.py                ← /scribd (download tài liệu)
│   │   ├── banlist.py               ← /banlist (quản lý danh sách cấm)
│   │   ├── badwords.py              ← Lọc từ tục tự động
│   │   ├── ban_guard.py             ← Chặn user bị cấm khi vào nhóm
│   │   ├── group_monitor.py         ← Giám sát vào/rời nhóm
│   │   ├── notification.py          ← /notification (broadcast)
│   │   └── tracker.py               ← Theo dõi user tương tác
│   │
│   ├── handlers/
│   │   └── loader.py                ← Auto-load tất cả command modules
│   │
│   ├── services/                    ← Logic nghiệp vụ
│   │   ├── checkinfo/               ← Service cho /checkinfo
│   │   │   ├── gifts.py             ← Lấy Star Gift qua Telethon
│   │   │   └── rose_query.py        ← Query Rose Bot qua Telethon
│   │   ├── telethon_user.py         ← Resolve user + lấy thông tin sâu
│   │   ├── user_service.py          ← Xử lý thông tin user (Bot API + Telethon)
│   │   ├── banlist_service.py       ← CRUD danh sách cấm
│   │   ├── group_member_tracker.py  ← Lưu lịch sử thành viên nhóm
│   │   └── user_tracker.py          ← Theo dõi user đã tương tác với bot
│   │
│   ├── sessions/                    ← Telethon session files
│   │
│   └── utils/                       ← Tiện ích dùng chung
│       ├── format.py                ← Escape MarkdownV2, tạo link
│       ├── logger.py                ← Ghi log command theo ngày
│       └── rate_limiter.py          ← Giới hạn tần suất lệnh
│
├── data/                            ← Dữ liệu runtime
│   ├── bad_words.json               ← Danh sách từ cấm
│   ├── banlist.json                 ← Danh sách user bị ban
│   ├── bin-list-data.csv            ← Database BIN thẻ ngân hàng
│   ├── known_users.json             ← User đã tương tác với bot
│   ├── members.json                 ← Lịch sử thành viên nhóm
│   ├── user_violations.json         ← Số lần vi phạm từ tục
│   ├── cookies/                     ← Kho cookie Netflix
│   └── cookies_used/                ← Cookie đã sử dụng
│
└── log/                             ← Log hàng ngày
    └── 2026-05-17.log
```

---

## 🚀 Cài Đặt

### Yêu Cầu
- Python 3.12+
- Bot Token từ [@BotFather](https://t.me/BotFather)
- *(Tùy chọn)* Telethon API credentials từ [my.telegram.org](https://my.telegram.org/apps)

## 📦 Dependencies

| Package | Phiên bản | Mục đích |
|---|---|---|
| `python-telegram-bot` | 21.10 | Bot API framework |
| `telethon` | 1.39.0 | MTProto API (OSINT sâu) |
| `python-dotenv` | 1.1.0 | Load biến môi trường từ .env |
| `pandas` | 2.2.3 | Đọc database BIN (CSV) |
| `requests` | ≥2.31.0 | HTTP requests (Netflix, Scribd) |

---

### Các Bước

```bash
# 1. Clone repo
git clone <repo-url>
cd "Telegram Bot"

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Tạo file .env từ mẫu
cp .env.example .env

# 4. Chỉnh sửa .env với thông tin của bạn
# (xem phần Cấu Hình bên dưới)

# 5. Chạy bot
python main.py
```

> **Lần đầu chạy với Telethon:** Bot sẽ hỏi số điện thoại + mã OTP để đăng nhập tài khoản cá nhân. Session được lưu tại `bot/sessions/` — chỉ cần đăng nhập 1 lần.

---

## ⚙️ Cấu Hình (.env)

```env
# [BẮT BUỘC] Bot Token từ @BotFather
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11

# [BẮT BUỘC] Chat ID của admin — nhận thông báo vào/rời nhóm
ADMIN_CHAT_ID=123456789

# [TÙY CHỌN] Telethon — mở khóa tính năng OSINT sâu
TELETHON_API_ID=12345678
TELETHON_API_HASH=abcdef1234567890abcdef1234567890

# [TÙY CHỌN] Group riêng chứa Rose Bot — dùng cho /checkinfo
ROSE_QUERY_GROUP_ID=-100xxxxxxxxxx

# [TÙY CHỌN] Admin IDs được dùng /notification và /banlist
NOTIFICATION_ADMIN_IDS=123456789,987654321
```

### Cách Lấy Thông Tin

| Giá trị | Cách lấy |
|---|---|
| `BOT_TOKEN` | Chat với [@BotFather](https://t.me/BotFather) → `/newbot` |
| `ADMIN_CHAT_ID` | Gửi `/myid` cho bot sau khi chạy |
| `TELETHON_API_ID/HASH` | Đăng nhập [my.telegram.org](https://my.telegram.org/apps) → Tạo app |
| `ROSE_QUERY_GROUP_ID` | Tạo group mới → thêm [@MissRose_bot](https://t.me/MissRose_bot) → gửi `/myid` |

---

## 🔌 Thêm Lệnh Mới

Hệ thống auto-load — chỉ cần tạo file mới trong `bot/commands/`:

```python
# bot/commands/hello.py
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

async def hello_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Xin chào! 👋")

def get_handlers():
    return [
        CommandHandler("hello", hello_command),
    ]
```

Khởi động lại bot → lệnh `/hello` tự động hoạt động.

---

Khởi Động: 
terminal 1: Chạy bot
Terminal 2: Get Lịch Sử Giao Dịch Các Cổng
Termianl 3: Chạy Frontend, Quản lí bot - admin
Terminal 4: Chạy Database MongoDB

## 🚀 Cài Đặt Nâng Cao (Docker)

### Yêu Cầu
- Docker
- Docker Compose

### Cài Đặt

1. **Clone repo**
```bash
git clone <repo-url>
cd "Telegram Bot"
```

2. **Tạo file cấu hình**
```bash
# Tạo .env từ mẫu
cp .env.example .env

# Chỉnh sửa .env với thông tin của bạn
nano .env
```

3. **Chạy với Docker Compose**
```bash
# Build và start tất cả service
docker-compose up -d --build

# Xem log
docker-compose logs -f

# Stop và xóa container (giữ data)
docker-compose down

# Stop, xóa container và volume (xóa hết data)
docker-compose down -v
```

### Cấu Hình Docker Compose

File `docker-compose.yml` cấu hình:

**Services:**
- `mongodb`: Database MongoDB (Port 27017)
- `app`: Bot Telegram (Port 8080)
- `frontend`: Giao diện Admin (Port 3000)

**Port Mapping:**
| Host | Container | Service |
|---|---|---|
| `27017` | `27017` | MongoDB |
| `8080` | `8080` | App Bot |
| `3000` | `3000` | Frontend Admin |

**Volume Mapping:**
- Dữ liệu bot: `./data:/usr/src/app/data`
- Session Telethon: `./bot/sessions:/usr/src/app/bot/sessions`

### Cấu Hình .env cho Docker

```env
# [Docker] Hostnames - Dùng tên service trong Compose
MONGO_HOST=mongodb
FRONTEND_HOST=frontend

# [Docker] Ports - Map internal ports to host
BOT_PORT_MAPPING=8080
FRONTEND_PORT_MAPPING=3000

# [BẮT BUỘC] Bot Token từ @BotFather
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11

# [BẮT BUỘC] Chat ID của admin
ADMIN_CHAT_ID=123456789

# [TÙY CHỌN] Telethon
TELETHON_API_ID=12345678
TELETHON_API_HASH=abcdef1234567890abcdef1234567890

# [TÙY CHỌN] Rose Bot Group
ROSE_QUERY_GROUP_ID=-100xxxxxxxxxx

# [TÙY CHỌN] Admin IDs
NOTIFICATION_ADMIN_IDS=123456789,987654321
```

### Cấu Hình Nâng Cao

**Multi-bot support** (nếu cần nhiều bot):
```bash
# Số lượng bot
BOT_COUNT=3

# Cổng cho từng bot
BOT_PORTS=8080,8081,8082
```

**Database configuration**:
```bash
# Kết nối MongoDB local (ngoài Docker)
MONGO_HOST=localhost

# Kết nối MongoDB trong Docker (mặc định)
MONGO_HOST=mongodb
```

## 📝 License

Private project — Kimidev Community.
