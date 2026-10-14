"""
Telethon Client — Kết nối
Quản lý kết nối singleton Telethon (Userbot / MTProto API).
Chỉ chứa: start, stop, get_client, is_connected.
"""

import os
from telethon import TelegramClient
from bot.config import Config


_client: TelegramClient | None = None


def get_client() -> TelegramClient | None:
    """Trả về Telethon client instance"""
    return _client


def is_connected() -> bool:
    """Kiểm tra Telethon client đã kết nối chưa"""
    return _client is not None and _client.is_connected()


async def start() -> bool:
    """Khởi tạo và kết nối Telethon (tài khoản cá nhân)"""
    global _client

    if not Config.has_telethon():
        print("⚠️ Telethon chưa cấu hình — bot chạy Bot API only.")
        return False

    try:
        os.makedirs("bot/sessions", exist_ok=True)

        _client = TelegramClient(
            "bot/sessions/userbot",
            int(Config.TELETHON_API_ID),
            Config.TELETHON_API_HASH,
        )

        print("📱 Đang kết nối Telethon...")
        await _client.start()

        me = await _client.get_me()
        if me.bot:
            print("❌ Telethon đang login bằng BOT TOKEN — cần login bằng SĐT CÁ NHÂN!")
            await _client.disconnect()
            _client = None
            return False

        print(f"✅ Telethon connected: {me.first_name} (@{me.username}) [id={me.id}]")
        return True

    except Exception as e:
        print(f"❌ Telethon connection failed: {e}")
        _client = None
        return False


async def stop():
    """Disconnect Telethon client"""
    global _client
    if _client:
        await _client.disconnect()
        _client = None
        print("🔌 Telethon disconnected.")
