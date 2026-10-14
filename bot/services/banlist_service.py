"""
Ban List Service
Quản lý danh sách cấm người dùng.

Mức độ vi phạm:
  - "scam"     : Lừa đảo       → Ban (kick + cấm vào lại)
  - "fake_bio" : Giả mạo Bio   → Ban (kick + cấm vào lại)
  - "spam"     : Spam           → Mute vĩnh viễn (cấm chat, vẫn ở trong nhóm)

File dữ liệu: data/banlist.json
"""
import json
from datetime import datetime
from pathlib import Path
import threading

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
BANLIST_FILE = DATA_DIR / "banlist.json"

from bot.database.mongo import db

# Mức độ nào sẽ bị BAN (kick khỏi nhóm)
BAN_SEVERITIES = {"scam", "fake_bio", "left_group"}
# Mức độ nào sẽ bị MUTE (cấm chat vĩnh viễn)
MUTE_SEVERITIES = {"spam"}


_cached_data = None
_write_lock = threading.Lock()


# def _load_data() -> dict:
#     """Load dữ liệu từ file JSON (có sử dụng memory cache)"""
#     global _cached_data
#     if _cached_data is not None:
#         return _cached_data

#     if not BANLIST_FILE.exists():
#         _cached_data = {"users": {}, "severity_levels": {}}
#         return _cached_data
#     try:
#         with open(BANLIST_FILE, "r", encoding="utf-8") as f:
#             _cached_data = json.load(f)
#     except (json.JSONDecodeError, IOError):
#         _cached_data = {"users": {}, "severity_levels": {}}
#     return _cached_data


# def _save_data(data: dict):
#     global _cached_data
#     _cached_data = data
#     DATA_DIR.mkdir(parents=True, exist_ok=True)
#     with _write_lock:
#         try:
#             with open(BANLIST_FILE, "w", encoding="utf-8") as f:
#                 json.dump(data, f, ensure_ascii=False, indent=2)
#         except Exception as e:
#             print(f"⚠️ Lỗi ghi file banlist.json: {e}")


def add_user(
    user_id: int,
    severity: str,
    reason: str = "",
    added_by: str = "admin",
) -> bool:
    """
    Thêm user vào danh sách cấm.
    severity: "scam", "fake_bio", "spam"
    Returns True nếu thêm thành công.
    """
    if severity not in (BAN_SEVERITIES | MUTE_SEVERITIES):
        return False

    str_id = str(user_id)
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    db.banlist.update_one(
        {"_id": str_id},
        {
            "$set": {
                "user_id": int(user_id) if str(user_id).isdigit() else user_id,
                "severity": severity,
                "reason": reason,
                "added_by": added_by,
                "added_date": now,
            }
        },
        upsert=True
    )
    return True


def remove_user(user_id: int) -> bool:
    """Xóa user khỏi danh sách cấm. Returns True nếu có user để xóa."""
    str_id = str(user_id)
    res = db.banlist.delete_one({"_id": str_id})
    return res.deleted_count > 0


def check_user(user_id: int) -> dict | None:
    """
    Kiểm tra user có trong danh sách cấm không.
    Returns dict {"severity", "reason", "action"} hoặc None.
    """
    str_id = str(user_id)
    entry = db.banlist.find_one({"_id": str_id})
    if not entry:
        return None

    severity = entry.get("severity", "")
    severity_lower = severity.lower() if severity else ""

    if severity_lower in BAN_SEVERITIES:
        action = "ban"
    elif severity_lower in MUTE_SEVERITIES:
        action = "mute"
    else:
        action = "unknown"

    return {
        "severity": severity,
        "reason": entry.get("reason", ""),
        "action": action,
        "added_by": entry.get("added_by", ""),
        "added_date": entry.get("added_date", ""),
    }


def get_all_banned() -> dict:
    """Trả về toàn bộ danh sách cấm."""
    docs = db.banlist.find()
    return {doc["_id"]: doc for doc in docs}


def get_severity_label(severity: str) -> str:
    """Trả về label tiếng Việt của mức độ vi phạm."""
    labels = {
        "scam": "🔴 Lừa đảo",
        "fake_bio": "🟠 Giả mạo Bio",
        "spam": "🟡 Spam",
        "left_group": "🚪 Tự rời nhóm",
    }
    return labels.get(severity.lower() if severity else "", severity)
