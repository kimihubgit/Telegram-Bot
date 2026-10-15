"""
/start, /help, /myid và /me Commands
Tin nhắn chào mừng + hiển thị thông tin user chi tiết,
hướng dẫn sử dụng, và lấy Chat ID.
"""
from telegram import InlineKeyboardMarkup
from telegram import InlineKeyboardButton
from telegram.constants import ParseMode
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from bot.config import Config
from bot.utils.format import escape_md
from bot.utils.logger import log_from_update
from bot.utils.rate_limiter import rate_limit, daily_limit
from bot.connection import get_client, is_connected
from telethon.tl.functions.users import GetFullUserRequest
from bot.services.deeplinks import dispatch_deeplink
def _is_admin(user_id: int) -> bool:
    """Kiểm tra user có phải admin không (dựa trên NOTIFICATION_ADMIN_IDS)"""
    return user_id in Config.get_notification_admin_ids()


# ══════════════════════════════════════════════════════════════
#  Hàm dùng chung: lấy thông tin user chi tiết
# ══════════════════════════════════════════════════════════════

async def _build_user_info_message(user) -> str:
    """Lấy thông tin user từ Bot API + Telethon rồi build message HTML."""
    user_id = user.id
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    username = f"@{user.username}" if user.username else "Không có"
    language = user.language_code or "Không rõ"
    is_premium = "Có ⭐" if user.is_premium else "Không"
    is_bot_flag = "Có 🤖" if user.is_bot else "Không"

    bio = None

    if is_connected():
        client = get_client()
        try:
            
            entity = await client.get_entity(user_id)
            full_data = await client(GetFullUserRequest(entity))
            full_user = full_data.full_user
            bio = full_user.about
        except Exception as e:
            print(f"⚠️ Telethon get user info failed /start: {e}")

    # ── Permanent link ──
    perm_link = f"<a href='tg://user?id={user_id}'>{first_name or 'User'}</a>"

    # ── Build message ──
    message = (
        f"👤 <b>USER INFORMATION</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"👤 <b>First Name:</b> {first_name}\n"
        f"👥 <b>Last Name:</b> {last_name}\n"
        f"🔗 <b>Username:</b> {username}\n"
        f"⭐️ <b>Premium:</b> {is_premium}\n"
        f"🤖 <b>Bot:</b> {is_bot_flag}\n"
        f"🌍 <b>Language:</b> {language}\n"
        f"🔗 <b>Permanent Link:</b> {perm_link}\n"
    )

    if bio:
        message += f"📝 <b>Bio:</b> {bio}\n"

    return message


# ══════════════════════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════════════════════

@rate_limit(seconds=3)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /start — group: chào ngắn, private: hiện info chi tiết"""
    log_from_update(update)

    user = update.effective_user
    chat = update.effective_chat

    # ── Điều phối và xử lý Deep Link nếu có ──
    
    if await dispatch_deeplink(update, context):
        return

    # ── Group chat → chào ngắn gọn ──
    if chat.type != "private":
        name = escape_md(user.first_name or "bạn")
        welcome = (
            f"👋 Xin chào *{name}*\\!\n"
            f"\n"
            f"💡  /help \\- Xem thêm nhiều lệnh khác\n"
            f"📡 _Hệ thống Bot tự động giám sát ra/vào nhóm, check scam và spam group được phát triển bởi Cộng Đồng Kimidev_"
        )
        await update.message.reply_text(welcome, parse_mode="MarkdownV2")
        return

    # ── Private chat → hiển thị thông tin user chi tiết ──
    # message = await _build_user_info_message(user, context)

    keyboard = [[InlineKeyboardButton(text="Add Me To Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if _is_admin(user.id):
        message = (
            f"\n🔐 <b>ADMIN PANEL</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📢 /notification — Broadcast tin nhắn đến tất cả user\n"
            f"🚫 /banlist — Quản lý danh sách cấm\n"
            f"🔄 /resetwarn — Reset cảnh báo vi phạm\n"
            f"🔍 /checkinfo — Kiểm tra thông tin user chi tiết\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡  /help - Xem thêm nhiều lệnh khác\n"
            f"\n📡 <i>_Hệ thống Bot tự động giám sát ra/vào nhóm, check scam và spam group được phát triển bởi Cộng Đồng Kimidev_</i>"
        )
        await update.message.reply_text(message, parse_mode="HTML", disable_web_page_preview=True)
        return

    message = (
        f"💡 /help — Xem thêm nhiều lệnh khác\n"
        f"💡 /me — Xem thông tin của bạn trong nhóm\n"
    )

    # ── Admin: hiển thị thêm lệnh admin ──

    message += f"\n📡 <i>Hệ thống Bot tự động giám sát ra/vào nhóm, check scam và spam group được phát triển bởi Cộng Đồng Kimidev_</i>"

    await update.message.reply_text(message, parse_mode="HTML", reply_markup=reply_markup, disable_web_page_preview=True)


# ══════════════════════════════════════════════════════════════
#  /me — xem thông tin chính mình (dùng được ở mọi nơi)
# ══════════════════════════════════════════════════════════════

@daily_limit(max_uses=5)
@rate_limit(seconds=3)
async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /me — xem thông tin chi tiết của chính mình"""
    log_from_update(update)

    user = update.effective_user
    message = await _build_user_info_message(user)

    await update.message.reply_text(message, parse_mode="HTML", disable_web_page_preview=True)


# ══════════════════════════════════════════════════════════════
#  /help
# ══════════════════════════════════════════════════════════════

@rate_limit(seconds=2)
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /help"""
    log_from_update(update)
    help_text = (
        f"📚 *DANH SÁCH LỆNH CHÍNH*\n\n"
        f"🔍 `/check` ⁃ Xem info bản thân hoặc reply một người để xem info họ\n"
        f"🆔 `/myid` ⁃ Lấy Telegram Chat ID của bạn\n"
        f"🤖 `/checksales` ⁃ Kiểm tra tin nhắn có phải bài rao bán/QC không\n"
        f"📊 `/stats` ⁃ Xem báo cáo kiểm duyệt hôm nay của nhóm\n"
        f"ℹ️ `/bin` ⁃ Kiểm tra thông tin thẻ \\(BIN\\)\n"
        f"🔑 `/token` ⁃ Kiểm tra token Bot Telegram còn sống hay đã die\n"
        f"👤 `/me` ⁃ Xem thông tin bản thân\n"
        f"💝 `/donate` ⁃ Ủng hộ phát triển bot\n"
    )
    user = update.effective_user
    chat = update.effective_chat

    if _is_admin(user.id) or (chat and chat.type in ("group", "supergroup")):
        help_text += (
            f"\n🛡️ *QUẢN TRỊ NHÓM & CHẶN QC*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ `/marketguard on\\|off` ⁃ Bật/tắt AI lọc quảng cáo nhóm\n"
            f"🏷️ `/sethashtag #tag` ⁃ Đổi hashtag bắt buộc khi bán hàng\n"
            f"📈 `/setmaxsales <số>` ⁃ Đổi hạn mức bài bán hàng/ngày\n"
            f"🔄 `/resetsales <id>` ⁃ Reset hạn mức bài đăng cho user\n"
            f"🚫 `/addbadword <từ>` ⁃ Thêm từ cấm vào danh sách\n"
            f"🗑️ `/delbadword <từ>` ⁃ Xóa từ cấm khỏi danh sách\n"
            f"📋 `/badwords` ⁃ Xem số lượng từ cấm đang kích hoạt\n"
            f"🧹 `/resetwarn <id>` ⁃ Reset số lần vi phạm chửi tục\n"
            f"📢 `/notification` ⁃ Broadcast thông báo (Admin Bot)\n"
            f"⛔ `/banlist` ⁃ Quản lý danh sách cấm (Admin Bot)\n"
        )

    help_text += f"\n📡 *Cre:* System bot design by Kimidev Community"

    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN_V2)


# ══════════════════════════════════════════════════════════════
#  /myid
# ══════════════════════════════════════════════════════════════

@rate_limit(seconds=3)
async def myid_command(update: Update):
    """Xử lý lệnh /myid - hiện Chat ID để cấu hình ADMIN_CHAT_ID"""
    log_from_update(update)
    user = update.effective_user
    chat = update.effective_chat

    text = (
        f"🆔 *Thông tin ID*\n"
        f"\n"
        f"👤 Your ID: `{user.id}`\n"
        f"💬 Chat ID: `{chat.id}`\n"
    )

    await update.message.reply_text(text, parse_mode="MarkdownV2")


def get_handlers():
    """Trả về danh sách handlers để đăng ký"""
    return [
        CommandHandler("start", start_command),
        CommandHandler("me", me_command),
        CommandHandler("help", help_command),
        CommandHandler("myid", myid_command),
    ]
