"""
/checkinfo Command
Hỗ trợ 4 kiểu tra cứu:
  1. Check bằng Username (@username) → Telethon
  2. Check bằng Link (https://t.me/xxxx) → trích username → Telethon
  3. Check bằng ID số → Rose Bot (phụ trợ) + Gift
  4. Check bằng SĐT (+84xxx) → Telethon

Kết quả hiển thị đầy đủ thông tin tùy loại tra cứu.
"""
from bot.utils.rate_limiter import daily_limit
from numpy import rint
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
from bot.services.checkinfo.rose_query import query_rose_bot
from bot.services.checkinfo.gifts import get_user_gifts
from bot.services.checkinfo.telethon_lookup import lookup_by_username, lookup_by_phone
from bot.config import Config
from telegram.constants import ParseMode
from bot.utils.logger import log_from_update
from bot.utils.rate_limiter import rate_limit
from bot.services.scoring import calculate_scores
import requests
import urllib.parse
import re
import asyncio

# ── Regex trích xuất username từ link Telegram ────────────────
# Hỗ trợ: https://t.me/username, http://t.me/username, t.me/username
# Cũng hỗ trợ invite link: https://t.me/+XXXX
_TG_LINK_PATTERN = re.compile(
    r"(?:https?://)?t\.me/(\+?[a-zA-Z0-9_]+)",
    re.IGNORECASE,
)
# _PHONE_PATTERN = re.compile(r"^\+?[0-9]{9,14}$")
_PHONE_PATTERN = re.compile(r"^\+[0-9]{9,14}$")
_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def _extract_username_from_link(text: str) -> str | None:
    """Trích xuất username hoặc invite hash từ link t.me"""
    match = _TG_LINK_PATTERN.match(text.strip())
    if match:
        return match.group(1)  # Trả về username (không có @) hoặc +hash
    return None


def _detect_query_type(query: str) -> tuple[str, str]:
    """
    Phân loại input thành:
      ("link", extracted_username)  — nếu là link t.me
      ("username", clean_username)  — nếu bắt đầu bằng @
      ("phone", phone_number)        — nếu là SĐT quốc tế
      ("email", email_address)       — nếu là email
      ("id", raw_id_string)         — nếu là số ID
      ("invalid", original_query)   — không hợp lệ
    """
    q = query.strip()

    # 1. Check link Telegram
    extracted = _extract_username_from_link(q)
    if extracted:
        return ("link", extracted)

    # 2. Check username (bắt đầu bằng @)
    if q.startswith("@") and len(q) > 1:
        return ("username", q[1:])  # bỏ @
    # 3. check số điện thoại
    if _PHONE_PATTERN.match(q):
        return ("phone", q)
    # 4. check email
    if _EMAIL_PATTERN.match(q):
        return ("email", q)
    # 5. check id
    if q.isdigit():
        return ("id", q)
    # 6. trường hợp ngoại lệ 
    return ("invalid", q)


@rate_limit(seconds=10)
async def checkinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /checkinfo — phân loại input rồi tra cứu phù hợp"""
    log_from_update(update)

    # Xác định target
    query = None
    query_type = None
    query_value = None

    # Từ argument
    if context.args and len(context.args) >= 1:
        query = context.args[0]
        query_type, query_value = _detect_query_type(query)

        if query_type == "invalid":
            await update.message.reply_text(
                "⚠️ <b>Sai định dạng!</b>\n\n"
                "Hỗ trợ các dạng:\n"
                "• <code>@username</code> (Username Telegram)\n"
                "• <code>https://t.me/username</code> (Link Telegram)\n"
                "• <code>123456789</code> (ID Telegram)\n"
                "• <code>+84xxxxxxxx</code> (Mã Quốc Gia + SDT)\n"
                "• <code>example@gmail.com</code> (Địa chỉ Email)\n"
                "• reply tin nhắn bất kì + gõ <code>/checkinfo</code>\n",
                parse_mode="HTML",
            )
            return

    # Từ reply
    elif update.message.reply_to_message and update.message.reply_to_message.from_user:
        reply_user = update.message.reply_to_message.from_user
        query = str(reply_user.id)
        query_type = "id"
        query_value = query
    else:
        await update.message.reply_text(
            "⚠️ <b>Cách Dùng Lệnh CheckInfo:</b>\n\n"
            "• <code>/checkinfo @username</code> — check bằng username\n"
            "• <code>/checkinfo https://t.me/username</code> — check bằng link\n"
            "• <code>/checkinfo 123456789</code> — check bằng User ID\n"
            "• <code>/checkinfo +84xxxxxxxx</code> — check bằng SDT (Mã Quốc Gia + SDT)\n"
            "• <code>/checkinfo example@gmail.com</code> — check bằng Email\n"
            "• Reply tin nhắn bất kỳ + <code>/checkinfo</code> — check qua tin nhắn reply\n\n"
            "📡 <i>Lệnh tra cứu thông tin từ database Telegram</i>",
            parse_mode="HTML",
        )
        return

    processing_msg = await update.message.reply_text("🔄 Đang truy vấn database Telegram...")

    if query_type in ("username", "link"):
        await _check_by_username(update, processing_msg, query_value)

    elif query_type == "phone":
        await _check_by_phone(update, processing_msg, query_value)

    elif query_type == "email":
        await _check_by_email(update, processing_msg, query_value)

    elif query_type == "id":
        await _check_by_id(update, processing_msg, query, query_value)


# ══════════════════════════════════════════════════════════════
#  CHECK BY EMAIL (HaveIBeenPwned API)
# ══════════════════════════════════════════════════════════════
@daily_limit(max_uses=10)
@rate_limit(seconds=10)
async def _check_by_email(update: Update, processing_msg, email: str):
    """Check bằng email bằng cách gọi ChongLuaDao API và định dạng kết quả đẹp mắt"""

    # 1. Truy vấn API ChongLuaDao
    encoded_email = urllib.parse.quote(email)
    url = f"https://feeds.chongluadao.vn/checkbreach/email?q={encoded_email}&lang=vi"

    headers = {
        'sec-ch-ua-platform': '"Android"',
        'Referer': f'https://chongluadao.vn/analyze/?q={encoded_email}&type=email',
        'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        'Content-Type': 'application/json',
        'sec-ch-ua-mobile': '?1',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36'
    }

    def do_request():
        try:
            return requests.get(url, headers=headers, timeout=10)
        except Exception as e:
            print(f"⚠️ ChongLuaDao Request error: {e}")
            return None

    response = await asyncio.to_thread(do_request)
    print(response.text)

    # Xóa tin nhắn "đang xử lý"
    try:
        await processing_msg.delete()
    except Exception:
        pass

    if not response:
        await update.message.reply_text(
            "❌ <b>Lỗi kết nối!</b>\n\n"
            "Không thể kết nối đến máy chủ ChongLuaDao lúc này. Vui lòng thử lại sau.",
            parse_mode="HTML"
        )
        return

    if response.status_code != 200:
        await update.message.reply_text(
            f"❌ <b>Lỗi truy vấn ChongLuaDao!</b>\n\n"
            f"Máy chủ phản hồi với mã lỗi: <code>{response.status_code}</code>.",
            parse_mode="HTML"
        )
        return

    # Parse JSON kết quả
    try:
        data = response.json()
    except Exception as e:
        await update.message.reply_text(
            f"❌ <b>Lỗi phân tích cú pháp dữ liệu lộ lọt!</b>\n\n"
            f"Không thể đọc kết quả JSON từ API ChongLuaDao.",
            parse_mode="HTML"
        )
        return

    breaches = data.get("breaches", [])
    total_breaches = data.get("total_breaches", 0)

    # Nếu không có vụ lộ lọt nào
    if total_breaches == 0 or not breaches:
        message = (
            f"📧 <b>KIỂM TRA LỘ LỌT EMAIL</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Email:</b> <code>{email}</code>\n"
            f"• <b>Trạng thái:</b> 🟢 <b>AN TOÀN</b>\n"
            f"• <b>Số vụ lộ lọt:</b> <code>0</code> vụ\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎉 <i>Chúc mừng! Email của bạn không có trong bất kỳ vụ rò rỉ dữ liệu công khai nào được ghi nhận.</i>"
        )
        await update.message.reply_text(message, parse_mode="HTML")
        return

    # Thống kê loại dữ liệu rò rỉ
    all_data_classes = set()
    for b in breaches:
        for dc in b.get("DataClasses", []):
            all_data_classes.add(dc)

    # Từ điển Việt hóa dự phòng (để dịch các DataClasses nếu trả về Tiếng Anh)
    TRANSLATIONS = {
        "Email addresses": "Địa chỉ email",
        "Passwords": "Mật khẩu",
        "Usernames": "Tên đăng nhập",
        "IP addresses": "Địa chỉ IP",
        "Phone numbers": "Số điện thoại",
        "Names": "Họ và tên",
        "Dates of birth": "Ngày sinh",
        "Physical addresses": "Địa chỉ vật lý",
        "Genders": "Giới tính",
        "Device information": "Thông tin thiết bị",
        "Historical passwords": "Lịch sử mật khẩu",
        "Password hints": "Gợi ý mật khẩu",
        "Security questions and answers": "Câu hỏi & câu trả lời bảo mật",
        "Private messages": "Tin nhắn riêng tư"
    }

    vietnamese_classes = []
    for dc in sorted(all_data_classes):
        vietnamese_classes.append(TRANSLATIONS.get(dc, dc))

    leaked_data_summary = ", ".join(vietnamese_classes) if vietnamese_classes else "Không rõ"

    # Định dạng danh sách các vụ rò rỉ lớn nhất/mới nhất (tối đa 5 vụ)
    sorted_breaches = sorted(
        breaches,
        key=lambda x: x.get("BreachDate") or "",
        reverse=True
    )

    display_limit = 3
    breaches_list_str = ""

    def _get_short_clean_desc(text: str, max_len: int = 150) -> str:
        if not text:
            return ""
        # 1. Loại bỏ toàn bộ thẻ HTML để đảm bảo an toàn tuyệt đối khi truncate
        text = re.sub(r'<[^>]+>', '', text)
        # 2. Chuẩn hóa khoảng trắng
        text = " ".join(text.split())
        # 3. Cắt ngắn nếu vượt quá giới hạn
        if len(text) > max_len:
            return text[:max_len].strip() + "..."
        return text

    for i, b in enumerate(sorted_breaches[:display_limit], 1):
        title = b.get("Title", b.get("Name", "Không rõ"))
        breach_date = b.get("BreachDate", "Không rõ")
        pwn_count = b.get("PwnCount", 0)

        # Dữ liệu rò rỉ của vụ này (Sử dụng dịch thuật dự phòng)
        b_classes = [TRANSLATIONS.get(dc, dc) for dc in b.get("DataClasses", [])]
        b_classes_str = ", ".join(b_classes) if b_classes else "Không rõ"

        # Mô tả ngắn gọn sạch sẽ (Đã loại bỏ toàn bộ HTML và cắt ngắn)
        raw_desc = b.get("Description", "")
        cleaned_desc = _get_short_clean_desc(raw_desc, max_len=150)

        breaches_list_str += (
            f"<b>{i}. {title}</b> ({breach_date})\n"
            f" • 👤 Quy mô: <code>{pwn_count:,}</code> tài khoản\n"
            f" • 🔑 Dữ liệu lộ: <i>{b_classes_str}</i>\n"
            f" • 📝 Chi tiết: {cleaned_desc}\n\n"
        )

    remaining = total_breaches - display_limit

    if remaining > 0:
        breaches_list_str += f"<i>... và {remaining} vụ rò rỉ dữ liệu khác.</i>\n"

    message = (
        f"📧 <b>KẾT QUẢ KIỂM TRA LỘ LỌT EMAIL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Email:</b> <code>{email}</code>\n"
        f"• <b>Trạng thái:</b> 🔴 <b>CÓ LỘ LỌT DỮ LIỆU!</b>\n"
        f"• <b>Số vụ rò rỉ:</b> <code>{total_breaches}</code> vụ\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>CÁC DỮ LIỆU BỊ RÒ RỈ:</b>\n"
        f"<i>{leaked_data_summary}</i>\n\n"
        f"🔥 <b>CÁC VỤ LỘ LỌT CHI TIẾT GẦN NHẤT:</b>\n"
        f"{breaches_list_str}"
    )

    await update.message.reply_text(message, parse_mode="HTML", disable_web_page_preview=True)


# ══════════════════════════════════════════════════════════════
#  CHECK BY USERNAME (username / link → Telethon)
# ══════════════════════════════════════════════════════════════

async def _check_by_username(update: Update, processing_msg, username: str):
    """Check bằng username hoặc link — dùng Telethon trực tiếp"""

    # Chạy song song: lookup + gift
    async def safe_lookup():
        try:
            return await lookup_by_username(username)
        except Exception as e:
            print(f"⚠️ Telethon lookup failed: {e}")
            return None

    async def safe_get_gifts():
        try:
            return await get_user_gifts(username=username, limit=1000)
        except Exception as e:
            print(f"⚠️ Gift lookup failed: {e}")
            return {"gifts": []}

    lookup_task = asyncio.create_task(safe_lookup())
    gift_task = asyncio.create_task(safe_get_gifts())
    info, gift_data = await asyncio.gather(lookup_task, gift_task)

    # Xóa tin nhắn "đang xử lý"
    try:
        await processing_msg.delete()
    except Exception:
        pass

    if not info:
        await update.message.reply_text(
            "❌ <b>Không tìm thấy thông tin!</b>\n\n"
            "💡 Kiểm tra lại:\n"
            "• Username/Link có đúng không?\n"
            "• Tài khoản có thể không tồn tại hoặc đã bị xóa.",
            parse_mode="HTML",
        )
        return

    entity_type = info.get("type")

    if entity_type == "user":
        await _send_user_result(update, info, gift_data)
    elif entity_type == "channel":
        await _send_channel_result(update, info)
    else:
        print("Không thể xác định loại đối tượng", info)
        await update.message.reply_text(
            "❌ <b>Không thể xác định loại đối tượng.</b>",
            parse_mode="HTML",
        )


async def _send_user_result(update: Update, info: dict, gift_data: dict | None):
    """Format và gửi kết quả check User từ Telethon"""

    scores = calculate_scores(info, gift_data, is_rose=False)
    account_rank = scores["rank_html"]

    # ── Build thông tin ──
    username_display = f"@{info['username']}" if info.get('username') else "Không có"
    phone_display = info.get('phone') or "Ẩn số điện thoại"

    message = (
        f"🌹 <b>CHECK INFO ACCOUNTS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Phân loại:</b> {info.get('account_type', '👤 USER')}\n"
        f"• <b>Tên:</b> {info.get('full_name', 'Không rõ')}\n"
        f"• <b>Username:</b> {username_display}\n"
        f"• <b>ID:</b> <code>{info.get('id', 'N/A')}</code>\n"
        f"• <b>SĐT:</b> {phone_display}\n"

        f"• <b>Premium:</b> {'Có ⭐' if info.get('is_premium') else 'Không'}\n"
    )

    message += (
        f"\n• <b>Chỉ số:</b> {account_rank}\n"
    )

    # ── Nút Profile ──
    reply_markup = None
    if info.get('username'):
        profile_url = f"https://t.me/{info['username']}"
        keyboard = [[InlineKeyboardButton(text="👤 Profile", url=profile_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await update.message.reply_text(
            text=message,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
    except Exception:
        await update.message.reply_text(
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )


async def _send_channel_result(update: Update, info: dict):
    """Format và gửi kết quả check Channel/Group từ Telethon"""

    username_display = f"@{info['username']}" if info.get('username') else "Không có (Private)"
    members_display = f"{info.get('members_count', 0):,} người" if info.get('members_count') else "Không rõ"
    created_display = info.get('created_date') or "Không rõ"


    message = (
        f"📢 <b>CHECK INFO CHANNEL/GROUP</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Loại:</b> {info.get('channel_type', 'Không rõ')}\n"
        f"• <b>Tên:</b> {info.get('title', 'Không rõ')}\n"
        f"• <b>Username:</b> {username_display}\n"
        f"• <b>ID:</b> <code>{info.get('id', 'N/A')}</code>\n"
        f"• <b>Thành viên:</b> {members_display}\n"
        f"• <b>Ngày tạo:</b> {created_display} (UTC)\n"
    )

    # ── Nút truy cập ──
    reply_markup = None
    if info.get('username'):
        link_url = f"https://t.me/{info['username']}"
        keyboard = [[InlineKeyboardButton(text="🔗 Truy cập", url=link_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await update.message.reply_text(
            text=message,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
    except Exception:
        await update.message.reply_text(
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )


# ══════════════════════════════════════════════════════════════
#  CHECK BY PHONE (SĐT → Telethon)
# ══════════════════════════════════════════════════════════════

async def _check_by_phone(update: Update, processing_msg, phone: str):
    """Check bằng số điện thoại — TODO: implement"""
    try:
        await processing_msg.delete()
    except Exception:
        pass

    info = await lookup_by_phone(phone)

    if info is None:
        await update.message.reply_text(
            "❌ <b>Lỗi kết nối Telethon.</b>\n"
            "Vui lòng kiểm tra lại cấu hình.",
            parse_mode="HTML",
        )
        return

    if not info.get("found"):
        await update.message.reply_text(
            f"❌ <b>Không tìm thấy tài khoản Telegram nào.</b>\n\n"
            f"📞 SĐT: <code>{info.get('phone', phone)}</code>\n\n"
            f"💡 User có thể đã tắt chức năng tìm kiếm bằng số điện thoại.",
            parse_mode="HTML",
        )
        return

    # ── Hiển thị kết quả ──
    username_display = f"@{info['username']}" if info.get('username') else "Không có"
    dc_display = f"DC{info['dc_id']}" if info.get('dc_id') else "Không xác định"
    perm_link = f"<a href='tg://user?id={info['id']}'>{info['full_name'] or 'User'}</a>"

    flags = []
    if info.get('is_verified'):
        flags.append("✅ Verified")
    if info.get('is_scam'):
        flags.append("⚠️ SCAM")
    if info.get('is_fake'):
        flags.append("🚫 FAKE")
    flags_text = " | ".join(flags) if flags else None

    message = (
        f"📞 <b>CHECK INFO BY PHONE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Loại:</b> {info.get('account_type', '👤 USER')}\n"
        f"• <b>Tên:</b> {info.get('full_name', 'Không rõ')}\n"
        f"• <b>Username:</b> {username_display}\n"
        f"• <b>ID:</b> <code>{info['id']}</code>\n"
        f"• <b>SĐT tra:</b> <code>{info.get('phone_input', phone)}</code>\n"
        f"• <b>SĐT TG:</b> <code>{info.get('phone_resolved', 'Ẩn')}</code>\n"
        f"• <b>Premium:</b> {'Có ⭐' if info.get('is_premium') else 'Không'}\n"
        f"• <b>Permanent:</b> {perm_link}\n"
    )

    if flags_text:
        message += f"• <b>Cờ:</b> {flags_text}\n"
    if info.get('bio'):
        message += f"📝 <b>Bio:</b> {info['bio']}\n"

    # Nút Profile (nếu có username)
    reply_markup = None
    if info.get('username'):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [[InlineKeyboardButton(text="👤 Profile", url=f"https://t.me/{info['username']}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        message,
        parse_mode="HTML",
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )


# ══════════════════════════════════════════════════════════════
#  CHECK BY ID (ID số → Rose Bot phụ trợ + Gift)
# ══════════════════════════════════════════════════════════════

async def _check_by_id(update: Update, processing_msg, query: str, user_id_str: str):
    """Check bằng ID số — dùng Rose Bot phụ trợ để truy vấn thông tin"""

    rose_group_id = Config.get_rose_group_id()
    if not rose_group_id:
        try:
            await processing_msg.delete()
        except Exception:
            pass
        print('❌ ROSE_QUERY_GROUP_ID chưa được cấu hình.')
        return

    target_user_id = int(user_id_str)

    # Tạo task song song: Rose + Gift
    async def safe_get_gifts():
        try:
            return await get_user_gifts(user_id=target_user_id, limit=1000)
        except Exception as e:
            print(f"⚠️ Telethon không thể lấy gift cho {query}: {e}")
            return {"gifts": []}
    
    rose_task = asyncio.create_task(query_rose_bot(rose_group_id, query))
    gift_task = asyncio.create_task(safe_get_gifts())
    user_info, gift_data = await asyncio.gather(rose_task, gift_task)

    # Xóa tin nhắn "đang xử lý"
    try:
        await processing_msg.delete()
    except Exception:
        pass

    if user_info:
        print(user_info)
        
        scores = calculate_scores(user_info, gift_data, is_rose=True)
        account_rank = scores["rank_markdown"]
        first_name = user_info.get('first name', 'Không rõ')
        last_name = user_info.get('last name', 'Không rõ')
        raw_id = int(user_info.get('id', user_id_str))


        reply_markup = None
        username_val = user_info.get('username', '')
        clean_username = username_val.lstrip('@').strip() if username_val else ''
        message = (
            f"🌹 *CHECK INFO ACCOUNTS*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Name:* {first_name} {last_name}\n"
            f"• *ID:* `{raw_id}`\n"
            f"• *Username:* `{user_info.get('username')}`\n"
            f"📊 *Tín Nhiệm:* *{account_rank}*\n"
        )


        # if clean_username and clean_username != "":
        #     profile_url = f"https://t.me/{clean_username}"
        #     # profile_url = f"tg://user?id={raw_id}"
        #     keyboard = [[InlineKeyboardButton(text="👤 Profile", url=profile_url)]]
        #     reply_markup = InlineKeyboardMarkup(keyboard)
        if clean_username:
            profile_url = f"https://t.me/{clean_username}"
        else:
            profile_url = f"tg://user?id={raw_id}"

        keyboard = [[InlineKeyboardButton(
            text="👤 Profile",
            url=profile_url
        )]]

        reply_markup = InlineKeyboardMarkup(keyboard)
        # keyboard = [[InlineKeyboardButton(text="👤 Profile", url=profile_url)]]
        # reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await update.message.reply_text(
                text=message,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
        except Exception as e:
            print(f"❌ Error: {e}")
            await update.message.reply_text(
                text=message,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=True,
            )
    else:
        await update.message.reply_text(
            "❌ <b>Không tìm thấy thông tin.</b>\n\n"
            "💡 Kiểm tra lại các thông số sau:\n"
            "• User ID có đúng không?\n"
            "• Tài khoản có lẽ không tồn tại hoặc đã bị ẩn.",
            parse_mode=ParseMode.HTML,
        )


def get_handlers():
    """Trả về danh sách handlers để đăng ký"""
    return [
        CommandHandler("checkinfo", checkinfo_command),
    ]