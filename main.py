"""
Telegram Bot - Entry Point

Hệ thống bot modular với auto-loading commands.
Tích hợp Telethon (Userbot API) để lấy thông tin sâu.

Để thêm chức năng mới, tạo file mới trong bot/commands/
với function get_handlers() — sẽ tự động được load.
"""
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder
from bot.config import Config
from bot.handlers.loader import load_all_handlers
from bot import connection


async def main():
    # Validate config
    Config.validate()
    
    print("🤖 Starting Telegram Bot...")

    # === Khởi tạo Telethon (nếu đã cấu hình) ===
    telethon_ok = await connection.start()
    if telethon_ok:
        print("🔓 Telethon enabled — deep user info available!")
    else:
        print("🔒 Telethon disabled — running with Bot API only.")

    # === Build Bot application ===
    app = ApplicationBuilder().token(Config.BOT_TOKEN).build()

    # === Khởi chạy Payment Webhook Server ngầm ===
    from bot.services.payment_verifier import start_webhook_server
    loop = asyncio.get_running_loop()
    start_webhook_server(app.bot, loop)

    # Auto-load tất cả command modules
    print("📂 Loading commands...")
    load_all_handlers(app)

    async def error_handler(update, context):
        print(f"❌ Bot error: {context.error}")

    app.add_error_handler(error_handler)
    print("✅ Bot is running! Waiting for messages...")

    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )

    # Giữ chạy cho đến khi bị dừng (Ctrl+C)
    try:
        stop_event = asyncio.Event()
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        # Graceful shutdown
        print("\n🛑 Shutting down...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await connection.stop()
        print("👋 Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
