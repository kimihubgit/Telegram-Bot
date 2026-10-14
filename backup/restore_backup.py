"""
KiGuard Backup Restore Tool
Công cụ độc lập để khôi phục file ZIP dữ liệu từ các mảnh phân tách (.part0, .part1, .part2).
Chỉ cần tối thiểu 2 mảnh bất kỳ của cùng một phiên backup để khôi phục 100% dữ liệu gốc.
Cách dùng:
    python restore_backup.py
"""

import os
import sys
from pathlib import Path

# Thêm đường dẫn dự án (thư mục cha) để có thể import mô-đun erasure_coding
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))
sys.path.append(str(current_dir.parent))

# Import mô-đun phục hồi dữ liệu dùng chung
from xor import restore_file_xor, MAGIC_HEADER


def restore_backup():
    print("==================================================")
    print("   💾 KIGUARD BACKUP RESTORE TOOL (AWS Style)   ")
    print("==================================================")
    
    parts = list(current_dir.glob("*.part*"))
    
    if not parts:
        # Check in temp_backup too
        temp_dir = current_dir / "temp_backup"
        if temp_dir.exists():
            parts = list(temp_dir.glob("*.part*"))
            
    if not parts:
        print("\n❌ Không tìm thấy mảnh dữ liệu (*.part*) nào trong thư mục hiện tại!")
        print("Vui lòng đặt ít nhất 2 mảnh phân tách (ví dụ: *.part0 và *.part2) vào cùng thư mục với script này.")
        input("\nNhấn Enter để thoát...")
        return
        
    print(f"\n🔍 Tìm thấy {len(parts)} mảnh dữ liệu:")
    for p in parts:
        print(f"  - {p.name} ({p.stat().st_size / 1024:.2f} KB)")
        
    # Trích xuất tên gốc của file từ mảnh đầu tiên tìm thấy
    orig_name = None
    for p in parts:
        name_parts = p.name.split(".part")
        if len(name_parts) > 1:
            orig_name = "".join(name_parts[:-1])
            break
            
    output_name = orig_name if orig_name else "restored_backup.zip"
    output_path = current_dir / output_name
    
    try:
        print(f"\n🟢 Đang giải mã và phục hồi dữ liệu bằng Erasure Coding...")
        # Gọi hàm phục hồi từ mô-đun dùng chung
        restore_file_xor(parts, output_path)
        
        print(f"\n🎉 KHÔI PHỤC THÀNH CÔNG!")
        print(f"📦 File zip gốc đã được tạo tại: {output_path.name}")
        print("💡 Bạn có thể giải nén file này để khôi phục thư mục data/")
    except Exception as e:
        print(f"\n❌ Thất bại: {e}")
        
    input("\nNhấn Enter để thoát...")


if __name__ == "__main__":
    restore_backup()
