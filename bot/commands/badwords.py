# """
# Bad Words Filter
# Tự động phát hiện và xử lý tin nhắn chứa từ tục trong nhóm.

# Hệ thống xử lý:
# - Vi phạm 1-2 lần: Xóa tin nhắn (không thông báo)
# - Vi phạm lần 3: Xóa tin nhắn + gửi tin nhắn riêng cho user
#   (thông báo vi phạm quá nhiều, kèm nút inbox bot)
# - Vi phạm lần 4+: Xóa tin nhắn + gửi tin nhắn riêng kèm từ khóa vi phạm
# - Admin/Creator: Miễn trừ

# Cần file data/bad_words.json chứa danh sách từ cấm.
# """


import re
import os
import json
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, filters, CallbackQueryHandler, ApplicationHandlerStop
from bot.utils.logger import log_command

# === Config ===
SILENT_THRESHOLD = 4

# === File paths ===
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_BAD_WORDS_PATH = os.path.join(_DATA_DIR, "bad_words.json")
_VIOLATIONS_PATH = os.path.join(_DATA_DIR, "user_violations.json")

# === In-memory data ===
_bad_words: list = []
_bad_words_regex = None
_violations: dict = {}

def _load_json(path, default):
    try:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            with open(abs_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading {path}: {e}")
    return default

def _save_json(path, data):
    try:
        abs_path = os.path.abspath(path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Error saving {path}: {e}")

def _init_filter():
    global _bad_words, _bad_words_regex, _violations
    _bad_words = _load_json(_BAD_WORDS_PATH, [])
    _violations = _load_json(_VIOLATIONS_PATH, {})

    if _bad_words:
        pattern = r'(?:' + '|'.join(map(re.escape, _bad_words)) + r')'
        _bad_words_regex = re.compile(pattern, re.IGNORECASE)
    else:
        _bad_words_regex = None

async def _auto_delete_warning(context):
    """Tự động xóa tin nhắn cảnh báo + reset vi phạm sau khi hết mute."""
    data = context.job.data
    try:
        await context.bot.delete_message(
            chat_id=data["chat_id"],
            message_id=data["message_id"]
        )
    except Exception as e:
        print(f"⚠️ Không xóa được tin nhắn cảnh báo: {e}")
        # return
    # Chỉ reset history nếu từ lúc bị mute đến giờ họ chưa vi phạm thêm lần nào (count vẫn bằng 0)
    user_key = data["user_key"]
    if _violations.get(user_key, {}).get("count") == 0:
        _violations[user_key]["history"] = []
        _save_json(_VIOLATIONS_PATH, _violations)

async def check_bad_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _bad_words_regex or not update.message or not update.message.text:
        return
    if update.effective_chat.type not in ("group", "supergroup"):
        return

    message_text = update.message.text
    user = update.message.from_user
    chat_id = update.effective_chat.id
    thread_id = update.message.message_thread_id
    match = _bad_words_regex.search(message_text.lower())
    if not match:
        return

    # Miễn trừ Admin
    # try:
    #     member = await context.bot.get_chat_member(chat_id, user.id)
    #     if member.status in ("administrator", "creator"):
    #         return
    # except:
    #     pass

    try:
        await update.message.delete()
    except Exception as e:
        print(f"⚠️ Không xóa được tin nhắn: {e}")

    # Ghi log vi phạm
    user_name = user.full_name or user.first_name or str(user.id)
    log_command(
        user_id=user.id,
        user_name=user_name,
        username=user.username,
        command_text=f"[BADWORD] Từ cấm: \"{match.group()}\" | Câu vi phạm: \"{message_text}\""
    )

    # 2. Cập nhật số lần vi phạm
    user_key = str(user.id)
    matched_word = match.group()

    # Migrate old format (int) to new format (dict)
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
    # Chỉ giữ lại history trong chu kỳ hiện tại (giới hạn SILENT_THRESHOLD)
    _violations[user_key]["history"] = _violations[user_key]["history"][-SILENT_THRESHOLD:]
    count = _violations[user_key]["count"]

    # 3. Xử lý thông báo theo số lần
    if count >= SILENT_THRESHOLD:
        mute_permissions = ChatPermissions(can_send_messages=False)
        mute_duration = 300  # 5 phút
        until_date = int(time.time() + mute_duration)
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user.id,
                permissions=mute_permissions,
                until_date=until_date
            )
        except Exception as e:
            print(f"⚠️ Lỗi mute bad_words: {e}")
        bot_username = context.bot.username
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 check vi phạm", url=f"https://t.me/{bot_username}?start=check_violation")],
            [InlineKeyboardButton("✅ Hứa không chửi tục nữa (Gỡ Mute)", callback_data=f"unmute_{user.id}")]
        ])

        text_warning = (
            f"⚠️ <a href='tg://user?id={user.id}'>{user.first_name}</a>, "
            f"bạn chửi tục ít lại nhé, chửi tục hơi nhiều rồi đó!\n"
            f"<i>(Vi phạm lần thứ {count} rồi đó :V)</i>"
        )
        
        
        try:
            warning_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=text_warning,
                message_thread_id=thread_id, # Gửi vào đúng Topic
                reply_markup=keyboard,       # Thêm nút bấm
                parse_mode="HTML"
            )
            # Tự động xóa tin nhắn cảnh báo + reset vi phạm sau khi hết mute
            context.job_queue.run_once(
                _auto_delete_warning,
                when=mute_duration,
                data={
                    "chat_id": chat_id,
                    "message_id": warning_msg.message_id,
                    "user_key": user_key,
                },
                name=f"delete_warn_{user.id}"
            )
        except Exception as e:
            print(f"⚠️ Lỗi gửi cảnh báo group: {e}")

        # === QUAN TRỌNG: Reset số lần vi phạm về 0 sau khi nhắc nhở (giữ lại history) ===
        _violations[user_key]["count"] = 0
    
    # Lưu lại dữ liệu (dù là tăng lên 1, 2 hay reset về 0)
    _save_json(_VIOLATIONS_PATH, _violations)

    # Chặn đứng hoàn toàn, không cho chạy xuống các handler phía sau (lệnh)
    raise ApplicationHandlerStop()


async def handle_unmute_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id_to_unmute = int(data.split("_")[1])
    current_user_id = query.from_user.id

    # Chỉ người bị mute mới có quyền nhấn nút của chính mình
    if current_user_id != user_id_to_unmute:
        await query.answer("❌ Nút này không dành cho bạn!", show_alert=True)
        return

    # Gỡ mute (trả lại quyền hạn bình thường của group)
    normal_permissions = (await context.bot.get_chat(update.effective_chat.id)).permissions
    current_jobs = context.job_queue.get_jobs_by_name(f"delete_warn_{current_user_id}")
    
    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=current_user_id,
            permissions=normal_permissions
        )
        for job in current_jobs:
            job.schedule_removal() # Hủy lịch hẹn giờ, Job sẽ biến mất hoàn toàn!
        await query.answer("✅ Bạn đã được gỡ mute. Hãy giữ văn hóa nhé!", show_alert=True)
        # Reset vi phạm (count + history) sau khi gỡ mute
        user_key = str(current_user_id)
        _violations[user_key] = {"count": 0, "history": []}
        _save_json(_VIOLATIONS_PATH, _violations)
        # Sửa lại tin nhắn cũ để thông báo đã xong
        await query.edit_message_text(
            text=f"✅ Nhớ nhé <a href='tg://user?id={current_user_id}'>{query.from_user.first_name}</a> đã hứa rồi đó, không được chửi tục nữa, không thui là lần sau mute lâu hơn đó :V",
            parse_mode="HTML"
        )
    except Exception as e:
        await query.answer("⚠️ Lỗi: Bot không đủ quyền để gỡ mute.", show_alert=True)

async def resetwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"): return
    
    caller = await context.bot.get_chat_member(chat.id, update.effective_user.id)
    if caller.status not in ("administrator", "creator"):
        return

    target_id = None
    if context.args and context.args[0].isdigit():
        target_id = context.args[0]
    elif update.message.reply_to_message:
        target_id = str(update.message.reply_to_message.from_user.id)

    if target_id and target_id in _violations:
        _violations[target_id] = {"count": 0, "history": []}
        _save_json(_VIOLATIONS_PATH, _violations)
        await update.message.reply_text(f"✅ Đã reset vi phạm cho `{target_id}`", parse_mode="MarkdownV2")

def get_user_violations(user_id: str) -> list:
    """Trả về danh sách lịch sử vi phạm của user (dùng cho deep link check_violation)."""
    data = _violations.get(user_id)
    if isinstance(data, dict):
        return data.get("history", [])
    return []

_init_filter()

def get_handlers():
    return [
        MessageHandler(filters.TEXT & filters.ChatType.GROUPS & ~filters.COMMAND, check_bad_words),
        CommandHandler("resetwarn", resetwarn_command),
        CallbackQueryHandler(handle_unmute_callback, pattern="^unmute_"), # Xử lý nút bấm gỡ mute
    ]
