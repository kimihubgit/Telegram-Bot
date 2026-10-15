"""
Group Member Tracker Service (v2 - Hybrid MongoDB / JSON Fallback)
Lưu trữ thông tin thành viên theo cấu trúc nested:
- Mỗi user lưu current_info, danh sách groups, và changes history.
- Hỗ trợ theo dõi nhiều nhóm cùng lúc cho 1 user.
- Tự động ghi nhận thay đổi info (tên, username, premium...) vào changes[].
- Tự động chuyển đổi mượt mà giữa MongoDB và File JSON cục bộ nếu DB mất kết nối.
"""
import json
import os
from datetime import datetime
from pathlib import Path
import threading

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
GROUP_MEMBERS_FILE = DATA_DIR / "members.json"

from bot.database.mongo import db

_local_lock = threading.Lock()


def _load_data() -> dict:
    """Load toàn bộ dữ liệu từ MongoDB hoặc fallback sang members.json"""
    if db is not None:
        try:
            docs = db.members.find()
            return {doc["_id"]: doc for doc in docs}
        except Exception as e:
            print(f"⚠️ [Tracker] Lỗi đọc MongoDB: {e}, chuyển sang file JSON")

    with _local_lock:
        if GROUP_MEMBERS_FILE.exists():
            try:
                with open(GROUP_MEMBERS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def _save_data(data: dict):
    """Lưu dữ liệu vào MongoDB hoặc fallback sang members.json an toàn"""
    if db is not None:
        try:
            from pymongo import ReplaceOne
            operations = []
            for uid, udata in data.items():
                udata["_id"] = str(uid)
                operations.append(ReplaceOne({"_id": str(uid)}, udata, upsert=True))
            if operations:
                db.members.bulk_write(operations)
            return
        except Exception as e:
            print(f"⚠️ [Tracker] Lỗi ghi MongoDB: {e}, fallback sang JSON")

    with _local_lock:
        try:
            GROUP_MEMBERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp = GROUP_MEMBERS_FILE.with_suffix(".tmp")
            with open(temp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            temp.replace(GROUP_MEMBERS_FILE)
        except Exception as e:
            print(f"⚠️ Lỗi ghi fallback members.json: {e}")


def _get_user_doc(str_user_id: str) -> dict | None:
    if db is not None:
        try:
            return db.members.find_one({"_id": str_user_id})
        except Exception:
            pass
    data = _load_data()
    return data.get(str_user_id)


def _save_user_doc(str_user_id: str, user_doc: dict):
    if db is not None:
        try:
            db.members.replace_one({"_id": str_user_id}, user_doc, upsert=True)
            return
        except Exception:
            pass
    data = _load_data()
    data[str_user_id] = user_doc
    _save_data(data)


def track_member_join(
    user_id: int,
    first_name: str = "",
    full_name: str = "",
    username: str = "",
    is_premium: bool = False,
    group_id: int = 0,
    group_name: str = "",
    group_username: str = "",
):
    """Ghi nhận user vào nhóm."""
    str_user_id = str(user_id)
    str_group_id = str(group_id)
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    new_info = {
        "first_name": first_name or "",
        "full_name": full_name or "",
        "username": username or "",
        "is_premium": is_premium,
    }

    user_doc = _get_user_doc(str_user_id)

    if not user_doc:
        user_doc = {
            "_id": str_user_id,
            "current_info": new_info,
            "groups": {},
            "changes": [],
        }
    else:
        old_info = user_doc.get("current_info", {})
        changed_fields = {}

        for key in new_info:
            if old_info.get(key) != new_info[key]:
                changed_fields[key] = old_info.get(key, "")

        if changed_fields:
            if "changes" not in user_doc:
                user_doc["changes"] = []

            user_doc["changes"].append({
                "date": now,
                "changed_fields": changed_fields,
            })
            user_doc["changes"] = user_doc["changes"][-50:]

        user_doc["current_info"] = new_info

    if "groups" not in user_doc:
        user_doc["groups"] = {}

    user_doc["groups"][str_group_id] = {
        "name": group_name or "",
        "username": group_username or "",
        "status": "member",
        "joined": now,
        "left": None,
    }

    _save_user_doc(str_user_id, user_doc)


def track_member_leave(
    user_id: int,
    group_id: int = 0,
    status: str = "left",
):
    """Cập nhật khi user rời nhóm hoặc bị kick/ban."""
    str_user_id = str(user_id)
    str_group_id = str(group_id)

    user_doc = _get_user_doc(str_user_id)
    if not user_doc or "groups" not in user_doc or str_group_id not in user_doc["groups"]:
        return

    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    user_doc["groups"][str_group_id]["left"] = now
    user_doc["groups"][str_group_id]["status"] = status

    _save_user_doc(str_user_id, user_doc)


def get_all_members() -> dict:
    """Trả về toàn bộ danh sách thành viên"""
    return _load_data()


def get_member_count() -> tuple[int, int]:
    """Trả về (số thành viên active, tổng số user từng vào)."""
    data = _load_data()
    total = len(data)
    active = 0
    for doc in data.values():
        groups = doc.get("groups", {})
        if any(g.get("status") == "member" for g in groups.values()):
            active += 1
    return active, total


def update_member_info(
    user_id: int,
    first_name: str = "",
    full_name: str = "",
    username: str = "",
    is_premium: bool = False,
) -> bool:
    """Kiểm tra và cập nhật thông tin user nếu có thay đổi."""
    str_user_id = str(user_id)
    user_doc = _get_user_doc(str_user_id)
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    new_info = {
        "first_name": first_name or "",
        "full_name": full_name or "",
        "username": username or "",
        "is_premium": is_premium,
    }

    if not user_doc:
        user_doc = {
            "_id": str_user_id,
            "current_info": new_info,
            "groups": {},
            "changes": [],
        }
        _save_user_doc(str_user_id, user_doc)
        return True

    old_info = user_doc.get("current_info", {})
    changed_fields = {}
    for key in new_info:
        if old_info.get(key) != new_info[key]:
            changed_fields[key] = old_info.get(key, "")

    if not changed_fields:
        return False

    if "changes" not in user_doc:
        user_doc["changes"] = []

    user_doc["changes"].append({
        "date": now,
        "changed_fields": changed_fields,
    })
    user_doc["changes"] = user_doc["changes"][-50:]
    user_doc["current_info"] = new_info

    for old_key in ["first_name", "full_name", "username", "is_premium"]:
        if old_key in user_doc and old_key != "current_info":
            del user_doc[old_key]

    _save_user_doc(str_user_id, user_doc)
    return True
