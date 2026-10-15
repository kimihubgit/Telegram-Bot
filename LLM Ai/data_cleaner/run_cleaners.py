"""
Tool Xuất Bộ Dữ Liệu Sau Khi Làm Sạch (Dataset Export Runner)
Cho phép làm sạch toàn bộ dataset và xuất ra các file CSV riêng biệt theo từng phiên bản
để bạn có thể huấn luyện và so sánh kết quả của từng bộ data.

Các phiên bản hỗ trợ:
- v1 : dataset_v1_light.csv
- v2 : dataset_v2_standard.csv
- v3 : dataset_v3_deep.csv
- v4 : dataset_v4_sales.csv
- all: Xuất toàn bộ 4 phiên bản cùng lúc và in bảng thống kê so sánh

Cách dùng:
  python run_cleaners.py --version all
  python run_cleaners.py --version v4
"""

import sys
import json
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime

# Đảm bảo in tiếng Việt & emoji mượt mà trên console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Import module cleaners
_CURRENT_DIR = Path(__file__).resolve().parent
if str(_CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(_CURRENT_DIR))

from cleaners import clean_v1_light, clean_v2_standard, clean_v3_deep, clean_v4_sales, get_all_cleaners

_ROOT_DIR = _CURRENT_DIR.parent
_DEFAULT_DATASET = _ROOT_DIR / "dataset.csv"
_OUTPUTS_DIR = _CURRENT_DIR / "outputs"


CLEANER_MAPPING = {
    "v1": ("dataset_v1_light.csv", clean_v1_light, "V1 - Light Clean (Giữ nguyên Emoji, URL, dấu câu)"),
    "v2": ("dataset_v2_standard.csv", clean_v2_standard, "V2 - Standard Clean (Tiêu chuẩn, khử emoji, URL, chữ thường)"),
    "v3": ("dataset_v3_deep.csv", clean_v3_deep, "V3 - Deep Clean (Siêu sạch, khử @username, ID số, dấu câu rác)"),
    "v4": ("dataset_v4_sales.csv", clean_v4_sales, "V4 - Sales Specialized (Quy đổi 200k, 1th, dịch viết tắt bh, ib, sll)"),
}


def process_dataset_version(df_raw: pd.DataFrame, version_key: str) -> dict:
    filename, clean_fn, desc = CLEANER_MAPPING[version_key]
    print(f"\n⚙️ Đang xử lý: {desc}...")

    cleaned_rows = []
    seen_texts = set()

    for _, row in df_raw.iterrows():
        raw_text = str(row["text"])
        label = int(row["label"])

        cleaned = clean_fn(raw_text)

        # Lọc bỏ tin nhắn rỗng hoặc quá ngắn dưới 3 ký tự
        if not cleaned or len(cleaned.strip()) < 3:
            continue

        # Chống trùng lặp tin nhắn
        norm_key = cleaned.lower()
        if norm_key in seen_texts:
            continue
        seen_texts.add(norm_key)

        cleaned_rows.append({
            "text": cleaned,
            "label": label
        })

    df_clean = pd.DataFrame(cleaned_rows)

    # Thống kê
    total_samples = len(df_clean)
    sales_count = int((df_clean["label"] == 1).sum())
    normal_count = int((df_clean["label"] == 0).sum())

    words = [w for t in df_clean["text"] for w in t.split()]
    vocab_size = len(set(words))
    avg_char_len = round(float(df_clean["text"].str.len().mean()), 1) if total_samples > 0 else 0
    avg_word_count = round(float(df_clean["text"].apply(lambda t: len(t.split())).mean()), 1) if total_samples > 0 else 0

    # Lưu file CSV
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = _OUTPUTS_DIR / filename
    df_clean.to_csv(out_file, index=False, encoding="utf-8-sig")

    stats = {
        "version": version_key,
        "description": desc,
        "filename": filename,
        "output_path": str(out_file),
        "total_samples": total_samples,
        "sales_count": sales_count,
        "normal_count": normal_count,
        "vocab_size": vocab_size,
        "avg_char_length": avg_char_len,
        "avg_word_count": avg_word_count,
    }

    print(f"  ✅ Đã lưu: {out_file.name}")
    print(f"     📊 Mẫu sạch: {total_samples:,} | Bán hàng (1): {sales_count:,} | Thường (0): {normal_count:,}")
    print(f"     📝 Từ vựng: {vocab_size:,} từ duy nhất | Độ dài TB: {avg_word_count} từ/câu")

    return stats


def run_pipeline(version: str = "all", dataset_path: str = None):
    input_file = Path(dataset_path) if dataset_path else _DEFAULT_DATASET
    if not input_file.exists():
        print(f"❌ Không tìm thấy file dữ liệu tại: {input_file}")
        return

    print("=" * 80)
    print("🚀 BẮT ĐẦU XỬ LÝ LÀM SẠCH BỘ DỮ LIỆU HUẤN LUYỆN (DATA CLEANING PIPELINE)")
    print(f"📂 File nguồn: {input_file}")
    print("=" * 80)

    df_raw = pd.read_csv(input_file).dropna(subset=["text", "label"])
    print(f"📌 Tổng số mẫu thô ban đầu: {len(df_raw):,}")

    versions_to_run = list(CLEANER_MAPPING.keys()) if version.lower() == "all" else [version.lower()]

    summary = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "raw_samples": len(df_raw),
        "versions": []
    }

    for v in versions_to_run:
        if v not in CLEANER_MAPPING:
            print(f"⚠️ Bỏ qua phiên bản không hợp lệ: {v} (Chỉ hỗ trợ: v1, v2, v3, v4, all)")
            continue
        stats = process_dataset_version(df_raw, v)
        summary["versions"].append(stats)

    # Lưu file báo cáo tổng hợp JSON
    report_file = _OUTPUTS_DIR / "cleaning_summary.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("📋 BẢNG TỔNG HỢP SO SÁNH CÁC BỘ DỮ LIỆU ĐÃ CLEAN")
    print("=" * 80)
    print(f"{'Phiên bản':<10} | {'File xuất':<25} | {'Tổng mẫu':<10} | {'Bán hàng':<10} | {'Tin thường':<10} | {'Từ vựng':<8} | {'Từ/câu':<6}")
    print("-" * 92)
    for s in summary["versions"]:
        print(f"{s['version'].upper():<10} | {s['filename']:<25} | {s['total_samples']:<10,d} | {s['sales_count']:<10,d} | {s['normal_count']:<10,d} | {s['vocab_size']:<8,d} | {s['avg_word_count']:<6.1f}")
    print("=" * 80)
    print(f"🎉 Hoàn tất! Báo cáo chi tiết đã lưu tại: {report_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chạy quy trình làm sạch và xuất các phiên bản dataset")
    parser.add_argument("--version", type=str, default="all", choices=["v1", "v2", "v3", "v4", "all"], help="Phiên bản cần xuất (v1, v2, v3, v4 hoặc all)")
    parser.add_argument("--dataset", type=str, default=None, help="Đường dẫn dataset gốc cần xử lý")
    args = parser.parse_args()

    run_pipeline(args.version, args.dataset)
