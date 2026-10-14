import os
import sys
from dotenv import load_dotenv

load_dotenv()


class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
    BOT_USERNAME = os.getenv("BOT_USERNAME", "")

    # Telethon (Userbot API)
    TELETHON_API_ID = os.getenv("TELETHON_API_ID", "")
    TELETHON_API_HASH = os.getenv("TELETHON_API_HASH", "")

    # Rose Bot query group
    ROSE_QUERY_GROUP_ID = os.getenv("ROSE_QUERY_GROUP_ID", "")

    # Notification admin IDs (comma-separated) — ai được dùng /notification
    NOTIFICATION_ADMIN_IDS = os.getenv("NOTIFICATION_ADMIN_IDS", "")

    # MongoDB Config
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "telegram")

    # Backup Bot Config
    BACKUP_BOT_TOKEN = os.getenv("BACKUP_BOT_TOKEN", "")
    BACKUP_CHAT_ID = os.getenv("BACKUP_CHAT_ID", "")

    # Donate Config (MB Bank, Binance, TRC20 Wallet, Webhook Port)
    DONATE_BANK_NAME = os.getenv("DONATE_BANK_NAME", "MB Bank (Ngân hàng Quân Đội)")
    DONATE_BANK_ACC = os.getenv("DONATE_BANK_ACC", "999999999999")
    DONATE_BANK_OWNER = os.getenv("DONATE_BANK_OWNER", "VU KHANH AN")
    DONATE_BINANCE_ID = os.getenv("DONATE_BINANCE_ID", "123456789")
    DONATE_TRC20_WALLET = os.getenv("DONATE_TRC20_WALLET", "TX1234567890QWERTYUIOPASDFGHJKLZXC")
    DONATE_PORT = int(os.getenv("DONATE_PORT", "8080"))

    # Autobank Polling
    AUTOBANK_POLL_INTERVAL = int(os.getenv("AUTOBANK_POLL_INTERVAL", "30"))

    # Binance API (Ví Binance Pay)
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN or cls.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            print("❌ BOT_TOKEN chưa được cài đặt trong file .env!")
            sys.exit(1)

        if not cls.ADMIN_CHAT_ID or cls.ADMIN_CHAT_ID == "YOUR_ADMIN_CHAT_ID_HERE":
            print("⚠️ ADMIN_CHAT_ID chưa được cài đặt — sẽ không gửi thông báo ra/vào nhóm.")
            print("   Gửi /myid cho bot để lấy Chat ID của bạn.")

        if not cls.BOT_USERNAME or cls.BOT_USERNAME == "YOUR_BOT_USERNAME_HERE":
            print("⚠️ BOT_USERNAME chưa được cài đặt — sẽ không gửi thông báo ra/vào nhóm.")


    @classmethod
    def has_telethon(cls) -> bool:
        """Kiểm tra Telethon đã được cấu hình chưa"""
        return (
            bool(cls.TELETHON_API_ID)
            and cls.TELETHON_API_ID != "YOUR_API_ID_HERE"
            and bool(cls.TELETHON_API_HASH)
            and cls.TELETHON_API_HASH != "YOUR_API_HASH_HERE"
        )

    @classmethod
    def has_rose_group(cls) -> bool:
        """Kiểm tra Rose query group đã cấu hình chưa"""
        return bool(cls.ROSE_QUERY_GROUP_ID) and cls.ROSE_QUERY_GROUP_ID.lstrip("-").isdigit()

    @classmethod
    def get_rose_group_id(cls) -> int | None:
        """Lấy Rose query group ID (int)"""
        if cls.has_rose_group():
            return int(cls.ROSE_QUERY_GROUP_ID)
        return None

    @classmethod
    def get_notification_admin_ids(cls) -> list[int]:
        """Lấy danh sách admin IDs được phép dùng /notification"""
        raw = cls.NOTIFICATION_ADMIN_IDS.strip()
        if not raw:
            # Fallback: dùng ADMIN_CHAT_ID nếu không set riêng
            if cls.ADMIN_CHAT_ID and cls.ADMIN_CHAT_ID.lstrip("-").isdigit():
                return [int(cls.ADMIN_CHAT_ID)]
            return []
        ids = []
        for part in raw.split(","):
            part = part.strip()
            if part.lstrip("-").isdigit():
                ids.append(int(part))
        return ids
    
    def get_bot_username(cls) -> str:
        """Lấy bot username"""
        # return cls.BOT_USERNAME if cls.BOT_USERNAME.startswith("@") else f"@{cls.BOT_USERNAME}"
        return cls.BOT_USERNAME


