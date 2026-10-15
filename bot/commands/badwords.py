"""
Bad Words Filter
Tự động phát hiện và xử lý tin nhắn chứa từ tục, ngôn từ độc hại trong nhóm.

Hệ thống xử lý:
- Vi phạm 1-3 lần: Xóa tin nhắn âm thầm (hoặc ghi log)
- Vi phạm lần 4: Mute 5 phút + cảnh báo trong nhóm + nút "Hứa không chửi tục nữa (Gỡ Mute)"
- Hỗ trợ bắt cả tin nhắn text, ảnh/video có chú thích (caption), và tin nhắn được chỉnh sửa (edited_message)
- Miễn trừ Quản trị viên (Admin/Creator)
- Quản trị động qua lệnh: /addbadword, /delbadword, /badwords, /resetwarn
"""

import re
import os
import json
import time
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
    CallbackQueryHandler,
    ApplicationHandlerStop
)
from bot.utils.logger import log_command

# === Config ===
SILENT_THRESHOLD = 4

# === File paths ===
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_BAD_WORDS_PATH = os.path.join(_DATA_DIR, "bad_words.json")
_VIOLATIONS_PATH = os.path.join(_DATA_DIR, "user_violations.json")

# === Thread safety & cache ===
_lock = threading.Lock()
_bad_words: list = []
_bad_words_regex = None
_violations: dict = {}


def _atomic_write_json(file_path: str, data):
    """Ghi file dạng atomic để tránh hỏng dữ liệu khi ghi đồng thời"""
    abs_path = os.path.abspath(file_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    temp_path = f"{abs_path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, abs_path)


def _load_json(path, default):
    with _lock:
        try:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading {path}: {e}")
    return default


def _save_json(path, data):
    with _lock:
        try:
            _atomic_write_json(path, data)
        except Exception as e:
            print(f"⚠️ Error saving {path}: {e}")


def _init_filter():
    global _bad_words, _bad_words_regex, _violations
    _bad_words = _load_json(_BAD_WORDS_PATH, [])
    _violations = _load_json(_VIOLATIONS_PATH, {})
    _rebuild_regex()


def _rebuild_regex():
    global _bad_words_regex
    if _bad_words:
        # Sắp xếp từ dài trước từ ngắn để regex match chính xác
        sorted_words = sorted(set(_bad_words), key=len, reverse=True)
        pattern = r'(?:\b|_|\s|^)(?:' + '|'.join(map(re.escape, sorted_words)) + r')(?:\b|_|\s|$)'
        _bad_words_regex = re.compile(pattern, re.IGNORECASE)
    else:
        _bad_words_regex = None


async def _is_admin(chat, user, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not chat or chat.type not in ("group", "supergroup"):
        return False
    if not user:
        return False
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def _auto_delete_warning(context: ContextTypes.DEFAULT_TYPE):
    """Tự động xóa tin nhắn cảnh báo + reset vi phạm sau khi hết mute."""
    data = context.job.data
    try:
        await context.bot.delete_message(
            chat_id=data["chat_id"],
            message_id=data["message_id"]
        )
    except Exception as e:
        print(f"⚠️ Không xóa được tin nhắn cảnh báo: {e}")

    user_key = data["user_key"]
    if _violations.get(user_key, {}).get("count") == 0:
        _violations[user_key]["history"] = []
        _save_json(_VIOLATIONS_PATH, _violations)


async def check_bad_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quét tin nhắn trong nhóm, bao gồm cả text, caption ảnh và tin chỉnh sửa"""
    if not _bad_words_regex:
        return

    msg = update.effective_message
    if not msg:
        return

    # Lấy text từ tin nhắn hoặc caption media
    message_text = (msg.text or msg.caption or "").strip()
    if not message_text:
        return

    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return

    user = update.effective_user
    if not user or user.is_bot:
        return

    # Miễn trừ Quản trị viên
    if await _is_admin(chat, user, context):
        return

    match = _bad_words_regex.search(message_text.lower())
    if not match:
        return

    # 1. Xóa tin nhắn vi phạm
    try:
        await msg.delete()
    except Exception as e:
        print(f"⚠️ Không xóa được tin nhắn vi phạm từ cấm: {e}")

    # Ghi log vi phạm
    user_name = user.full_name or user.first_name or str(user.id)
    log_command(
        user_id=user.id,
        user_name=user_name,
        username=user.username,
        command_text=f"[BADWORD] Từ cấm: \"{match.group().strip()}\" | Câu: \"{message_text}\""
    )

    # 2. Cập nhật số lần vi phạm
    user_key = str(user.id)
    matched_word = match.group().strip()

    if isinstance(_violations.get(user_key), int):
        _violations[user_key] = {"count": _violations[user_key], "history": []}

    if user_key not in _violations:
        _violations[user_key] = {"count": 0, "history": []}

    _violations[user_key]["count"] += 1
    _violations[user_key]["history"].append({
        "message": message_text,
        "word": matched_word,
        "time": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    _violations[user_key]["history"] = _violations[user_key]["history"][-SILENT_THRESHOLD:]
    count = _violations[user_key]["count"]

    # 3. Mute nếu vi phạm vượt ngưỡng
    if count >= SILENT_THRESHOLD:
        mute_duration = 300  # 5 phút
        until_date = int(time.time() + mute_duration)
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date
            )
        except Exception as e:
            print(f"⚠️ Lỗi restrict_chat_member badwords: {e}")

        bot_username = context.bot.username or ""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Xem chi tiết vi phạm", url=f"https://t.me/{bot_username}?start=check_violation")],
            [InlineKeyboardButton("✅ Hứa không chửi tục nữa (Gỡ Mute)", callback_data=f"unmute_{user.id}")]
        ])

        text_warning = (
            f"⚠️ <a href='tg://user?id={user.id}'>{user.first_name}</a>, "
            f"bạn hãy giữ văn hóa giao tiếp trong nhóm nhé!\n"
            f"<i>(Đã vi phạm quy định ngôn từ lần thứ {count} — tạm dừng gửi tin nhắn 5 phút)</i>"
        )

        try:
            warning_msg = await context.bot.send_message(
                chat_id=chat.id,
                text=text_warning,
                message_thread_id=msg.message_thread_id,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

            # Tự động xóa cảnh báo và reset sau khi hết thời gian mute
            if context.job_queue:
                context.job_queue.run_once(
                    _auto_delete_warning,
                    when=mute_duration,
                    data={
                        "chat_id": chat.id,
                        "message_id": warning_msg.message_id,
                        "user_key": user_key,
                    },
                    name=f"delete_warn_{user.id}"
                )
        except Exception as e:
            print(f"⚠️ Lỗi gửi cảnh báo group: {e}")

        # Reset count về 0 sau khi xử phạt
        _violations[user_key]["count"] = 0

    _save_json(_VIOLATIONS_PATH, _violations)
    raise ApplicationHandlerStop()


async def handle_unmute_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id_to_unmute = int(data.split("_")[1])
    current_user_id = query.from_user.id

    if current_user_id != user_id_to_unmute:
        await query.answer("❌ Nút này chỉ dành cho người đang bị hạn chế!", show_alert=True)
        return

    chat_id = update.effective_chat.id
    current_jobs = context.job_queue.get_jobs_by_name(f"delete_warn_{current_user_id}") if context.job_queue else []

    try:
        chat_obj = await context.bot.get_chat(chat_id)
        normal_permissions = chat_obj.permissions
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=current_user_id,
            permissions=normal_permissions
        )
        for job in current_jobs:
            job.schedule_removal()

        await query.answer("✅ Bạn đã được gỡ hạn chế. Hãy tuân thủ văn hóa nhóm nhé!", show_alert=True)

        user_key = str(current_user_id)
        if user_key in _violations:
            _violations[user_key] = {"count": 0, "history": []}
            _save_json(_VIOLATIONS_PATH, _violations)

        await query.edit_message_text(
            text=f"✅ <a href='tg://user?id={current_user_id}'>{query.from_user.first_name}</a> đã cam kết giữ văn hóa giao tiếp và được gỡ mute thành công.",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"⚠️ Lỗi unmute callback: {e}")
        await query.answer("⚠️ Bot không đủ quyền hạn quản trị để gỡ mute.", show_alert=True)


async def resetwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh Admin: /resetwarn <user_id|reply>"""
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if not await _is_admin(chat, user, context):
        await msg.reply_text("⛔ Chỉ Quản trị viên mới được sử dụng lệnh này.")
        return

    target_id = None
    if context.args and context.args[0].isdigit():
        target_id = context.args[0]
    elif msg.reply_to_message and msg.reply_to_message.from_user:
        target_id = str(msg.reply_to_message.from_user.id)

    if target_id and target_id in _violations:
        _violations[target_id] = {"count": 0, "history": []}
        _save_json(_VIOLATIONS_PATH, _violations)
        await msg.reply_text(f"✅ Đã reset lịch sử vi phạm cho user: <code>{target_id}</code>", parse_mode="HTML")
    else:
        await msg.reply_text("Không tìm thấy dữ liệu vi phạm của user này.")


async def add_badword_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh Admin: /addbadword <từ_cấm>"""
    log_command("addbadword", update)
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if not await _is_admin(chat, user, context):
        await msg.reply_text("⛔ Chỉ Quản trị viên mới được sử dụng lệnh này.")
        return

    if not context.args:
        await msg.reply_text("Cú pháp: <code>/addbadword &lt;từ khóa cần cấm&gt;</code>", parse_mode="HTML")
        return

    word = " ".join(context.args).strip().lower()
    if word in _bad_words:
        await msg.reply_text(f"ℹ️ Từ khóa <code>{word}</code> đã có trong danh sách cấm.", parse_mode="HTML")
        return

    _bad_words.append(word)
    _save_json(_BAD_WORDS_PATH, _bad_words)
    _rebuild_regex()

    await msg.reply_text(f"✅ Đã thêm từ cấm mới: <code>{word}</code> (Tổng cộng: {_bad_words.__len__()} từ).", parse_mode="HTML")


async def del_badword_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh Admin: /delbadword <từ_cấm>"""
    log_command("delbadword", update)
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if not await _is_admin(chat, user, context):
        await msg.reply_text("⛔ Chỉ Quản trị viên mới được sử dụng lệnh này.")
        return

    if not context.args:
        await msg.reply_text("Cú pháp: <code>/delbadword &lt;từ khóa muốn xóa&gt;</code>", parse_mode="HTML")
        return

    word = " ".join(context.args).strip().lower()
    if word not in _bad_words:
        await msg.reply_text(f"❌ Từ khóa <code>{word}</code> không tồn tại trong danh sách cấm.", parse_mode="HTML")
        return

    _bad_words.remove(word)
    _save_json(_BAD_WORDS_PATH, _bad_words)
    _rebuild_regex()

    await msg.reply_text(f"✅ Đã xóa từ cấm: <code>{word}</code> (Còn lại: {_bad_words.__len__()} từ).", parse_mode="HTML")


async def list_badwords_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh Admin: /badwords xem tổng số từ cấm"""
    log_command("badwords", update)
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if not await _is_admin(chat, user, context):
        await msg.reply_text("⛔ Chỉ Quản trị viên mới được sử dụng lệnh này.")
        return

    total = len(_bad_words)
    await msg.reply_text(
        f"📋 <b>Danh Sách Từ Cấm (Bad Words)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 <b>Tổng số từ ngữ đang lọc:</b> <code>{total}</code> từ\n"
        f"💡 <i>Để thêm từ cấm mới:</i> <code>/addbadword &lt;từ&gt;</code>\n"
        f"💡 <i>Để xóa từ cấm:</i> <code>/delbadword &lt;từ&gt;</code>",
        parse_mode="HTML"
    )


def get_user_violations(user_id: str) -> list:
    """Trả về danh sách lịch sử vi phạm của user (dùng cho deep link check_violation)."""
    data = _violations.get(user_id)
    if isinstance(data, dict):
        return data.get("history", [])
    return []


# Khởi tạo nạp từ cấm ban đầu
_init_filter()


def get_handlers():
    group_filter = (filters.TEXT | filters.CAPTION) & filters.ChatType.GROUPS & ~filters.COMMAND
    return [
        MessageHandler(group_filter, check_bad_words),
        CommandHandler("resetwarn", resetwarn_command),
        CommandHandler("addbadword", add_badword_command),
        CommandHandler("delbadword", del_badword_command),
        CommandHandler("badwords", list_badwords_command),
        CallbackQueryHandler(handle_unmute_callback, pattern="^unmute_"),
    ]
