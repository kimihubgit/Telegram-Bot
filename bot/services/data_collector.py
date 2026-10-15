"""
Data Collector Service
Thu thập và tự động phân loại dữ liệu tin nhắn Telegram vào 2 thư mục riêng biệt:
1. 'ban_hang/' (Chứa tin nhắn bán hàng / rao vặt - label 1)
2. 'khong_ban_hang/' (Chứa tin nhắn thường / hỏi mua / đàm thoại - label 0)

Lưu dưới định dạng CSV (mã hóa utf-8-sig) chuẩn hóa để sẵn sàng train tiếp cho mô hình AI.
"""
import os
import csv
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Thư mục gốc chứa dữ liệu thu thập (hỗ trợ cả 'LLM Ai' ở root và 'bot/LLM Ai')
_candidate1 = Path(__file__).resolve().parent.parent.parent / "LLM Ai"
_candidate2 = Path(__file__).resolve().parent.parent / "LLM Ai"
_llm_ai_dir = _candidate1 if _candidate1.exists() else _candidate2

_BASE_DIR = _llm_ai_dir / "collected_data"
_SALES_DIR = _BASE_DIR / "ban_hang"
_NON_SALES_DIR = _BASE_DIR / "khong_ban_hang"

_SALES_CSV = _SALES_DIR / "ban_hang.csv"
_NON_SALES_CSV = _NON_SALES_DIR / "khong_ban_hang.csv"

# Bộ nhớ đệm lưu hash các câu đã thu thập để chống trùng lặp dữ liệu
_seen_hashes = set()
_is_initialized = False


def _get_vn_now_str() -> str:
    """Lấy thời gian hiện tại theo giờ Việt Nam (UTC+7) định dạng YYYY-MM-DD HH:MM:SS"""
    vn_tz = timezone(timedelta(hours=7))
    return datetime.now(vn_tz).strftime("%Y-%m-%d %H:%M:%S")


def _init_collector():
    """Khởi tạo cấu trúc thư mục và nạp hash các câu đã có để chống trùng lặp"""
    global _is_initialized
    if _is_initialized:
        return

    _SALES_DIR.mkdir(parents=True, exist_ok=True)
    _NON_SALES_DIR.mkdir(parents=True, exist_ok=True)

    csv_headers = ["text", "label", "date", "user_id", "chat_id", "confidence", "engine"]

    for file_path in [_SALES_CSV, _NON_SALES_CSV]:
        if not file_path.exists():
            with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(csv_headers)
        else:
            # Đọc sẵn các câu đã có vào set chống trùng lặp
            try:
                with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.reader(f)
                    next(reader, None)  # Bỏ qua header
                    for row in reader:
                        if row and len(row) > 0:
                            clean_snippet = row[0].strip().lower()
                            h = hashlib.md5(clean_snippet.encode("utf-8")).hexdigest()
                            _seen_hashes.add(h)
            except Exception as e:
                print(f"⚠️ [Data Collector] Lỗi nạp cache từ {file_path.name}: {e}")

    _is_initialized = True


def save_message_for_training(
    text: str,
    is_sales: bool,
    user_id: int = 0,
    chat_id: int = 0,
    confidence: float = 0.0,
    engine: str = "AI"
) -> bool:
    """
    Lưu một tin nhắn mới vào đúng thư mục:
    - is_sales == True  -> Lưu vào 'ban_hang/ban_hang.csv' (label = 1)
    - is_sales == False -> Lưu vào 'khong_ban_hang/khong_ban_hang.csv' (label = 0)

    Trả về True nếu lưu thành công, False nếu tin nhắn trùng lặp hoặc không hợp lệ.
    """
    if not text or len(text.strip()) < 3:
        return False

    _init_collector()

    # Chuẩn hóa khoảng trắng để kiểm tra trùng lặp
    normalized = " ".join(text.strip().split())
    h = hashlib.md5(normalized.lower().encode("utf-8")).hexdigest()

    # Chống ghi trùng dữ liệu lặp lại nhiều lần
    if h in _seen_hashes:
        return False
    _seen_hashes.add(h)

    target_csv = _SALES_CSV if is_sales else _NON_SALES_CSV
    label = 1 if is_sales else 0
    now_str = _get_vn_now_str()

    try:
        with open(target_csv, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                normalized,
                label,
                now_str,
                user_id,
                chat_id,
                round(float(confidence), 2),
                engine
            ])
        return True
    except Exception as e:
        print(f"⚠️ [Data Collector] Lỗi ghi CSV ({target_csv.name}): {e}")
        return False


def get_collector_stats() -> dict:
    """Trả về thống kê số lượng mẫu đã thu thập trong cả 2 thư mục"""
    _init_collector()

    def _count_rows(csv_path: Path) -> int:
        if not csv_path.exists():
            return 0
        try:
            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    return 0
                return sum(1 for _ in reader)
        except Exception:
            return 0

    sales_count = _count_rows(_SALES_CSV)
    non_sales_count = _count_rows(_NON_SALES_CSV)

    return {
        "sales_count": sales_count,
        "non_sales_count": non_sales_count,
        "total_count": sales_count + non_sales_count,
        "sales_path": str(_SALES_CSV),
        "non_sales_path": str(_NON_SALES_CSV)
    }


# Khởi tạo sẵn khi import
_init_collector()
