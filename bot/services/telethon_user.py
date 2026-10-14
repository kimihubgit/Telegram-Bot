"""
Telethon User — Resolve & Deep Info
Resolve user entity và lấy thông tin chi tiết qua MTProto API.
"""

from telethon.tl.functions.users import GetFullUserRequest, GetUsersRequest
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import (
    UserStatusOnline,
    UserStatusOffline,
    UserStatusRecently,
    UserStatusLastWeek,
    UserStatusLastMonth,
    InputPeerUser,
    InputUser,
)

from bot.connection import get_client, is_connected


# ── Resolve user entity ──────────────────────────────────────

async def resolve_user(user_id: int = None, username: str = None, chat_id: int = None):
    """
    Resolve user entity qua nhiều phương pháp:
    username → cache → MTProto raw → group membership.
    Returns: User entity hoặc None
    """
    client = get_client()
    if not client:
        return None

    if username:
        try:
            return await client.get_entity(username)
        except Exception:
            pass

    if not user_id:
        return None

    try:
        return await client.get_entity(user_id)
    except (ValueError, KeyError):
        pass

    try:
        result = await client(GetUsersRequest([InputUser(user_id, 0)]))
        if result and result[0].id == user_id:
            return result[0]
    except Exception:
        pass

    try:
        full = await client(GetFullUserRequest(InputUser(user_id, 0)))
        if full.users:
            return full.users[0]
    except Exception:
        pass

    if chat_id:
        try:
            group = await client.get_entity(chat_id)
            result = await client(GetParticipantRequest(
                channel=group,
                participant=InputPeerUser(user_id, 0),
            ))
            if result.users:
                return result.users[0]
        except Exception:
            pass

    return None


# ── Deep user info ────────────────────────────────────────────

async def get_deep_user_info(user_id: int = None, username: str = None, chat_id: int = None) -> dict | None:
    """
    Lấy thông tin sâu về user qua MTProto API.
    Returns: dict hoặc None
    """
    if not is_connected():
        return None

    client = get_client()

    try:
        entity = await resolve_user(user_id=user_id, username=username, chat_id=chat_id)
        if entity is None:
            return None

        full = await client(GetFullUserRequest(entity))
        full_user = full.full_user
        user = full.users[0]

        dc_id = user.photo.dc_id if user.photo else None

        return {
            "id": user.id,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip() or "",
            "username": user.username,
            "phone": user.phone,
            "is_premium": bool(user.premium),
            "is_bot": bool(user.bot),
            "is_verified": bool(user.verified),
            "is_scam": bool(user.scam),
            "is_fake": bool(user.fake),
            "is_restricted": bool(user.restricted),
            "bio": full_user.about,
            "last_seen": _parse_last_seen(user.status),
            "dc_id": dc_id,
            "dc_location": _get_dc_location(dc_id) if dc_id else None,
            "common_chats_count": full_user.common_chats_count,
        }

    except Exception as e:
        print(f"⚠️ get_deep_user_info failed: {e}")
        return None


# ── Helpers ───────────────────────────────────────────────────

_STATUS_MAP = {
    UserStatusOnline: "🟢 Online ngay bây giờ",
    UserStatusRecently: "🔵 Gần đây (trong vài giờ)",
    UserStatusLastWeek: "🟡 Trong tuần qua",
    UserStatusLastMonth: "🟠 Trong tháng qua",
}

_DC_LOCATIONS = {
    1: "🇺🇸 Miami, USA (DC1)",
    2: "🇳🇱 Amsterdam, NL (DC2)",
    3: "🇺🇸 Miami, USA (DC3)",
    4: "🇳🇱 Amsterdam, NL (DC4)",
    5: "🇸🇬 Singapore (DC5)",
}


def _parse_last_seen(status) -> str:
    if status is None:
        return "🔒 Ẩn (Privacy)"
    for status_type, label in _STATUS_MAP.items():
        if isinstance(status, status_type):
            return label
    if isinstance(status, UserStatusOffline):
        if status.was_online:
            return f"⚪ Offline — lần cuối: {status.was_online.strftime('%d/%m/%Y %H:%M:%S')}"
        return "⚪ Offline"
    return "❓ Không xác định"


def _get_dc_location(dc_id: int) -> str:
    return _DC_LOCATIONS.get(dc_id, f"DC{dc_id}")
