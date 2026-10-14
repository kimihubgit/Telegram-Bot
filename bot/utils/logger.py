"""
Command Logger
Ghi log toàn bộ lệnh/tin nhắn của người dùng vào file .log theo ngày.

Format log:
    2024-09-12 15:10:29,698 - UserID: UserID: 6671951119, UserName: Trần Thị Huệ, UserLink: https://t.me/hue2403, Command: /freepik https://...

Log files được lưu vào thư mục log/ theo ngày: log/2026-05-14.log
"""
import logging
import os
from datetime import datetime
from pathlib import Path

# Thư mục log
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Cache logger theo ngày để không tạo lại mỗi lần
_current_date: str = ""
_logger: logging.Logger | None = None


def _get_logger() -> logging.Logger:
    """Lấy logger cho ngày hiện tại. Tự tạo file mới khi sang ngày."""
    global _current_date, _logger

    today = datetime.now().strftime("%Y-%m-%d")

    if today != _current_date or _logger is None:
        _current_date = today

        # Tạo/lấy logger
        logger = logging.getLogger("bot_command_log")
        logger.setLevel(logging.INFO)

        # Xóa handler cũ (nếu sang ngày mới)
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

        # Tạo file handler mới cho ngày hôm nay
        log_file = LOG_DIR / f"{today}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)

        # Format giống mẫu user cung cấp
        formatter = logging.Formatter("%(asctime)s - %(message)s")
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        _logger = logger

    return _logger


def log_command(user_id: int, user_name: str, username: str | None, command_text: str):
    """
    Ghi log 1 lệnh/tin nhắn của người dùng.

    Args:
        user_id: Telegram user ID
        user_name: Tên hiển thị (first_name + last_name)
        username: @username (có thể None)
        command_text: Nội dung lệnh hoặc tin nhắn
    """
    logger = _get_logger()

    # Build user link
    if username:
        user_link = f"https://t.me/{username}"
    else:
        user_link = "No username"

    # Format giống mẫu cũ
    log_message = (
        f"UserID: UserID: {user_id}, "
        f"UserName: {user_name}, "
        f"UserLink: {user_link}, "
        f"Command: {command_text}"
    )

    logger.info(log_message)


def log_from_update(update, command_text: str | None = None):
    """
    Tiện ích: tự lấy thông tin user từ Update object và ghi log.

    Args:
        update: telegram.Update object
        command_text: Nội dung lệnh. Nếu None, lấy từ message.text
    """
    if not update.effective_user:
        return

    user = update.effective_user
    user_name = user.full_name or user.first_name or str(user.id)
    username = user.username

    # Lấy command text
    if command_text is None:
        if update.message and update.message.text:
            command_text = update.message.text
        else:
            command_text = "[non-text message]"

    log_command(
        user_id=user.id,
        user_name=user_name,
        username=username,
        command_text=command_text,
    )
