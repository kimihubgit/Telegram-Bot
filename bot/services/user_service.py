from telegram import Update
from telegram.ext import ContextTypes
from bot.connection import is_connected
from bot.services.telethon_user import get_deep_user_info


# ID của các bot hệ thống Telegram (không phải người dùng thực)
SYSTEM_BOT_IDS = {
    1087968824,  # @GroupAnonymousBot — admin ẩn danh
    777000,      # Telegram Service Messages
    136817688,   # @Channel_Bot — kênh forward
}


async def get_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user=None):
    """
    Lấy thông tin chi tiết user từ User object (reply hoặc chính mình).
    Tự động enrich với Telethon nếu available.
    """
    user = target_user or update.effective_user
    chat = update.effective_chat
    is_group = chat.type in ("group", "supergroup")

    info = {
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "full_name": user.full_name or user.first_name or "",
        "id": user.id,
        "username": user.username,
        "language_code": user.language_code or "Unknown",
        "is_premium": bool(user.is_premium),
        "bio": None,
        "last_seen": None,
        "dc_id": None,
        "dc_location": None,
        "common_chats_count": None,
        "is_verified": False,
        "is_scam": False,
        "is_fake": False,
        "status": None,
        "join_date": None,
        "boost_count": 0,
        "profile_photo_file_id": None,
    }

    # Lấy status trong nhóm (Bot API)
    if is_group:
        try:
            member = await context.bot.get_chat_member(chat.id, user.id)
            info["status"] = member.status
        except Exception as e:
            print(f"⚠️ Không lấy được chat member info cho {user.id}: {e}")

    # Lấy ảnh đại diện (Bot API)
    try:
        photos = await context.bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count > 0:
            best_photo = photos.photos[0][-1]
            info["profile_photo_file_id"] = best_photo.file_id
    except Exception as e:
        print(f"⚠️ Không lấy được ảnh đại diện cho {user.id}: {e}")

    # Enrich với Telethon (thông tin sâu)
    telethon_chat_id = chat.id if is_group else None
    await _enrich_with_telethon(info, user_id=user.id, chat_id=telethon_chat_id)

    return info


async def get_user_info_by_id(context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int = None):
    """
    Lấy thông tin user bằng User ID.
    Ưu tiên get_chat_member (trong group), sau đó enrich bằng Telethon.
    """
    info = {
        "first_name": "",
        "last_name": "",
        "full_name": "",
        "id": user_id,
        "username": None,
        "language_code": "Unknown",
        "is_premium": False,
        "bio": None,
        "last_seen": None,
        "dc_id": None,
        "dc_location": None,
        "common_chats_count": None,
        "is_verified": False,
        "is_scam": False,
        "is_fake": False,
        "status": None,
        "join_date": None,
        "boost_count": 0,
        "profile_photo_file_id": None,
    }

    found = False

    # === Bước 1: Bot API — get_chat_member nếu trong group ===
    if chat_id:
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            user = member.user
            info["first_name"] = user.first_name or ""
            info["last_name"] = user.last_name or ""
            info["full_name"] = user.full_name or user.first_name or ""
            info["username"] = user.username
            info["language_code"] = user.language_code or "Unknown"
            info["is_premium"] = bool(user.is_premium)
            info["status"] = member.status
            found = True
        except Exception as e:
            print(f"⚠️ get_chat_member failed cho {user_id}: {e}")

    # === Bước 2: Bot API — get_chat để lấy bio ===
    try:
        chat_info = await context.bot.get_chat(user_id)
        if not found:
            first = chat_info.first_name or ""
            last = chat_info.last_name or ""
            info["first_name"] = first
            info["last_name"] = last
            info["full_name"] = f"{first} {last}".strip() or first
            info["username"] = chat_info.username
        if not info["bio"]:
            info["bio"] = chat_info.bio or None
        found = True
    except Exception as e:
        print(f"⚠️ get_chat failed cho {user_id}: {e}")

    # === Bước 3: Telethon — thông tin sâu ===
    telethon_found = await _enrich_with_telethon(info, user_id=user_id, chat_id=chat_id)
    if telethon_found:
        found = True

    # === Bước 4: Ảnh đại diện (Bot API) ===
    if found and not info["profile_photo_file_id"]:
        try:
            photos = await context.bot.get_user_profile_photos(user_id, limit=1)
            if photos.total_count > 0:
                best_photo = photos.photos[0][-1]
                info["profile_photo_file_id"] = best_photo.file_id
        except Exception:
            pass

    if not found:
        raise ValueError(f"Không tìm thấy user {user_id}")

    return info


async def get_user_info_by_username(context: ContextTypes.DEFAULT_TYPE, username: str, chat_id: int = None):
    """
    Lấy thông tin user bằng @username thông qua Telethon.
    Bot API không hỗ trợ resolve username cho user thường — chỉ Telethon làm được.
    """
    if not is_connected():
        raise ValueError("Telethon chưa kết nối — không thể check bằng @username")

    # Đảm bảo format đúng
    clean_username = username.lstrip("@")

    # Lấy deep info từ Telethon (truyền chat_id để hỗ trợ resolve)
    deep = await get_deep_user_info(username=clean_username, chat_id=chat_id)
    if not deep:
        raise ValueError(f"Không tìm thấy user @{clean_username}")

    user_id = deep["id"]

    info = {
        "first_name": deep["first_name"],
        "last_name": deep["last_name"],
        "full_name": deep["full_name"],
        "id": user_id,
        "username": deep["username"],
        "language_code": "Unknown",
        "is_premium": deep["is_premium"],
        "bio": deep["bio"],
        "last_seen": deep["last_seen"],
        "dc_id": deep["dc_id"],
        "dc_location": deep["dc_location"],
        "common_chats_count": deep["common_chats_count"],
        "is_verified": deep["is_verified"],
        "is_scam": deep["is_scam"],
        "is_fake": deep["is_fake"],
        "status": None,
        "join_date": None,
        "boost_count": 0,
        "profile_photo_file_id": None,
    }

    # Bot API: lấy status trong group + ảnh
    if chat_id:
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            info["status"] = member.status
        except Exception:
            pass

    # Ảnh đại diện (Bot API — compatible file_id)
    try:
        photos = await context.bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count > 0:
            best_photo = photos.photos[0][-1]
            info["profile_photo_file_id"] = best_photo.file_id
    except Exception:
        pass

    return info


async def _enrich_with_telethon(info: dict, user_id: int = None, username: str = None, chat_id: int = None) -> bool:
    """
    Bổ sung thông tin sâu từ Telethon vào dict info.
    Returns True nếu lấy được data.
    """
    deep = await get_deep_user_info(user_id=user_id, username=username, chat_id=chat_id)
    if not deep:
        return False

    # Bổ sung các field mà Bot API không có
    info["last_seen"] = deep["last_seen"]
    info["dc_id"] = deep["dc_id"]
    info["dc_location"] = deep["dc_location"]
    info["common_chats_count"] = deep["common_chats_count"]
    info["is_verified"] = deep["is_verified"]
    info["is_scam"] = deep["is_scam"]
    info["is_fake"] = deep["is_fake"]

    # Override bio nếu Telethon có (chính xác hơn)
    if deep["bio"]:
        info["bio"] = deep["bio"]

    # Override premium nếu Telethon có
    info["is_premium"] = deep["is_premium"]

    # Lấy thêm info cơ bản nếu thiếu
    if not info["full_name"] and deep["full_name"]:
        info["first_name"] = deep["first_name"]
        info["last_name"] = deep["last_name"]
        info["full_name"] = deep["full_name"]
    if not info["username"] and deep["username"]:
        info["username"] = deep["username"]

    return True


def get_status_display(status: str) -> str:
    """Map Telegram member status sang text hiển thị"""
    status_map = {
        "creator": "👑 Creator",
        "administrator": "🛡️ Administrator",
        "member": "✅ Member",
        "restricted": "⚠️ Restricted",
        "left": "🚪 Left",
        "kicked": "🚫 Banned",
    }
    return status_map.get(status, "❓ Unknown")

