"""
/notification Command
Gửi thông báo (broadcast) đến tất cả người dùng đã tương tác với bot.

Cách dùng:
    1. Soạn 1 tin nhắn (text, ảnh, video, document, sticker, v.v.) và gửi tin nhắn đã soạn lên bot
    2. Reply tin nhắn đó ( Điều kiện tiên quyết là Reply ) + gõ lệnh /notification
    3. Bot sẽ forward/gửi nội dung đó đến tất cả user đã biết

Giới hạn: Chỉ admin (NOTIFICATION_ADMIN_IDS trong .env) mới được dùng.
Chỉ gửi đến user cá nhân, KHÔNG gửi vào group/channel.
"""
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from bot.config import Config
from bot.services.user_tracker import get_all_user_ids, get_user_count, remove_user
from bot.utils.format import escape_md
from bot.utils.logger import log_from_update
from bot.utils.rate_limiter import rate_limit


def _is_authorized(user_id: int) -> bool:
    """Kiểm tra user có quyền sử dụng lệnh notification không"""
    allowed_ids = Config.get_notification_admin_ids()
    return user_id in allowed_ids


@rate_limit(seconds=30)
async def notification_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /notification — broadcast tin nhắn đến tất cả users"""
    log_from_update(update)
    user_id = update.effective_user.id

    # === Kiểm tra quyền ===
    if not _is_authorized(user_id):
        await update.message.reply_text(
            "🚫 *Không có quyền truy cập*\n\n"
            "Lệnh này chỉ dành cho admin được cấu hình\\.",
            parse_mode="MarkdownV2",
        )
        return

    # === Kiểm tra reply ===
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ *Cách sử dụng lệnh /notification*\n\n"
            "1️⃣ Soạn tin nhắn bạn muốn gửi \\(text, ảnh, video\\.\\.\\.\\)\n"
            "2️⃣ Reply tin nhắn đó \\+ gõ `/notification`\n"
            "3️⃣ Bot sẽ gửi đến tất cả người dùng đã tương tác\\!\n\n"
            "📌 _Tin nhắn sẽ được copy nguyên bản đến từng user\\._",
            parse_mode="MarkdownV2",
        )
        return

    # === Lấy tin nhắn cần gửi ===
    source_message = update.message.reply_to_message

    # === Lấy danh sách users ===
    user_ids = get_all_user_ids()
    total_users = len(user_ids)

    if total_users == 0:
        await update.message.reply_text(
            "📭 *Chưa có người dùng nào*\n\n"
            "Chưa có ai tương tác với bot\\. "
            "Hãy đợi người dùng gửi tin nhắn hoặc dùng /start\\.",
            parse_mode="MarkdownV2",
        )
        return

    # === Bắt đầu gửi ===
    progress_msg = await update.message.reply_text(
        f"📤 *Đang gửi thông báo\\.\\.\\.*\n\n"
        f"👥 Tổng người nhận: `{total_users}`\n"
        f"⏳ Vui lòng đợi\\.\\.\\.",
        parse_mode="MarkdownV2",
    )

    success = 0
    failed = 0
    blocked = 0

    for uid in user_ids:
        # Không gửi cho chính bot hoặc người gửi lệnh (tùy chọn)
        try:
            await source_message.copy(chat_id=uid)
            success += 1
        except Exception as e:
            error_str = str(e).lower()
            if "blocked" in error_str or "deactivated" in error_str:
                # User đã block bot hoặc tài khoản bị xóa → loại khỏi danh sách
                remove_user(uid)
                blocked += 1
            elif "chat not found" in error_str:
                # Chat không tồn tại
                remove_user(uid)
                blocked += 1
            else:
                failed += 1
                print(f"⚠️ Không gửi được notification đến {uid}: {e}")

        # Delay nhẹ để tránh bị rate limit (Telegram giới hạn ~30 msg/s)
        await asyncio.sleep(0.05)

    # === Báo cáo kết quả ===
    report = (
        f"✅ *Gửi thông báo hoàn tất\\!*\n\n"
        f"📊 *Kết quả:*\n"
        f"  • Thành công: `{success}/{total_users}`\n"
        f"  • Thất bại: `{failed}`\n"
        f"  • Đã block/xóa: `{blocked}`\n\n"
    )

    if blocked > 0:
        report += f"🗑 _Đã tự động xóa {blocked} user không còn hoạt động\\._"

    try:
        await progress_msg.edit_text(report, parse_mode="MarkdownV2")
    except Exception:
        await update.message.reply_text(report, parse_mode="MarkdownV2")


def get_handlers():
    """Trả về danh sách handlers để đăng ký"""
    return [
        CommandHandler("notification", notification_command),
    ]
