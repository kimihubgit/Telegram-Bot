"""
Deep Links Dispatcher Service
Quản lý và điều phối các lệnh Deep Link từ /start?start=xxxx
Tránh phình to và rắc rối code tại start.py.
"""
from telegram import Update
from telegram.ext import ContextTypes

# ══════════════════════════════════════════════════════════════
#  Hàm xử lý các loại Deep Link cụ thể (Handlers)
# ══════════════════════════════════════════════════════════════

async def handle_check_violation(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str | None = None):
    """
    Xử lý Deep Link: /start check_violation
    Hiển thị lịch sử vi phạm của người dùng.
    """
    from bot.commands.badwords import get_user_violations
    user = update.effective_user
    user_id_str = str(user.id)
    violations = get_user_violations(user_id_str)

    if not violations:
        await update.message.reply_text(
            "✅ Bạn chưa có vi phạm nào!",
            parse_mode="HTML"
        )
        return

    text = "📋 <b>LỊCH SỬ VI PHẠM CỦA BẠN</b>\n" \
           "━━━━━━━━━━━━━━━━━━━━\n\n"

    for i, v in enumerate(violations, 1):
        text += (
            f"<b>#{i}</b> 🕐 <i>{v['time']}</i>\n"
            f"💬 Câu vi phạm: <code>{v['message']}</code>\n"
            f"🚫 Từ cấm: <code>{v['word']}</code>\n\n"
        )

    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📊 Tổng: <b>{len(violations)}</b> lần vi phạm\n" \
            "<i>Hãy giữ văn hóa khi chat nhé!</i>"

    await update.message.reply_text(text, parse_mode="HTML")

# ══════════════════════════════════════════════════════════════
#  Đăng ký các Handlers vào Registry
# ══════════════════════════════════════════════════════════════

# Đăng ký các action tương ứng với hàm xử lý
# Cấu trúc: "tên_lệnh_deep_link": hàm_xử_lý
DEEPLINK_REGISTRY = {
    "check": handle_check_violation,  # Chấp nhận cả /start check
    "check_violation": handle_check_violation,  # Chấp nhận /start check_violation
    # Thêm các deep link khác tại đây trong tương lai:
    # "verify": handle_verify_account,
    # "gift": handle_claim_gift,
}


# ══════════════════════════════════════════════════════════════
#  Bộ điều phối chính (Dispatcher)
# ══════════════════════════════════════════════════════════════

async def dispatch_deeplink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Phân tích và điều phối tham số deep link nếu có.
    Dạng link: t.me/your_bot?start=action_payload (hoặc t.me/your_bot?start=action)
    
    Returns:
        True: Nếu đây là deep link hợp lệ và đã được xử lý thành công.
        False: Nếu không có deep link, hoặc deep link không được đăng ký.
    """
    chat = update.effective_chat
    if not chat or chat.type != "private":
        return False

    args = context.args or []
    if not args:
        return False

    raw_arg = args[0]
    
    # Phân tách action và payload theo định dạng "action_payload" (ví dụ: gift_12345)
    # Nếu chỉ có action (ví dụ: check_violation), payload sẽ là None
    parts = raw_arg.split("_", 1)
    action = parts[0].lower()
    payload = parts[1] if len(parts) > 1 else None

    # Tìm handler trong registry
    handler = DEEPLINK_REGISTRY.get(action)
    if not handler:
        return False

    # Thực thi handler tương ứng
    try:
        await handler(update, context, payload)
        return True
    except Exception as e:
        print(f"⚠️ Lỗi khi xử lý deep link '{action}' với payload '{payload}': {e}")
        return False
