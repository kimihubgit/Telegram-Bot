"""
/banlist Command
Quản lý danh sách cấm người dùng.

Cách dùng:
    /banlist add <user_id> <severity> [reason]
    /banlist remove <user_id>
    /banlist check <user_id>
    /banlist list

Severity:
    scam      → Ban (lừa đảo)
    fake_bio  → Ban (giả mạo bio)
    spam      → Mute vĩnh viễn

Giới hạn: Chỉ admin (NOTIFICATION_ADMIN_IDS trong .env) mới được dùng.
"""
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from bot.config import Config
from bot.services.banlist_service import (
    add_user,
    remove_user,
    check_user,
    get_all_banned,
    get_severity_label,
)
from bot.utils.format import escape_md
from bot.utils.logger import log_from_update


def _is_authorized(user_id: int) -> bool:
    allowed_ids = Config.get_notification_admin_ids()
    return user_id in allowed_ids


async def banlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_from_update(update)
    user_id = update.effective_user.id

    if not _is_authorized(user_id):
        await update.message.reply_text(
            "🚫 <b>Không có quyền truy cập</b>\n\n"
            "Lệnh này chỉ dành cho admin.",
            parse_mode="HTML",
        )
        return

    args = context.args or []

    if not args:
        await _show_help(update)
        return

    action = args[0].lower()

    if action == "add" and len(args) >= 3:
        await _handle_add(update, args)
    elif action == "remove" and len(args) >= 2:
        await _handle_remove(update, args)
    elif action == "check" and len(args) >= 2:
        await _handle_check(update, args)
    elif action == "list":
        await _handle_list(update)
    else:
        await _show_help(update)


async def _show_help(update: Update):
    await update.message.reply_text(
        "📋 <b>Quản lý danh sách cấm</b>\n\n"
        "<b>Thêm user:</b>\n"
        "<code>/banlist add &lt;user_id&gt; &lt;severity&gt; [lý do]</code>\n\n"
        "<b>Xóa user:</b>\n"
        "<code>/banlist remove &lt;user_id&gt;</code>\n\n"
        "<b>Kiểm tra user:</b>\n"
        "<code>/banlist check &lt;user_id&gt;</code>\n\n"
        "<b>Xem danh sách:</b>\n"
        "<code>/banlist list</code>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "<b>Mức độ vi phạm (severity):</b>\n"
        "  🔴 <code>scam</code> — Lừa đảo → <b>Ban</b>\n"
        "  🟠 <code>fake_bio</code> — Giả mạo Bio → <b>Ban</b>\n"
        "  🟡 <code>spam</code> — Spam → <b>Mute vĩnh viễn</b>\n",
        parse_mode="HTML",
    )


async def _handle_add(update: Update, args: list):
    try:
        target_id = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ User ID không hợp lệ.", parse_mode="HTML")
        return

    severity = args[2].lower()
    valid_severities = {"scam", "fake_bio", "spam"}

    if severity not in valid_severities:
        await update.message.reply_text(
            f"❌ Mức độ không hợp lệ: <code>{severity}</code>\n\n"
            f"Chọn: <code>scam</code>, <code>fake_bio</code>, <code>spam</code>",
            parse_mode="HTML",
        )
        return

    reason = " ".join(args[3:]) if len(args) > 3 else ""
    admin_name = update.effective_user.full_name or str(update.effective_user.id)

    success = add_user(
        user_id=target_id,
        severity=severity,
        reason=reason,
        added_by=admin_name,
    )

    if success:
        label = get_severity_label(severity)
        msg = (
            f"✅ <b>Đã thêm vào danh sách cấm</b>\n\n"
            f"🆔 User ID: <code>{target_id}</code>\n"
            f"📋 Mức độ: {label}\n"
        )
        if reason:
            msg += f"📝 Lý do: {reason}\n"

        action_desc = "Ban khỏi nhóm" if severity != "spam" else "Mute vĩnh viễn"
        msg += f"\n⚡ Khi vào nhóm sẽ bị: <b>{action_desc}</b>"
        await update.message.reply_text(msg, parse_mode="HTML")
    else:
        await update.message.reply_text("❌ Thêm thất bại. Kiểm tra lại severity.", parse_mode="HTML")


async def _handle_remove(update: Update, args: list):
    try:
        target_id = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ User ID không hợp lệ.", parse_mode="HTML")
        return

    success = remove_user(target_id)
    if success:
        await update.message.reply_text(
            f"✅ Đã xóa <code>{target_id}</code> khỏi danh sách cấm.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"⚠️ User <code>{target_id}</code> không có trong danh sách cấm.",
            parse_mode="HTML",
        )


async def _handle_check(update: Update, args: list):
    try:
        target_id = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ User ID không hợp lệ.", parse_mode="HTML")
        return

    info = check_user(target_id)
    if info:
        label = get_severity_label(info["severity"])
        action_desc = "Ban khỏi nhóm" if info["action"] == "ban" else "Mute vĩnh viễn"
        msg = (
            f"⛔ <b>User trong danh sách cấm</b>\n\n"
            f"🆔 User ID: <code>{target_id}</code>\n"
            f"📋 Mức độ: {label}\n"
            f"📝 Lý do: {info['reason'] or 'Không rõ'}\n"
            f"👤 Thêm bởi: {info['added_by']}\n"
            f"📅 Ngày thêm: {info['added_date']}\n"
            f"⚡ Hành động: <b>{action_desc}</b>"
        )
    else:
        msg = f"✅ User <code>{target_id}</code> <b>không</b> trong danh sách cấm."

    await update.message.reply_text(msg, parse_mode="HTML")


async def _handle_list(update: Update):
    banned = get_all_banned()

    if not banned:
        await update.message.reply_text(
            "📋 Danh sách cấm hiện đang <b>trống</b>.",
            parse_mode="HTML",
        )
        return

    lines = ["📋 <b>DANH SÁCH CẤM</b>\n", f"Tổng: <b>{len(banned)}</b> user\n", "━━━━━━━━━━━━━━━━━━\n"]

    for uid, info in banned.items():
        label = get_severity_label(info["severity"])
        reason = info.get("reason", "") or "—"
        lines.append(
            f"🆔 <code>{uid}</code> — {label}\n"
            f"    📝 {reason}\n"
        )

    msg = "".join(lines)

    # Telegram giới hạn 4096 ký tự
    if len(msg) > 4000:
        msg = msg[:4000] + "\n\n... (danh sách quá dài)"

    await update.message.reply_text(msg, parse_mode="HTML")


def get_handlers():
    return [
        CommandHandler("banlist", banlist_command),
    ]
