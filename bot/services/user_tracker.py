"""
User Tracker Service
Theo dõi tất cả người dùng đã tương tác với bot (chỉ private chat).

Lưu trữ user_id, tên, username vào data/known_users.json
để sử dụng cho chức năng broadcast/notification.
"""
import json
import os
from pathlib import Path
import threading

# Đường dẫn file lưu danh sách users
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
KNOWN_USERS_FILE = DATA_DIR / "known_users.json"


from bot.database.mongo import db


def track_user(user_id: int, first_name: str = "", username: str = ""):
    """
    Ghi nhận 1 user đã tương tác với bot.
    Chỉ lưu user cá nhân (không lưu group/channel).
    """
    str_id = str(user_id)

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


def get_all_user_ids() -> list[int]:
    """Trả về danh sách tất cả user IDs đã biết"""
    docs = db.known_users.find({}, {"_id": 1})
    return [int(doc["_id"]) for doc in docs if doc["_id"].isdigit()]


def get_user_count() -> int:
    """Trả về số lượng users đã biết"""
    return db.known_users.count_documents({})


def remove_user(user_id: int):
    """Xóa user khỏi danh sách (ví dụ khi bot bị block)"""
    str_id = str(user_id)
    db.known_users.delete_one({"_id": str_id})
