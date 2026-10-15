"""
Công cụ gộp dữ liệu từ 2 thư mục:
- 'classified_export/co_ban_hang' (Label 1)
- 'classified_export/khong_ban_hang' (Label 0)

Tự động:
1. Đọc tất cả file CSV trong cả 2 thư mục
2. Chuẩn hóa nhãn (label 1 cho bán hàng, label 0 cho không bán hàng)
3. Loại bỏ trùng lặp nếu có
4. Trộn ngẫu nhiên (shuffle) để sẵn sàng cho huấn luyện AI
5. Xuất ra 2 file:
   - 'classified_export/dataset_gop.csv' (Đầy đủ tất cả các cột chi tiết)
   - 'classified_export/dataset_train_gop.csv' (Chuẩn hóa 2 cột text, label để train ngay)
"""

import os
import sys
import pandas as pd
from pathlib import Path

# Đảm bảo UTF-8 trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_CURRENT_DIR = Path(__file__).resolve().parent
_CLASSIFIED_DIR = _CURRENT_DIR / "classified_export"
_SALES_DIR = _CLASSIFIED_DIR / "co_ban_hang"
_NON_SALES_DIR = _CLASSIFIED_DIR / "khong_ban_hang"

_OUT_FULL_CSV = _CLASSIFIED_DIR / "dataset_gop.csv"
_OUT_TRAIN_CSV = _CLASSIFIED_DIR / "dataset_train_gop.csv"


def merge_datasets():
    print("=" * 80)
    print("🔄 BẮT ĐẦU GỘP DỮ LIỆU TỪ 2 THƯ MỤC CLASSIFIED EXPORT")
    print("=" * 80)

    # 1. Đọc dữ liệu từ thư mục CÓ BÁN HÀNG
    sales_dfs = []
    for csv_file in _SALES_DIR.glob("*.csv"):
        try:
            df = pd.read_csv(csv_file)
            df["label"] = 1  # Đảm bảo label là 1
            sales_dfs.append(df)
            print(f"  📂 Đã đọc file bán hàng: {csv_file.name} ({len(df):,} dòng)")
        except Exception as e:
            print(f"  ⚠️ Lỗi đọc file {csv_file}: {e}")

    # 2. Đọc dữ liệu từ thư mục KHÔNG BÁN HÀNG
    non_sales_dfs = []
    for csv_file in _NON_SALES_DIR.glob("*.csv"):
        try:
            df = pd.read_csv(csv_file)
            df["label"] = 0  # Đảm bảo label là 0
            non_sales_dfs.append(df)
            print(f"  📂 Đã đọc file không bán hàng: {csv_file.name} ({len(df):,} dòng)")
        except Exception as e:
            print(f"  ⚠️ Lỗi đọc file {csv_file}: {e}")

    if not sales_dfs and not non_sales_dfs:
        print("❌ Không tìm thấy file dữ liệu nào để gộp!")
        return

    df_sales = pd.concat(sales_dfs, ignore_index=True) if sales_dfs else pd.DataFrame()
    df_non_sales = pd.concat(non_sales_dfs, ignore_index=True) if non_sales_dfs else pd.DataFrame()

    print("\n📊 THỐNG KÊ TRƯỚC KHI GỘP:")
    print(f"  • Bán hàng (Label 1)     : {len(df_sales):,} dòng")
    print(f"  • Không bán hàng (Label 0): {len(df_non_sales):,} dòng")

    # 3. Gộp 2 tập dữ liệu
    merged_df = pd.concat([df_sales, df_non_sales], ignore_index=True)

    # 4. Loại bỏ trùng lặp dựa trên tin nhắn gốc hoặc tin nhắn tinh gọn
    initial_count = len(merged_df)
    subset_col = "tin_nhan_tinh_gon" if "tin_nhan_tinh_gon" in merged_df.columns else "tin_nhan_goc"
    merged_df = merged_df.drop_duplicates(subset=[subset_col]).reset_index(drop=True)
    dedup_count = len(merged_df)

    if initial_count != dedup_count:
        print(f"  🧹 Đã loại bỏ {initial_count - dedup_count:,} dòng trùng lặp!")

    # 5. Xáo trộn ngẫu nhiên (Shuffle) với random_state cố định để dữ liệu đan xen nhau
    merged_shuffled = merged_df.sample(frac=1.0, random_state=42).reset_index(drop=True)

    # 6. Xuất file đầy đủ tất cả các cột
    merged_shuffled.to_csv(_OUT_FULL_CSV, index=False, encoding="utf-8-sig")
    print(f"\n✅ 1. Đã xuất file gộp đầy đủ chi tiết:")
    print(f"     📁 {_OUT_FULL_CSV}")
    print(f"     📝 Tổng số dòng: {len(merged_shuffled):,} | Cột: {list(merged_shuffled.columns)}")

    # 7. Xuất file tinh gọn chuẩn 'text', 'label' để huấn luyện mô hình ngay
    text_source_col = "tin_nhan_tinh_gon" if "tin_nhan_tinh_gon" in merged_shuffled.columns else "tin_nhan_goc"
    train_df = pd.DataFrame({
        "text": merged_shuffled[text_source_col],
        "label": merged_shuffled["label"]
    })
    # Bỏ các dòng rỗng nếu có
    train_df = train_df.dropna().reset_index(drop=True)
    train_df.to_csv(_OUT_TRAIN_CSV, index=False, encoding="utf-8-sig")

    print(f"\n✅ 2. Đã xuất file dataset chuẩn hóa để huấn luyện (train):")
    print(f"     📁 {_OUT_TRAIN_CSV}")
    print(f"     📝 Định dạng: text, label ({len(train_df):,} dòng)")

    sales_final = int((merged_shuffled["label"] == 1).sum())
    non_sales_final = int((merged_shuffled["label"] == 0).sum())

    print("\n" + "=" * 80)
    print("🎉 HOÀN TẤT GỘP DỮ LIỆU THÀNH CÔNG!")
    print(f"  • Tổng mẫu gộp: {len(merged_shuffled):,}")
    print(f"  • Bán hàng (1) : {sales_final:,} ({round(sales_final / len(merged_shuffled) * 100, 1)}%)")
    print(f"  • Tin thường (0): {non_sales_final:,} ({round(non_sales_final / len(merged_shuffled) * 100, 1)}%)")
    print("=" * 80)


if __name__ == "__main__":
    merge_datasets()
