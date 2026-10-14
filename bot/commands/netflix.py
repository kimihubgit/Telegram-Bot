"""
/tv và /netflix Commands
Các lệnh liên quan đến Netflix:
  - /tv <code>   : Kích hoạt mã TV Netflix (8 ký tự) bằng cookie có sẵn
  - /netflix     : Các tính năng Netflix khác (sẽ mở rộng sau)

Logic kích hoạt được tách ra tại:
  bot/services/netflix/tvcode.py
"""
from telegram.constants import ParseMode
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
import asyncio
import os

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from bot.config import Config
from bot.utils.logger import log_from_update
from bot.utils.rate_limiter import rate_limit
from bot.services.user_tracker import track_user
from bot.services.netflix.tvcode import (
    parse_netscape_cookies,
    check_cookie_live,
    activate_tv_code,
    get_available_cookies,
    USED_COOKIE_DIR,
)
from bot.services.netflix.nflogin import (
    extract_netflix_id_from_file,
    fetch_nftoken,
    build_login_url,
    format_expiry,
)


# ══════════════════════════════════════════════════════════════
#  /tv — Kích hoạt mã TV Netflix
# ══════════════════════════════════════════════════════════════

@rate_limit(seconds=20, warning="⏳ Lệnh /tv cần thời gian xử lý.\nVui lòng đợi <b>{remaining}s</b> trước khi dùng lại.")
async def tv8_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /tv — nhập code Netflix cho TV."""
    log_from_update(update)

    # Track user nếu private chat
    if update.effective_user and update.effective_chat and update.effective_chat.type == "private":
        user = update.effective_user
        track_user(
            user_id=user.id,
            first_name=user.first_name or "",
            username=user.username or "",
        )

    # Kiểm tra mã code
    if not context.args:
        await update.message.reply_text(
            "📺 <b>Netflix TV Code Activator</b>\n\n"
            "Nhập mã code hiển thị trên TV để đăng nhập Netflix.\n\n"
            "Cách dùng: /tv8 <b>&lt;mã code&gt;</b>\n"
            "Ví dụ: /tv8 <b>12345678</b> hoặc /tv8 <b>1234-5678</b>\n\n"
            "💡 Mã code là dãy 8 ký tự hiển thị trên TV của bạn.",
            parse_mode="HTML",
        )
        return

    tv_code = context.args[0].strip()
    tv_code = tv_code.replace(" ", "").replace("-", "")

    if len(tv_code) != 8:
        await update.message.reply_text(
            "❌ <b>Sai định dạng mã code!</b>\n\n"
            "Mã code Netflix TiVi phải có đúng 8 ký tự.\n\n"
            f"Bạn đã nhập: <b>{tv_code}</b> ({len(tv_code)} ký tự)\n\n"
            "Vui lòng kiểm tra lại mã code trên TiVi và thử lại.",
            parse_mode="HTML",
        )
        return

    if not tv_code.isalnum():
        await update.message.reply_text(
            "❌ <b>Sai định dạng mã code!</b>\n\n"
            "Mã code Netflix TiVi phải là ký tự alpha-numeric (chữ và số).\n\n"
            f"Bạn đã nhập: <b>{tv_code}</b>\n\n"
            "Vui lòng kiểm tra lại mã code trên TV và thử lại.",
            parse_mode="HTML",
        )
        return

    # === Kiểm tra kho cookie ===
    cookie_files = get_available_cookies()

    if not cookie_files:
        await update.message.reply_text(
            "❌ <b>Hết cookie!</b>\n\n"
            "Kho cookie hiện tại đã hết. Vui lòng liên hệ admin để bổ sung.",
            parse_mode="HTML",
        )
        return

    status_msg = await update.message.reply_text(
        f"⏳ Đang xử lý...\n"
        f"📦 Kho còn <b>{len(cookie_files)}</b> cookie\n"
        f"🔍 Đang tìm cookie LIVE...",
        parse_mode="HTML",
    )

    loop = asyncio.get_event_loop()

    for cookie_path in cookie_files:
        cookie_filename = os.path.basename(cookie_path)

        cookie_string = await loop.run_in_executor(None, parse_netscape_cookies, cookie_path)
        if not cookie_string:
            continue

        check_result = await loop.run_in_executor(None, check_cookie_live, cookie_string)

        if not check_result["live"]:
            try:
                used_path = USED_COOKIE_DIR / cookie_filename
                os.rename(cookie_path, str(used_path))
            except Exception:
                try:
                    os.remove(cookie_path)
                except Exception:
                    pass
            continue

        info = check_result.get("info") or {}
        email = info.get("email") or "Unknown"
        plan = info.get("plan") or "Unknown"
        country = info.get("country") or "Unknown"

        await status_msg.edit_text(
            f"✅ Tìm thấy cookie <b>LIVE</b>!\n"
            f"📧 Email: <code>{email}</code>\n"
            f"📋 Plan: <b>{plan}</b>\n"
            f"🌍 Country: <b>{country}</b>\n\n"
            f"⏳ Đang nhập code <b>{tv_code}</b>...",
            parse_mode="HTML",
        )

        activate_result = await loop.run_in_executor(
            None, activate_tv_code, cookie_string, tv_code
        )
        print(activate_result)

        if activate_result["status"] == "success":
            try:
                used_path = USED_COOKIE_DIR / cookie_filename
                os.rename(cookie_path, str(used_path))
            except Exception:
                pass

            remaining = len(get_available_cookies())

            await status_msg.edit_text(
                f"🎉 <b>THÀNH CÔNG!</b>\n\n"
                f"📺 Mã TiVi <b>{tv_code}</b> đã được kích hoạt!\n"
                f"📧 Account: <code>{email}</code>\n"
                f"📋 Plan: <b>{plan}</b>\n"
                f"🌍 Country: <b>{country}</b>\n\n"
                f"📦 Cookie còn lại: <b>{remaining}</b>",
                parse_mode="HTML",
            )

            # Thông báo cho admin
            admin_id = Config.ADMIN_CHAT_ID
            if admin_id and admin_id.lstrip("-").isdigit():
                try:
                    await context.bot.send_message(
                        chat_id=int(admin_id),
                        text=(
                            f"📺 Netflix TV Activated!\n"
                            f"Code: {tv_code}\n"
                            f"Account: {email}\n"
                            f"Plan: {plan} | Country: {country}\n"
                            f"User: {update.effective_user.full_name} (ID: {update.effective_user.id})\n"
                            f"Cookie còn lại: {remaining}"
                        ),
                    )
                except Exception:
                    pass

            return
        else:
            await status_msg.edit_text(
                f"⚠️ Cookie <code>{email}</code> không kích hoạt được.\n"
                f"🔄 Đang thử cookie khác...",
                parse_mode="HTML",
            )
            continue

    await status_msg.edit_text(
        "❌ <b>Thất bại!</b>\n\n"
        "Đã thử tất cả cookie trong kho nhưng không thể kích hoạt.\n"
        "Có thể mã TV không hợp lệ hoặc tất cả cookie đã hết hạn.\n\n"
        "💡 Vui lòng kiểm tra lại mã code hoặc liên hệ admin.",
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════
#  /netflix — Tính năng Netflix (mở rộng sau)
# ══════════════════════════════════════════════════════════════

@rate_limit(seconds=5)
async def netflix_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /netflix — tổng hợp tính năng Netflix."""
    log_from_update(update)

    cookie_count = len(get_available_cookies())

    await update.message.reply_text(
        "🎬 <b>Cách Dùng Lệnh Netflix</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Cookie trong kho: <b>{cookie_count}</b>\n\n"
        "📺 /tv8 <code>&lt;code&gt;</code> — Kích hoạt mã TV Netflix\n\n"
        "📺 /nflogin — Đăng Nhập Netflix bằng link\n\n"
        "💡 <i>Các tính năng khác đang được phát triển...</i>",
        parse_mode=ParseMode.HTML,
    )


# ══════════════════════════════════════════════════════════════
#  /nflogin — Đăng nhập Netflix bằng link nftoken
# ══════════════════════════════════════════════════════════════

@rate_limit(seconds=15, warning="⏳ Lệnh /nflogin cần thời gian xử lý.\nVui lòng đợi <b>{remaining}s</b> trước khi dùng lại.")
async def nflogin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /nflogin — tạo link đăng nhập Netflix bằng nftoken từ cookie."""
    log_from_update(update)

    cookie_files = get_available_cookies()

    if not cookie_files:
        await update.message.reply_text(
            "❌ <b>Hết cookie!</b>\n\n"
            "Kho cookie hiện tại đã hết. Vui lòng liên hệ admin để bổ sung.",
            parse_mode="HTML",
        )
        return

    status_msg = await update.message.reply_text(
        f"⏳ Đang xử lý...\n"
        f"📦 Kho còn <b>{len(cookie_files)}</b> cookie\n"
        f"🔍 Đang tìm cookie LIVE...",
        parse_mode="HTML",
    )

    loop = asyncio.get_event_loop()

    for cookie_path in cookie_files:
        cookie_filename = os.path.basename(cookie_path)

        # Lấy NetflixId từ file cookie
        netflix_id = await loop.run_in_executor(None, extract_netflix_id_from_file, cookie_path)
        if not netflix_id:
            continue

        await status_msg.edit_text(
            f"🔑 Tìm thấy cookie, đang tạo link đăng nhập...",
            parse_mode="HTML",
        )

        try:
            token, expires = await loop.run_in_executor(
                None, fetch_nftoken, netflix_id
            )
        except Exception as e:
            # Cookie này lỗi → thử cái tiếp
            print(f"⚠️ nflogin failed for {cookie_filename}: {e}")
            await status_msg.edit_text(
                f"⚠️ Cookie không tạo được token.\n"
                f"🔄 Đang thử cookie khác...",
                parse_mode="HTML",
            )
            continue

        login_url = build_login_url(token)
        expiry_str = format_expiry(expires)

        keyboard = [[InlineKeyboardButton(
            text="📚 Đăng Nhập Netflix",
            url=login_url
        )]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await status_msg.edit_text(
            f"🎉 <b>Tạo link đăng nhập thành công!</b>\n\n"
            f"🔗 <b>Link Đăng Nhập:</b>\n"
            f"<code>{login_url}</code>\n\n"
            f"⏰ <b>Hết hạn:</b> {expiry_str}\n\n"
            f"💡 Nhấp vào link hoặc copy vào trình duyệt để đăng nhập Netflix.",
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
        return

    # Hết cookie mà không thành công
    await status_msg.edit_text(
        "❌ <b>Thất bại!</b>\n\n"
        "Đã thử tất cả cookie trong kho nhưng không thể tạo link.\n"
        "Có thể tất cả cookie đã hết hạn hoặc bị khóa.\n\n"
        "💡 Vui lòng liên hệ admin để bổ sung cookie mới.",
        parse_mode="HTML",
    )


def get_handlers():
    """Trả về danh sách handlers để đăng ký"""
    return [
        CommandHandler("tv8", tv8_command),
        CommandHandler("netflix", netflix_command),
        CommandHandler("nflogin", nflogin_command),
    ]
