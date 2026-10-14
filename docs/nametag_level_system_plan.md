# 🎮 HỆ THỐNG CẤP ĐỘ & NAMETAG (LEVELING & NAMETAG SYSTEM)
> [!NOTE]  
> Tài liệu này phác thảo ý tưởng, cấu trúc dữ liệu và lộ trình triển khai cơ chế **Tích lũy kinh nghiệm (EXP), Lên cấp (Level up) và Đeo Danh hiệu (Nametag)** dành cho người dùng tương tác trong các nhóm Telegram.

---

## 💡 Ý Tưởng Cốt Lõi (Core Concept)

Vì Bot Telegram **không thể tự ý sửa đổi First Name/Username thực tế** của người dùng trên Telegram (do giới hạn bảo mật từ Telegram API), hệ thống Nametag sẽ được thiết kế hoạt động theo các hình thức sau:

1. **Hiển thị đi kèm (Bot Representation):** Mỗi khi Bot tương tác hoặc hiển thị thông tin của user (Ví dụ: khi gõ `/me`, `/checkinfo`, `/rank`, hoặc khi Bot phát thông báo vi phạm, vinh danh...), tên người dùng sẽ được đính kèm danh hiệu tương ứng.
   * *Ví dụ:* `[🔱 Huyền Thoại] Nguyễn Văn A` hoặc `[🍀 Tân Binh] kimiddev`.
2. **Quản trị viên Custom Title (Admin Custom Title):** Nếu người dùng là Admin nhóm chat, Bot có thể tự động đổi "Custom Title" của họ trong nhóm sang Nametag họ chọn (Nếu Bot có quyền `can_promote_members`).
3. **Mở khóa theo cấp độ (Level Unlocks):** Người dùng hoạt động tích cực (gửi tin nhắn) để nhận EXP. Khi đạt mốc level nhất định, họ sẽ tự động mở khóa các Nametag độc quyền và có thể tự do lựa chọn trang bị chúng.
4. **Nametag Tự chọn (Custom Nametags):** Đối với các user đạt cấp độ rất cao (Ví dụ: Level 30+), họ có thể dùng lệnh `/nametag set <nội dung>` để tự tạo danh hiệu cá nhân theo sở thích.

---

## 📊 Cấu Trúc Dữ Liệu (`members.json`)

Chúng ta sẽ mở rộng cấu trúc dữ liệu Nested hiện tại của `members.json` bằng cách bổ sung thêm các trường liên quan đến EXP, Cấp độ, và Danh hiệu trong `current_info`:

```json
{
  "123456789": {
    "current_info": {
      "first_name": "Kimi",
      "full_name": "Kimidev Community",
      "username": "kimidev",
      "is_premium": true,
      
      "xp": 450,
      "level": 3,
      "message_count": 84,
      "last_xp_gain": "23/05/2026 23:30:15",
      
      "active_nametag": "🍀 Tân Binh",
      "unlocked_nametags": [
        "🍀 Tân Binh",
        "🛡️ Thành Viên"
      ]
    },
    "groups": {
      "-10022223333": {
        "name": "Cộng Đồng Kimidev",
        "username": "kimidev_group",
        "status": "member",
        "joined": "19/05/2026 21:00:00",
        "left": null
      }
    },
    "changes": []
  }
}
```

---

## 📈 Cơ Chế Tính Kinh Nghiệm & Lên Cấp (EXP & Leveling Logic)

### 1. Công thức tính EXP Lên Cấp
Để cấp độ tăng dần độ khó một cách cân bằng, chúng ta có thể áp dụng công thức mũ nhẹ:
$$\text{XP cần thiết} = 100 \times (\text{Level hiện tại})^{1.2}$$

* **Level 1 → 2:** Cần $100$ EXP.
* **Level 2 → 3:** Cần $229$ EXP.
* **Level 3 → 4:** Cần $373$ EXP.
* **Level 10 → 11:** Cần $1,584$ EXP.

### 2. Cơ chế nhận EXP tránh Spam (Cooldown)
* Mỗi khi gửi 1 tin nhắn trong nhóm chat được theo dõi: Nhận **5 - 15 EXP ngẫu nhiên**.
* **Thời gian chờ (Cooldown):** 30 giây cho mỗi user. Tin nhắn gửi trong thời gian chờ vẫn được ghi nhận vào `message_count` nhưng không cộng thêm EXP. Điều này tránh việc người dùng spam tin nhắn liên tục để cày cấp.

### 3. Hệ thống Cấp bậc & Danh hiệu mặc định

| Cấp độ | Danh hiệu | Biểu tượng | Quyền lợi mở khóa |
| :--- | :--- | :---: | :--- |
| **Lv 1 - 4** | **Tân Binh** | 🍀 | Mở khóa danh hiệu Tân Binh mặc định |
| **Lv 5 - 9** | **Thành Viên** | 🛡️ | Đã quen thuộc với nhóm |
| **Lv 10 - 19** | **Chiến Binh** | 🔥 | Thành viên tích cực |
| **Lv 20 - 34** | **Thủ Lĩnh** | 👑 | Trở nên uy tín trong cộng đồng |
| **Lv 35 - 49** | **Trưởng Lão** | 🔮 | Gương mặt kỳ cựu |
| **Lv 50+** | **Huyền Thoại** | 🔱 | Quyền tự đặt Custom Nametag bằng lệnh `/nametag set` |

---

## 🛠️ Thiết Kế Module và Các Hàm Chức Năng

### 1. Trong `bot/services/group_member_tracker.py`
Xây dựng hàm xử lý cộng EXP, lưu trữ và nâng cấp:

```python
def gain_xp(user_id: int, xp_min: int = 5, xp_max: int = 15, cooldown_sec: int = 30) -> dict | None:
    """
    Cộng EXP cho người dùng sau mỗi tin nhắn (có áp dụng cooldown).
    Trả về dict chứa thông tin {old_level, new_level, leveled_up: bool} nếu có cập nhật.
    """
    # 1. Load data
    # 2. Kiểm tra cooldown (dựa trên last_xp_gain)
    # 3. Cộng XP & Message count
    # 4. Kiểm tra xem có vượt mốc level hiện tại không
    # 5. Nếu lên level:
    #    - Tính toán danh hiệu mới mở khóa (nếu có)
    #    - Tự động gán làm active_nametag (hoặc để người dùng tự chọn)
    # 6. Save data & Trả về thông báo nâng cấp
```

### 2. Trong `bot/commands/tracker.py`
Chèn logic nhận EXP vào middleware để kiểm soát mọi tin nhắn trong nhóm:

```python
async def _track_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... logic cũ (lưu info & group status) ...

    # Thêm logic cộng EXP:
    if chat.type in ("group", "supergroup"):
        res = gain_xp(user.id)
        if res and res.get("leveled_up"):
            # Phát thông báo chúc mừng lên cấp cực đẹp ngay trong nhóm!
            await update.message.reply_text(
                f"🎉 Chúc mừng <b>{user.first_name}</b> đã đạt <b>Cấp {res['new_level']}</b>!\n"
                f"🏆 Danh hiệu mới mở khóa: <b>{res['new_nametag']}</b>",
                parse_mode="HTML"
            )
```

### 3. Lệnh Mới `/rank` hoặc `/level` (`bot/commands/level.py`)
Cho phép người dùng kiểm tra cấp độ và thanh tiến trình EXP của họ.

```
📊 THÔNG TIN CẤP ĐỘ CỦA BẠN
━━━━━━━━━━━━━━━━━━━━
👤 Người dùng: Nguyễn Văn A
🏷️ Danh hiệu trang bị: [🔥 Chiến Binh]
⭐ Cấp độ hiện tại: 12

📈 Tiến trình EXP:
[██████░░░░░░░░░░] 38% (600 / 1584 XP)
💬 Tổng tin nhắn gửi: 452 tin

💡 Mẹo: Chat tích cực trong nhóm để mở khóa thêm nhiều danh hiệu xịn hơn nhé!
```

### 4. Lệnh Mới `/nametag`
Cho phép người dùng tùy chọn danh hiệu đã mở khóa hoặc chỉnh sửa danh hiệu tự chọn nếu đạt cấp 50.

* `/nametag`: Trả về bàn phím Inline Keyboard danh sách các danh hiệu đã mở khóa để chọn trang bị.
* `/nametag set <nội dung>`: (Chỉ dành cho Lv 50+) Đổi danh hiệu tự chọn thành bất cứ gì (tối đa 15 ký tự).
* `/nametag reset`: Reset danh hiệu về mặc định của cấp độ hiện tại.

---

## 🚀 Kế Hoạch Triển Khai (Roadmap)

* [ ] **Bước 1:** Cập nhật `group_member_tracker.py` để bổ sung cấu trúc dữ liệu EXP, hàm `gain_xp`, và hàm xác định cấp độ/danh hiệu mở khóa.
* [ ] **Bước 2:** Cập nhật `bot/commands/tracker.py` để tích hợp việc tự động cộng EXP khi người dùng nhắn tin trong nhóm kèm theo cơ chế cooldown 30 giây.
* [ ] **Bước 3:** Xây dựng module lệnh `/rank` và `/nametag` tại file `bot/commands/level.py` để hiển thị thanh tiến trình đẹp mắt và hỗ trợ đổi danh hiệu.
* [ ] **Bước 4:** Tích hợp Nametag vào các lệnh hiển thị thông tin sẵn có như `/me`, `/checkinfo`, `/check` để người dùng thấy rõ sự thay đổi và thúc đẩy tương tác.

---
💡 **Bạn thấy ý tưởng và thiết kế này thế nào? Bạn muốn điều chỉnh công thức EXP hay các danh hiệu mở khóa không? Hãy cho tôi biết nhé!**
