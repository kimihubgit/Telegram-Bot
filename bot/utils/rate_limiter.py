"""
Rate Limiter & Daily Limit
Chống spam lệnh — giới hạn tần suất sử dụng command cho từng user.
Giới hạn số lần dùng lệnh trong 1 ngày cho từng user.

Cách dùng:
    from bot.utils.rate_limiter import rate_limit

    @rate_limit(seconds=5)           # Mỗi user chỉ được dùng 1 lần / 5 giây
    async def my_command(update, context):
        ...

    @rate_limit(seconds=10, warning="Đợi {remaining}s nữa nhé!")
    async def heavy_command(update, context):
        ...

Tính năng:
    - Per-user cooldown (mỗi user có timer riêng)
    - Per-command cooldown (mỗi lệnh có thời gian riêng)
    - Warning message tự động xóa sau vài giây
    - Admin bypass (admin không bị giới hạn)
    - Daily limit: giới hạn số lần dùng lệnh/ngày, tự reset lúc 0h
"""
import asyncio
import time
from datetime import date
from functools import wraps
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes
from bot.config import Config


# Storage: {command_name: {user_id: last_used_timestamp}}
_cooldowns: dict[str, dict[int, float]] = defaultdict(dict)

# Storage: {command_name: {user_id: {"date": "YYYY-MM-DD", "count": int}}}
_daily_usage: dict[str, dict[int, dict]] = defaultdict(dict)


def _get_admin_ids() -> list[int]:
    """Lấy danh sách admin IDs được bypass rate limit."""
    ids = []
    admin = Config.ADMIN_CHAT_ID
    if admin and admin.lstrip("-").isdigit():
        ids.append(int(admin))
    ids.extend(Config.get_notification_admin_ids())
    return list(set(ids))


def rate_limit(
    seconds: int = 5,
    warning: str | None = None,
    delete_warning_after: int = 5,
    admin_bypass: bool = True,
):
    """
    Decorator chống spam command.

    Args:
        seconds: Thời gian cooldown (giây) giữa 2 lần dùng cùng 1 lệnh.
        warning: Tin nhắn cảnh báo khi user spam. Dùng {remaining} để hiện
                 số giây còn lại. Nếu None → dùng message mặc định.
        delete_warning_after: Xóa tin nhắn cảnh báo sau N giây. Set 0 để không xóa.
        admin_bypass: Nếu True, admin sẽ không bị giới hạn.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            # Bỏ qua nếu không có user hoặc message
            if not update.effective_user or not update.message:
                return await func(update, context, *args, **kwargs)

            user_id = update.effective_user.id
            command_name = func.__name__

            # Admin bypass
            # if admin_bypass and user_id in _get_admin_ids():
            #     return await func(update, context, *args, **kwargs)

            # Kiểm tra cooldown
            now = time.time()
            last_used = _cooldowns[command_name].get(user_id, 0)
            elapsed = now - last_used

            if elapsed < seconds:
                remaining = round(seconds - elapsed)
                if remaining < 1:
                    remaining = 1

                # Tạo warning message
                if warning:
                    msg_text = warning.format(remaining=remaining)
                else:
                    msg_text = (
                        f"⏳ Bạn đang sử dụng lệnh quá nhanh!\n"
                        f"Vui lòng đợi <b>{remaining}s</b> nữa."
                    )

                # Gửi cảnh báo
                warn_msg = await update.message.reply_text(
                    msg_text,
                    parse_mode="HTML",
                )

                # Tự động xóa cảnh báo sau N giây
                if delete_warning_after > 0:
                    async def _delete_later(msg, delay):
                        await asyncio.sleep(delay)
                        try:
                            await msg.delete()
                        except Exception:
                            pass

                    asyncio.create_task(_delete_later(warn_msg, delete_warning_after))

                return  # Không chạy command

            # Cho phép chạy — cập nhật timestamp
            _cooldowns[command_name][user_id] = now
            return await func(update, context, *args, **kwargs)

        return wrapper
    return decorator


def daily_limit(
    max_uses: int = 5,
    warning: str | None = None,
    delete_warning_after: int = 8,
    admin_bypass: bool = True,
):
    """
    Decorator giới hạn số lần dùng lệnh trong 1 ngày cho từng user.
    Tự động reset lúc 0h mỗi ngày.

    Cách dùng:
        @daily_limit(max_uses=3)
        async def netflix_command(update, context):
            ...

        @daily_limit(max_uses=10, warning="Bạn đã dùng hết {used}/{max} lượt hôm nay!")
        async def check_command(update, context):
            ...

    Args:
        max_uses: Số lần tối đa được dùng lệnh trong 1 ngày.
        warning: Tin nhắn khi hết lượt. Dùng {used}, {max}, {command} để format.
                 Nếu None → dùng message mặc định.
        delete_warning_after: Xóa cảnh báo sau N giây. Set 0 để không xóa.
        admin_bypass: Nếu True, admin không bị giới hạn.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            # Bỏ qua nếu không có user hoặc message
            if not update.effective_user or not update.message:
                return await func(update, context, *args, **kwargs)

            user_id = update.effective_user.id
            command_name = func.__name__

            # Admin bypass
            if admin_bypass and user_id in _get_admin_ids():
                return await func(update, context, *args, **kwargs)

            # Lấy ngày hôm nay
            today = date.today().isoformat()  # "YYYY-MM-DD"

            # Lấy hoặc tạo record cho user
            user_record = _daily_usage[command_name].get(user_id)

            if not user_record or user_record["date"] != today:
                # Ngày mới → reset về 0
                _daily_usage[command_name][user_id] = {"date": today, "count": 0}
                user_record = _daily_usage[command_name][user_id]

            # Kiểm tra đã hết lượt chưa
            if user_record["count"] >= max_uses:
                # Tạo warning message
                if warning:
                    msg_text = warning.format(
                        used=user_record["count"],
                        max=max_uses,
                        command=command_name,
                    )
                else:
                    msg_text = (
                        f"🚫 <b>Đã hết lượt sử dụng hôm nay!</b>\n\n"
                        f"📊 Bạn đã dùng <b>{user_record['count']}/{max_uses}</b> lượt.\n"
                        f"🕛 Lượt sử dụng sẽ reset lúc <b>0:00</b> ngày mai."
                    )

                warn_msg = await update.message.reply_text(
                    msg_text,
                    parse_mode="HTML",
                )

                if delete_warning_after > 0:
                    async def _delete_later(msg, delay):
                        await asyncio.sleep(delay)
                        try:
                            await msg.delete()
                        except Exception:
                            pass

                    asyncio.create_task(_delete_later(warn_msg, delete_warning_after))

                return  # Không chạy command

            # Cho phép chạy — tăng counter
            user_record["count"] += 1
            return await func(update, context, *args, **kwargs)

        return wrapper
    return decorator
