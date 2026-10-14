"""
/bin Command
Tra cứu thông tin BIN (Bank Identification Number) từ database CSV

Cách dùng:
    /bin 542034    - Tra cứu BIN 6 chữ số
    /bin 5420340000  - Tự lấy 6 số đầu
"""
import re
import os
import pandas as pd
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from bot.utils.format import escape_md
from bot.utils.logger import log_from_update

# === Load BIN database ===
_df = None
_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "bin-list-data.csv")


def _load_bin_data():
    """Load dữ liệu BIN từ CSV (lazy loading - chỉ load 1 lần)"""
    global _df
    if _df is not None:
        return _df

    abs_path = os.path.abspath(_DATA_PATH)
    if not os.path.exists(abs_path):
        print(f"⚠️ Không tìm thấy BIN database: {abs_path}")
        print("   Đặt file bin-list-data.csv vào thư mục data/")
        return None

    try:
        _df = pd.read_csv(abs_path, header=None, names=[
            'BIN', 'Brand', 'Type', 'Category', 'Issuer', 'IssuerPhone',
            'IssuerUrl', 'isoCode2', 'isoCode3', 'CountryName'
        ])
        # Chuyển BIN sang string để so sánh chính xác
        _df['BIN'] = _df['BIN'].astype(str).str.strip()
        print(f"✅ Loaded BIN database: {len(_df)} records")
        return _df
    except Exception as e:
        print(f"❌ Lỗi load BIN database: {e}")
        return None


# Country flag emoji từ ISO code
def _get_flag(iso_code: str) -> str:
    """Chuyển ISO 2-letter code sang emoji flag"""
    if not iso_code or len(iso_code) != 2:
        return "🏳️"
    return "".join(chr(0x1F1E6 + ord(c) - ord('A')) for c in iso_code.upper())


async def bin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /bin"""
    log_from_update(update)

    # Kiểm tra argument
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ *Cách sử dụng:*\n"
            "`/bin <BIN\\_number>`\n\n"
            "📋 *Ví dụ:*\n"
            "• `/bin 542034`\n"
            "• `/bin 5420340000123456`\n\n"
            "💡 BIN là 6 số đầu trên thẻ ngân hàng",
            parse_mode="MarkdownV2",
        )
        return

    number = context.args[0]

    # Validate input
    if not re.match(r'^\d{6,20}$', number):
        await update.message.reply_text(
            "❌ Số BIN không hợp lệ\\.\n"
            "BIN chỉ chứa *6\\-20 chữ số*, không có chữ cái hay ký tự đặc biệt\\.",
            parse_mode="MarkdownV2",
        )
        return

    bin_number = number[:6]

    # Load data
    df = _load_bin_data()
    if df is None:
        await update.message.reply_text(
            "❌ BIN database chưa được cài đặt\\.\n"
            "Đặt file `bin\\-list\\-data\\.csv` vào thư mục `data/`",
            parse_mode="MarkdownV2",
        )
        return

    # Tìm kiếm BIN
    result = df[df['BIN'] == bin_number]

    if result.empty:
        await update.message.reply_text(
            f"❌ Không tìm thấy thông tin cho BIN: `{escape_md(bin_number)}`",
            parse_mode="MarkdownV2",
        )
        return

    # Build response
    row = result.iloc[0]

    brand = str(row.get('Brand', 'N/A'))
    card_type = str(row.get('Type', 'N/A'))
    category = str(row.get('Category', 'N/A'))
    issuer = str(row.get('Issuer', 'N/A'))
    issuer_phone = str(row.get('IssuerPhone', 'N/A'))
    issuer_url = str(row.get('IssuerUrl', 'N/A'))
    country = str(row.get('CountryName', 'N/A'))
    iso2 = str(row.get('isoCode2', ''))
    iso3 = str(row.get('isoCode3', ''))

    # Emoji cho type
    type_emoji = "💰" if "DEBIT" in card_type.upper() else "💎" if "CREDIT" in card_type.upper() else "💳"

    flag = _get_flag(iso2)

    message = (
        f"🔍 *BIN:* `{escape_md(bin_number)}`\n"
        f"🏷️ *Brand:* `{escape_md(brand)}`\n"
        f"{type_emoji} *Type:* `{escape_md(card_type)} {escape_md(category)}`\n"
        f"🏦 *Issuer:* `{escape_md(issuer)}`\n"
        f"🌍 *Country:* {flag} `*{escape_md(country)}* \\({escape_md(iso2)}, {escape_md(iso3)}\\)`\n"
        f"🔗 *URL:* `{escape_md(issuer_url)}`\n"
        f"📞 *Phone:* `{escape_md(issuer_phone)}`"
)

    await update.message.reply_text(
        message,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )


def get_handlers():
    """Trả về danh sách handlers để đăng ký"""
    return [
        CommandHandler("bin", bin_command),
    ]
