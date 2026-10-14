"""
Ban Guard Ultimate (Bản Vá Lỗi)
1. Chặn user trong banlist sử dụng bot (Xóa + Chặn).
2. Quét tin nhắn forward từ User/Group/Channel bị cấm -> Xóa ngay + BAN luôn thằng forward.
"""
import asyncio
import re
from telegram import (
    Update, 
    MessageOriginUser, 
    MessageOriginHiddenUser, 
    MessageOriginChannel, 
    MessageOriginChat,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.ext import ApplicationHandlerStop

from bot.config import Config
from bot.services.banlist_service import check_user as banlist_check, get_severity_label, add_user
from bot.services.group_member_tracker import update_member_info


async def _ban_guard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    user = update.effective_user
    if not user:
        return

    # ══════════════════════════════════════════════════════════════
    # TẦNG 1: Kiểm tra người gửi trực tiếp (Bảo vệ Bot)
    # ══════════════════════════════════════════════════════════════
    ban_info = banlist_check(user.id)
    if ban_info:
        severity_label = get_severity_label(ban_info["severity"])
        reason = ban_info["reason"] or "Không rõ"

        # Nếu đang ở trong nhóm
        if update.effective_chat and update.effective_chat.type in ("group", "supergroup"):
            # 1. Xóa tin nhắn của người dùng đó
            # try:
            #     await msg.delete()
            # except Exception as e:
                # print(f"⚠️ Không xóa được tin nhắn của user bị ban: {e}")

            # 2. Phát lệnh cảnh báo trên nhóm
            try:
                group_warning = (
                    f"🚨 <b>KiGuard Detector</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"👤 <b>Thành viên:</b> <a href='tg://user?id={user.id}'>{user.full_name}</a>\n"
                    f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
                    f"📋 <b>Mức độ cấm:</b> {severity_label}\n"
                    f"📝 <b>Lý do:</b> {reason}\n\n"
                    f"🚫 <i>Trạng thái: Đề nghị Admin vui lòng kiểm tra người dùng này</i>"
                )
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=group_warning,
                    message_thread_id=msg.message_thread_id,
                    parse_mode="HTML",
                )
            except Exception as e:
                print(f"⚠️ Không gửi được cảnh báo lên nhóm: {e}")

            # 3. Mute người dùng
            try:
                await context.bot.restrict_chat_member(
                    chat_id=update.effective_chat.id,
                    user_id=user.id,
                    permissions=ChatPermissions(can_send_messages=False)
                )
            except Exception as e:
                print(f"⚠️ Không mute được user trong banlist tại nhóm {update.effective_chat.id}: {e}")

            # 4. Gửi báo cáo về cho các admin biết là có vi phạm trong nhóm
            admin_ids = Config.get_notification_admin_ids()
            chat_title = update.effective_chat.title or "Không rõ"
            admin_alert = (
                f"🚨 <b>PHÁT HIỆN THÀNH VIÊN BANLIST HOẠT ĐỘNG TRONG NHÓM</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 <b>Thành viên:</b> <a href='tg://user?id={user.id}'>{user.full_name}</a>\n"
                f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
                f"📋 <b>Mức độ:</b> {severity_label}\n"
                f"📝 <b>Lý do:</b> {reason}\n\n"
                f"💬 <b>Hoạt động tại nhóm:</b> {chat_title}\n"
                f"❌ <i>Trạng thái: Đã xóa tin nhắn & Đã Mute thành viên này!</i>"
            )

            # Keyboard hành động dành cho Admin
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🚫 Ban", callback_data=f"bg_ban_{update.effective_chat.id}_{user.id}"),
                    InlineKeyboardButton("🔊 Gỡ Mute", callback_data=f"bg_unmute_{update.effective_chat.id}_{user.id}")
                ]
            ])

            async def send_admin_alert(admin_id):
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_alert,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                        reply_markup=keyboard,
                    )
                except Exception as e:
                    print(f"⚠️ Không gửi được báo cáo banlist cho admin {admin_id}: {e}")

            if admin_ids:
                await asyncio.gather(*(send_admin_alert(aid) for aid in admin_ids))

        # Nếu đang ở trong chat riêng tư với Bot (DMs)
        elif update.effective_chat.type == "private":
            admin_id = Config.ADMIN_CHAT_ID
            admin_link = f"tg://user?id={admin_id}" if admin_id else ""
            contact_text = f'👉 <a href="{admin_link}">Liên hệ Admin</a>' if admin_link else "👉 Liên hệ Admin"

            message = (
                f"🚫 <b>VanGuard Detector - Blocked User</b>\n\n"
                f"📋 Mức độ: <b>{severity_label}</b>\n"
                f"📝 Lý do: {reason}\n\n"
                f"{contact_text} để biết thêm chi tiết."
            )
            try:
                await msg.reply_text(message, parse_mode="HTML", disable_web_page_preview=True)
            except Exception:
                pass

        # Chặn đứng hoàn toàn, không cho chạy xuống các handler phía sau
        raise ApplicationHandlerStop()

    # ══════════════════════════════════════════════════════════════
    # TẦNG 2: Kiểm tra nguồn tin nhắn FORWARD (Bảo vệ Cộng đồng)
    # ══════════════════════════════════════════════════════════════
    # Chỉ quét forward trong các Nhóm/Siêu nhóm
    if update.effective_chat and update.effective_chat.type in ("group", "supergroup") and msg.forward_origin:
        origin = msg.forward_origin
        target_id_to_check = None
        source_type = "Không rõ"
        source_name = "Không xác định"

        # Phân loại nguồn để lấy ID đối chiếu banlist
        if isinstance(origin, MessageOriginUser):
            target_id_to_check = origin.sender_user.id
            source_type = "User Cá Nhân"
            source_name = origin.sender_user.full_name or str(target_id_to_check)

        elif isinstance(origin, MessageOriginChannel):
            target_id_to_check = origin.chat.id  # ID của Kênh gốc (Số âm, ví dụ: -100xxx)
            source_type = "Kênh (Channel)"
            source_name = origin.chat.title or "Kênh ẩn danh"

        elif isinstance(origin, MessageOriginChat):
            target_id_to_check = origin.sender_chat.id  # ID của Nhóm gốc (Số âm)
            source_type = "Nhóm (Group)"
            source_name = origin.sender_chat.title or "Nhóm ẩn danh"
            
        elif isinstance(origin, MessageOriginHiddenUser):
            # SỬA LỖI TẠI ĐÂY: Telegram ẩn danh hoàn toàn cá nhân này -> Không có ID nguồn gốc để check.
            # Để an toàn cho hệ thống (tránh kẻ xấu dùng acc ẩn danh để spam lệnh qua forward),
            # chúng ta chặn đứng tin nhắn này không cho kích hoạt lệnh của Bot nữa.
            raise ApplicationHandlerStop()

        # Tiến hành kiểm tra ID nguồn gốc (Cá nhân/Kênh/Nhóm đó có bị Ban không)
        if target_id_to_check:
            forward_ban_info = banlist_check(target_id_to_check)
            
            if forward_ban_info:
                # 💥 ĐÃ PHÁT HIỆN VI PHẠM: Nguồn gốc nằm trong Banlist!
                
                # 1. BẤT KỂ GIÁ NÀO CŨNG PHẢI XÓA TIN NHẮN TRƯỚC
                try:
                    await msg.delete()
                except Exception as e:
                    print(f"⚠️ LỖI KHÔNG XÓA ĐƯỢC TIN NHẮN VI PHẠM: {e}")

                # 2. TỰ ĐỘNG THÊM THẰNG FORWARD VÀO BANLIST (Vì tội tiếp tay)
                try:
                    reason_ban_forwarder = f"Forward nội dung từ {source_type} bị cấm (ID nguồn: {target_id_to_check})"
                    add_user(
                        user_id=user.id,
                        severity="scam",
                        reason=reason_ban_forwarder,
                        added_by="BanGuard Auto",
                    )
                except Exception as e:
                    print(f"⚠️ Không tự động ban được thằng forward: {e}")

                # 3. CHUẨN BỊ NỘI DUNG CẢNH BÁO GỬI CHO ADMIN
                severity_label = get_severity_label(forward_ban_info["severity"])
                reason_source = forward_ban_info["reason"] or "Không rõ"
                chat_title = update.effective_chat.title or "Không rõ"

                alert = (
                    f"🚨 <b>THÀNH VIÊN BỊ BAN TỰ ĐỘNG (XÓA + BAN CHÉO)</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"👤 <b>Kẻ tiếp tay (Vừa bị BAN):</b> <a href='tg://user?id={user.id}'>{user.full_name}</a>\n"
                    f"🆔 <b>ID kẻ tiếp tay:</b> <code>{user.id}</code>\n"
                    f"📝 <b>Hành vi:</b> Phát tán nội dung bị cấm.\n\n"
                    f"📦 <b>Nguồn gốc vi phạm ({source_type}):</b> {source_name}\n"
                    f"🆔 <b>ID Nguồn gốc:</b> <code>{target_id_to_check}</code>\n"
                    f"📋 <b>Mức độ nguồn gốc:</b> {severity_label}\n"
                    f"📝 <b>Lý do nguồn gốc bị cấm trước đó:</b> {reason_source}\n\n"
                    f"💬 <b>Tại nhóm:</b> {chat_title}\n"
                    f"❌ <i>Trạng thái: Đã xóa tin nhắn & Đã BAN kẻ tiếp tay thành công!</i>"
                )

                admin_ids = Config.get_notification_admin_ids()

                async def send_alert(admin_id):
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=alert,
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                        )
                    except Exception as e:
                        print(f"⚠️ Không gửi được báo cáo cho admin {admin_id}: {e}")

                if admin_ids:
                    await asyncio.gather(*(send_alert(aid) for aid in admin_ids))
                
                # Chặn đứng hoàn toàn, không cho chạy xuống các handler phía sau
                raise ApplicationHandlerStop()



async def ban_guard_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    admin_id = query.from_user.id
    if admin_id not in Config.get_notification_admin_ids():
        await query.answer("❌ Bạn không có quyền thực hiện hành động này!", show_alert=True)
        return
        
    data = query.data
    # Dạng dữ liệu: bg_ban_chatId_userId hoặc bg_unmute_chatId_userId
    parts = data.split("_")
    if len(parts) != 4 or parts[0] != "bg":
        await query.answer("❌ Dữ liệu không hợp lệ!", show_alert=True)
        return
        
    action = parts[1]
    try:
        chat_id = int(parts[2])
        user_id = int(parts[3])
    except ValueError:
        await query.answer("❌ ID không hợp lệ!", show_alert=True)
        return

    admin_name = query.from_user.full_name or str(admin_id)

    if action == "ban":
        try:
            # Thực hiện BAN khỏi nhóm
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            
            # Cập nhật trạng thái trong báo cáo gửi admin
            original_text = query.message.text_html
            new_status = f"❌ <i>Trạng thái: Đã BAN thành viên thành công! (Bởi Admin {admin_name})</i>"
            new_text = re.sub(
                r"❌\s*<i>Trạng thái:.*?</i>",
                new_status,
                original_text,
                flags=re.DOTALL
            )
            
            await query.edit_message_text(
                text=new_text,
                parse_mode="HTML",
                reply_markup=None
            )
            await query.answer("✅ Đã BAN thành viên khỏi nhóm!", show_alert=True)
        except Exception as e:
            await query.answer(f"⚠️ Lỗi khi ban: {e}", show_alert=True)
            
    elif action == "unmute":
        try:
            # Thực hiện gỡ mute user (trả lại quyền hạn bình thường của group)
            chat = await context.bot.get_chat(chat_id)
            normal_permissions = chat.permissions
            
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=normal_permissions
            )
            
            # Cập nhật trạng thái trong báo cáo gửi admin
            original_text = query.message.text_html
            new_status = f"❌ <i>Trạng thái: Đã gỡ Mute thành công! (Bởi Admin {admin_name})</i>"
            new_text = re.sub(
                r"❌\s*<i>Trạng thái:.*?</i>",
                new_status,
                original_text,
                flags=re.DOTALL
            )
            
            await query.edit_message_text(
                text=new_text,
                parse_mode="HTML",
                reply_markup=None
            )
            await query.answer("✅ Đã gỡ Mute thành viên thành công!", show_alert=True)
        except Exception as e:
            await query.answer(f"⚠️ Lỗi khi gỡ mute: {e}", show_alert=True)


def get_handlers():
    return [
        MessageHandler(filters.ALL, _ban_guard_handler, block=True),
        CallbackQueryHandler(ban_guard_callback_handler, pattern="^bg_")
    ]