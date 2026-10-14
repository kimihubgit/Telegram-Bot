"""
Star Gifts — Service cho /checkinfo
Lấy danh sách Star Gift của user qua Telethon MTProto API.
"""

from telethon.tl.functions.payments import GetSavedStarGiftsRequest
from telethon.utils import get_input_peer

from bot.connection import get_client, is_connected
from bot.services.telethon_user import resolve_user


async def get_user_gifts(user_id: int = None, username: str = None, limit: int = 10) -> dict | None:
    """
    Lấy danh sách Star Gift của user.
    Returns: {"count": int, "gifts": list[dict]} hoặc None
    """
    if not is_connected():
        return None

    client = get_client()

    try:
        entity = await resolve_user(user_id=user_id, username=username)
        if entity is None:
            return None

        input_peer = get_input_peer(entity)

        result = await client(GetSavedStarGiftsRequest(
            peer=input_peer,
            offset="",
            limit=limit,
        ))

        gifts_list = []
        for saved_gift in result.gifts:
            star_gift = getattr(saved_gift, "gift", None)

            gift_info = {
                "gift_id": getattr(star_gift, "id", None) if star_gift else None,
                "stars": getattr(star_gift, "stars", None) if star_gift else None,
                "limited": getattr(star_gift, "limited", False) if star_gift else False,
                "availability_total": getattr(star_gift, "availability_total", None) if star_gift else None,
                "availability_remains": getattr(star_gift, "availability_remains", None) if star_gift else None,
                "message": _extract_gift_message(saved_gift),
                "date": getattr(saved_gift, "date", None),
                "name_hidden": getattr(saved_gift, "name_hidden", False),
                "unsaved": getattr(saved_gift, "unsaved", False),
                "from_id": getattr(saved_gift, "from_id", None),
                "msg_id": getattr(saved_gift, "msg_id", None),
                "convert_stars": getattr(saved_gift, "convert_stars", None),
                "title": getattr(saved_gift, "title", None),
            }
            gifts_list.append(gift_info)

        return {
            "count": result.count,
            "gifts": gifts_list,
        }

    except Exception as e:
        print(f"⚠️ get_user_gifts failed: {e}")
        return None


def _extract_gift_message(saved_gift) -> str | None:
    """Trích xuất text tin nhắn kèm gift"""
    gift_msg = getattr(saved_gift, "message", None)
    if gift_msg:
        return getattr(gift_msg, "text", None) or str(gift_msg)
    return None
