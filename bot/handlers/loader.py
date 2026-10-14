"""
Handler Loader
Tự động tìm và đăng ký tất cả command modules

Để thêm command mới:
1. Tạo file mới trong bot/commands/ (ví dụ: ban.py)
2. Định nghĩa function get_handlers() trả về list handlers
3. Hệ thống tự động load!
"""
import importlib
import pkgutil
from telegram.ext import Application
from bot import commands


def load_all_handlers(app: Application):
    """
    Tự động tìm tất cả module trong bot/commands/
    và đăng ký handlers từ get_handlers()
    """
    loaded = 0
    total = 0

    for importer, module_name, is_pkg in pkgutil.iter_modules(commands.__path__):
        if module_name.startswith("_"):
            continue

        total += 1
        try:
            module = importlib.import_module(f"bot.commands.{module_name}")

            if hasattr(module, "get_handlers"):
                handlers = module.get_handlers()

                # Thứ tự ưu tiên xử lý tin nhắn (Middleware Groups):
                # 1. tracker (group -4): Kiểm tra và lưu lịch sử thay đổi thông tin user
                # 2. ban_guard (group -3): Kiểm tra ID người dùng có trong banlist toàn cục không
                # 3. badwords (group -2): Kiểm tra từ khóa vi phạm (tục tĩu) trong nhóm
                # 4. market_guard (group -1): Kiểm duyệt tin bán hàng / rao vặt bằng AI
                # 5. Các lệnh khác (group 0): Xử lý lệnh bình thường (/start, /help,...)
                if module_name == "tracker":
                    handler_group = -4
                elif module_name == "ban_guard":
                    handler_group = -3
                elif module_name == "badwords":
                    handler_group = -2
                elif module_name == "market_guard":
                    handler_group = -1
                else:
                    handler_group = 0

                for handler in handlers:
                    app.add_handler(handler, group=handler_group)
                loaded += 1
                print(f"  ✅ Loaded command: {module_name}.py")
            else:
                print(f"  ⚠️ Skipped {module_name}.py — không có get_handlers()")

        except Exception as e:
            print(f"  ❌ Failed to load {module_name}.py: {e}")

    print(f"📦 Total commands loaded: {loaded}/{total}")
