"""
User Tracker Handler
Tự động ghi nhận tất cả user tương tác với bot qua private chat.
Đồng thời ghi log toàn bộ tin nhắn/lệnh vào file log theo ngày.

Handler này chạy ẩn, không ảnh hưởng đến các command khác.
Mỗi khi user gửi tin nhắn trong private chat → lưu vào known_users.json + ghi log.
"""
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, filters
from bot.services.user_tracker import track_user
from bot.utils.logger import log_from_update


async def _track_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ghi nhận và kiểm tra thông tin user cho BẤT KỲ tin nhắn nào (group, private, v.v.).
    Cập nhật thay đổi hồ sơ (first_name, full_name, username, premium) vào members.json.
    """
    if not update.effective_user:
        return

    user = update.effective_user

    # 1. Cập nhật thông tin cơ bản và lịch sử thay đổi vào members.json
    try:
        from bot.services.group_member_tracker import update_member_info
        update_member_info(
            user_id=user.id,
            first_name=user.first_name or "",
            full_name=user.full_name or "",
            username=user.username or "",
            is_premium=user.is_premium or False,
        )
    except Exception as e:
        print(f"⚠️ Lỗi cập nhật lịch sử thay đổi user {user.id}: {e}")

    # 2. Nếu ở trong nhóm, cập nhật thêm trạng thái của nhóm đó trong members.json nếu chưa có
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        try:
            from bot.services.group_member_tracker import _load_data, _save_data
            from datetime import datetime
            
            data = _load_data()
            str_user_id = str(user.id)
            str_group_id = str(chat.id)
            
            if str_user_id in data:
                if "groups" not in data[str_user_id]:
                    data[str_user_id]["groups"] = {}
                
                # Nếu chưa lưu nhóm này, hoặc nhóm này đang lưu status rời nhóm -> cập nhật lại thành member
                group_entry = data[str_user_id]["groups"].get(str_group_id, {})
                if not group_entry or group_entry.get("status") != "member":
                    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    data[str_user_id]["groups"][str_group_id] = {
                        "name": chat.title or "",
                        "username": chat.username or "",
                        "status": "member",
                        "joined": now,
                        "left": None
                    }
                    _save_data(data)
        except Exception as e:
            print(f"⚠️ Lỗi cập nhật group info trong tracker: {e}")

    # 3. Nếu là chat riêng tư (DMs), lưu vào known_users.json + ghi log tin nhắn
    if chat and chat.type == "private":
        try:
            # Lưu user vào known_users.json
            track_user(
                user_id=user.id,
                first_name=user.first_name or "",
                username=user.username or "",
            )
            # Ghi log tin nhắn/lệnh
            log_from_update(update)
        except Exception as e:
            print(f"⚠️ Lỗi track private user: {e}")


def get_handlers():
    """Trả về danh sách handlers để đăng ký"""
    return [
        # Track và cập nhật lịch sử thay đổi của TẤT CẢ tin nhắn từ mọi chat type
        # group=-4 để handler này chạy đầu tiên trong luồng xử lý tin nhắn
        MessageHandler(filters.ALL, _track_user_profile, block=False),
    ]
