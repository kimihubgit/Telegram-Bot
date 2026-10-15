"""
Công cụ trích xuất, làm sạch và phân loại tin nhắn từ file Telegram Export (result.json)
Sử dụng mô hình AI (PhoBERT / TF-IDF + Ensemble) và Rule-Engine để gán nhãn:
- Label 1: Có bán hàng / rao vặt
- Label 0: Không bán hàng / tin nhắn thường

Xuất ra 2 thư mục riêng biệt:
1. 'classified_export/co_ban_hang/co_ban_hang.csv'
2. 'classified_export/khong_ban_hang/khong_ban_hang.csv'
Và file tổng hợp: 'classified_export/tat_ca_tin_nhan.csv'
"""

import os
import sys
import json
import csv
import pandas as pd
from pathlib import Path

# Đảm bảo in UTF-8 không lỗi trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_CURRENT_DIR = Path(__file__).resolve().parent
if str(_CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(_CURRENT_DIR))

from sales_detector import check_sales_detail

# Cấu hình đường dẫn
_INPUT_JSON = _CURRENT_DIR / "result.json"
_BASE_EXPORT_DIR = _CURRENT_DIR / "classified_export"
_SALES_DIR = _BASE_EXPORT_DIR / "co_ban_hang"
_NON_SALES_DIR = _BASE_EXPORT_DIR / "khong_ban_hang"

_SALES_CSV = _SALES_DIR / "co_ban_hang.csv"
_NON_SALES_CSV = _NON_SALES_DIR / "khong_ban_hang.csv"
_ALL_CSV = _BASE_EXPORT_DIR / "tat_ca_tin_nhan.csv"


def extract_raw_text(text_field) -> str:
    """Trích xuất chuỗi văn bản gốc từ trường text của Telegram export (chuỗi hoặc list các object)"""
    if isinstance(text_field, str):
        return text_field
    elif isinstance(text_field, list):
        parts = []
        for part in text_field:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(str(part["text"]))
        return "".join(parts)
    return ""


def main(input_json_path: Path = _INPUT_JSON):
    if not input_json_path.exists():
        print(f"❌ Không tìm thấy file nguồn: {input_json_path}")
        return

    print("=" * 80)
    print("🚀 BẮT ĐẦU XỬ LÝ & PHÂN LOẠI DỮ LIỆU TELEGRAM EXPORT")
    print(f"📂 File nguồn: {input_json_path.name}")
    print("=" * 80)

    # Đọc file JSON (tự động xử lý nếu thiếu đóng ngoặc)
    with open(input_json_path, "r", encoding="utf-8") as f:
        content = f.read().rstrip()

    if not content.endswith("}"):
        if not content.endswith("]}") and not content.endswith("]\n}"):
            content += "\n ]\n}"

    try:
        data = json.loads(content)
    except Exception as e:
        print(f"❌ Lỗi đọc JSON: {e}")
        return

    messages = data.get("messages", [])
    print(f"📌 Tổng số tin nhắn trong file: {len(messages):,}")

    # Tạo thư mục xuất
    _SALES_DIR.mkdir(parents=True, exist_ok=True)
    _NON_SALES_DIR.mkdir(parents=True, exist_ok=True)

    sales_records = []
    non_sales_records = []
    all_records = []

    print("🔍 Đang làm sạch và chạy mô hình AI nhận dạng từng tin nhắn...")

    for idx, msg in enumerate(messages, 1):
        # Bỏ qua thông báo hệ thống (join/leave group, pin message...)
        if msg.get("type") != "message":
            continue

        raw_text = extract_raw_text(msg.get("text", "")).strip()

        # Bỏ qua tin nhắn trống hoặc chỉ có 1 ký tự
        if len(raw_text) < 2:
            continue

        # Dự đoán qua Model AI + Rule Engine
        result = check_sales_detail(raw_text)
        is_sales = result["is_sales"]
        label = 1 if is_sales else 0
        clean_text = result["clean_text"]
        confidence = result["confidence"]
        engine = result["engine"]

        # Gom dòng tin nhắn gốc thành 1 dòng sạch để không vỡ cấu trúc CSV
        single_line_raw = " ".join(raw_text.split())

        record = {
            "tin_nhan_goc": single_line_raw,
            "tin_nhan_tinh_gon": clean_text,
            "label": label,
            "do_tu_tin": confidence,
            "engine": engine,
            "message_id": msg.get("id"),
            "ngay": msg.get("date"),
            "nguoi_gui": msg.get("from", "")
        }

        all_records.append(record)
        if is_sales:
            sales_records.append(record)
        else:
            non_sales_records.append(record)

        if idx % 200 == 0 or idx == len(messages):
            print(f"  ⏳ Đã xử lý: {idx:,}/{len(messages):,} tin nhắn...")

    # Chuyển thành DataFrame và lưu CSV chuẩn utf-8-sig
    cols_order = [
        "tin_nhan_goc",
        "tin_nhan_tinh_gon",
        "label",
        "do_tu_tin",
        "engine",
        "message_id",
        "ngay",
        "nguoi_gui"
    ]

    df_sales = pd.DataFrame(sales_records)
    if not df_sales.empty:
        df_sales = df_sales[cols_order]
        df_sales.to_csv(_SALES_CSV, index=False, encoding="utf-8-sig")

    df_non_sales = pd.DataFrame(non_sales_records)
    if not df_non_sales.empty:
        df_non_sales = df_non_sales[cols_order]
        df_non_sales.to_csv(_NON_SALES_CSV, index=False, encoding="utf-8-sig")

    df_all = pd.DataFrame(all_records)
    if not df_all.empty:
        df_all = df_all[cols_order]
        df_all.to_csv(_ALL_CSV, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 80)
    print("🎉 HOÀN TẤT PHÂN LOẠI & XUẤT DỮ LIỆU THÀNH CÔNG!")
    print("=" * 80)
    print(f"🛒 Thư mục CÓ BÁN HÀNG   (Label 1): {_SALES_CSV}")
    print(f"   -> Số lượng: {len(sales_records):,} tin nhắn")
    print(f"💬 Thư mục KHÔNG BÁN HÀNG (Label 0): {_NON_SALES_CSV}")
    print(f"   -> Số lượng: {len(non_sales_records):,} tin nhắn")
    print(f"📑 File tổng hợp toàn bộ            : {_ALL_CSV}")
    print(f"   -> Tổng cộng: {len(all_records):,} tin nhắn hợp lệ")
    print("=" * 80)


if __name__ == "__main__":
    main()
