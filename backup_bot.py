"""
KiGuard Backup Bot
Bot phụ chạy ẩn dưới nền để tự động sao lưu cơ sở dữ liệu đúng 00:00 mỗi ngày.
Không nhận lệnh, không phản hồi tin nhắn, hoạt động độc lập và bảo mật.
Sử dụng công nghệ phân mảnh dữ liệu Erasure Coding (XOR 2+1) kiểu AWS S3.
Cách chạy:
    python backup_bot.py
"""

import os
import zipfile
import asyncio
from datetime import datetime, time
from pathlib import Path
from dotenv import load_dotenv
from telegram.ext import Application, ContextTypes
from zoneinfo import ZoneInfo  # Thư viện chuẩn từ Python 3.9+ để xử lý múi giờ

# Import mô-đun mã hóa phân mảnh dữ liệu
from backup.xor import split_file_xor

# Load cấu hình từ file .env
load_dotenv()
BACKUP_BOT_TOKEN = os.getenv("BACKUP_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# Thư mục dữ liệu
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "temp_backup"


def create_backup_zip() -> Path | None:
    """Tạo file ZIP chứa toàn bộ thư mục data/"""
    if not DATA_DIR.exists():
        print("⚠️ Thư mục data/ không tồn tại, không thể backup.")
        return None

    TEMP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = TEMP_DIR / f"kiguard_backup_{timestamp}.zip"

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(DATA_DIR):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(BASE_DIR)
                    zipf.write(file_path, arcname)
        return zip_path
    except Exception as e:
        print(f"⚠️ Lỗi tạo zip backup: {e}")
        return None


async def auto_backup_job(context: ContextTypes.DEFAULT_TYPE):
    """Job tự động chạy lúc 00:00 hằng ngày để chia và gửi 3 mảnh backup cho admin"""
    if not ADMIN_CHAT_ID:
        print("⚠️ Không có ADMIN_CHAT_ID được cấu hình!")
        return

    print(f"⚡ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Đang tiến hành backup tự động định kỳ...")
    zip_file = create_backup_zip()
    if not zip_file or not zip_file.exists():
        return

    # Gọi hàm phân tách phân mảnh từ mô-đun dùng chung
    shard_paths = split_file_xor(zip_file, TEMP_DIR)
    if not shard_paths or len(shard_paths) < 3:
        if zip_file.exists():
            zip_file.unlink()
        return

    try:
        allowed_ids = [int(aid.strip()) for aid in os.getenv("NOTIFICATION_ADMIN_IDS", "").split(",") if aid.strip().isdigit()]
        if not allowed_ids and ADMIN_CHAT_ID.isdigit():
            allowed_ids = [int(ADMIN_CHAT_ID)]

        labels = [
            "🧩 <b>[Auto] Mảnh A (Nửa đầu dữ liệu)</b>",
            "🧩 <b>[Auto] Mảnh B (Nửa sau dữ liệu)</b>",
            "🛡️ <b>[Auto] Mảnh C (Mảnh dự phòng XOR)</b>"
        ]

        for admin_id in allowed_ids:
            try:
                # Gửi lần lượt 3 mảnh phân tách
                for i, shard_path in enumerate(shard_paths):
                    with open(shard_path, "rb") as f:
                        await context.bot.send_document(
                            chat_id=admin_id,
                            document=f,
                            filename=shard_path.name,
                            caption=f"{labels[i]}\n📅 Ngày tạo: <code>{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</code>",
                            parse_mode="HTML"
                        )
                
                # Gửi thông báo hoàn thành kèm hướng dẫn
                info_text = (
                    "💾 <b>[Tự động] Bản sao lưu hàng ngày (00:00)</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "Hệ thống đã gửi thành công 3 mảnh dữ liệu tự động.\n\n"
                    "💡 <b>Lưu ý:</b>\n"
                    "Hãy cất giữ tối thiểu 2 mảnh khác nhau ở các nơi an toàn độc lập. "
                    "Sử dụng script <code>restore_backup.py</code> để khôi phục khi cần thiết."
                )
                await context.bot.send_message(chat_id=admin_id, text=info_text, parse_mode="HTML")
                print(f"✅ Backup Success: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} / {admin_id}")
            except Exception as e:
                print(f"⚠️ Không gửi được auto-backup cho admin {admin_id}: {e}")
    finally:
        # Dọn dẹp tất cả file tạm trên ổ đĩa
        if zip_file and zip_file.exists():
            zip_file.unlink()
        for shard_path in shard_paths:
            if shard_path.exists():
                shard_path.unlink()


def main():
    """Hàm khởi chạy chính của bot nền"""
    if not BACKUP_BOT_TOKEN or BACKUP_BOT_TOKEN == "YOUR_BACKUP_BOT_TOKEN_HERE":
        print("❌ LỖI: Chưa cấu hình BACKUP_BOT_TOKEN trong file .env!")
        return

    print("⚡ Khởi động daemon KiGuard Backup Bot (Chạy ẩn dưới nền)...")
    app = Application.builder().token(BACKUP_BOT_TOKEN).build()

    # Cài đặt lịch trình chạy đúng 00:00 hằng ngày theo giờ Việt Nam (UTC+7)
    vn_timezone = ZoneInfo("Asia/Ho_Chi_Minh")
    target_time = time(hour=0, minute=0, second=0, tzinfo=vn_timezone)
    app.job_queue.run_daily(auto_backup_job, time=target_time)

    print("✅ KiGuard Backup Bot đang hoạt động!")
    print(f"⏰ Lịch trình sao lưu tự động: đúng 00:00 hằng ngày (Múi giờ Việt Nam).")
    print("🔒 Trạng thái: An toàn (Không nhận lệnh chat, chỉ chạy ngầm gửi dữ liệu).")

    # allowed_updates=[] giúp chặn tất cả các yêu cầu nhận tin nhắn đến bot, giảm tải tối đa CPU/Băng thông
    app.run_polling(allowed_updates=[])


if __name__ == "__main__":
    main()
