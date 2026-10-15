"""
User Tracker Service (Hybrid MongoDB / JSON Fallback)
Theo dõi tất cả người dùng đã tương tác với bot (chỉ private chat).
Lưu trữ user_id, tên, username để sử dụng cho chức năng broadcast/notification.
"""
import json
import os
from pathlib import Path
import threading

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
KNOWN_USERS_FILE = DATA_DIR / "known_users.json"

from bot.database.mongo import db

_lock = threading.Lock()


def _load_json() -> dict:
    with _lock:
        if KNOWN_USERS_FILE.exists():
            try:
                with open(KNOWN_USERS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}


def _save_json(data: dict):
    with _lock:
        try:
            KNOWN_USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp = KNOWN_USERS_FILE.with_suffix(".tmp")
            with open(temp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            temp.replace(KNOWN_USERS_FILE)
        except Exception as e:
            print(f"⚠️ Lỗi ghi file known_users.json fallback: {e}")


def track_user(user_id: int, first_name: str = "", username: str = ""):
    """Ghi nhận 1 user đã tương tác với bot."""
    str_id = str(user_id)

    if db is not None:
        try:
            db.known_users.update_one(
                {"_id": str_id},
                {
                    "$set": {
                        "user_id": int(user_id) if str(user_id).isdigit() else user_id,
                        "first_name": first_name or "",
                        "username": username or "",
                    }
                },
                upsert=True
            )
            return
        except Exception as e:
            print(f"⚠️ [UserTracker] Lỗi MongoDB: {e}, fallback sang JSON")

    # Fallback JSON
    data = _load_json()
    data[str_id] = {
        "user_id": int(user_id) if str(user_id).isdigit() else user_id,
        "first_name": first_name or "",
        "username": username or "",
    }
    _save_json(data)


def get_all_user_ids() -> list[int]:
    """Trả về danh sách tất cả user IDs đã biết"""
    if db is not None:
        try:
            docs = db.known_users.find({}, {"_id": 1})
            return [int(doc["_id"]) for doc in docs if doc["_id"].isdigit()]
        except Exception as e:
            print(f"⚠️ [UserTracker] Lỗi đọc MongoDB: {e}, fallback sang JSON")

    data = _load_json()
    return [int(uid) for uid in data if uid.isdigit()]


def get_user_count() -> int:
    """Trả về số lượng users đã biết"""
    if db is not None:
        try:
            return db.known_users.count_documents({})
        except Exception as e:
            print(f"⚠️ [UserTracker] Lỗi count MongoDB: {e}, fallback sang JSON")

    data = _load_json()
    return len(data)


def remove_user(user_id: int):
    """Xóa user khỏi danh sách (ví dụ khi bot bị block)"""
    str_id = str(user_id)
    if db is not None:
        try:
            db.known_users.delete_one({"_id": str_id})
            return
        except Exception as e:
            print(f"⚠️ [UserTracker] Lỗi delete MongoDB: {e}, fallback sang JSON")

    data = _load_json()
    if str_id in data:
        del data[str_id]
        _save_json(data)
