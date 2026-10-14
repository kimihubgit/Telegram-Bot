"""
/check Command
Kiểm tra và hiển thị thông tin chi tiết người dùng

Cách dùng:
    /check              - Xem info của chính mình
    /check <user_id>    - Xem info bằng User ID (số)
    /check @username    - Xem info bằng username (cần Telethon)
    Reply + /check      - Xem info người được reply
"""
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from bot.services.user_service import (
    get_user_info,
    get_user_info_by_id,
    get_user_info_by_username,
    get_status_display,
    SYSTEM_BOT_IDS,
)
from bot.connection import is_connected
from bot.utils.format import escape_md, md_link
from bot.utils.logger import log_from_update
from bot.utils.rate_limiter import rate_limit


@rate_limit(seconds=5)
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /check"""
    log_from_update(update)
    try:
        info = None
        chat = update.effective_chat
        chat_id = chat.id if chat.type in ("group", "supergroup") else None

        # === Ưu tiên 1: /check <argument> ===
        if context.args and len(context.args) == 1:
            arg = context.args[0]

            # Check bằng User ID (số)
            if arg.isdigit():
                user_id = int(arg)
                try:
                    info = await get_user_info_by_id(context, user_id, chat_id)
                except Exception:
                    await update.message.reply_text(
                        f"❌ Không tìm thấy user với ID `{arg}`\\.\n\n"
                        f"Có thể user không ở trong group này hoặc ID không tồn tại\\.",
                        parse_mode="MarkdownV2",
                    )
                    return

            # Check bằng @username (cần Telethon)
            elif arg.startswith("@") and len(arg) > 1:
                if not is_connected():
                    await update.message.reply_text(
                        "⚠️ Check bằng @username cần Telethon \\(Userbot\\)\\.\n\n"
                        "💡 Cấu hình `TELETHON_API_ID` và `TELETHON_API_HASH` trong \\.env "
                        "để mở khóa tính năng này\\.",
                        parse_mode="MarkdownV2",
                    )
                    return

                try:
                    info = await get_user_info_by_username(context, arg, chat_id)
                except Exception:
                    await update.message.reply_text(
                        f"❌ Không tìm thấy user `{escape_md(arg)}`\\.\n\n"
                        f"💡 *Thử cách khác:*\n"
                        f"• Reply tin nhắn của họ \\+ `/check`\n"
                        f"• Dùng User ID: `/check 123456789`",
                        parse_mode="MarkdownV2",
                    )
                    return

            else:
                await update.message.reply_text(
                    "⚠️ Sai cú pháp\\. Dùng:\n"
                    "• `/check` — check chính mình\n"
                    "• `/check 123456789` — check bằng User ID\n"
                    "• `/check @username` — check bằng username\n"
                    "• Reply \\+ `/check` — check người được reply",
                    parse_mode="MarkdownV2",
                )
                return

        # === Ưu tiên 2: Reply + /check ===
        if info is None and update.message.reply_to_message and update.message.reply_to_message.from_user:
            reply_user = update.message.reply_to_message.from_user

            # Xử lý admin ẩn danh (GroupAnonymousBot)
            if reply_user.id in SYSTEM_BOT_IDS:
                bot_names = {
                    1087968824: "Admin ẩn danh (GroupAnonymousBot)",
                    777000: "Telegram Service Messages",
                    136817688: "Channel Bot",
                }
                name = bot_names.get(reply_user.id, "System Bot")
                await update.message.reply_text(
                    f"⚠️ Đây là *{escape_md(name)}*\\, không phải người dùng thực\\.\n\n"
                    f"💡 Để check user cụ thể\\, dùng:\n"
                    f"• `/check <user\\_id>` — ví dụ `/check 8673754009`\n"
                    f"• `/check @username` — ví dụ `/check @bestcoin995`",
                    parse_mode="MarkdownV2",
                )
                return

            info = await get_user_info(update, context, reply_user)

        # === Ưu tiên 3: Check chính mình ===
        if info is None:
            info = await get_user_info(update, context)

        # === Build & send info card ===
        await _send_info_card(update, info)

    except Exception as e:
        print(f"❌ Error in /check command: {e}")
        await update.message.reply_text(
            "❌ Có lỗi khi lấy thông tin người dùng\\. Vui lòng thử lại\\.",
            parse_mode="MarkdownV2",
        )


async def _send_info_card(update: Update, info: dict):
    """Build và gửi thẻ thông tin người dùng"""
    separator = escape_md("═" * 28)
    thin_sep = escape_md("─" * 28)

    profile_link = f"tg://user?id={info['id']}"

    # Username
    username_display = (
        f"@{escape_md(info['username'])}" if info["username"] else escape_md("Không có")
    )
    username_note = " \\(⛔️ CẢNH BÁO\\)" if not info["username"] else ""

    # Profile link
    profile_text = md_link("Xem hồ sơ", profile_link)

    # Status trong group
    status_display = (
        escape_md(get_status_display(info["status"]))
        if info["status"]
        else escape_md("❓ Unknown")
    )

    # Premium
    premium_display = "✅ Yes" if info["is_premium"] else "❌ No"

    # Bio
    bio_display = escape_md(info["bio"]) if info.get("bio") else escape_md("Không có")

    # === Build message ===
    lines = [
        f"{separator}",
        f"🔎 *THÔNG TIN NGƯỜI DÙNG*",
        f"{separator}",
        f"",
        f"👤 Name: *{escape_md(info['full_name'])}*",
        f"🆔 ID: `{info['id']}`",
        f"🔗 Username: {username_display}{username_note}",
        f"🔎 Profile: {profile_text}",
    ]

    # Cảnh báo scam/fake nếu có
    if info.get("is_scam"):
        lines.append(f"🚨 *SCAM ACCOUNT* 🚨")
    if info.get("is_fake"):
        lines.append(f"🚨 *FAKE ACCOUNT* 🚨")
    if info.get("is_verified"):
        lines.append(f"✅ *Tài khoản đã xác minh*")

    lines.extend([
        f"",
        f"{thin_sep}",
        f"",
        f"⚙️ Status: {status_display}",
        f"⭐️ Premium: {premium_display}",
        f"📝 Bio: {bio_display}",
    ])

    # === Thông tin sâu từ Telethon ===
    if info.get("common_chats_count") is not None:
        lines.append(f"💬 Nhóm chung: {escape_md(str(info['common_chats_count']))}")

    lines.extend([
        f"",
        f"{separator}",
    ])

    message = "\n".join(lines)

    # Gửi kèm ảnh đại diện nếu có
    if info["profile_photo_file_id"]:
        await update.message.reply_photo(
            photo=info["profile_photo_file_id"],
            caption=message,
            parse_mode="MarkdownV2",
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )


def get_handlers():
    """Trả về danh sách handlers để đăng ký"""
    return [
        CommandHandler("check", check_command),
    ]
