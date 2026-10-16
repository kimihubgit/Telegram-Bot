"""
Công cụ lọc và trích xuất dữ liệu:
1. 'CẦN MUA HÀNG / TÌM DỊCH VỤ' (Buyer / Demand Intent)
2. 'CẦN TRỢ GIÚP / HỎI ĐÁP KỸ THUẬT' (Help / Support Intent)

Đọc từ kho dữ liệu tin nhắn Telegram thực tế (telegram_clean.csv & dataset.csv),
phân loại chính xác, loại bỏ tin bán hàng và xuất ra file Excel (.xlsx) tuyệt đẹp kèm file CSV.
"""

import sys
import re
import pandas as pd
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Đảm bảo in UTF-8 không lỗi trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_CURRENT_DIR = Path(__file__).resolve().parent
_OUTPUT_XLSX = _CURRENT_DIR / "loc_nhu_cau_va_tro_giup.xlsx"
_OUTPUT_CSV = _CURRENT_DIR / "loc_nhu_cau_va_tro_giup.csv"

# 1. Regex loại bỏ các tin rao bán của người bán / spammer
SELLER_EXCLUDE_REGEX = re.compile(
    r'(?:'
    r'#nghienplusmarket|\b(?:bhf|kbh|inbox\s+tôi|ib\s+mình|ib\s+em|liên\s+hệ|bán\s+lại|pass\s+lại|'
    r'sẵn\s+sll|kho\s+sẵn|bảo\s+hành\s+full|rate\s+\d+|bot\s+auto|t\.me/|giá\s+chỉ|chiết\s+khấu|'
    r'chính\s+chủ\s+bảo\s+hành|vào\s+tiểu\s+sử|xem\s+bio|link\s+trong\s+bio)\b|'
    r'\d+k/\d+|\d+k/tháng|\d+k/1th|\d+k/acc|\d+k/thg'
    r')',
    re.IGNORECASE
)

# 2. Regex nhận diện nhu cầu mua hàng / tìm dịch vụ (Buyer Intent)
BUYER_PATTERNS = [
    (re.compile(r'\b(?:cần\s+mua|tìm\s+mua|mua\s+hộ|e\s+tìm|em\s+tìm|mình\s+tìm|tìm\s+acc|tìm\s+slot|tìm\s+gấp|kiếm\s+acc|kiếm\s+slot|kiếm\s+nguồn|tìm\s+nguồn|mua\s+acc|cần\s+acc|cần\s+gấp|cần\s+thuê|cần\s+1\b|cần\s+\d+\s+acc|tìm\s+1\b|mua\s+1\b)\b', re.IGNORECASE), "Tìm mua tài khoản / dịch vụ"),
    (re.compile(r'\b(?:ai\s+bán|còn\s+ai\s+bán)\b', re.IGNORECASE), "Hỏi người bán"),
    (re.compile(r'\b(?:bác\s+nào\s+còn|ai\s+còn|còn\s+ai)\s+(?:slot|acc|hàng|key)\b', re.IGNORECASE), "Hỏi tìm slot còn trống"),
    (re.compile(r'\b(?:xin\s+giá|báo\s+giá|xin\s+rate|xin\s+slot|giá\s+sao\s+ạ|giá\s+bao\s+nhiêu|bao\s+nhiêu\s+vậy)\b', re.IGNORECASE), "Hỏi giá / khảo giá mua"),
    (re.compile(r'\b(?:ai\s+nhận|bác\s+nào\s+nhận|có\s+bác\s+nào\s+nhận|nhận\s+làm\s+không)\s+(?:reg|làm|kéo|quét|chuyển|check|buff)\b', re.IGNORECASE), "Tìm người làm dịch vụ"),
    (re.compile(r'\b(?:anyone\s+have|who\s+have|looking\s+for|need\s+to\s+buy|want\s+to\s+buy|wtb)\b', re.IGNORECASE), "Hỏi mua (Tiếng Anh)"),
    (re.compile(r'\b(?:ai\s+có|bác\s+nào\s+có|ae\s+có|có\s+ai\s+có)\s+.{2,35}?(?:k\b|ko\b|không\b|ạ\b|\?|bán\s+k|pass\s+k)', re.IGNORECASE), "Hỏi ai có hàng để mua"),
]

# 3. Regex nhận diện cần trợ giúp / hỏi đáp kỹ thuật (Help / Support Intent)
HELP_PATTERNS = [
    (re.compile(r'\b(?:làm\s+sao\s+(?:để|fix|được|qua|xử\s+lý|kích\s+hoạt)|làm\s+thế\s+nào\s+để|cách\s+nào\s+(?:để|fix|qua))\b', re.IGNORECASE), "Hỏi cách làm / cách thực hiện"),
    (re.compile(r'\b(?:fix\s+sao|sửa\s+sao|fix\s+được\s+chưa|chỉ\s+(?:em|mình|với)\s+cách|hướng\s+dẫn\s+(?:em|mình|cách)|bác\s+nào\s+biết\s+cách|ai\s+biết\s+cách)\b', re.IGNORECASE), "Hỏi cách sửa lỗi / nhờ chỉ dẫn"),
    (re.compile(r'\b(?:bị\s+lỗi|lỗi\s+gì|gặp\s+lỗi|bị\s+quét|bị\s+khóa|bị\s+ban|failed\s+to|payment\s+declined|declined|error)\b', re.IGNORECASE), "Báo lỗi gặp phải"),
    (re.compile(r'\b(?:sao\s+bị|sao\s+không|sao\s+k\s+được|sao\s+nay|sao\s+nó\s+cứ|sao\s+thế|sao\s+vậy\s+ae|sao\s+kì\s+vậy)\b', re.IGNORECASE), "Thắc mắc bất thường"),
    (re.compile(r'\b(?:cứu\s+(?:em|mình|với)|giúp\s+(?:em|mình|với)|nhờ\s+(?:ae|các\s+bác|cao\s+nhân)|check\s+hộ\s+em|phân\s+xử\s+hộ)\b', re.IGNORECASE), "Kêu gọi giúp đỡ / hỗ trợ khẩn"),
    (re.compile(r'\b(?:cho\s+(?:em|e|mình)\s+hỏi|ae\s+cho\s+hỏi|tiện\s+hỏi|hỏi\s+(?:ngu|tí|xíu|thật))\b', re.IGNORECASE), "Mở lời hỏi đáp kinh nghiệm"),
    (re.compile(r'\b(?:có\s+cách\s+nào|có\s+tool\s+nào|dùng\s+tool\s+gì|dùng\s+app\s+nào|dùng\s+mạng\s+gì|dùng\s+proxy\s+gì)\b', re.IGNORECASE), "Hỏi công cụ / phương pháp"),
    (re.compile(r'\b(?:dùng\s+ổn\s+k|dùng\s+ngon\s+k|nên\s+mua\s+(?:gói|loại|bản)|có\s+nên\s+dùng|ai\s+dùng\s+thử\s+chưa|ai\s+test\s+chưa|ai\s+rành\s+về)\b', re.IGNORECASE), "Tham khảo ý kiến / đánh giá"),
    (re.compile(r'\b(?:giới\s+hạn\s+như\s+nào|chính\s+sách\s+sao|quy\s+định\s+sao|tính\s+năng\s+gì)\b', re.IGNORECASE), "Hỏi chính sách / giới hạn dịch vụ"),
]


def classify_text(text: str):
    """Phân loại tin nhắn xem thuộc Buyer hay Help hay None"""
    clean_snippet = " ".join(text.strip().split())
    
    # Bỏ qua tin quá ngắn hoặc quá dài
    if len(clean_snippet) < 6 or len(clean_snippet) > 300:
        return None
    
    # Bỏ qua tin bán hàng / spam
    if SELLER_EXCLUDE_REGEX.search(clean_snippet):
        return None

    # 1. Kiểm tra nhu cầu mua (Buyer)
    for pattern, sub_desc in BUYER_PATTERNS:
        match = pattern.search(clean_snippet)
        if match:
            trigger_word = match.group(0).strip()
            # Gợi ý xử lý cho AI
            ai_action = "Gợi ý người bán trong database hoặc lưu nhu cầu để thông báo khi có người bán"
            return {
                "loai": "🛒 CẦN MUA HÀNG / TÌM DỊCH VỤ",
                "loai_code": "BUYER",
                "chi_tiet": sub_desc,
                "text_goc": clean_snippet,
                "tu_khoa": trigger_word,
                "huong_xu_ly": ai_action
            }

    # 2. Kiểm tra câu hỏi / trợ giúp (Help)
    for pattern, sub_desc in HELP_PATTERNS:
        match = pattern.search(clean_snippet)
        if match:
            trigger_word = match.group(0).strip()
            ai_action = "Kích hoạt AI Assistant (LLM) trả lời giải đáp thắc mắc / hướng dẫn sửa lỗi"
            return {
                "loai": "❓ CẦN TRỢ GIÚP / HỎI ĐÁP KỸ THUẬT",
                "loai_code": "HELP",
                "chi_tiet": sub_desc,
                "text_goc": clean_snippet,
                "tu_khoa": trigger_word,
                "huong_xu_ly": ai_action
            }

    # 3. Câu hỏi có dấu '?' và dài từ 5 từ trở lên (hỏi chung)
    if clean_snippet.endswith("?") and len(clean_snippet.split()) >= 5:
        # Nếu hỏi ai có / ai bán mà sót ở trên
        if re.search(r'\b(?:ai\s+có|ai\s+bán|giá\s+sao|bao\s+nhiêu)\b', clean_snippet, re.IGNORECASE):
            return {
                "loai": "🛒 CẦN MUA HÀNG / TÌM DỊCH VỤ",
                "loai_code": "BUYER",
                "chi_tiet": "Hỏi mua / khảo giá",
                "text_goc": clean_snippet,
                "tu_khoa": "Dấu hỏi mua ?",
                "huong_xu_ly": "Gợi ý người bán trong database"
            }
        else:
            return {
                "loai": "❓ CẦN TRỢ GIÚP / HỎI ĐÁP KỸ THUẬT",
                "loai_code": "HELP",
                "chi_tiet": "Câu hỏi thắc mắc",
                "text_goc": clean_snippet,
                "tu_khoa": "Câu hỏi kết thúc ?",
                "huong_xu_ly": "Kích hoạt AI Assistant (LLM) trả lời"
            }

    return None


def run_extraction():
    print("=" * 80)
    print("🚀 BẮT ĐẦU TRÍCH XUẤT CÁC TIN NHẮN CÓ NHU CẦU & CẦN TRỢ GIÚP")
    print("=" * 80)

    # Đọc dữ liệu từ telegram_clean.csv và dataset.csv
    sources = [
        _CURRENT_DIR / "telegram_clean.csv",
        _CURRENT_DIR / "dataset.csv"
    ]

    all_texts = []
    for s in sources:
        if s.exists():
            print(f"📂 Đang nạp nguồn: {s.name}...")
            df = pd.read_csv(s)
            if "text" in df.columns:
                all_texts.extend(df["text"].dropna().tolist())

    print(f"📌 Tổng số câu quét qua: {len(all_texts):,}")

    records = []
    seen = set()

    for text in all_texts:
        t_clean = str(text).strip()
        norm_key = t_clean.lower()
        if norm_key in seen:
            continue
        seen.add(norm_key)

        classified = classify_text(t_clean)
        if classified:
            records.append(classified)

    print(f"\n🎯 ĐÃ TRÍCH XUẤT ĐƯỢC: {len(records):,} MẪU CHẤT LƯỢNG CAO!")
    
    buyer_count = sum(1 for r in records if r["loai_code"] == "BUYER")
    help_count = sum(1 for r in records if r["loai_code"] == "HELP")
    print(f"  • 🛒 Cần mua hàng / tìm dịch vụ : {buyer_count:,} mẫu")
    print(f"  • ❓ Cần trợ giúp / hỏi đáp kỹ thuật : {help_count:,} mẫu")

    # Tạo DataFrame
    df_export = pd.DataFrame([
        {
            "STT": i + 1,
            "Phân Loại": r["loai"],
            "Mục Đích Chi Tiết": r["chi_tiet"],
            "Nội Dung Tin Nhắn": r["text_goc"],
            "Từ Khóa Nhận Diện": r["tu_khoa"],
            "Hướng Xử Lý Của AI": r["huong_xu_ly"]
        }
        for i, r in enumerate(records)
    ])

    # 1. Xuất file CSV
    df_export.to_csv(_OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n✅ Đã lưu file CSV: {_OUTPUT_CSV.name}")

    # 2. Xuất file Excel (.xlsx) với định dạng đẹp mắt
    print(f"🎨 Đang định dạng file Excel đẹp mắt...")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Nhu Cầu & Trợ Giúp"

    # Header
    headers = list(df_export.columns)
    ws.append(headers)

    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid") # Xanh navy sang trọng
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9")
    )

    # Style Header
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center
        cell.border = thin_border
    ws.row_dimensions[1].height = 28

    # Fills cho các loại
    buyer_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid") # Xanh lá nhạt
    help_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")   # Vàng nhạt

    # Append data rows
    for row_idx, row in df_export.iterrows():
        excel_row = [row[col] for col in headers]
        ws.append(excel_row)
        current_row_idx = row_idx + 2

        loai_val = row["Phân Loại"]
        row_fill = buyer_fill if "MUA HÀNG" in loai_val else help_fill

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=current_row_idx, column=col_idx)
            cell.border = thin_border
            cell.font = Font(name="Arial", size=10)
            
            # Cột STT, Phân Loại, Từ Khóa canh giữa
            if col_idx in (1, 2, 5):
                cell.alignment = align_center
            else:
                cell.alignment = align_left
            
            # Tô màu phân loại ở cột 2
            if col_idx == 2:
                cell.fill = row_fill
                cell.font = Font(name="Arial", size=10, bold=True)

        ws.row_dimensions[current_row_idx].height = 22

    # Tự động điều chỉnh độ rộng cột
    col_widths = {
        "A": 8,   # STT
        "B": 32,  # Phân Loại
        "C": 28,  # Mục Đích Chi Tiết
        "D": 65,  # Nội Dung Tin Nhắn
        "E": 22,  # Từ Khóa Nhận Diện
        "F": 45   # Hướng Xử Lý Của AI
    }
    for col_letter, width in col_widths.items():
        ws.column_dimensions[col_letter].width = width

    # Bật tính năng Auto-Filter cho toàn bộ bảng
    ws.auto_filter.ref = ws.dimensions

    wb.save(_OUTPUT_XLSX)
    print(f"✅ Đã xuất file Excel hoàn chỉnh: {_OUTPUT_XLSX.name}")
    print(f"📁 Đường dẫn: {_OUTPUT_XLSX}")
    print("=" * 80)


if __name__ == "__main__":
    run_extraction()
