"""
/donate Command & Automated Verification
Hiển thị thông tin ủng hộ/quyên góp cho sự phát triển của KiGuard Bot.
Hỗ trợ xác nhận tự động thanh toán:
1. Nhận dạng chuyển khoản Bank Việt Nam tự động qua Webhook Server ngầm.
2. Tự động quét và xác thực giao dịch USDT TRC-20 trực tiếp trên Blockchain TRON.
"""

import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.utils.logger import log_from_update
from bot.services.payment_verifier import verify_trc20_usdt

# Cấu hình thanh toán (Đọc từ .env hoặc dùng mặc định)
BANK_NAME = os.getenv("DONATE_BANK_NAME", "MB Bank (Ngân hàng Quân Đội)")
BANK_ACC = os.getenv("DONATE_BANK_ACC", "999999999999")
BANK_OWNER = os.getenv("DONATE_BANK_OWNER", "VU KHANH AN")
BINANCE_PAY_ID = os.getenv("DONATE_BINANCE_ID", "123456789")
TRC20_ADDRESS = os.getenv("DONATE_TRC20_WALLET", "TX1234567890QWERTYUIOPASDFGHJKLZXC")


def _get_main_keyboard() -> InlineKeyboardMarkup:
    """Tạo bàn phím menu chính cho lệnh /donate"""
    keyboard = [
        [
            InlineKeyboardButton("🏦 Bank Việt Nam", callback_data="donate_bank"),
            InlineKeyboardButton("🔶 Ví Binance", callback_data="donate_binance"),
        ],
        [
            InlineKeyboardButton("🛡️ Mạng TRC20 (USDT)", callback_data="donate_trc20"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def _get_back_keyboard() -> InlineKeyboardMarkup:
    """Tạo nút quay lại cho các menu con thông thường"""
    keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data="donate_main")]]
    return InlineKeyboardMarkup(keyboard)


def _get_trc20_keyboard() -> InlineKeyboardMarkup:
    """Bàn phím cho mục TRC20 tích hợp nút xác minh TxID"""
    keyboard = [
        [InlineKeyboardButton("🔍 Xác minh tự động (TxID)", callback_data="donate_verify_trc20")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="donate_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


def _get_main_text(user_id: int) -> str:
    """Trả về nội dung giới thiệu chính kèm hướng dẫn Memo riêng cho từng User"""
    return (
        "💝 <b>ỦNG HỘ PHÁT TRIỂN KIGUARD BOT</b> 💝\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Chào bạn! KiGuard Bot là dự án phi lợi nhuận được vận hành và bảo trì hoàn toàn miễn phí.\n\n"
        "Sự đồng hành và ủng hộ của các bạn là nguồn động lực to lớn giúp đội ngũ duy trì máy chủ "
        "(VPS chất lượng cao) và liên tục phát triển thêm các tính năng thông minh mới bảo vệ cộng đồng.\n\n"
        "Hãy chọn một trong các phương thức quyên góp dưới đây nhé:\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <b>LƯU Ý ĐỂ XÁC NHẬN BANK TỰ ĐỘNG:</b>\n"
        "Để hệ thống tự nhận dạng giao dịch tức thì qua Webhook, nội dung chuyển khoản (Memo) bắt buộc phải ghi:\n"
        f"👉 <code>KGBK {user_id}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✨ <i>Cảm ơn sự đóng góp vô cùng đáng quý của bạn!</i>"
    )


async def donate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler xử lý khi người dùng gõ lệnh /donate"""
    log_from_update(update)
    
    user_id = update.effective_user.id
    await update.message.reply_text(
        text=_get_main_text(user_id),
        parse_mode="HTML",
        reply_markup=_get_main_keyboard()
    )


async def donate_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler xử lý các nút bấm tương tác quyên góp"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "donate_main":
        await query.edit_message_text(
            text=_get_main_text(user_id),
            parse_mode="HTML",
            reply_markup=_get_main_keyboard()
        )
        
    elif data == "donate_bank":
        # Tạo link QR thanh toán nhanh
        bank_qr_url = f"https://img.vietqr.io/image/970422-990979899-qr_only.png?amount=&addInfo=11111"
        
        
        bank_text = (
            "🏦 <b>THANH TOÁN QUA BANK VIỆT NAM</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Bạn có thể chuyển khoản trực tiếp qua ngân hàng Việt Nam bằng thông tin dưới đây:\n\n"
            f"• <b>Ngân hàng:</b> <code>{BANK_NAME}</code>\n"
            f"• <b>Số tài khoản:</b> <code>{BANK_ACC}</code>\n"
            f"• <b>Chủ tài khoản:</b> <code>{BANK_OWNER}</code>\n"
            f"• <b>Nội dung chuyển tiền:</b> <code>KGBK {user_id}</code>\n\n"
            "📲 <b>Mã QR Quét Nhanh (Đã điền sẵn nội dung):</b>\n"
            f"👉 Nhấp vào <a href='{bank_qr_url}'>đây để hiển thị QR chuyển tiền</a>\n\n"
            "💡 <i>Chạm/nhấp vào số tài khoản hoặc nội dung chuyển tiền để copy cực nhanh!</i>\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(
            text=bank_text,
            parse_mode="HTML",
            reply_markup=_get_back_keyboard(),
            disable_web_page_preview=True
        )
        
    elif data == "donate_binance":
        binance_text = (
            "🔶 <b>THANH TOÁN QUA BINANCE PAY / VÍ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Bạn có thể ủng hộ qua cổng Binance Pay bằng thông tin sau:\n\n"
            f"• <b>Binance Pay ID:</b> <code>{BINANCE_PAY_ID}</code>\n"
            f"• <b>Binance UID:</b> <code>{BINANCE_PAY_ID}</code>\n\n"
            "💡 <i>Chạm/nhấp vào dãy số trên để copy nhanh Pay ID. Hãy đảm bảo bạn chọn chuyển khoản đúng mục Binance Pay để được miễn phí giao dịch nhé!</i>\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(
            text=binance_text,
            parse_mode="HTML",
            reply_markup=_get_back_keyboard()
        )
        
    elif data == "donate_trc20":
        trc20_text = (
            "🛡️ <b>THANH TOÁN QUA MẠNG USDT (TRC-20)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Bạn có thể ủng hộ bằng tiền mã hóa USDT qua mạng lưới TRON (TRC-20):\n\n"
            "• <b>Địa chỉ ví (Address):</b>\n"
            f"<code>{TRC20_ADDRESS}</code>\n\n"
            "⚠️ <b>LƯU Ý QUAN TRỌNG:</b>\n"
            "Chỉ chuyển tiền dạng <b>USDT</b> qua mạng lưới <b>TRON (TRC-20)</b>. "
            "Gửi sai mạng lưới sẽ làm mất tài sản vĩnh viễn!\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(
            text=trc20_text,
            parse_mode="HTML",
            reply_markup=_get_trc20_keyboard()
        )

    elif data == "donate_verify_trc20":
        verify_instructions = (
            "🛡️ <b>XÁC MINH GIAO DỊCH USDT (TRC-20)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Hệ thống đã tích hợp quét Blockchain tự động. Để xác nhận quyên góp:\n\n"
            "1. Thực hiện chuyển khoản USDT TRC-20 vào địa chỉ ví nhận.\n"
            "2. Lấy mã <b>TxID (Transaction Hash)</b> của giao dịch đó (Dãy 64 ký tự hex).\n"
            "3. Gửi tin nhắn theo cú pháp sau cho Bot:\n"
            "👉 <code>/verify &lt;Mã TxID&gt;</code>\n\n"
            "Ví dụ:\n"
            "<code>/verify 312521f75d691060938f23758b292e10a05a8f4c9c1b82a7f511942a98cb9b6d</code>\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(
            text=verify_instructions,
            parse_mode="HTML",
            reply_markup=_get_back_keyboard()
        )


async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xác minh giao dịch USDT TRC-20 tự động thông qua TxID"""
    log_from_update(update)
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ <b>Thiếu thông tin!</b>\n\n"
            "Vui lòng nhập mã giao dịch TxID theo cú pháp:\n"
            "<code>/verify &lt;Mã TxID&gt;</code>",
            parse_mode="HTML"
        )
        return

    txid = context.args[0].strip()
    processing_msg = await update.message.reply_text("⚡ Đang quét Blockchain TRON để kiểm tra giao dịch...")

    result = await verify_trc20_usdt(txid, TRC20_ADDRESS)
    
    try:
        await processing_msg.delete()
    except Exception:
        pass

    if result["success"]:
        success_text = (
            "🎉 <b>XÁC NHẬN QUYÊN GÓP THÀNH CÔNG!</b> 💝\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Hệ thống đã xác nhận giao dịch thành công trên Blockchain:\n\n"
            f"• <b>Mệnh giá:</b> <code>{result['amount']:.2f} USDT</code>\n"
            f"• <b>Mạng lưới:</b> <code>TRON (TRC-20)</code>\n"
            f"• <b>Mã TxID:</b> <code>{txid}</code>\n\n"
            "🙏 <i>Cảm ơn tấm lòng hảo tâm vô cùng to lớn của bạn! Khoản đóng góp "
            "này sẽ được duy trì hoàn toàn cho các chi phí máy chủ duy trì hoạt động ổn định của Bot.</i>"
        )
        await update.message.reply_text(success_text, parse_mode="HTML")
        
        # Thông báo cho toàn bộ Admin
        from bot.config import Config
        admin_ids = Config.get_notification_admin_ids()
        admin_msg = (
            "💰 <b>PHÁT HIỆN QUYÊN GÓP USDT MỚI (TỰ ĐỘNG XÁC NHẬN)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Người gửi:</b> <a href='tg://user?id={update.effective_user.id}'>{update.effective_user.full_name}</a>\n"
            f"💵 <b>Số tiền:</b> <code>{result['amount']:.2f} USDT</code>\n"
            f"🔑 <b>Mã TxID:</b> <code>{txid}</code>\n"
            "🟢 <i>Trạng thái: Blockchain xác nhận thành công!</i>"
        )
        for aid in admin_ids:
            try:
                await context.bot.send_message(chat_id=aid, text=admin_msg, parse_mode="HTML")
            except Exception:
                pass
    else:
        failure_text = (
            "❌ <b>XÁC MINH THẤT BẠI!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Yêu cầu xác nhận giao dịch của bạn không thành công:\n\n"
            f"🚨 <b>Lý do:</b> {result['error']}\n\n"
            "💡 <i>Lưu ý: Mạng lưới TRON cần 1-2 phút để đóng gói và xác nhận khối. "
            "Nếu bạn vừa chuyển tiền, vui lòng đợi một chút rồi gõ lại lệnh nhé!</i>"
        )
        await update.message.reply_text(failure_text, parse_mode="HTML")


def get_handlers():
    """Trả về danh sách handlers để loader tự động tải"""
    return [
        CommandHandler("donate", donate_command),
        CommandHandler("verify", verify_command),
        CallbackQueryHandler(donate_callback_handler, pattern="^donate_")
    ]
