"""
Group Monitor
Giám sát người dùng vào/ra nhóm và gửi thông báo đến admin

Sử dụng ChatMemberHandler để bắt MỌI trường hợp:
    - Vào qua invite link
    - Được admin thêm
    - Tự join
    - Rời nhóm / bị kick / bị ban
"""
from datetime import datetime
from telegram import Update, ChatMemberUpdated, ChatPermissions
from telegram.ext import ContextTypes, ChatMemberHandler
from bot.config import Config
from bot.utils.format import escape_md, md_link
from bot.utils.logger import log_command
from bot.services.group_member_tracker import track_member_join, track_member_leave
from bot.services.banlist_service import check_user as banlist_check, get_severity_label


async def _send_admin_notification(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Gửi thông báo đến admin qua tin nhắn riêng"""
    admin_id = Config.ADMIN_CHAT_ID
    if not admin_id or admin_id == "YOUR_ADMIN_CHAT_ID_HERE":
        return

    try:
        await context.bot.send_message(
            chat_id=int(admin_id),
            text=message,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )
    except Exception as e:
        print(f"⚠️ Không gửi được thông báo đến admin: {e}")


def _extract_status_change(chat_member_update: ChatMemberUpdated):
    """
    Phân tích thay đổi trạng thái thành viên.
    
    Lưu ý: User bị 'restricted' có thể ở TRONG hoặc NGOÀI nhóm.
    Phải kiểm tra thêm attribute is_member cho trường hợp này.
    
    Returns:
        tuple (was_member, is_member) hoặc None nếu không có thay đổi
    """
    old = chat_member_update.old_chat_member
    new = chat_member_update.new_chat_member

    old_status = old.status if old else None
    new_status = new.status if new else None

    # Các trạng thái chắc chắn "đang trong nhóm"
    definite_member = {"member", "administrator", "creator"}

    # Với restricted: phải check is_member (restricted user có thể ở ngoài nhóm)
    was_member = old_status in definite_member or (
        old_status == "restricted" and getattr(old, "is_member", False)
    )
    is_member = new_status in definite_member or (
        new_status == "restricted" and getattr(new, "is_member", False)
    )

    if was_member == is_member:
        return None  # Không có thay đổi ra/vào

    return was_member, is_member


def _build_user_card(user, action_emoji: str, action_text: str, chat_title: str) -> str:
    """Build thẻ thông tin user cho thông báo ra/vào nhóm"""
    separator = escape_md("═" * 26)
    thin_sep = escape_md("─" * 26)

    # Thông tin cơ bản
    full_name = escape_md(user.full_name or user.first_name or "Unknown")
    user_id = user.id
    profile_link = f"tg://user?id={user_id}"

    username_display = (
        f"@{escape_md(user.username)}" if user.username else escape_md("Không có")
    )
    username_warn = " ⚠️" if not user.username else ""

    premium_display = "✅ Yes" if user.is_premium else "❌ No"

    # Thời gian
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    time_display = escape_md(now)

    # Profile link
    profile_text = md_link("Xem hồ sơ", profile_link)

    message = (
        f"{separator}\n"
        f"{action_emoji} *{escape_md(action_text)}*\n"
        f"{separator}\n"
        f"\n"
        f"👤 Name: *{full_name}*\n"
        f"🆔 ID: `{user_id}`\n"
        f"🔗 Username: {username_display}{username_warn}\n"
        f"🔎 Profile: {profile_text}\n"
        f"⭐️ Premium: {premium_display}\n"
        f"\n"
        f"{thin_sep}\n"
        f"\n"
        f"💬 Group: *{escape_md(chat_title)}*\n"
        f"🕐 Time: {time_display}\n"
        f"\n"
        f"{separator}"
    )

    return message


async def on_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Xử lý khi trạng thái thành viên thay đổi.
    Bắt được TẤT CẢ trường hợp: join link, được thêm, rời, bị kick, bị ban.
    """
    # DEBUG: kiểm tra handler có được gọi không
    print(f"🔔 [DEBUG] chat_member update received: {update.chat_member is not None}")
    if update.chat_member:
        old = update.chat_member.old_chat_member
        new = update.chat_member.new_chat_member
        old_s = old.status if old else "?"
        new_s = new.status if new else "?"
        old_im = getattr(old, "is_member", "N/A")
        new_im = getattr(new, "is_member", "N/A")
        user_name = new.user.full_name if new else "?"
        print(f"🔔 [DEBUG] {user_name}: {old_s}(is_member={old_im}) → {new_s}(is_member={new_im})")

    if not update.chat_member:
        return

    result = _extract_status_change(update.chat_member)
    if result is None:
        return  # Không phải thay đổi ra/vào

    was_member, is_member = result
    user = update.chat_member.new_chat_member.user
    chat_title = update.chat_member.chat.title or "Unknown Group"

    # Bỏ qua nếu là bot
    if user.id == context.bot.id:
        action = "thêm vào" if is_member else "xóa khỏi"
        print(f"🤖 Bot đã được {action} nhóm: {chat_title}")
        return

    if is_member and not was_member:
        # === VÀO NHÓM ===
        print(f"📥 {user.full_name} ({user.id}) đã vào nhóm {chat_title}")
        log_command(user.id, user.full_name or "Unknown", user.username, f"[JOIN] {chat_title}")

        # Lưu thông tin thành viên vào database
        chat = update.chat_member.chat
        track_member_join(
            user_id=user.id,
            first_name=user.first_name or "",
            full_name=user.full_name or "",
            username=user.username or "",
            is_premium=user.is_premium or False,
            group_id=chat.id,
            group_name=chat.title or "",
            group_username=chat.username or "",
        )

        # === KIỂM TRA DANH SÁCH CẤM ===
        ban_info = banlist_check(user.id)
        if ban_info:
            chat_id = update.chat_member.chat.id
            severity = ban_info["severity"]
            reason = ban_info["reason"] or "Không rõ"
            severity_label = get_severity_label(severity)

            if ban_info["action"] == "ban":
                # Lừa đảo / Giả bio → BAN (kick + cấm vào lại)
                try:
                    await context.bot.ban_chat_member(
                        chat_id=chat_id,
                        user_id=user.id,
                    )
                    action_result = "🚫 Đã BAN khỏi nhóm"
                    print(f"🚫 Auto-ban {user.full_name} ({user.id}) — {severity}")
                except Exception as e:
                    action_result = f"⚠️ Ban thất bại: {e}"
                    print(f"⚠️ Không thể ban {user.id}: {e}")

            elif ban_info["action"] == "mute":
                # Spam → MUTE vĩnh viễn (cấm chat, vẫn ở trong nhóm)
                try:
                    await context.bot.restrict_chat_member(
                        chat_id=chat_id,
                        user_id=user.id,
                        permissions=ChatPermissions(
                            can_send_messages=False,
                            can_send_audios=False,
                            can_send_documents=False,
                            can_send_photos=False,
                            can_send_videos=False,
                            can_send_video_notes=False,
                            can_send_voice_notes=False,
                            can_send_polls=False,
                            can_send_other_messages=False,
                            can_add_web_page_previews=False,
                            can_invite_users=False,
                        ),
                    )
                    action_result = "🔇 Đã MUTE vĩnh viễn"
                    print(f"🔇 Auto-mute {user.full_name} ({user.id}) — {severity}")
                except Exception as e:
                    action_result = f"⚠️ Mute thất bại: {e}"
                    print(f"⚠️ Không thể mute {user.id}: {e}")
            else:
                action_result = "❓ Không rõ hành động"

            # Gửi thông báo cho admin về hành động tự động
            separator = escape_md("═" * 26)
            full_name = escape_md(user.full_name or user.first_name or "Unknown")
            username_display = (
                f"@{escape_md(user.username)}" if user.username else escape_md("Không có")
            )
            ban_message = (
                f"{separator}\n"
                f"⛔ *{escape_md('PHÁT HIỆN USER TRONG DANH SÁCH CẤM')}*\n"
                f"{separator}\n"
                f"\n"
                f"👤 Name: *{full_name}*\n"
                f"🆔 ID: `{user.id}`\n"
                f"🔗 Username: {username_display}\n"
                f"\n"
                f"📋 Mức độ: *{escape_md(severity_label)}*\n"
                f"📝 Lý do: {escape_md(reason)}\n"
                f"⚡ Kết quả: {escape_md(action_result)}\n"
                f"💬 Nhóm: *{escape_md(chat_title)}*\n"
                f"\n"
                f"{separator}"
            )
            await _send_admin_notification(context, ban_message)
            return  # Không gửi thông báo vào nhóm bình thường

        message = _build_user_card(
            user=user,
            action_emoji="📥",
            action_text="THÀNH VIÊN MỚI VÀO NHÓM",
            chat_title=chat_title,
        )
        await _send_admin_notification(context, message)

    elif was_member and not is_member:
        # === RỜI NHÓM ===
        new_status = update.chat_member.new_chat_member.status
        print(f"new status: {new_status}")
        chat_id = update.chat_member.chat.id

        if new_status == "kicked":
            action_text = "THÀNH VIÊN BỊ BAN"
            action_emoji = "🚫"
            leave_status = "kicked"
        else:
            action_text = "THÀNH VIÊN RỜI NHÓM"
            action_emoji = "📤"
            leave_status = "left"

        print(f"{action_emoji} {user.full_name} ({user.id}) đã rời nhóm {chat_title}")
        log_command(user.id, user.full_name or "Unknown", user.username, f"[{action_text}] {chat_title}")

        # Cập nhật trạng thái rời nhóm trong database
        track_member_leave(
            user_id=user.id,
            group_id=chat_id,
            status=leave_status,
        )

        # === TỰ RỜI NHÓM → AUTO-BAN (KHÔNG THÊM VÀO BLACKLIST TOÀN CỤC) ===
        if leave_status == "left":
            # Ban khỏi nhóm (cấm vào lại)
            ban_result = ""
            try:
                await context.bot.ban_chat_member(
                    chat_id=chat_id,
                    user_id=user.id,
                )
                ban_result = "🚫 Đã BAN — cấm vào lại nhóm"
                print(f"🚫 Auto-ban {user.full_name} ({user.id}) — tự rời nhóm {chat_title}")
            except Exception as e:
                ban_result = f"⚠️ Ban thất bại: {e}"
                print(f"⚠️ Không thể auto-ban {user.id}: {e}")

            # Gửi thông báo cho admin
            separator = escape_md("═" * 26)
            thin_sep = escape_md("─" * 26)
            full_name = escape_md(user.full_name or user.first_name or "Unknown")
            username_display = (
                f"@{escape_md(user.username)}" if user.username else escape_md("Không có")
            )

            ban_message = (
                f"{separator}\n"
                f"🚪 *{escape_md('AUTO-BAN: THÀNH VIÊN TỰ RỜI NHÓM')}*\n"
                f"{separator}\n"
                f"\n"
                f"👤 Name: *{full_name}*\n"
                f"🆔 ID: `{user.id}`\n"
                f"🔗 Username: {username_display}\n"
                f"\n"
                f"{thin_sep}\n"
                f"\n"
                f"📋 Hành động: *{escape_md('Ban khỏi nhóm (Tự rời)')}*\n"
                f"📝 Lý do: {escape_md(f'Tự rời nhóm {chat_title}')}\n"
                f"⚡ Kết quả: {escape_md(ban_result)}\n"
                f"💬 Nhóm: *{escape_md(chat_title)}*\n"
                f"\n"
                f"{separator}"
            )
            await _send_admin_notification(context, ban_message)
            return  # Đã gửi thông báo riêng, không cần gửi thông báo thường

        message = _build_user_card(
            user=user,
            action_emoji=action_emoji,
            action_text=action_text,
            chat_title=chat_title,
        )
        await _send_admin_notification(context, message)


def get_handlers():
    return [
        ChatMemberHandler(on_chat_member_update, ChatMemberHandler.CHAT_MEMBER),
    ]
