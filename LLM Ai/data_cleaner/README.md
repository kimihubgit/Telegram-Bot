# 🧪 PHÒNG THÍ NGHIỆM LÀM SẠCH DỮ LIỆU (DATA CLEANER LAB)

Thư mục này được thiết kế để bạn **kiểm tra, so sánh trực quan và xuất các phiên bản làm sạch dữ liệu (Data Cleaning Pipelines)** trước khi đưa vào huấn luyện mô hình AI (PhoBERT, TF-IDF + Logistic Regression, SVM,...).

---

## 📂 1. Cấu Trúc Thư Mục

```
LLM Ai/data_cleaner/
│
├── README.md               # File hướng dẫn này
├── cleaners.py             # Chứa 4 pipeline làm sạch văn bản (V1, V2, V3, V4)
├── preview_clean.py        # Tool kiểm tra mẫu trực quan (xuất console, CSV & Web HTML)
├── run_cleaners.py         # Tool xuất toàn bộ các bộ dataset đã làm sạch
│
└── outputs/                # Thư mục chứa kết quả xuất ra (được tạo tự động)
    ├── preview_comparison.html   # Giao diện web xem đối chiếu trước & sau clean
    ├── preview_comparison.csv    # Bảng CSV so sánh mở bằng Excel
    ├── dataset_v1_light.csv      # Bộ data sạch V1
    ├── dataset_v2_standard.csv   # Bộ data sạch V2
    ├── dataset_v3_deep.csv       # Bộ data sạch V3
    ├── dataset_v4_sales.csv      # Bộ data sạch V4
    └── cleaning_summary.json     # Thống kê tổng hợp số mẫu, từ vựng, độ dài
```

---

## 🌟 2. Ý Nghĩa 4 Phiên Bản Làm Sạch (V1 - V4)

| Phiên bản | Tên | Đặc điểm xử lý | Khuyên dùng khi train |
| :--- | :--- | :--- | :--- |
| **V1** | **Light Clean** | • Chuẩn hóa font chữ Unicode NFKC<br>• Gỡ ký tự tàng hình/điều khiển<br>• **Giữ nguyên**: Chữ hoa/thường, Emoji, URL, dấu câu đầy đủ | **PhoBERT**, RoBERTa, LLM học ngữ cảnh tự nhiên và cảm xúc |
| **V2** | **Standard Clean** | • Chuẩn hóa NFKC & gỡ ký tự vô hình<br>• Chuyển về chữ thường (lowercase)<br>• Khử Emoji, gỡ đường kẻ trang trí (━━━, ───)<br>• Chuẩn hóa tiền tệ: `$` -> `usd`, `₫` -> `đ`<br>• Gỡ URLs web & link Telegram | **TF-IDF + Classifier** hoặc PhoBERT tiêu chuẩn (rất ổn định) |
| **V3** | **Deep Clean** | • Kế thừa V2<br>• Gỡ @username Telegram<br>• Gỡ ID số Telegram trong ngoặc `(5442136592)`<br>• Tự động lọc các câu cảnh báo scam boilerplate từ bot<br>• Xóa sạch dấu câu lạ, chỉ giữ chữ & số thuần khiết | **Naive Bayes**, Word2Vec, TF-IDF cần từ điển thuần túy |
| **V4** | **Sales Specialized** | • Kế thừa V2<br>• **Quy đổi giá & thời hạn**: `340k` -> `340 nghìn`, `1th` -> `1 tháng`, `1m` -> `1 triệu`, `24h` -> `24 giờ`<br>• **Dịch từ lóng/viết tắt bán hàng**: `bhf` -> `bảo hành full`, `bh` -> `bảo hành`, `ib` -> `inbox`, `sll` -> `số lượng lớn`, `acc` -> `tài khoản`, `vpo` -> `văn phòng`, `slot` -> `suất slot` | **Mô hình chuyên bắt tin bán hàng lách chữ**, tăng độ nhạy (Recall) |

---

## 🚀 3. Hướng Dẫn Sử Dụng

### Bước 1: Xem trước & Đối chiếu dữ liệu (Preview)
Chạy lệnh sau trong PowerShell hoặc Terminal:
```bash
python preview_clean.py
```
- Lệnh này sẽ lấy ngẫu nhiên các mẫu (cả Bán hàng và Tin thường), in đối chiếu ra màn hình console.
- Tự động tạo file giao diện trực quan: `outputs/preview_comparison.html`. Bạn chỉ cần **nhấp đúp chuột để mở bằng trình duyệt (Chrome/Edge)**:
  - Có thanh tìm kiếm từ khóa.
  - Có nút lọc xem riêng tin **Bán hàng (1)** hoặc **Tin thường (0)**.
  - Xem trước và so sánh song song 4 phiên bản.
- Tự động tạo file `outputs/preview_comparison.csv` để bạn mở bằng **Excel** hoặc **Google Sheets**.

---

### Bước 2: Xuất các bộ Dataset sạch để huấn luyện
Chạy lệnh sau để xuất toàn bộ cả 4 phiên bản:
```bash
python run_cleaners.py --version all
```

Hoặc xuất riêng từng phiên bản mong muốn:
```bash
python run_cleaners.py --version v1   # Xuất outputs/dataset_v1_light.csv
python run_cleaners.py --version v2   # Xuất outputs/dataset_v2_standard.csv
python run_cleaners.py --version v3   # Xuất outputs/dataset_v3_deep.csv
python run_cleaners.py --version v4   # Xuất outputs/dataset_v4_sales.csv
```

---

### Bước 3: Dùng bộ dataset để train mô hình
Khi muốn thử nghiệm train với bộ dataset nào, bạn chỉ cần truyền file đó vào script huấn luyện:
- Trong `train_model.py`: Sửa đường dẫn dataset thành `data_cleaner/outputs/dataset_v4_sales.csv`.
- Hoặc trong notebook Google Colab `KiGuard_Train_PhoBERT_Colab.ipynb`: Tải file `dataset_v1_light.csv` hoặc `dataset_v4_sales.csv` lên để train và đánh giá độ chính xác!
