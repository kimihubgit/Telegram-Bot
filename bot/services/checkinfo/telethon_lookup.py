"""
Telethon Lookup — Service cho /checkinfo
Lấy thông tin chi tiết User hoặc Channel/Group qua Telethon MTProto API.
Dùng cho check bằng username hoặc link (không phải ID số).
"""

from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import User, Channel

from bot.connection import get_client, is_connected

from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
from telethon.tl.functions.users import GetFullUserRequest


# ── Lookup by username ────────────────────────────────────────

async def lookup_by_username(username: str) -> dict | None:
    """
    Tra cứu entity bằng username qua Telethon.
    Tự động phân loại User hay Channel/Group rồi trả về dict thông tin đầy đủ.
    
    Args:
        username: Username (có hoặc không có @), hoặc invite link dạng +XXXX
    Returns:
        dict chứa thông tin hoặc None nếu thất bại
    """
    if not is_connected():
        return None

    client = get_client()

    try:
        # Chuẩn hóa username
        target = username.strip()
        if not target.startswith("@") and not target.startswith("+"):
            target = f"@{target}"

        entity = await client.get_entity(target)

        if isinstance(entity, User):
            return await _get_full_user_info(client, entity)
        elif isinstance(entity, Channel):
            return await _get_full_channel_info(client, entity)
        else:
            return {
                "type": "unknown",
                "error": "Đối tượng không phải User hay Channel/Group.",
            }

    except Exception as e:
        print(f"⚠️ lookup_by_username failed for '{username}': {e}")
        return None


async def _get_full_user_info(client, entity) -> dict:
    """Lấy thông tin chi tiết User bằng GetFullUserRequest"""
    full_user_data = await client(GetFullUserRequest(entity))
    full_user = full_user_data.full_user
    user = full_user_data.users[0]

    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    # Phân loại tài khoản
    if user.bot:
        account_type = "🤖 BOT (Tài khoản tự động)"
    else:
        account_type = "👤 USER (Người dùng thật)"

    return {
        "type": "user",
        "id": user.id,
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "username": user.username,
        "phone": f"+{user.phone}" if user.phone else None,
        "bio": full_user.about,

        "account_type": account_type,
        "is_premium": bool(user.premium),
        "is_bot": bool(user.bot),
        "is_verified": bool(user.verified),
        "is_scam": bool(user.scam),
        "is_fake": bool(user.fake),
        "is_restricted": bool(user.restricted),
        "common_chats_count": full_user.common_chats_count,
    }


async def _get_full_channel_info(client, entity) -> dict:
    """Lấy thông tin chi tiết Channel/Group bằng GetFullChannelRequest"""
    channel_full = await client(GetFullChannelRequest(entity))
    full_chat = channel_full.full_chat
    main_channel = channel_full.chats[0]

    title = main_channel.title
    username = main_channel.username if main_channel.username else None
    about = full_chat.about if full_chat.about else None
    members = full_chat.participants_count

    # Ngày tạo channel
    created_date = main_channel.date
    formatted_date = created_date.strftime("%d/%m/%Y %H:%M:%S") if created_date else None

    # Phân loại: Channel hay Megagroup (Supergroup)
    if getattr(main_channel, 'megagroup', False):
        channel_type = "👥 Supergroup (Nhóm siêu cấp)"
    elif getattr(main_channel, 'gigagroup', False):
        channel_type = "🏟️ Broadcast Group"
    elif getattr(main_channel, 'broadcast', False):
        channel_type = "📢 Channel (Kênh)"
    else:
        channel_type = "👥 Group (Nhóm)"

    return {
        "type": "channel",
        "id": main_channel.id,
        "title": title,
        "username": username,
        "about": about,
        "members_count": members,
        "channel_type": channel_type,
        "created_date": formatted_date,
        "is_verified": bool(getattr(main_channel, 'verified', False)),
        "is_scam": bool(getattr(main_channel, 'scam', False)),
        "is_fake": bool(getattr(main_channel, 'fake', False)),
        "is_restricted": bool(getattr(main_channel, 'restricted', False)),
    }


# ── Lookup by phone ───────────────────────────────────────────

async def lookup_by_phone(phone: str) -> dict | None:
    """
    Tra cứu Telegram account bằng số điện thoại.
    Dùng ImportContactsRequest để resolve, sau đó tự xóa khỏi danh bạ.

    Args:
        phone: Số điện thoại (có hoặc không có +, VD: +84912345678 hoặc 0912345678)
    Returns:
        dict thông tin user hoặc None nếu không tìm thấy
    """
    if not is_connected():
        return None

    client = get_client()

    try:
        

        # Chuẩn hóa số điện thoại về dạng quốc tế
        formatted = phone.strip()
        if formatted.startswith("0"):
            formatted = "+84" + formatted[1:]
        elif not formatted.startswith("+"):
            formatted = "+" + formatted

        contact = InputPhoneContact(
            client_id=0,
            phone=formatted,
            first_name="Check",
            last_name="",
        )

        result = await client(ImportContactsRequest(contacts=[contact]))

        if not result.users:
            # Không tìm thấy hoặc user chặn tìm kiếm bằng SĐT
            return {"found": False, "phone": formatted}

        user = result.users[0]

        # Lấy thêm bio qua GetFullUserRequest
        bio = None
        dc_id = None
        try:
            
            full_data = await client(GetFullUserRequest(user))
            bio = full_data.full_user.about
            dc_id = user.photo.dc_id if user.photo else None
        except Exception:
            pass

        # Phân loại tài khoản
        account_type = "🤖 BOT" if user.bot else "👤 USER"

        info = {
            "found": True,
            "type": "user",
            "id": user.id,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "username": user.username,
            "phone_input": formatted,
            "phone_resolved": f"+{user.phone}" if user.phone else formatted,
            "bio": bio,
            "account_type": account_type,
            "is_premium": bool(user.premium),
            "is_bot": bool(user.bot),
            "is_verified": bool(user.verified),
            "is_scam": bool(user.scam),
            "is_fake": bool(user.fake),
            "dc_id": dc_id,
        }

        # Tự xóa contact khỏi danh bạ sau khi check
        try:
            await client(DeleteContactsRequest(id=[user]))
        except Exception:
            pass

        return info

    except Exception as e:
        print(f"⚠️ lookup_by_phone failed for '{phone}': {e}")
        return None
