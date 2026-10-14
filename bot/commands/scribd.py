"""
/scribd Command
Download tài liệu từ Scribd — lấy link tải trực tiếp.

Cách dùng:
    /scribd https://www.scribd.com/document/123456/tên-tài-liệu

Bot sẽ trả về link tải trực tiếp + link xem không quảng cáo.
"""
import re
import json
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
from bot.utils.format import escape_md
from bot.utils.logger import log_from_update


async def scribd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /scribd — lấy link download tài liệu Scribd"""
    log_from_update(update)

    # Kiểm tra argument
    if len(context.args) != 1:
        await update.message.reply_photo(
            "https://i.imgur.com/qvYiLhO.jpeg",
            caption=(
                "📚 Copy link Scribd mà bạn cần download, sau đó sử dụng "
                "theo lệnh phía dưới và gửi cho bot.\n"
                "Bot sẽ tự trả về link để bạn download. Chúc bạn may mắn.\n\n"
                "<strong>Cách dùng:</strong> <code>Cách Dùng: /scribd https://www.scribd.com/xxxxxxxxxxxx</code>"
            ),
            parse_mode="html",
        )
        return

    scribd_url = context.args[0]

    # Validate URL
    match = re.search(r'https://(?:\w+\.)?scribd\.com/\w+/(\d+)/[^_]', scribd_url)
    if not match:
        await update.message.reply_text(
            "❌ *URL không hợp lệ*\n\n"
            "Vui lòng nhập URL Scribd đúng định dạng:\\n"
            "`/scribd https://www\\.scribd\\.com/document/xxxx/tên`",
            parse_mode="MarkdownV2",
        )
        return

    scribd_id = match.group(1)

    # Thông báo đang xử lý
    processing_msg = await update.message.reply_text("🔄 Đang xử lý link Scribd\\.\\.\\.", parse_mode="MarkdownV2")

    try:
        # Gọi API lấy thông tin tài liệu
        response = await asyncio.to_thread(
            requests.get,
            f"https://smuledownloader.online/tools/api/get-pages?url={scribd_url}",
            timeout=30,
        )

        if response.status_code != 200:
            await processing_msg.edit_text("❌ Đã xảy ra lỗi khi truy xuất URL\\.", parse_mode="MarkdownV2")
            return

        # Tìm JSON trong response
        message_pattern = r'data: ({.*})'
        data_match = re.search(message_pattern, response.text, re.DOTALL)

        if not data_match:
            await processing_msg.edit_text(
                "❌ Không tìm thấy thông tin JSON trong phản hồi\\.\n\n"
                "💡 _API có thể đã thay đổi hoặc URL không được hỗ trợ\\._",
                parse_mode="MarkdownV2",
            )
            return

        # Parse JSON
        json_str = data_match.group(1)
        json_data = json.loads(json_str)
        url = json_data.get("url", "").replace("\\/", "/")

        if not url:
            await processing_msg.edit_text("❌ Không tìm thấy URL tải\\.", parse_mode="MarkdownV2")
            return

        # Lấy HTML từ URL
        html_response = await asyncio.to_thread(requests.get, url, timeout=30)
        if html_response.status_code != 200:
            await processing_msg.edit_text("❌ Đã xảy ra lỗi khi truy xuất URL tải\\.", parse_mode="MarkdownV2")
            return

        # Tìm iframe src
        iframe_pattern = r'<iframe[^>]+src="([^"]+)"'
        iframe_match = re.search(iframe_pattern, html_response.text)

        if not iframe_match:
            await processing_msg.edit_text(
                "❌ Không tìm thấy iframe trong phản hồi HTML\\.\n\n"
                "💡 _Tài liệu này có thể không được hỗ trợ\\._",
                parse_mode="MarkdownV2",
            )
            return

        iframe_src = iframe_match.group(1)
        full_url = f"https://ilide.info{iframe_src}"

        # Xóa tin nhắn "đang xử lý"
        try:
            await processing_msg.delete()
        except Exception:
            pass

        # Build response với inline buttons
        keyboard = [
            [InlineKeyboardButton("📥 Tải Tài Liệu Ngay", url=full_url)],
            [InlineKeyboardButton(
                "👁 Xem Trực Tiếp (Không QC)",
                url=f"https://www.scribd.com/embeds/{scribd_id}/content?start_page=1&view_mode=scroll&access_key=key-fFexxf7r1bzEfWu3HKwf",
            )],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ *Tải tài liệu Scribd*\n\n"
            f"🔗 Link: `{escape_md(full_url)}`\n\n"
            f"💡 Thêm URL này vào IDM để GET hoặc dán link vào trình duyệt Chrome nhé\\.\n"
            f"⏰ _Link có thời hạn, vui lòng sử dụng sớm\\._",
            reply_markup=reply_markup,
            parse_mode="MarkdownV2",
        )

    except requests.Timeout:
        await processing_msg.edit_text(
            "❌ Hết thời gian chờ\\. Vui lòng thử lại sau\\.",
            parse_mode="MarkdownV2",
        )
    except Exception as e:
        print(f"❌ Error in /scribd command: {e}")
        try:
            await processing_msg.edit_text(
                "❌ Có lỗi xảy ra\\. Vui lòng thử lại sau\\.",
                parse_mode="MarkdownV2",
            )
        except Exception:
            pass


def get_handlers():
    """Trả về danh sách handlers để đăng ký"""
    return [
        CommandHandler("scribd", scribd_command),
    ]
