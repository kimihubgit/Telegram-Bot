"""
Tool Xem Trước & So Sánh Dữ Liệu Sau Khi Clean (Preview & Compare Cleaners)
Cho phép bạn kiểm tra trực tiếp từng câu trước và sau khi làm sạch qua 4 phiên bản:
V1 (Light), V2 (Standard), V3 (Deep), V4 (Sales).

Xuất kết quả:
1. Console: In so sánh mẫu có màu sắc trực quan
2. CSV: 'outputs/preview_comparison.csv' để mở bằng Excel / Google Sheets
3. HTML: 'outputs/preview_comparison.html' mở bằng trình duyệt xem dashboard cực kỳ đẹp mắt
"""

import os
import sys
import html
import pandas as pd
from pathlib import Path

# Đảm bảo in tiếng Việt & emoji mượt mà trên console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Thêm thư mục hiện tại vào sys.path để import cleaners
_CURRENT_DIR = Path(__file__).resolve().parent
if str(_CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(_CURRENT_DIR))

from cleaners import get_all_cleaners, clean_v1_light, clean_v2_standard, clean_v3_deep, clean_v4_sales

# Đường dẫn dataset gốc
_ROOT_DIR = _CURRENT_DIR.parent
_DEFAULT_DATASET = _ROOT_DIR / "dataset.csv"
_OUTPUTS_DIR = _CURRENT_DIR / "outputs"


def generate_html_preview(df_preview: pd.DataFrame, output_html_path: Path):
    """Tạo giao diện web HTML tương tác hiển thị bảng so sánh trước - sau clean"""
    output_html_path.parent.mkdir(parents=True, exist_ok=True)

    rows_html = []
    for idx, row in df_preview.iterrows():
        label = row.get("label", 0)
        label_badge = (
            '<span class="badge badge-sales">🛒 BÁN HÀNG (1)</span>'
            if label == 1
            else '<span class="badge badge-normal">💬 THƯỜNG (0)</span>'
        )
        orig = html.escape(str(row.get("original_text", "")))
        v1 = html.escape(str(row.get("v1_light", "")))
        v2 = html.escape(str(row.get("v2_standard", "")))
        v3 = html.escape(str(row.get("v3_deep", "")))
        v4 = html.escape(str(row.get("v4_sales", "")))

        card = f"""
        <div class="sample-card" data-label="{label}">
            <div class="card-header">
                <span class="sample-id">#Mẫu {idx + 1}</span>
                {label_badge}
            </div>
            <div class="card-body">
                <div class="version-box raw">
                    <div class="version-label">📝 Dữ Liệu Gốc (Raw Text)</div>
                    <div class="version-content">{orig}</div>
                </div>
                <div class="versions-grid">
                    <div class="version-box v1">
                        <div class="version-label">🔹 V1 (Light Clean)</div>
                        <div class="version-content">{v1}</div>
                    </div>
                    <div class="version-box v2">
                        <div class="version-label">🔸 V2 (Standard Clean)</div>
                        <div class="version-content">{v2}</div>
                    </div>
                    <div class="version-box v3">
                        <div class="version-label">⚡ V3 (Deep Clean)</div>
                        <div class="version-content">{v3 if v3 else '<em style="color:#888;">(Đã bị lọc rỗng)</em>'}</div>
                    </div>
                    <div class="version-box v4">
                        <div class="version-label">💎 V4 (Sales Specialized)</div>
                        <div class="version-content">{v4 if v4 else '<em style="color:#888;">(Đã bị lọc rỗng)</em>'}</div>
                    </div>
                </div>
            </div>
        </div>
        """
        rows_html.append(card)

    cards_block = "\n".join(rows_html)

    html_template = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kiểm Tra & So Sánh Dữ Liệu Làm Sạch (Clean Data Preview)</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0f172a;
            --card-bg: #1e293b;
            --border: #334155;
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
            --accent: #38bdf8;
            --sales: #ef4444;
            --normal: #10b981;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg);
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
            padding: 30px 20px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        h1 {{
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        p.desc {{
            color: var(--text-sub);
            font-size: 15px;
        }}
        .controls {{
            display: flex;
            gap: 15px;
            margin-bottom: 25px;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            background: var(--card-bg);
            padding: 15px 20px;
            border-radius: 12px;
            border: 1px solid var(--border);
        }}
        .search-box {{
            flex: 1;
            min-width: 250px;
        }}
        .search-box input {{
            width: 100%;
            padding: 10px 14px;
            background: #0f172a;
            border: 1px solid var(--border);
            border-radius: 8px;
            color: #fff;
            font-size: 14px;
            outline: none;
        }}
        .search-box input:focus {{
            border-color: var(--accent);
        }}
        .filter-buttons {{
            display: flex;
            gap: 8px;
        }}
        .btn {{
            padding: 8px 16px;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: #0f172a;
            color: var(--text-sub);
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .btn.active, .btn:hover {{
            background: var(--accent);
            color: #0f172a;
            border-color: var(--accent);
        }}
        .sample-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            margin-bottom: 20px;
            overflow: hidden;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .sample-card:hover {{
            border-color: #475569;
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
        }}
        .card-header {{
            background: rgba(15, 23, 42, 0.6);
            padding: 12px 18px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .sample-id {{
            font-weight: 600;
            color: var(--text-sub);
            font-size: 13px;
        }}
        .badge {{
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}
        .badge-sales {{
            background: rgba(239, 68, 68, 0.2);
            color: #fca5a5;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }}
        .badge-normal {{
            background: rgba(16, 185, 129, 0.2);
            color: #6ee7b7;
            border: 1px solid rgba(16, 185, 129, 0.4);
        }}
        .card-body {{
            padding: 18px;
        }}
        .version-box {{
            background: #0f172a;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 12px;
        }}
        .version-box.raw {{
            border-color: #475569;
            background: #141e33;
        }}
        .version-label {{
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            margin-bottom: 6px;
            letter-spacing: 0.5px;
        }}
        .raw .version-label {{ color: #cbd5e1; }}
        .v1 .version-label {{ color: #38bdf8; }}
        .v2 .version-label {{ color: #fbbf24; }}
        .v3 .version-label {{ color: #ec4899; }}
        .v4 .version-label {{ color: #a855f7; }}
        .version-content {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            white-space: pre-wrap;
            word-break: break-word;
            color: #e2e8f0;
        }}
        .versions-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 12px;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            color: var(--text-sub);
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔬 Clean Data Preview Dashboard</h1>
            <p class="desc">So sánh trực tiếp dữ liệu trước và sau khi xử lý qua các phiên bản làm sạch</p>
        </header>

        <div class="controls">
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="🔍 Tìm kiếm từ khóa trong các mẫu..." oninput="filterSamples()">
            </div>
            <div class="filter-buttons">
                <button class="btn active" onclick="setLabelFilter('all')">Tất Cả</button>
                <button class="btn" onclick="setLabelFilter('1')">🛒 Bán Hàng</button>
                <button class="btn" onclick="setLabelFilter('0')">💬 Tin Thường</button>
            </div>
        </div>

        <div id="samplesList">
            {cards_block}
        </div>

        <div class="footer">
            Phòng thí nghiệm dữ liệu AI KiGuard • Hỗ trợ huấn luyện PhoBERT & TF-IDF
        </div>
    </div>

    <script>
        let currentFilter = 'all';

        function setLabelFilter(filter) {{
            currentFilter = filter;
            document.querySelectorAll('.filter-buttons .btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            filterSamples();
        }}

        function filterSamples() {{
            const search = document.getElementById('searchInput').value.toLowerCase();
            const cards = document.querySelectorAll('.sample-card');

            cards.forEach(card => {{
                const label = card.getAttribute('data-label');
                const text = card.textContent.toLowerCase();

                const matchesLabel = (currentFilter === 'all') || (label === currentFilter);
                const matchesSearch = text.includes(search);

                if (matchesLabel && matchesSearch) {{
                    card.style.display = 'block';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}
    </script>
</body>
</html>
"""
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_template)


def run_preview(dataset_path: str = None, num_samples: int = 10):
    """Đọc dữ liệu và tạo bản so sánh mẫu"""
    file_path = Path(dataset_path) if dataset_path else _DEFAULT_DATASET
    if not file_path.exists():
        print(f"❌ Không tìm thấy file dữ liệu tại: {file_path}")
        return

    print(f"📂 Đang tải dữ liệu từ: {file_path.name}...")
    df = pd.read_csv(file_path)

    if "text" not in df.columns or "label" not in df.columns:
        print("❌ Dataset phải có ít nhất 2 cột: 'text' và 'label'")
        return

    # Lấy mẫu cân bằng: một nửa Bán hàng (label 1), một nửa Thường (label 0)
    half = max(num_samples // 2, 2)
    df_sales = df[df["label"] == 1].dropna(subset=["text"])
    df_normal = df[df["label"] == 0].dropna(subset=["text"])

    sample_sales = df_sales.sample(min(half, len(df_sales)), random_state=42)
    sample_normal = df_normal.sample(min(half, len(df_normal)), random_state=42)
    sample_df = pd.concat([sample_sales, sample_normal]).reset_index(drop=True)

    print(f"🔍 Đang áp dụng 4 pipeline làm sạch trên {len(sample_df)} mẫu thử...")

    results = []
    for idx, row in sample_df.iterrows():
        raw_text = str(row["text"])
        lbl = int(row["label"])

        v1 = clean_v1_light(raw_text)
        v2 = clean_v2_standard(raw_text)
        v3 = clean_v3_deep(raw_text)
        v4 = clean_v4_sales(raw_text)

        results.append({
            "original_text": raw_text,
            "label": lbl,
            "v1_light": v1,
            "v2_standard": v2,
            "v3_deep": v3,
            "v4_sales": v4
        })

        # In console minh họa 4 mẫu đầu tiên
        if idx < 4:
            lbl_str = "🛒 [BÁN HÀNG]" if lbl == 1 else "💬 [THƯỜNG]"
            print("=" * 80)
            print(f"📌 MẪU #{idx + 1} {lbl_str}")
            print(f"📝 GỐC      : {raw_text[:120]}{'...' if len(raw_text) > 120 else ''}")
            print(f"🔹 V1 Light : {v1[:120]}{'...' if len(v1) > 120 else ''}")
            print(f"🔸 V2 Std   : {v2[:120]}{'...' if len(v2) > 120 else ''}")
            print(f"⚡ V3 Deep  : {v3[:120]}{'...' if len(v3) > 120 else ''}")
            print(f"💎 V4 Sales : {v4[:120]}{'...' if len(v4) > 120 else ''}")

    res_df = pd.DataFrame(results)

    # 1. Lưu file so sánh CSV
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_out = _OUTPUTS_DIR / "preview_comparison.csv"
    res_df.to_csv(csv_out, index=False, encoding="utf-8-sig")
    print(f"\n✅ Đã xuất file CSV so sánh: {csv_out}")

    # 2. Tạo file HTML Dashboard
    html_out = _OUTPUTS_DIR / "preview_comparison.html"
    generate_html_preview(res_df, html_out)
    print(f"🌐 Đã tạo giao diện HTML trực quan: {html_out}")
    print("👉 Hãy mở file HTML trên trình duyệt để kiểm tra trực tiếp giao diện!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Kiểm tra & So sánh các phiên bản làm sạch dữ liệu")
    parser.add_argument("--dataset", type=str, default=None, help="Đường dẫn file dataset cần kiểm tra")
    parser.add_argument("--samples", type=int, default=16, help="Số lượng mẫu hiển thị xem trước (mặc định: 16)")
    args = parser.parse_args()

    run_preview(args.dataset, args.samples)
