"""
Market Guard (KiGuard Sales AI Moderator)
Tự động phát hiện tin nhắn bán hàng / rao vặt trong nhóm Telegram bằng AI:
1. Yêu cầu hashtag bắt buộc (mặc định #NghienPlusMarket).
   Nếu chưa có hashtag -> Bot nhắc nhở thành viên bổ sung.
2. Giới hạn số bài rao bán tối đa mỗi ngày (mặc định 6 bài/ngày).
   Nếu vượt quá -> Xóa bài + Mute 12 giờ + Thông báo.
3. Lệnh thủ công: /checksales kiểm tra xem tin nhắn có phải tin bán hàng hay không.
"""
import os
import json
import asyncio
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

_llm_dir = Path(__file__).resolve().parent.parent / "LLM Ai"
if str(_llm_dir) not in sys.path:
    sys.path.insert(0, str(_llm_dir))

from sales_detector import check_sales_detail
from bot.services.data_collector import save_message_for_training, get_collector_stats
from bot.utils.logger import log_command

# === Cấu hình Market Guard ===
REQUIRED_HASHTAG = "#NghienPlusMarket"
MAX_SALES_PER_DAY = 6
MUTE_DURATION_HOURS = 12
AUTO_DELETE_WARNING_SECONDS = 60  # Xóa tin nhắc nhở sau 60s để không loãng group

# Đường dẫn lưu dữ liệu bài đăng của user theo ngày
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_POSTS_TRACKER_PATH = os.path.join(_DATA_DIR, "market_posts_tracker.json")

_posts_cache = {}


def _get_vn_date_str() -> str:
    """Lấy ngày theo giờ Việt Nam (UTC+7) định dạng YYYY-MM-DD"""
    vn_tz = timezone(timedelta(hours=7))
    return datetime.now(vn_tz).strftime("%Y-%m-%d")


def _load_tracker() -> dict:
    global _posts_cache
    try:
        abs_path = os.path.abspath(_POSTS_TRACKER_PATH)
        if os.path.exists(abs_path):
            with open(abs_path, "r", encoding="utf-8") as f:
                _posts_cache = json.load(f)
                return _posts_cache
    except Exception as e:
        print(f"⚠️ [Market Guard] Lỗi đọc file tracker: {e}")
    _posts_cache = {}
    return _posts_cache


def _save_tracker():
    try:
        abs_path = os.path.abspath(_POSTS_TRACKER_PATH)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            json.dump(_posts_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ [Market Guard] Lỗi ghi file tracker: {e}")


def _get_user_posts_today(user_id: int) -> int:
    """Lấy số lượng bài đã rao bán của user trong ngày hôm nay"""
    today = _get_vn_date_str()
    uid = str(user_id)
    today_records = _posts_cache.get(today, {})
    return today_records.get(uid, 0)


def _increment_user_posts(user_id: int) -> int:
    """Tăng số lượng bài rao bán trong ngày và lưu lại"""
    today = _get_vn_date_str()
    uid = str(user_id)
    if today not in _posts_cache:
        # Xóa các ngày cũ để file JSON gọn nhẹ
        _posts_cache.clear()
        _posts_cache[today] = {}

    current = _posts_cache[today].get(uid, 0) + 1
    _posts_cache[today][uid] = current
    _save_tracker()
    return current


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


async def market_guard_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Middleware quét nội dung tin nhắn gửi vào nhóm.
    Nếu AI phát hiện là tin rao bán:
    - Kiểm tra hashtag #NghienPlusMarket
    - Đếm số bài trong ngày, mute nếu vượt quá hạn mức 6 bài/ngày.
    """
    msg = update.effective_message
    if not msg or not msg.text:
        return

    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return

    user = update.effective_user
    if not user or user.is_bot:
        return

    # 1. Miễn trừ Admin / Chủ nhóm
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in ("administrator", "creator"):
            return
    except Exception:
        pass

    text = msg.text.strip()
    if len(text) < 3:
        return

    # 2. Phân tích nội dung qua mô hình AI (PhoBERT hoặc TF-IDF Ensemble)
    try:
        analysis = check_sales_detail(text)
    except Exception as e:
        print(f"⚠️ [Market Guard] Lỗi AI Detector: {e}")
        return

    is_sales = bool(analysis.get("is_sales", False))
    conf = float(analysis.get("confidence", 0.0))
    engine = str(analysis.get("engine", "AI"))

    # 3. Thu thập dữ liệu vào 2 thư mục riêng biệt ('ban_hang/' và 'khong_ban_hang/')
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
    full_name = user.full_name or user.first_name or "Bạn"
    has_hashtag = REQUIRED_HASHTAG.lower() in text.lower()

    # Kiểm tra hạn mức bài rao bán trong ngày
    count_today = _get_user_posts_today(user.id)

    # TRƯỜNG HỢP 1: Vượt quá giới hạn bài rao bán trong ngày (>= 6 bài)
    if count_today >= MAX_SALES_PER_DAY:
        # Xóa tin nhắn vi phạm
        try:
            await msg.delete()
        except Exception as e:
            print(f"⚠️ [Market Guard] Không xóa được tin nhắn: {e}")

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
        mute_alert = f"{full_name}({user.id}) đã vượt giới hạn rao bán {MAX_SALES_PER_DAY} bài/ngày. Tài khoản của bạn bị mute {MUTE_DURATION_HOURS} giờ."
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=mute_alert,
                message_thread_id=msg.message_thread_id
            )
        except Exception as e:
            print(f"⚠️ [Market Guard] Không thể gửi thông báo mute: {e}")
        return

    # Tăng số lượng bài đăng bán trong ngày
    new_count = _increment_user_posts(user.id)

    # TRƯỜNG HỢP 2: Bài đăng thiếu hashtag yêu cầu
    if not has_hashtag:
        warning_text = f"{full_name} hãy thêm hashtag {REQUIRED_HASHTAG} vào bài nếu là rao bán hàng nhé!"
        try:
            warn_msg = await msg.reply_text(warning_text)

            # Tự động xóa cảnh báo sau 60s để giữ group sạch sẽ
            if context.job_queue:
                context.job_queue.run_once(
                    _delete_message_after_delay,
                    AUTO_DELETE_WARNING_SECONDS,
                    data={"chat_id": chat.id, "message_id": warn_msg.message_id}
                )
        except Exception as e:
            print(f"⚠️ [Market Guard] Không gửi được lời nhắc hashtag: {e}")


async def check_sales_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Lệnh kiểm tra: /checksales <văn bản> hoặc Reply tin nhắn bất kỳ bằng /checksales
    Dùng để test độ nhạy và phân loại của mô hình AI.
    """
    log_command("checksales", update)
    msg = update.effective_message
    if not msg:
        return

    text_to_check = ""
    if msg.reply_to_message and msg.reply_to_message.text:
        text_to_check = msg.reply_to_message.text
    elif context.args:
        text_to_check = " ".join(context.args)

    if not text_to_check:
        await msg.reply_text(
            "ℹ️ <b>Cách dùng lệnh /checksales:</b>\n"
            "1. Reply tin nhắn bất kỳ và gõ: <code>/checksales</code>\n"
            "2. Hoặc gõ trực tiếp: <code>/checksales &lt;nội dung tin nhắn&gt;</code>",
            parse_mode="HTML"
        )
        return

    analysis = check_sales_detail(text_to_check)
    is_sales = analysis["is_sales"]
    conf = analysis["confidence"]
    engine = analysis["engine"]
    clean_t = analysis["clean_text"]
    has_tag = REQUIRED_HASHTAG.lower() in text_to_check.lower()

    status_icon = "🛒 BÁN HÀNG / RAO VẶT (1)" if is_sales else "💬 BÌNH THƯỜNG / HỎI MUA (0)"
    tag_status = "✅ Đã có" if has_tag else f"❌ Thiếu ({REQUIRED_HASHTAG})"

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

    # Chỉ Admin mới được dùng
    if chat.type in ("group", "supergroup"):
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ("administrator", "creator"):
            return

    target_id = None
    if context.args and context.args[0].isdigit():
        target_id = context.args[0]
    elif msg.reply_to_message:
        target_id = str(msg.reply_to_message.from_user.id)

    if not target_id:
        await msg.reply_text("Vui lòng chỉ định user_id hoặc reply tin nhắn của user cần reset.")
        return

    today = _get_vn_date_str()
    if today in _posts_cache and target_id in _posts_cache[today]:
        del _posts_cache[today][target_id]
        _save_tracker()
        await msg.reply_text(f"✅ Đã reset số lượt rao bán hôm nay của user: <code>{target_id}</code>", parse_mode="HTML")
    else:
        await msg.reply_text(f"ℹ️ User <code>{target_id}</code> chưa có bài rao bán nào hôm nay.", parse_mode="HTML")


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


# Nạp dữ liệu tracker khi khởi động
_load_tracker()


def get_handlers():
    """Hàm trả về danh sách handlers để loader.py tự động đăng ký"""
    return [
        # Middleware quét tin nhắn rao bán trong nhóm
        MessageHandler(filters.TEXT & filters.ChatType.GROUPS & ~filters.COMMAND, market_guard_message_handler),
        # Lệnh kiểm tra thủ công cho admin / member
        CommandHandler("checksales", check_sales_command),
        CommandHandler("resetsales", reset_sales_limit_command),
        CommandHandler("datastats", datastats_command),
    ]
