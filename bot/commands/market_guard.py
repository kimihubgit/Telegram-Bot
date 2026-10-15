"""
Market Guard (KiGuard Sales AI Moderator)
Tự động phát hiện tin nhắn bán hàng / rao vặt / quảng cáo trong nhóm Telegram bằng AI:
1. Hỗ trợ bắt cả tin nhắn văn bản (text), tin nhắn media kèm chú thích (caption), và tin nhắn đã chỉnh sửa (edited_message).
2. Yêu cầu hashtag bắt buộc (mặc định #NghienPlusMarket hoặc tùy biến theo từng group qua /sethashtag).
   Nếu chưa có hashtag -> Bot nhắc nhở thành viên bổ sung.
3. Giới hạn số bài rao bán tối đa mỗi ngày (mặc định 6 bài/ngày, tùy biến qua /setmaxsales).
   Nếu vượt quá -> Xóa bài + Mute 12 giờ + Thông báo.
4. Quản trị động qua lệnh: /marketguard, /sethashtag, /setmaxsales, /resetsales, /marketstats, /checksales, /datastats.
5. Thread-safe & atomic save chống xung đột đọc/ghi đồng thời trên các nhóm đông thành viên.
"""
import os
import json
import asyncio
import threading
from datetime import datetime, timedelta, timezone
from telegram import Update, ChatPermissions
from telegram.ext import (
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters
)

# Import module AI detector
import sys
from pathlib import Path

_candidate1 = Path(__file__).resolve().parent.parent.parent / "LLM Ai"
_candidate2 = Path(__file__).resolve().parent.parent / "LLM Ai"
_llm_dir = _candidate1 if _candidate1.exists() else _candidate2

if str(_llm_dir) not in sys.path:
    sys.path.insert(0, str(_llm_dir))

from sales_detector import check_sales_detail
from bot.services.data_collector import save_message_for_training, get_collector_stats
from bot.utils.logger import log_command

# === Cấu hình Mặc Định ===
DEFAULT_REQUIRED_HASHTAG = "#NghienPlusMarket"
DEFAULT_MAX_SALES_PER_DAY = 6
MUTE_DURATION_HOURS = 12
AUTO_DELETE_WARNING_SECONDS = 60

# Đường dẫn dữ liệu
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_POSTS_TRACKER_PATH = os.path.join(_DATA_DIR, "market_posts_tracker.json")
_SETTINGS_PATH = os.path.join(_DATA_DIR, "market_guard_settings.json")
_STATS_PATH = os.path.join(_DATA_DIR, "market_guard_stats.json")

# Locks & Cache chống Race Condition
_file_lock = threading.Lock()
_posts_cache = {}
_settings_cache = {}
_stats_cache = {}


def _get_vn_date_str() -> str:
    """Lấy ngày theo giờ Việt Nam (UTC+7) định dạng YYYY-MM-DD"""
    vn_tz = timezone(timedelta(hours=7))
    return datetime.now(vn_tz).strftime("%Y-%m-%d")


def _atomic_write_json(file_path: str, data: dict):
    """Ghi file an toàn dạng atomic (ghi vào file tmp rồi rename) tránh hỏng dữ liệu"""
    abs_path = os.path.abspath(file_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    temp_path = f"{abs_path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, abs_path)


# ══════════════════════════════════════════════════════════════
# CẤU HÌNH NHÓM (SETTINGS CACHE)
# ══════════════════════════════════════════════════════════════

def _load_settings() -> dict:
    global _settings_cache
    with _file_lock:
        if os.path.exists(_SETTINGS_PATH):
            try:
                with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    _settings_cache = json.load(f)
                    return _settings_cache
            except Exception as e:
                print(f"⚠️ [Market Guard] Lỗi đọc settings: {e}")
        _settings_cache = {}
        return _settings_cache


def _save_settings():
    with _file_lock:
        try:
            _atomic_write_json(_SETTINGS_PATH, _settings_cache)
        except Exception as e:
            print(f"⚠️ [Market Guard] Lỗi ghi settings: {e}")


def _get_group_settings(chat_id: int) -> dict:
    cid = str(chat_id)
    if cid not in _settings_cache:
        _settings_cache[cid] = {
            "enabled": True,
            "required_hashtag": DEFAULT_REQUIRED_HASHTAG,
            "max_sales_per_day": DEFAULT_MAX_SALES_PER_DAY
        }
    return _settings_cache[cid]


# ══════════════════════════════════════════════════════════════
# TRACKER BÀI ĐĂNG (POSTS TRACKER)
# ══════════════════════════════════════════════════════════════

def _load_tracker() -> dict:
    global _posts_cache
    with _file_lock:
        if os.path.exists(_POSTS_TRACKER_PATH):
            try:
                with open(_POSTS_TRACKER_PATH, "r", encoding="utf-8") as f:
                    _posts_cache = json.load(f)
                    return _posts_cache
            except Exception as e:
                print(f"⚠️ [Market Guard] Lỗi đọc file tracker: {e}")
        _posts_cache = {}
        return _posts_cache


def _save_tracker():
    with _file_lock:
        try:
            _atomic_write_json(_POSTS_TRACKER_PATH, _posts_cache)
        except Exception as e:
            print(f"⚠️ [Market Guard] Lỗi ghi file tracker: {e}")


def _get_user_posts_today(chat_id: int, user_id: int) -> int:
    today = _get_vn_date_str()
    key = f"{chat_id}_{user_id}"
    today_records = _posts_cache.get(today, {})
    return today_records.get(key, 0)


def _increment_user_posts(chat_id: int, user_id: int) -> int:
    today = _get_vn_date_str()
    key = f"{chat_id}_{user_id}"
    if today not in _posts_cache:
        _posts_cache.clear()  # Xóa ngày cũ để giữ nhẹ file
        _posts_cache[today] = {}

    current = _posts_cache[today].get(key, 0) + 1
    _posts_cache[today][key] = current
    _save_tracker()
    return current


# ══════════════════════════════════════════════════════════════
# THỐNG KÊ KIỂM DUYỆT (STATS TRACKER)
# ══════════════════════════════════════════════════════════════

def _record_stat(chat_id: int, stat_type: str):
    """Ghi nhận thống kê: scanned, sales_detected, warned, muted"""
    global _stats_cache
    today = _get_vn_date_str()
    cid = str(chat_id)
    with _file_lock:
        if today not in _stats_cache:
            _stats_cache.clear()
            _stats_cache[today] = {}
        if cid not in _stats_cache[today]:
            _stats_cache[today][cid] = {
                "scanned": 0,
                "sales_detected": 0,
                "warned": 0,
                "muted": 0
            }
        _stats_cache[today][cid][stat_type] = _stats_cache[today][cid].get(stat_type, 0) + 1
        try:
            _atomic_write_json(_STATS_PATH, _stats_cache)
        except Exception:
            pass


async def _is_admin(chat, user, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Kiểm tra xem người dùng có phải admin hoặc chủ nhóm hay không"""
    if not chat or chat.type not in ("group", "supergroup"):
        return False
    if not user:
        return False
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def _delete_message_after_delay(context: ContextTypes.DEFAULT_TYPE):
    """Job xóa tin nhắn nhắc nhở tự động sau khoảng thời gian định sẵn"""
    job_data = context.job.data
    try:
        await context.bot.delete_message(
            chat_id=job_data["chat_id"],
            message_id=job_data["message_id"]
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
# MIDDLEWARE KIỂM DUYỆT BÀI ĐĂNG (TEXT + CAPTION + EDITED)
# ══════════════════════════════════════════════════════════════

async def market_guard_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Middleware quét nội dung tin nhắn gửi vào nhóm.
    Hỗ trợ cả tin nhắn gốc (message), tin chỉnh sửa (edited_message),
    và ảnh/video đính kèm chú thích (caption).
    """
    msg = update.effective_message
    if not msg:
        return

    # Lấy văn bản từ text hoặc caption (ảnh/video đính kèm bài viết)
    raw_text = msg.text or msg.caption
    if not raw_text:
        return

    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return

    user = update.effective_user
    if not user or user.is_bot:
        return

    # 1. Kiểm tra trạng thái bật/tắt Market Guard của nhóm
    settings = _get_group_settings(chat.id)
    if not settings.get("enabled", True):
        return

    # 2. Miễn trừ Admin / Chủ nhóm
    if await _is_admin(chat, user, context):
        return

    text = raw_text.strip()
    if len(text) < 3:
        return

    _record_stat(chat.id, "scanned")

    # 3. Phân tích nội dung qua mô hình AI (PhoBERT hoặc TF-IDF Ensemble)
    try:
        analysis = check_sales_detail(text)
    except Exception as e:
        print(f"⚠️ [Market Guard] Lỗi AI Detector: {e}")
        return

    is_sales = bool(analysis.get("is_sales", False))
    conf = float(analysis.get("confidence", 0.0))
    engine = str(analysis.get("engine", "AI"))

    # 4. Thu thập dữ liệu vào 2 thư mục riêng biệt ('ban_hang/' và 'khong_ban_hang/')
    try:
        save_message_for_training(
            text=text,
            is_sales=is_sales,
            user_id=user.id,
            chat_id=chat.id,
            confidence=conf,
            engine=engine
        )
    except Exception as e:
        print(f"⚠️ [Market Guard] Lỗi lưu dữ liệu thu thập: {e}")

    # Nếu AI xác nhận KHÔNG PHẢI tin bán hàng -> Cho phép tin nhắn đi tiếp bình thường
    if not is_sales:
        return

    # ══════════════════════════════════════════════════════════════
    # PHÁT HIỆN TIN BÁN HÀNG / DỊCH VỤ!
    # ══════════════════════════════════════════════════════════════
    _record_stat(chat.id, "sales_detected")

    full_name = user.full_name or user.first_name or "Bạn"
    required_tag = settings.get("required_hashtag", DEFAULT_REQUIRED_HASHTAG)
    max_sales = settings.get("max_sales_per_day", DEFAULT_MAX_SALES_PER_DAY)
    has_hashtag = required_tag.lower() in text.lower()

    # Kiểm tra hạn mức bài rao bán trong ngày
    count_today = _get_user_posts_today(chat.id, user.id)

    # TRƯỜNG HỢP 1: Vượt quá giới hạn bài rao bán trong ngày
    if count_today >= max_sales:
        _record_stat(chat.id, "muted")
        try:
            await msg.delete()
        except Exception as e:
            print(f"⚠️ [Market Guard] Không xóa được tin nhắn vi phạm: {e}")

        # Mute user 12 giờ
        until_time = datetime.now() + timedelta(hours=MUTE_DURATION_HOURS)
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                until_date=until_time,
                permissions=ChatPermissions(can_send_messages=False)
            )
        except Exception as e:
            print(f"⚠️ [Market Guard] Không thể mute user {user.id}: {e}")

        # Gửi thông báo vi phạm lên nhóm
        mute_alert = (
            f"🚫 <b>Market Guard Alert</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <a href='tg://user?id={user.id}'>{full_name}</a> (<code>{user.id}</code>)\n"
            f"⚠️ Bạn đã vượt hạn mức rao bán <b>{max_sales} bài/ngày</b>.\n"
            f"⏳ Tài khoản bị tạm dừng quyền gửi tin nhắn trong <b>{MUTE_DURATION_HOURS} giờ</b>."
        )
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=mute_alert,
                message_thread_id=msg.message_thread_id,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ [Market Guard] Không thể gửi thông báo mute: {e}")
        return

    # Tăng số lượng bài đăng bán trong ngày
    _increment_user_posts(chat.id, user.id)

    # TRƯỜNG HỢP 2: Bài đăng thiếu hashtag yêu cầu
    if not has_hashtag:
        _record_stat(chat.id, "warned")
        warning_text = (
            f"⚠️ <a href='tg://user?id={user.id}'>{full_name}</a> ơi!\n"
            f"Bài viết của bạn được nhận diện là tin bán hàng/dịch vụ.\n"
            f"👉 Vui lòng bổ sung hashtag <code>{required_tag}</code> vào bài viết nhé!"
        )
        try:
            warn_msg = await msg.reply_text(warning_text, parse_mode="HTML")

            # Tự động xóa cảnh báo sau 60s để giữ group sạch sẽ
            if context.job_queue:
                context.job_queue.run_once(
                    _delete_message_after_delay,
                    AUTO_DELETE_WARNING_SECONDS,
                    data={"chat_id": chat.id, "message_id": warn_msg.message_id}
                )
        except Exception as e:
            print(f"⚠️ [Market Guard] Không gửi được lời nhắc hashtag: {e}")


# ══════════════════════════════════════════════════════════════
# CÁC LỆNH ADMIN & TIỆN ÍCH (COMMANDS)
# ══════════════════════════════════════════════════════════════

async def check_sales_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Lệnh kiểm tra: /checksales <văn bản> hoặc Reply tin nhắn bất kỳ bằng /checksales
    Hỗ trợ kiểm tra cả ảnh có caption!
    """
    log_command("checksales", update)
    msg = update.effective_message
    if not msg:
        return

    text_to_check = ""
    reply = msg.reply_to_message
    if reply:
        text_to_check = (reply.text or reply.caption or "").strip()
    elif context.args:
        text_to_check = " ".join(context.args).strip()

    if not text_to_check:
        await msg.reply_text(
            "ℹ️ <b>Cách dùng lệnh /checksales:</b>\n"
            "1. Reply tin nhắn bất kỳ (text hoặc ảnh có caption) và gõ: <code>/checksales</code>\n"
            "2. Hoặc gõ trực tiếp: <code>/checksales &lt;nội dung tin nhắn&gt;</code>",
            parse_mode="HTML"
        )
        return

    chat_id = update.effective_chat.id if update.effective_chat else 0
    settings = _get_group_settings(chat_id)
    required_tag = settings.get("required_hashtag", DEFAULT_REQUIRED_HASHTAG)

    analysis = check_sales_detail(text_to_check)
    is_sales = analysis["is_sales"]
    conf = analysis["confidence"]
    engine = analysis["engine"]
    clean_t = analysis["clean_text"]
    has_tag = required_tag.lower() in text_to_check.lower()

    status_icon = "🛒 BÁN HÀNG / RAO VẶT (1)" if is_sales else "💬 BÌNH THƯỜNG / HỎI MUA (0)"
    tag_status = "✅ Đã có" if has_tag else f"❌ Thiếu ({required_tag})"

    response = (
        f"🤖 <b>KiGuard AI - Sales Detector</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Kết quả:</b> {status_icon}\n"
        f"🎯 <b>Độ tin cậy:</b> <code>{conf:.2f}%</code>\n"
        f"⚙️ <b>Engine AI:</b> <code>{engine}</code>\n"
        f"🏷️ <b>Hashtag:</b> {tag_status}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🧹 <b>Đã khử nhiễu:</b> <i>{clean_t[:150]}...</i>" if len(clean_t) > 150 else
        f"🧹 <b>Đã khử nhiễu:</b> <i>{clean_t}</i>"
    )

    await msg.reply_text(response, parse_mode="HTML")


async def reset_sales_limit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Lệnh Admin: /resetsales <user_id>
    Reset số bài rao bán trong ngày của một user.
    """
    log_command("resetsales", update)
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not await _is_admin(chat, user, context):
        await msg.reply_text("⛔ Chỉ Quản trị viên mới được sử dụng lệnh này.")
        return

    target_id = None
    if context.args and context.args[0].isdigit():
        target_id = context.args[0]
    elif msg.reply_to_message and msg.reply_to_message.from_user:
        target_id = str(msg.reply_to_message.from_user.id)

    if not target_id:
        await msg.reply_text("Vui lòng chỉ định user_id hoặc reply tin nhắn của user cần reset.")
        return

    today = _get_vn_date_str()
    key = f"{chat.id}_{target_id}"
    if today in _posts_cache and key in _posts_cache[today]:
        del _posts_cache[today][key]
        _save_tracker()
        await msg.reply_text(f"✅ Đã reset số lượt rao bán hôm nay của user: <code>{target_id}</code>", parse_mode="HTML")
    else:
        await msg.reply_text(f"ℹ️ User <code>{target_id}</code> chưa có bài rao bán nào trong nhóm hôm nay.", parse_mode="HTML")


async def marketguard_config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Lệnh Admin: /marketguard <on|off|status>
    Bật, tắt hoặc xem trạng thái Market Guard trong nhóm hiện tại.
    """
    log_command("marketguard", update)
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not await _is_admin(chat, user, context):
        await msg.reply_text("⛔ Chỉ Quản trị viên mới được sử dụng lệnh này.")
        return

    settings = _get_group_settings(chat.id)
    if not context.args:
        status_text = "🟢 Đang BẬT" if settings.get("enabled", True) else "🔴 Đang TẮT"
        await msg.reply_text(
            f"🛡️ <b>Trạng Thái Market Guard Nhóm</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ <b>Trạng thái:</b> {status_text}\n"
            f"🏷️ <b>Hashtag yêu cầu:</b> <code>{settings.get('required_hashtag', DEFAULT_REQUIRED_HASHTAG)}</code>\n"
            f"📊 <b>Giới hạn:</b> <code>{settings.get('max_sales_per_day', DEFAULT_MAX_SALES_PER_DAY)} bài/ngày</code>\n\n"
            f"💡 <i>Lệnh điều khiển:</i>\n"
            f"• <code>/marketguard on</code> — Bật bảo vệ\n"
            f"• <code>/marketguard off</code> — Tắt bảo vệ\n"
            f"• <code>/sethashtag #HashtagCuaBan</code> — Đổi hashtag\n"
            f"• <code>/setmaxsales &lt;số&gt;</code> — Đổi giới hạn bài/ngày",
            parse_mode="HTML"
        )
        return

    action = context.args[0].lower()
    if action == "on":
        settings["enabled"] = True
        _save_settings()
        await msg.reply_text("✅ Đã <b>BẬT</b> tính năng kiểm duyệt quảng cáo & bán hàng (Market Guard) cho nhóm!", parse_mode="HTML")
    elif action == "off":
        settings["enabled"] = False
        _save_settings()
        await msg.reply_text("⚠️ Đã <b>TẮT</b> Market Guard cho nhóm này.", parse_mode="HTML")
    else:
        await msg.reply_text("Cú pháp: <code>/marketguard on</code> hoặc <code>/marketguard off</code>", parse_mode="HTML")


async def sethashtag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Lệnh Admin: /sethashtag <#hashtag>
    Đổi hashtag bắt buộc khi đăng bài bán hàng trong nhóm.
    """
    log_command("sethashtag", update)
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not await _is_admin(chat, user, context):
        await msg.reply_text("⛔ Chỉ Quản trị viên mới được sử dụng lệnh này.")
        return

    if not context.args:
        await msg.reply_text("Cú pháp: <code>/sethashtag #TenHashtag</code>", parse_mode="HTML")
        return

    new_tag = context.args[0].strip()
    if not new_tag.startswith("#"):
        new_tag = f"#{new_tag}"

    settings = _get_group_settings(chat.id)
    settings["required_hashtag"] = new_tag
    _save_settings()

    await msg.reply_text(f"✅ Đã đổi hashtag bắt buộc của nhóm thành: <code>{new_tag}</code>", parse_mode="HTML")


async def setmaxsales_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Lệnh Admin: /setmaxsales <số_bài>
    Đổi số lượng bài rao bán tối đa mỗi ngày của thành viên.
    """
    log_command("setmaxsales", update)
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not await _is_admin(chat, user, context):
        await msg.reply_text("⛔ Chỉ Quản trị viên mới được sử dụng lệnh này.")
        return

    if not context.args or not context.args[0].isdigit():
        await msg.reply_text("Cú pháp: <code>/setmaxsales &lt;số bài&gt;</code> (ví dụ: /setmaxsales 5)", parse_mode="HTML")
        return

    limit = int(context.args[0])
    if limit < 1 or limit > 50:
        await msg.reply_text("Số bài mỗi ngày phải từ 1 đến 50.")
        return

    settings = _get_group_settings(chat.id)
    settings["max_sales_per_day"] = limit
    _save_settings()

    await msg.reply_text(f"✅ Đã cập nhật giới hạn bài rao bán: <b>{limit} bài/ngày</b>", parse_mode="HTML")


async def marketstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Lệnh Admin: /marketstats hoặc /stats
    Xem báo cáo kiểm duyệt hôm nay trong nhóm.
    """
    log_command("marketstats", update)
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not await _is_admin(chat, user, context):
        await msg.reply_text("⛔ Chỉ Quản trị viên mới được sử dụng lệnh này.")
        return

    today = _get_vn_date_str()
    cid = str(chat.id)
    group_stats = _stats_cache.get(today, {}).get(cid, {})

    scanned = group_stats.get("scanned", 0)
    sales = group_stats.get("sales_detected", 0)
    warned = group_stats.get("warned", 0)
    muted = group_stats.get("muted", 0)

    report = (
        f"📊 <b>Báo Cáo Kiểm Duyệt Hôm Nay ({today})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 <b>Tổng tin nhắn đã quét:</b> <code>{scanned}</code>\n"
        f"🛒 <b>Phát hiện rao bán/QC:</b> <code>{sales}</code>\n"
        f"⚠️ <b>Nhắc nhở thiếu hashtag:</b> <code>{warned}</code>\n"
        f"🚫 <b>Mute thành viên quá hạn:</b> <code>{muted}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <i>KiGuard Sales AI Moderator — Nhóm: {chat.title}</i>"
    )
    await msg.reply_text(report, parse_mode="HTML")


async def datastats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Lệnh /datastats: Xem thống kê dữ liệu đã thu thập để train tiếp
    """
    log_command("datastats", update)
    msg = update.effective_message
    stats = get_collector_stats()

    response = (
        f"📊 <b>Thống Kê Thu Thập Dữ Liệu Huấn Luyện AI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 <b>Thư mục Bán hàng:</b> <code>{stats['sales_count']}</code> mẫu\n"
        f"📁 <i>Vị trí: bot/LLM Ai/collected_data/ban_hang/ban_hang.csv</i>\n\n"
        f"💬 <b>Thư mục Không bán hàng:</b> <code>{stats['non_sales_count']}</code> mẫu\n"
        f"📁 <i>Vị trí: bot/LLM Ai/collected_data/khong_ban_hang/khong_ban_hang.csv</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Tổng cộng đã tích lũy:</b> <code>{stats['total_count']}</code> mẫu mới!\n"
        f"💡 <i>Dữ liệu được lưu chuẩn UTF-8-SIG chống trùng lặp tự động.</i>"
    )
    await msg.reply_text(response, parse_mode="HTML")


# Khởi tạo nạp dữ liệu ban đầu
_load_tracker()
_load_settings()


def get_handlers():
    """Hàm trả về danh sách handlers để loader.py tự động đăng ký"""
    # Lọc tất cả tin nhắn văn bản VÀ media có chú thích trong nhóm (cả tin nhắn mới và tin nhắn sửa)
    group_filter = (filters.TEXT | filters.CAPTION) & filters.ChatType.GROUPS & ~filters.COMMAND
    return [
        # Middleware quét bài đăng
        MessageHandler(group_filter, market_guard_message_handler),
        # Lệnh kiểm tra và quản trị
        CommandHandler("checksales", check_sales_command),
        CommandHandler("resetsales", reset_sales_limit_command),
        CommandHandler("datastats", datastats_command),
        CommandHandler("marketguard", marketguard_config_command),
        CommandHandler("sethashtag", sethashtag_command),
        CommandHandler("setmaxsales", setmaxsales_command),
        CommandHandler("marketstats", marketstats_command),
        CommandHandler("stats", marketstats_command),
    ]
