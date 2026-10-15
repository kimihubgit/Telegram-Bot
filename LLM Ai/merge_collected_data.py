"""
Merge Collected Data Script
Gộp tất cả các mẫu dữ liệu mới thu thập từ:
- collected_data/ban_hang/ban_hang.csv (nhãn 1)
- collected_data/khong_ban_hang/khong_ban_hang.csv (nhãn 0)
vào dataset.csv chính để sẵn sàng huấn luyện (retrain) mô hình AI.

Tự động:
- Khử trùng lặp giữa dữ liệu mới và dữ liệu cũ.
- Lưu file an toàn với mã hóa chuẩn utf-8-sig.
"""
import os
import pandas as pd

_DIR = os.path.dirname(__file__)
DATASET_PATH = os.path.join(_DIR, "dataset.csv")
SALES_PATH = os.path.join(_DIR, "collected_data", "ban_hang", "ban_hang.csv")
NON_SALES_PATH = os.path.join(_DIR, "collected_data", "khong_ban_hang", "khong_ban_hang.csv")


def merge_data():
    if not os.path.exists(DATASET_PATH):
        print(f"❌ Không tìm thấy file {DATASET_PATH}")
        return

    df_base = pd.read_csv(DATASET_PATH)
    initial_len = len(df_base)
    print(f"📂 Dữ liệu hiện tại trong dataset.csv: {initial_len} dòng")

    new_rows = []

    # 1. Đọc dữ liệu bán hàng mới
    if os.path.exists(SALES_PATH):
        try:
            df_s = pd.read_csv(SALES_PATH)
            if not df_s.empty and 'text' in df_s.columns:
                df_s = df_s[['text']].copy()
                df_s['label'] = 1
                new_rows.append(df_s)
                print(f"  + Tìm thấy {len(df_s)} mẫu trong collected_data/ban_hang/")
        except Exception as e:
            print(f"⚠️ Lỗi đọc {SALES_PATH}: {e}")

    # 2. Đọc dữ liệu không bán hàng mới
    if os.path.exists(NON_SALES_PATH):
        try:
            df_ns = pd.read_csv(NON_SALES_PATH)
            if not df_ns.empty and 'text' in df_ns.columns:
                df_ns = df_ns[['text']].copy()
                df_ns['label'] = 0
                new_rows.append(df_ns)
                print(f"  + Tìm thấy {len(df_ns)} mẫu trong collected_data/khong_ban_hang/")
        except Exception as e:
            print(f"⚠️ Lỗi đọc {NON_SALES_PATH}: {e}")

    if not new_rows:
        print("ℹ️ Chưa có dữ liệu thu thập mới nào để gộp.")
        return

    df_new = pd.concat(new_rows, ignore_index=True)

    # Gộp vào bộ dữ liệu gốc
    df_combined = pd.concat([df_base[['text', 'label']], df_new[['text', 'label']]], ignore_index=True)

    # Khử trùng lặp dựa trên nội dung text (giữ lại nhãn đầu tiên)
    df_combined['norm'] = df_combined['text'].astype(str).str.strip().str.lower()
    df_dedup = df_combined.drop_duplicates(subset=['norm']).drop(columns=['norm']).reset_index(drop=True)

    added_count = len(df_dedup) - initial_len
    df_dedup.to_csv(DATASET_PATH, index=False, encoding="utf-8-sig")

    print(f"🎉 Gộp thành công! Đã thêm {added_count} mẫu mới tinh (sau khi khử trùng lặp).")
    print(f"📊 Tổng số mẫu dataset.csv hiện tại: {len(df_dedup)}")
    print("Phân bổ nhãn:")
    print(df_dedup['label'].value_counts())


if __name__ == "__main__":
    merge_data()
