"""
KiGuard Erasure Coding (XOR 2+1) Module
Mô-đun chịu trách nhiệm phân tách và tái cấu trúc dữ liệu theo thuật toán Erasure Coding.
Công nghệ tương tự cơ chế đảm bảo độ bền dữ liệu của AWS S3.
"""

from datetime import datetime
from pathlib import Path

MAGIC_HEADER = b"KGBK"


def split_file_xor(file_path: Path | str, output_dir: Path | str) -> list[Path]:
    """
    Phân tách file gốc thành 3 mảnh dựa trên thuật toán XOR 2+1.
    - Mảnh A (part0): 50% dữ liệu đầu.
    - Mảnh B (part1): 50% dữ liệu sau (padded byte 0 nếu lẻ).
    - Mảnh C (part2): Mảnh dự phòng = A XOR B.
    
    Header mỗi mảnh: MAGIC (4B) + ID mảnh (1B) + Session ID (8B) + Cỡ file gốc (8B).
    """
    file_path = Path(file_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    with open(file_path, "rb") as f:
        data = f.read()
        
    orig_size = len(data)
    half = (orig_size + 1) // 2
    
    part_a = data[:half]
    part_b = data[half:]
    
    # Pad mảnh B với byte 0 để bằng chiều dài mảnh A
    part_b_padded = part_b + b'\x00' * (len(part_a) - len(part_b))
    
    # Tạo mảnh C = A XOR B
    part_c = bytes(x ^ y for x, y in zip(part_a, part_b_padded))
    
    # Tạo Session ID duy nhất đại diện cho phiên backup này (Timestamp)
    session_id = int(datetime.now().timestamp())
    
    shards = [part_a, part_b_padded, part_c]
    shard_paths = []
    
    for shard_id, shard_data in enumerate(shards):
        shard_path = output_dir / f"{file_path.name}.part{shard_id}"
        with open(shard_path, "wb") as f:
            f.write(MAGIC_HEADER)
            f.write(bytes([shard_id]))
            f.write(session_id.to_bytes(8, byteorder="big"))
            f.write(orig_size.to_bytes(8, byteorder="big"))
            f.write(shard_data)
        shard_paths.append(shard_path)
        
    return shard_paths


def restore_file_xor(shard_paths: list[Path | str], target_path: Path | str) -> Path:
    """
    Khôi phục file gốc từ danh sách các mảnh phân tách (.part*).
    Chỉ cần tối thiểu 2 mảnh khác nhau của cùng một phiên backup (Session ID).
    """
    shards = {}
    orig_size = None
    session_ids = set()
    
    for path in shard_paths:
        path = Path(path)
        if not path.exists():
            continue
            
        with open(path, "rb") as f:
            magic = f.read(4)
            if magic != MAGIC_HEADER:
                continue
            shard_id = int(f.read(1)[0])
            session_id = int.from_bytes(f.read(8), byteorder="big")
            orig_size = int.from_bytes(f.read(8), byteorder="big")
            shard_data = f.read()
            
            shards[shard_id] = shard_data
            session_ids.add(session_id)
            
    if len(shards) < 2:
        raise ValueError("❌ Thất bại: Cần tối thiểu 2 mảnh hợp lệ để khôi phục dữ liệu!")
        
    if len(session_ids) > 1:
        raise ValueError("❌ Lỗi bảo mật: Các mảnh thuộc các phiên backup khác nhau, không thể ghép!")

    has_a = 0 in shards
    has_b = 1 in shards
    has_c = 2 in shards
    
    if has_a and has_b:
        data_a = shards[0]
        data_b = shards[1]
    elif has_a and has_c:
        data_a = shards[0]
        data_c = shards[2]
        data_b = bytes(x ^ y for x, y in zip(data_a, data_c))
    elif has_b and has_c:
        data_b = shards[1]
        data_c = shards[2]
        data_a = bytes(x ^ y for x, y in zip(data_b, data_c))
    else:
        raise ValueError("❌ Mảnh dữ liệu không hợp lệ hoặc bị trùng lặp!")
        
    combined_data = (data_a + data_b)[:orig_size]
    
    target_path = Path(target_path)
    with open(target_path, "wb") as f:
        f.write(combined_data)
        
    return target_path
