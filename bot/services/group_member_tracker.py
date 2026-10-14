"""
Group Member Tracker Service (v2)
Lưu trữ thông tin thành viên theo cấu trúc nested:
- Mỗi user lưu current_info, danh sách groups, và changes history.
- Hỗ trợ theo dõi nhiều nhóm cùng lúc cho 1 user.
- Tự động ghi nhận thay đổi info (tên, username, premium...) vào changes[].

Cấu trúc:
{
    "user_id": {
        "current_info": {
            "first_name": "...",
            "full_name": "...",
            "username": "...",
            "is_premium": false
        },
        "groups": {
            "group_id": {
                "name": "Tên nhóm",
                "username": "nhom_username",
                "status": "member" / "left" / "kicked",
                "joined": "19/05/2026 21:00:00",
                "left": null
            }
        },
        "changes": [
            {
                "date": "19/05/2026 21:05:00",
                "changed_fields": { "username": "old_value" }
            }
        ]
    }
}
"""
import json
from datetime import datetime
from pathlib import Path
import threading

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
GROUP_MEMBERS_FILE = DATA_DIR / "members.json"

from bot.database.mongo import db


def _load_data() -> dict:
    """Load toàn bộ dữ liệu từ MongoDB (dạng dict tương thích ngược)"""
    docs = db.members.find()
    return {doc["_id"]: doc for doc in docs}


def _save_data(data: dict):
    """Lưu dữ liệu dạng bulk write vào MongoDB"""
    from pymongo import ReplaceOne
    operations = []
    for uid, udata in data.items():
        udata["_id"] = str(uid)
        operations.append(ReplaceOne({"_id": str(uid)}, udata, upsert=True))
    if operations:
        db.members.bulk_write(operations)


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
    """
    Ghi nhận user vào nhóm.
    - Nếu user chưa tồn tại → tạo mới với current_info + group entry.
    - Nếu user đã tồn tại → cập nhật current_info (nếu có thay đổi → ghi vào changes)
      + thêm/cập nhật group entry.
    """
    str_user_id = str(user_id)
    str_group_id = str(group_id)
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    new_info = {
        "first_name": first_name or "",
        "full_name": full_name or "",
        "username": username or "",
        "is_premium": is_premium,
    }

    user_doc = db.members.find_one({"_id": str_user_id})

    if not user_doc:
        # User mới hoàn toàn
        user_doc = {
            "_id": str_user_id,
            "current_info": new_info,
            "groups": {},
            "changes": [],
        }
    else:
        # User đã tồn tại → kiểm tra thay đổi info
        old_info = user_doc.get("current_info", {})
        changed_fields = {}

        for key in new_info:
            if old_info.get(key) != new_info[key]:
                # Lưu giá trị CŨ vào changes (để biết trước đó là gì)
                changed_fields[key] = old_info.get(key, "")

        if changed_fields:
            # Đảm bảo key "changes" tồn tại
            if "changes" not in user_doc:
                user_doc["changes"] = []

            user_doc["changes"].append({
                "date": now,
                "changed_fields": changed_fields,
            })

            # Giới hạn lưu tối đa 50 thay đổi gần nhất
            user_doc["changes"] = user_doc["changes"][-50:]

        # Cập nhật current_info
        user_doc["current_info"] = new_info

    # Đảm bảo key "groups" tồn tại
    if "groups" not in user_doc:
        user_doc["groups"] = {}

    # Thêm/cập nhật group entry
    user_doc["groups"][str_group_id] = {
        "name": group_name or "",
        "username": group_username or "",
        "status": "member",
        "joined": now,
        "left": None,
    }

    db.members.replace_one({"_id": str_user_id}, user_doc, upsert=True)


def track_member_leave(
    user_id: int,
    group_id: int = 0,
    status: str = "left",
):
    """
    Cập nhật khi user rời nhóm hoặc bị kick/ban.
    Chỉ cập nhật status và left cho group cụ thể.
    """
    str_user_id = str(user_id)
    str_group_id = str(group_id)

    user_doc = db.members.find_one({"_id": str_user_id})
    if not user_doc:
        return

    if "groups" not in user_doc:
        return

    if str_group_id not in user_doc["groups"]:
        return

    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    user_doc["groups"][str_group_id]["left"] = now
    user_doc["groups"][str_group_id]["status"] = status

    db.members.replace_one({"_id": str_user_id}, user_doc)


def get_all_members() -> dict:
    """Trả về toàn bộ danh sách thành viên"""
    return _load_data()


def get_member_count() -> tuple[int, int]:
    """
    Trả về (số thành viên hiện tại đang ở ít nhất 1 nhóm, tổng số user đã từng vào).
    """
    total = db.members.count_documents({})
    active = 0

    for doc in db.members.find({}, {"groups": 1}):
        groups = doc.get("groups", {})
        # User "active" nếu còn ở ít nhất 1 nhóm
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
    """
    Kiểm tra và cập nhật thông tin user nếu có thay đổi.
    Được gọi mỗi khi user gửi tin nhắn trong nhóm.

    Returns True nếu có thay đổi và đã cập nhật, False nếu không có gì thay đổi.
    """
    str_user_id = str(user_id)
    user_doc = db.members.find_one({"_id": str_user_id})

    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    new_info = {
        "first_name": first_name or "",
        "full_name": full_name or "",
        "username": username or "",
        "is_premium": is_premium,
    }

    if not user_doc:
        # User chưa có trong database -> khởi tạo mới để lưu lịch sử
        user_doc = {
            "_id": str_user_id,
            "current_info": new_info,
            "groups": {},
            "changes": [],
        }
        db.members.replace_one({"_id": str_user_id}, user_doc, upsert=True)
        return True

    # Lấy current_info (hỗ trợ cả format cũ: fields nằm ở top-level)
    if "current_info" in user_doc:
        old_info = user_doc["current_info"]
    else:
        # Format cũ → migrate: đọc fields từ top-level
        old_info = {
            "first_name": user_doc.get("first_name", ""),
            "full_name": user_doc.get("full_name", ""),
            "username": user_doc.get("username", ""),
            "is_premium": user_doc.get("is_premium", False),
        }

    # So sánh từng field
    changed_fields = {}
    for key in new_info:
        if old_info.get(key) != new_info[key]:
            # Lưu giá trị CŨ vào changes
            changed_fields[key] = old_info.get(key, "")

    if not changed_fields:
        return False  # Không có thay đổi

    # Ghi nhận thay đổi vào changes[]
    if "changes" not in user_doc:
        user_doc["changes"] = []

    user_doc["changes"].append({
        "date": now,
        "changed_fields": changed_fields,
    })

    # Giới hạn tối đa 50 thay đổi
    user_doc["changes"] = user_doc["changes"][-50:]

    # Cập nhật current_info (dùng format mới)
    user_doc["current_info"] = new_info

    # Dọn dẹp fields cũ ở top-level nếu còn sót (migrate)
    for old_key in ["first_name", "full_name", "username", "is_premium"]:
        if old_key in user_doc and old_key != "current_info":
            del user_doc[old_key]

    db.members.replace_one({"_id": str_user_id}, user_doc)
    return True
