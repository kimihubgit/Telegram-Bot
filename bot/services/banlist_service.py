"""
Ban List Service (Hybrid MongoDB / JSON Fallback)
Quản lý danh sách cấm người dùng:
- scam: Lừa đảo -> Ban (kick + cấm vào lại)
- fake_bio: Giả mạo Bio -> Ban (kick + cấm vào lại)
- spam: Spam -> Mute vĩnh viễn (cấm chat)
- Tự động fallback sang data/banlist.json khi MongoDB chưa khởi chạy.
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


def _load_json_data() -> dict:
    """Load dữ liệu từ file JSON (có sử dụng memory cache)"""
    global _cached_data
    with _write_lock:
        if _cached_data is not None:
            return _cached_data

        if not BANLIST_FILE.exists():
            _cached_data = {"users": {}, "severity_levels": {}}
            return _cached_data
        try:
            with open(BANLIST_FILE, "r", encoding="utf-8") as f:
                _cached_data = json.load(f)
        except Exception:
            _cached_data = {"users": {}, "severity_levels": {}}
        return _cached_data


def _save_json_data(data: dict):
    global _cached_data
    _cached_data = data
    with _write_lock:
        try:
            BANLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp = BANLIST_FILE.with_suffix(".tmp")
            with open(temp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            temp.replace(BANLIST_FILE)
        except Exception as e:
            print(f"⚠️ Lỗi ghi file banlist.json fallback: {e}")


def add_user(
    user_id: int,
    severity: str,
    reason: str = "",
    added_by: str = "admin",
) -> bool:
    """Thêm user vào danh sách cấm."""
    if severity not in (BAN_SEVERITIES | MUTE_SEVERITIES):
        return False

    str_id = str(user_id)
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    if db is not None:
        try:
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
        except Exception as e:
            print(f"⚠️ [Banlist] Lỗi ghi MongoDB: {e}, fallback sang JSON")

    # Fallback JSON
    data = _load_json_data()
    data.setdefault("users", {})[str_id] = {
        "severity": severity,
        "reason": reason,
        "added_by": added_by,
        "added_date": now,
    }
    _save_json_data(data)
    return True


def remove_user(user_id: int) -> bool:
    """Xóa user khỏi danh sách cấm."""
    str_id = str(user_id)
    if db is not None:
        try:
            res = db.banlist.delete_one({"_id": str_id})
            return res.deleted_count > 0
        except Exception as e:
            print(f"⚠️ [Banlist] Lỗi xóa MongoDB: {e}, fallback sang JSON")

    # Fallback JSON
    data = _load_json_data()
    users = data.get("users", {})
    if str_id in users:
        del users[str_id]
        _save_json_data(data)
        return True
    return False


def check_user(user_id: int) -> dict | None:
    """Kiểm tra user có trong danh sách cấm không."""
    str_id = str(user_id)
    entry = None

    if db is not None:
        try:
            entry = db.banlist.find_one({"_id": str_id})
        except Exception as e:
            print(f"⚠️ [Banlist] Lỗi query MongoDB: {e}, fallback sang JSON")

    if not entry:
        data = _load_json_data()
        entry = data.get("users", {}).get(str_id)

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
    if db is not None:
        try:
            docs = db.banlist.find()
            return {doc["_id"]: doc for doc in docs}
        except Exception as e:
            print(f"⚠️ [Banlist] Lỗi load MongoDB: {e}, fallback sang JSON")

    data = _load_json_data()
    return data.get("users", {})


def get_severity_label(severity: str) -> str:
    """Trả về label tiếng Việt của mức độ vi phạm."""
    labels = {
        "scam": "🔴 Lừa đảo",
        "fake_bio": "🟠 Giả mạo Bio",
        "spam": "🟡 Spam",
        "left_group": "🚪 Tự rời nhóm",
    }
    return labels.get(severity.lower() if severity else "", severity)
