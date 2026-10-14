# Hệ Thống Backend Truy Vấn Scam & Tên Miền Độc Hại (KiGuard Anti-Scam)

Hệ thống backend này được phát triển bằng **FastAPI (Python)**, được thiết kế để truy vấn nhanh độ an toàn của tên miền (URL), tìm kiếm thông tin chéo về các đối tượng lừa đảo (số điện thoại, tài khoản ngân hàng, ví điện tử, tài khoản mạng xã hội...) và hỗ trợ nhận báo cáo độc hại từ người dùng/mở rộng Chrome Extension.

---

## ⚡ Các Tính Năng Nổi Bật

1. **Kiểm Tra URL/Tên Miền Độc Hại**:
   - Trích xuất tự động và làm sạch tên miền từ bất kỳ URL thô nào.
   - Kiểm tra xem tên miền hoặc tên miền phụ có nằm trong danh sách đen hay không.
2. **Đồng Bộ Hoá Tên Miền Cho Chrome Extension**:
   - Cung cấp API tương thích 100% với extension KiGuard để tải danh sách đen tên miền chặn cục bộ trên trình duyệt.
3. **Tìm Kiếm Hỗ Trợ Chéo Đa Nền Tảng (Cross-Reference Search)**:
   - Tìm kiếm chéo từ một từ khóa đầu vào bất kỳ: Số tài khoản ngân hàng, tên chủ thẻ, số điện thoại, email, Telegram Username, Telegram ID, Facebook URL, Facebook ID, Ví Crypto (BTC/USDT), hoặc mã định danh hồ sơ (`SCM-xxxxx`).
4. **Cơ Chế Lưu Trữ Hybrid (Không Lo Mất Kết Nối)**:
   - **Chế độ chính thức**: Kết nối trực tiếp cơ sở dữ liệu MongoDB được định nghĩa trong tệp cấu hình `.env` của hệ thống.
   - **Chế độ Fallback (Offline)**: Nếu MongoDB không hoạt động, hệ thống tự động chuyển sang đọc/ghi trực tiếp vào các tệp JSON trong thư mục `data/scammer/` (như `scammer.json`, `scam-demo.json`, `websites.json`), đảm bảo hệ thống luôn sẵn sàng chạy mà không cần setup phức tạp.

---

## 📁 Cấu Trúc Thư Mục Hệ Thống (Clear Structure)

Hệ thống được thiết kế theo mô hình mô-đun hóa rõ ràng:

```text
website/backend/
├── app/
│   ├── __init__.py
│   ├── config.py           # Quản lý cấu hình, nạp biến môi trường từ .env
│   ├── database.py         # Bộ chuyển đổi MongoDB & Fallback JSON (Hybrid DB Engine)
│   ├── main.py             # Khởi tạo FastAPI app, cấu hình CORS, đăng ký routers
│   ├── models/             # Định nghĩa Pydantic Models (Kiểu dữ liệu và xác thực)
│   │   ├── __init__.py
│   │   ├── scammer.py      # Schema đối tượng lừa đảo, thanh toán, sự cố
│   │   └── website.py      # Schema trang web độc hại
│   ├── routers/            # Các API endpoints
│   │   ├── __init__.py
│   │   ├── scammers.py     # API tra cứu & báo cáo đối tượng lừa đảo
│   │   └── websites.py     # API đồng bộ & kiểm tra tên miền độc hại
│   └── utils/
│       ├── __init__.py
│       └── helpers.py      # Hàm tiện ích (trích xuất tên miền, chuẩn hóa SĐT)
├── run.py                  # Script khởi chạy nhanh máy chủ API
└── requirements.txt        # Danh sách thư viện phụ thuộc
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy

### 1. Cài đặt các thư viện phụ thuộc
Mở terminal tại thư mục `website/backend` và chạy lệnh sau:
```bash
pip install -r requirements.txt
```

### 2. Cấu hình biến môi trường
Hệ thống tự động quét tệp tin `.env` ở thư mục gốc của bot Telegram. Bạn không cần sao chép lại, chỉ cần đảm bảo tệp `.env` có cấu hình MongoDB nếu muốn dùng MongoDB:
```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=telegram
```
*Lưu ý: Nếu không có MongoDB hoặc không thể kết nối, backend vẫn chạy bình thường ở chế độ Offline Fallback sử dụng các tệp JSON.*

### 3. Khởi chạy Backend Server
Chạy script `run.py` để khởi động server:
```bash
python run.py
```
Mặc định, server sẽ chạy tại địa chỉ: **`http://localhost:8000`**

---

## 📖 Tài Liệu Hướng Dẫn API Endpoints (Swagger UI)

Khi server đang chạy, bạn truy cập địa chỉ **`http://localhost:8000/docs`** để xem tài liệu tương tác tự động và kiểm thử trực tiếp các API.

### 🌐 Nhóm API Tên Miền Độc Hại (`/api/scam-websites`)

| Phương thức | Endpoint | Mô tả | Định dạng dữ liệu |
|---|---|---|---|
| **GET** | `/api/scam-websites` | Lấy danh sách thô tất cả tên miền lừa đảo (Dành cho extension tải về chặn offline) | Trả về `{"domains": ["tên-miền-1.com", "tên-miền-2.vn", ...]}` |
| **GET** | `/api/scam-websites/list` | Lấy toàn bộ thông tin chi tiết của danh sách website lừa đảo đã duyệt | Trả về danh sách đối tượng website chi tiết |
| **GET** | `/api/scam-websites/check` | Truy vấn kiểm tra một URL/Tên miền thô | Params: `?url=https://ludao.vn/nap-the` <br> Trả về kết quả `is_scam: true/false` kèm lý do chi tiết |
| **POST** | `/api/scam-websites` | Báo cáo / Thêm mới một website lừa đảo | JSON Body chứa thông tin `domain`, `category`, `description`, `threat_level` |

### 👤 Nhóm API Đối Tượng Lừa Đảo (`/api/scammers`)

| Phương thức | Endpoint | Mô tả | Định dạng truy vấn / Payload |
|---|---|---|---|
| **GET** | `/api/scammers/search` | Tra cứu chéo thông tin đối tượng scammer | Params: `?q=từ-khóa-cần-tìm` (Ví dụ: Số tài khoản, SĐT, Username Telegram...) |
| **GET** | `/api/scammers/{scammer_id}`| Truy xuất toàn bộ thông tin chi tiết của scammer bằng ID | Path param: ID của scammer (Ví dụ: `SCM-00001`) |
| **POST** | `/api/scammers` | Báo cáo thêm mới một đối tượng lừa đảo | JSON Body chứa đầy đủ cấu trúc thông tin lừa đảo |

---

## 📋 Định dạng dữ liệu mẫu để Báo Cáo Scammer (`POST /api/scammers`)

Gửi một yêu cầu POST tới `/api/scammers` với dữ liệu JSON có cấu trúc rõ ràng như dưới đây:

```json
{
    "contact": {
        "telegram": [
            {
                "username": "kjhdkhsdf",
                "id": 8119900362
            }
        ],
        "facebook": [
            {
                "id": 109876543210,
                "link": "https://www.facebook.com/nguyenvanA",
                "name": "Nguyễn Văn A"
            }
        ],
        "phone": [
            {
                "full_number": "+84901234567",
                "carrier": "Viettel",
                "tag": ["Lừa Đảo Cọc Mua Hàng"]
            }
        ],
        "email": [
            {
                "address": "nguyenvana.crypto@gmail.com",
                "tag": ["Đăng ký Netflix lừa đảo"]
            }
        ],
        "other": []
    },
    "payments": {
        "bank": [
            {
                "bank_name": "Vietcombank",
                "short_name": "VCB",
                "account_number": "1012345678",
                "account_holder": "NGUYEN VAN A",
                "bin_code": "970436"
            }
        ],
        "wallet": [
            {
                "platform": "Momo",
                "phone_number": "0901234567",
                "owner_name": "NGUYEN VAN A"
            }
        ],
        "crypto": [
            {
                "network": "TRC20",
                "address": "Txxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "coin": "USDT"
            }
        ],
        "binance": [],
        "paypal": [],
        "other": []
    },
    "incidents": [
        {
            "date": "2026-05-13",
            "status": "active",
            "type": "Lừa đảo bán tài khoản game",
            "losses": [
                {
                    "amount": 200000,
                    "currency": "VND"
                }
            ],
            "description": "Nạn nhân mua tài khoản game, chuyển tiền cọc xong bị chặn tài khoản chat.",
            "raw": {
                "detail": "Bị tài khoản @kjhdkhsdf lừa bán acc game, sau khi cọc 200k vào Vietcombank thì bị block.",
                "images": ["https://cdn.example.com/bill_200k.jpg"],
                "posts": []
            }
        }
    ]
}
```
Hệ thống sẽ tự động gán nhãn ID lừa đảo (ví dụ: `SCM-00002`) và ghi nhận thời gian báo cáo vào metadata của bản ghi.
