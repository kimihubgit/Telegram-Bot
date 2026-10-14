# 📋 Test Cases — Ban Guard & Member Tracker

## Tổng quan hệ thống

```
Tin nhắn đến
    │
    ▼
[ban_guard.py - Group -2]
    ├── TẦNG 1: User bị ban? → Xóa msg (nhóm) + reply (private) + STOP
    ├── TẦNG 2: Forward từ nguồn bị ban? → Xóa + Ban forwarder + Alert admin + STOP
    └── TẦNG 3: User đổi info? → Cập nhật members.json + ghi changes[]
    │
    ▼
[group_monitor.py - ChatMemberHandler]
    ├── Join → track_member_join() + check banlist → auto-ban/mute
    └── Leave → track_member_leave() + auto-ban nếu tự rời
```

---

## 🔴 TẦNG 1 — Chặn User Bị Ban

### TC-1.1: User bị ban gửi tin nhắn trong nhóm
| Mục | Chi tiết |
|---|---|
| **Hành động** | User A (bị ban, severity=scam) gửi "Hello" trong nhóm |
| **Kỳ vọng** | ✅ Tin nhắn bị XÓA khỏi nhóm |
| | ✅ KHÔNG reply "bạn bị cấm" trong nhóm |
| | ✅ `ApplicationHandlerStop` → không handler nào khác chạy |
| | ✅ TẦNG 3 KHÔNG chạy (không cập nhật info) |

### TC-1.2: User bị ban gửi tin nhắn private cho bot
| Mục | Chi tiết |
|---|---|
| **Hành động** | User A (bị ban) gửi "/start" qua private chat |
| **Kỳ vọng** | ✅ Bot reply "🚫 BẠN ĐÃ BỊ CẤM SỬ DỤNG BOT" |
| | ✅ Hiển thị severity + reason + link admin |
| | ✅ `ApplicationHandlerStop` → /start KHÔNG chạy |

### TC-1.3: User bị ban gửi tin nhắn nhưng bot mất quyền admin
| Mục | Chi tiết |
|---|---|
| **Hành động** | User A (bị ban) gửi tin nhắn trong nhóm mà bot không có quyền delete |
| **Kỳ vọng** | ⚠️ `msg.delete()` throw exception → print lỗi |
| | ✅ Vẫn `raise ApplicationHandlerStop()` → chặn handler phía sau |
| | ❓ Tin nhắn vẫn tồn tại trong nhóm (vì không xóa được) |

### TC-1.4: User sạch (không bị ban) gửi tin nhắn
| Mục | Chi tiết |
|---|---|
| **Hành động** | User B (không bị ban) gửi tin nhắn trong nhóm |
| **Kỳ vọng** | ✅ TẦNG 1 skip (return) |
| | ✅ Tiếp tục xuống TẦNG 2 và TẦNG 3 |
| | ✅ Các handler khác (commands) chạy bình thường |

---

## 🟠 TẦNG 2 — Chặn Forward Từ Nguồn Bị Ban

### TC-2.1: Forward tin nhắn từ User bị ban (MessageOriginUser)
| Mục | Chi tiết |
|---|---|
| **Hành động** | User B (sạch) forward tin nhắn của User X (bị ban) vào nhóm |
| **Kỳ vọng** | ✅ Tin nhắn forward bị XÓA |
| | ✅ User B được thêm vào banlist (severity=scam, added_by=BanGuard Auto) |
| | ✅ Admin nhận alert "🚨 THÀNH VIÊN BỊ BAN TỰ ĐỘNG" |
| | ✅ `ApplicationHandlerStop` → TẦNG 3 KHÔNG chạy |

### TC-2.2: Forward tin nhắn từ Channel bị ban (MessageOriginChannel)
| Mục | Chi tiết |
|---|---|
| **Hành động** | User B forward từ Channel Z (ID -100xxx, bị ban) vào nhóm |
| **Kỳ vọng** | ✅ `origin.chat.id` → check banlist → phát hiện ban |
| | ✅ Xóa tin nhắn + ban User B + alert admin |
| | ✅ source_type = "Kênh (Channel)" |

### TC-2.3: Forward tin nhắn từ Group bị ban (MessageOriginChat)
| Mục | Chi tiết |
|---|---|
| **Hành động** | User B forward từ Group Y (bị ban) vào nhóm |
| **Kỳ vọng** | ✅ `origin.sender_chat.id` → check banlist → phát hiện ban |
| | ✅ Xóa + ban + alert |
| | ✅ source_type = "Nhóm (Group)" |

### TC-2.4: Forward tin nhắn từ User ẩn danh (MessageOriginHiddenUser)
| Mục | Chi tiết |
|---|---|
| **Hành động** | User B forward tin nhắn từ user đã bật "ẩn danh forward" |
| **Kỳ vọng** | ✅ `raise ApplicationHandlerStop()` → chặn luôn |
| | ✅ Tin nhắn KHÔNG bị xóa (chỉ chặn handler) |
| | ❓ **Potential issue:** Tin nhắn forward ẩn danh hợp lệ cũng bị chặn handler |

### TC-2.5: Forward tin nhắn từ User KHÔNG bị ban
| Mục | Chi tiết |
|---|---|
| **Hành động** | User B forward tin nhắn từ User C (sạch) vào nhóm |
| **Kỳ vọng** | ✅ `banlist_check()` → None → skip |
| | ✅ Tin nhắn tồn tại bình thường |
| | ✅ Tiếp tục xuống TẦNG 3 |

### TC-2.6: Forward trong private chat (không phải nhóm)
| Mục | Chi tiết |
|---|---|
| **Hành động** | User B forward tin nhắn từ User X (bị ban) vào private chat với bot |
| **Kỳ vọng** | ✅ TẦNG 2 skip (chỉ check trong group/supergroup) |
| | ✅ Tin nhắn KHÔNG bị xóa |

### TC-2.7: User A (đã bị ban) forward tin nhắn từ User X (cũng bị ban)
| Mục | Chi tiết |
|---|---|
| **Hành động** | User A (bị ban) forward tin nhắn từ User X (bị ban) vào nhóm |
| **Kỳ vọng** | ✅ TẦNG 1 bắt User A trước → xóa tin nhắn + STOP |
| | ❌ TẦNG 2 KHÔNG chạy → không detect forward vi phạm |
| | ❌ Admin KHÔNG nhận alert về forward nguồn bị ban |
| | ⚠️ **Trade-off chấp nhận được:** User A đã bị ban rồi, tin nhắn đã bị xóa |

---

## 🟢 TẦNG 3 — Cập Nhật Thông Tin User

### TC-3.1: User đổi username
| Mục | Chi tiết |
|---|---|
| **Hành động** | User B (username="old_name") đổi thành "new_name" rồi gửi tin nhắn |
| **Kỳ vọng** | ✅ `current_info.username` → "new_name" |
| | ✅ `changes[]` thêm entry: `{"username": "old_name"}` |
| | ✅ `update_member_info()` return True |

### TC-3.2: User đổi tên hiển thị
| Mục | Chi tiết |
|---|---|
| **Hành động** | User B đổi full_name từ "Nguyễn A" thành "Nguyễn B" |
| **Kỳ vọng** | ✅ `current_info.full_name` → "Nguyễn B" |
| | ✅ `changes[].changed_fields` chứa `{"full_name": "Nguyễn A"}` |

### TC-3.3: User mua Premium
| Mục | Chi tiết |
|---|---|
| **Hành động** | User B kích hoạt Telegram Premium rồi gửi tin nhắn |
| **Kỳ vọng** | ✅ `current_info.is_premium` → true |
| | ✅ `changes[].changed_fields` chứa `{"is_premium": false}` |

### TC-3.4: User không có trong members.json gửi tin nhắn
| Mục | Chi tiết |
|---|---|
| **Hành động** | User mới chưa từng join nhóm nào gửi /start qua private chat |
| **Kỳ vọng** | ✅ `update_member_info()` return False (user chưa có trong DB) |
| | ✅ Không tạo entry mới (chỉ tạo khi join nhóm) |
| | ✅ Không exception |

### TC-3.5: User gửi tin nhắn nhưng không đổi gì
| Mục | Chi tiết |
|---|---|
| **Hành động** | User B (đã có trong DB) gửi tin nhắn, info giữ nguyên |
| **Kỳ vọng** | ✅ `update_member_info()` return False |
| | ✅ Không ghi gì vào `changes[]` |
| | ✅ Không write file (tiết kiệm I/O) |

### TC-3.6: User ở format cũ (fields ở top-level, không có current_info)
| Mục | Chi tiết |
|---|---|
| **Hành động** | User C có data dạng cũ: `{"first_name": "A", "username": "old"}` rồi đổi username |
| **Kỳ vọng** | ✅ Đọc từ top-level fields (migrate) |
| | ✅ Ghi vào `current_info` mới |
| | ✅ Xóa fields cũ ở top-level (`first_name`, `full_name`, `username`, `is_premium`) |
| | ✅ `changes[]` ghi nhận thay đổi |

### TC-3.7: Quá 50 thay đổi
| Mục | Chi tiết |
|---|---|
| **Hành động** | User spam đổi tên 60 lần |
| **Kỳ vọng** | ✅ `changes[]` chỉ giữ 50 entry gần nhất |
| | ✅ 10 entry cũ nhất bị cắt |

---

## 🔵 Group Monitor — Join/Leave

### TC-4.1: User mới join nhóm lần đầu
| Mục | Chi tiết |
|---|---|
| **Hành động** | User D join nhóm "Dev Group" |
| **Kỳ vọng** | ✅ Tạo entry mới trong members.json |
| | ✅ `current_info` có đầy đủ thông tin |
| | ✅ `groups[-100xxx]` có `status=member`, `joined=now`, `left=null` |
| | ✅ Admin nhận thông báo "THÀNH VIÊN MỚI VÀO NHÓM" |

### TC-4.2: User đã có trong DB join nhóm thứ 2
| Mục | Chi tiết |
|---|---|
| **Hành động** | User D (đã ở nhóm A) join nhóm B |
| **Kỳ vọng** | ✅ `groups` thêm entry mới cho nhóm B |
| | ✅ Nhóm A vẫn giữ nguyên |
| | ✅ Nếu info thay đổi → ghi vào `changes[]` |

### TC-4.3: User rời nhóm (tự leave)
| Mục | Chi tiết |
|---|---|
| **Hành động** | User D tự rời nhóm "Dev Group" |
| **Kỳ vọng** | ✅ `groups[-100xxx].status` → "left" |
| | ✅ `groups[-100xxx].left` → timestamp hiện tại |
| | ✅ User D được thêm vào banlist (severity=left_group) |
| | ✅ User D bị ban khỏi nhóm (ban_chat_member) |
| | ✅ Admin nhận thông báo "AUTO-BAN: THÀNH VIÊN TỰ RỜI NHÓM" |

### TC-4.4: User bị admin kick
| Mục | Chi tiết |
|---|---|
| **Hành động** | Admin kick User D khỏi nhóm |
| **Kỳ vọng** | ✅ `groups[-100xxx].status` → "kicked" |
| | ✅ KHÔNG thêm vào banlist (chỉ auto-ban khi tự leave) |
| | ✅ Admin nhận thông báo "THÀNH VIÊN BỊ BAN" |

### TC-4.5: User bị ban join lại nhóm
| Mục | Chi tiết |
|---|---|
| **Hành động** | User X (bị ban, action=ban) join nhóm |
| **Kỳ vọng** | ✅ `track_member_join()` vẫn lưu thông tin |
| | ✅ `banlist_check()` phát hiện → auto `ban_chat_member()` |
| | ✅ Admin nhận thông báo "PHÁT HIỆN USER TRONG DANH SÁCH CẤM" |

### TC-4.6: User bị ban join lại (action=mute)
| Mục | Chi tiết |
|---|---|
| **Hành động** | User Y (bị ban, severity=spam, action=mute) join nhóm |
| **Kỳ vọng** | ✅ `restrict_chat_member()` → MUTE vĩnh viễn |
| | ✅ User vẫn ở trong nhóm nhưng không nói được |

### TC-4.7: User rời nhóm nhưng chưa có trong members.json
| Mục | Chi tiết |
|---|---|
| **Hành động** | User mới (chưa được track) rời nhóm |
| **Kỳ vọng** | ✅ `track_member_leave()` → `str_user_id not in data` → return |
| | ✅ Không crash, không tạo entry mới |

---

## 🟡 Edge Cases & Race Conditions

### TC-5.1: 2 tin nhắn đồng thời từ cùng 1 user
| Mục | Chi tiết |
|---|---|
| **Hành động** | User gửi 2 tin nhắn gần như cùng lúc |
| **Kỳ vọng** | ⚠️ `_load_data()` + `_save_data()` không có lock |
| | ⚠️ Có thể xảy ra race condition: tin nhắn 2 ghi đè data của tin nhắn 1 |
| | 💡 **Rủi ro thấp** vì python-telegram-bot xử lý tuần tự theo group |

### TC-5.2: members.json bị corrupt (JSON không hợp lệ)
| Mục | Chi tiết |
|---|---|
| **Hành động** | File members.json bị lỗi format |
| **Kỳ vọng** | ✅ `_load_data()` catch `JSONDecodeError` → return `{}` |
| | ⚠️ Dữ liệu cũ bị MẤT khi `_save_data()` ghi đè file rỗng |

### TC-5.3: Bot không có quyền admin trong nhóm
| Mục | Chi tiết |
|---|---|
| **Hành động** | Mọi thao tác delete/ban/mute |
| **Kỳ vọng** | ✅ Tất cả đều wrapped trong try/except |
| | ✅ Print lỗi nhưng không crash bot |

### TC-5.4: User gửi tin nhắn nhưng effective_user là None
| Mục | Chi tiết |
|---|---|
| **Hành động** | Channel post hoặc anonymous admin gửi tin nhắn |
| **Kỳ vọng** | ✅ `if not user: return` → skip hoàn toàn |

### TC-5.5: `add_user()` trong banlist_service bị lỗi
| Mục | Chi tiết |
|---|---|
| **Hành động** | TẦNG 2 cố ban forwarder nhưng `add_user()` throw exception |
| **Kỳ vọng** | ✅ Caught bởi try/except → print lỗi |
| | ✅ Tin nhắn vẫn bị xóa (bước 1 đã chạy trước) |
| | ✅ Alert admin vẫn được gửi (bước 3) |
| | ⚠️ User KHÔNG bị thêm vào banlist → có thể forward lại |

### TC-5.6: Forward tin nhắn từ nguồn bị ban nhưng `target_id_to_check = None`
| Mục | Chi tiết |
|---|---|
| **Hành động** | origin là kiểu mới chưa được handle (tương lai Telegram thêm type) |
| **Kỳ vọng** | ✅ Không match bất kỳ isinstance nào |
| | ✅ `target_id_to_check` vẫn None → `if target_id_to_check:` skip |
| | ✅ Tin nhắn forward tồn tại bình thường |

---

## 🔶 Bugs & Vấn Đề Phát Hiện Từ Data Thực Tế

### BUG-1: Data format không đồng nhất
| Mục | Chi tiết |
|---|---|
| **Vấn đề** | Một số user có fields ở top-level (format cũ), một số có `current_info` (format mới) |
| **Ví dụ** | User `5877290229` có `first_name` ở top-level, User `8119900362` có `current_info` |
| **Ảnh hưởng** | `track_member_join()` đọc `current_info` → nếu không có → `old_info = {}` → tất cả fields bị coi là "thay đổi" |
| **Khắc phục** | `update_member_info()` đã có logic migrate, nhưng `track_member_join()` chưa có |
| **Trạng thái** | ⚠️ CẦN SỬA — thêm fallback đọc top-level vào `track_member_join()` |

### BUG-2: Fields cũ còn sót ở top-level
| Mục | Chi tiết |
|---|---|
| **Vấn đề** | User `6671951119` có cả `first_name` ở top-level LẪN `current_info` |
| | Còn thừa `left_date` và `status` (format cũ) |
| **Ảnh hưởng** | Dữ liệu thừa chiếm dung lượng, gây nhầm lẫn khi đọc file |
| **Khắc phục** | `update_member_info()` đã dọn 4 fields cũ, nhưng chưa dọn `left_date`, `status`, `joined_date` |
| **Trạng thái** | ⚠️ NÊN SỬA — thêm cleanup cho các fields cũ còn sót |

### BUG-3: `track_member_join()` luôn ghi đè group entry
| Mục | Chi tiết |
|---|---|
| **Vấn đề** | Khi user re-join nhóm cũ, `joined` bị ghi đè thành thời gian mới |
| **Ảnh hưởng** | Mất lịch sử join lần đầu |
| **Giải pháp** | Chỉ cập nhật `status` + reset `left` nếu group entry đã tồn tại, giữ nguyên `joined` |
| **Trạng thái** | ⚠️ NÊN SỬA |

---

## 🔵 Các Lệnh Command - Test Cases

Hệ thống Bot hỗ trợ một loạt các lệnh tương tác cho cả User thường và Admin. Dưới đây là các kịch bản kiểm thử chi tiết để đảm bảo các lệnh hoạt động đúng thiết kế, phân quyền chính xác và xử lý lỗi mượt mà.

### 1. Nhóm Lệnh Cơ Bản (/start, /me, /help, /myid)

#### TC-6.1: Lệnh `/start` trong Private Chat (User thường vs Admin)
| Mục | Chi tiết |
|---|---|
| **Hành động** | 1. User thường gửi `/start` cho bot trong Private Chat.<br>2. Admin gửi `/start` cho bot trong Private Chat. |
| **Kỳ vọng** | ✅ Với User thường: Trả về danh sách lệnh cơ bản (`/help`, `/me`) và dòng chữ của hệ thống.<br>✅ Với Admin: Trả về **ADMIN PANEL** chứa các lệnh nâng cao (`/notification`, `/banlist`, `/resetwarn`, `/checkinfo`). |

#### TC-6.2: Lệnh `/start` trong Group Chat
| Mục | Chi tiết |
|---|---|
| **Hành động** | Gửi `/start` trong nhóm chat. |
| **Kỳ vọng** | ✅ Trả về câu chào ngắn gọn dạng MarkdownV2: `👋 Xin chào [Name]!...` kèm giới thiệu hệ thống tự động của Kimidev.<br>✅ Lệnh `/help` được nhắc đến để người dùng dễ tra cứu. |

#### TC-6.3: Deep Link `/start check_violation` (Xem lịch sử vi phạm từ nút cảnh báo)
| Mục | Chi tiết |
|---|---|
| **Hành động** | 1. Click nút "check vi phạm" từ tin nhắn cảnh báo trong nhóm (dẫn link `t.me/Bot?start=check_violation`).<br>2. Gửi `/start check_violation` trực tiếp trong private chat khi chưa có vi phạm.<br>3. Gửi `/start check_violation` khi đã có lịch sử vi phạm bad words. |
| **Kỳ vọng** | ✅ Chưa vi phạm: Bot reply "✅ Bạn chưa có vi phạm nào!".<br>✅ Đã vi phạm: Bot trả về bảng **LỊCH SỬ VI PHẠM CỦA BẠN** chi tiết từng lần (Thời gian, câu vi phạm, từ cấm) kèm tổng kết. |

#### TC-6.4: Lệnh `/me` (Xem thông tin bản thân)
| Mục | Chi tiết |
|---|---|
| **Hành động** | Gửi `/me` ở bất kỳ chat nào (Private hoặc Group). |
| **Kỳ vọng** | ✅ Trả về card thông tin HTML chi tiết (ID, First/Last Name, Username, Premium, Bot, Language, Permanent Link).<br>✅ Nếu Telethon online: Lấy và hiển thị thêm **DC ID** và **Bio** của user.<br>✅ Áp dụng rate limit 3 giây và giới hạn 3 lần/ngày (`@daily_limit`). |

#### TC-6.5: Lệnh `/help` & Lệnh `/myid`
| Mục | Chi tiết |
|---|---|
| **Hành động** | 1. User/Admin gửi `/help` ở Private/Group.<br>2. Gửi `/myid` ở Private/Group. |
| **Kỳ vọng** | ✅ `/help`: Hiển thị danh sách các lệnh cơ bản dạng MarkdownV2. Nếu là Admin, bổ sung thêm phần *LỆNH ADMIN* (`/notification`, `/banlist`, `/resetwarn`, `/checkinfo`).<br>✅ `/myid`: Trả về User ID của người gọi và Chat ID của phòng chat hiện tại dưới dạng monospace (dễ copy). |

---

### 2. Moderation & Bad Words (/resetwarn)

#### TC-7.1: Bộ lọc Bad Words tự động trong Group Chat
| Mục | Chi tiết |
|---|---|
| **Hành động** | User thường gửi tin nhắn chứa từ tục tĩu (có trong `bad_words.json`) vào Group. |
| **Kỳ vọng** | ✅ Tin nhắn ngay lập tức bị XÓA.<br>✅ Log vi phạm được ghi lại vào `user_violations.json` và log file hằng ngày.<br>✅ Lịch sử vi phạm của user được lưu (tối đa 4 entry gần nhất).<br>⚠️ Không gửi tin nhắn chửi bới hay spam nhóm khi số lần vi phạm chưa chạm ngưỡng mute. |

#### TC-7.2: Chạm ngưỡng cảnh báo & Auto-Mute (SILENT_THRESHOLD = 4)
| Mục | Chi tiết |
|---|---|
| **Hành động** | User thường chửi tục đến lần thứ 4. |
| **Kỳ vọng** | ✅ Tin nhắn bị xóa.<br>✅ Thực hiện mute user 5 phút (`restrict_chat_member` với can_send_messages=False).<br>✅ Bot gửi tin nhắn cảnh báo trong Topic (nếu có thread_id) kèm 2 nút: `check vi phạm` và `Hứa không chửi tục nữa (Gỡ Mute)`.<br>✅ Reset số lần vi phạm (`count`) về 0 (nhưng vẫn giữ history). |

#### TC-7.3: Tương tác nút "Gỡ Mute" (Callback Query Handler)
| Mục | Chi tiết |
|---|---|
| **Hành động** | 1. Người khác (không bị mute) click nút "Hứa không chửi tục nữa".<br>2. Chính người bị mute click nút này. |
| **Kỳ vọng** | ✅ Người khác click: Trả về alert "❌ Nút này không dành cho bạn!".<br>✅ Chính chủ click: <br>&nbsp;&nbsp;&nbsp;&nbsp;- Gỡ mute thành công (trả lại quyền hạn mặc định của group).<br>&nbsp;&nbsp;&nbsp;&nbsp;- Hủy Job tự động xóa cảnh báo (`job.schedule_removal()`).<br>&nbsp;&nbsp;&nbsp;&nbsp;- Reset hoàn toàn vi phạm (`count = 0` và `history = []`).<br>&nbsp;&nbsp;&nbsp;&nbsp;- Sửa tin nhắn cảnh báo thành thông báo nhắc nhở đã hứa. |

#### TC-7.4: Hết hạn Mute tự động (JobQueue)
| Mục | Chi tiết |
|---|---|
| **Hành động** | Đợi hết thời gian mute 5 phút mà user không tự bấm gỡ mute. |
| **Kỳ vọng** | ✅ Job `_auto_delete_warning` kích hoạt.<br>✅ Xóa tin nhắn cảnh báo khỏi nhóm chat.<br>✅ Nếu user chưa phạm lỗi mới (count vẫn = 0): Reset history vi phạm trong database về rỗng `history = []`. |

#### TC-7.5: Lệnh `/resetwarn` (Chỉ dành cho Admin)
| Mục | Chi tiết |
|---|---|
| **Hành động** | 1. Admin gõ `/resetwarn <user_id>` hoặc Reply tin nhắn + `/resetwarn`.<br>2. User thường dùng `/resetwarn`. |
| **Kỳ vọng** | ✅ Admin dùng: Reset vi phạm của user mục tiêu về 0, xóa history, phản hồi "✅ Đã reset vi phạm cho [user_id]".<br>✅ User thường dùng: Skip hoàn toàn (không có phản hồi, không reset). |

---

### 3. Quản lý danh sách cấm (/banlist)

#### TC-8.1: Sử dụng `/banlist` không quyền (User thường)
| Mục | Chi tiết |
|---|---|
| **Hành động** | User thường gửi bất kỳ lệnh `/banlist` nào (add, remove, check, list). |
| **Kỳ vọng** | ❌ Báo lỗi: "🚫 **Không có quyền truy cập** - Lệnh này chỉ dành cho admin." bằng HTML. |

#### TC-8.2: `/banlist` không tham số
| Mục | Chi tiết |
|---|---|
| **Hành động** | Admin gửi `/banlist` trống. |
| **Kỳ vọng** | ✅ Hiển thị menu hướng dẫn sử dụng và giải thích các mức độ vi phạm (scam, fake_bio, spam) bằng HTML. |

#### TC-8.3: `/banlist add <user_id> <severity> [lý do]`
| Mục | Chi tiết |
|---|---|
| **Hành động** | 1. Admin gõ `/banlist add 123456 scam Lý do lừa đảo`.<br>2. Admin gõ `/banlist add 123456 abc` (sai severity).<br>3. Admin gõ `/banlist add abc scam` (sai định dạng ID). |
| **Kỳ vọng** | ✅ Lần 1: Thành công, lưu vào `banlist.json`, hiển thị thông tin và cảnh báo hành động khi user vào nhóm (Ban khỏi nhóm).<br>❌ Lần 2: Báo lỗi severity không hợp lệ (yêu cầu scam, fake_bio, spam).<br>❌ Lần 3: Báo lỗi "User ID không hợp lệ". |

#### TC-8.4: `/banlist check <user_id>` & `/banlist remove <user_id>`
| Mục | Chi tiết |
|---|---|
| **Hành động** | 1. Check ID có trong banlist.<br>2. Check ID không có trong banlist.<br>3. Remove ID có trong banlist.<br>4. Remove ID không có trong banlist. |
| **Kỳ vọng** | ✅ 1: Trả về chi tiết lệnh cấm (Mức độ, lý do, người thêm, ngày thêm, hành động áp dụng).<br>✅ 2: Báo user không nằm trong danh sách cấm.<br>✅ 3: Xóa thành công khỏi database, báo "Đã xóa [ID] khỏi danh sách cấm".<br>✅ 4: Báo user không có trong danh sách cấm. |

#### TC-8.5: `/banlist list`
| Mục | Chi tiết |
|---|---|
| **Hành động** | Admin gõ `/banlist list`. |
| **Kỳ vọng** | ✅ Liệt kê tất cả user đang bị cấm cùng ID, mức độ và lý do.<br>✅ Giới hạn độ dài tin nhắn tối đa 4000 ký tự (tránh lỗi Telegram API giới hạn 4096 ký tự). |

---

### 4. Tra cứu thông tin người dùng (/check)

#### TC-9.1: `/check` xem thông tin bản thân
| Mục | Chi tiết |
|---|---|
| **Hành động** | Gửi `/check` không tham số trong nhóm hoặc private chat. |
| **Kỳ vọng** | ✅ Trả về thẻ thông tin dạng MarkdownV2 hiển thị Name, ID, Username, Profile Link, Status, Premium, Bio.<br>✅ Nếu có ảnh đại diện, gửi kèm dưới dạng caption của ảnh (`reply_photo`). |

#### TC-9.2: `/check <user_id>` & `/check @username`
| Mục | Chi tiết |
|---|---|
| **Hành động** | 1. Check bằng ID số tồn tại/không tồn tại.<br>2. Check bằng @username khi Telethon online/offline.<br>3. Check bằng định dạng không hợp lệ. |
| **Kỳ vọng** | ✅ ID tồn tại: Hiển thị thẻ thông tin của user đó.<br>❌ ID không tồn tại hoặc không chung group: Báo lỗi không tìm thấy user.<br>✅ Username (Telethon online): Tra cứu thành công, hiển thị cả DC, Last Seen, nhóm chung, Bio.<br>❌ Username (Telethon offline): Báo lỗi yêu cầu cấu hình Telethon API.<br>❌ Không hợp lệ: Báo sai cú pháp và hướng dẫn sử dụng. |

#### TC-9.3: Reply tin nhắn + `/check`
| Mục | Chi tiết |
|---|---|
| **Hành động** | 1. Reply tin nhắn của user thường + gõ `/check`.<br>2. Reply tin nhắn của Admin ẩn danh hoặc System Bot (ID 777000, 1087968824, 136817688). |
| **Kỳ vọng** | ✅ Lần 1: Lấy thông tin của người gửi tin nhắn đó và hiển thị thẻ thông tin.<br>❌ Lần 2: Nhận diện đây là System Bot/Admin ẩn danh, báo lỗi đây không phải người dùng thực và hướng dẫn check cụ thể. |

---

### 5. Lệnh Tra Cứu Nâng Cao (/checkinfo)

#### TC-10.1: Phân loại truy vấn thông minh (`_detect_query_type`)
| Mục | Chi tiết |
|---|---|
| **Hành động** | Gửi `/checkinfo` kèm các tham số: `@username`, `https://t.me/username`, `123456789`, `+84987654321`. |
| **Kỳ vọng** | ✅ Nhận diện chính xác và điều hướng sang hàm xử lý tương ứng:<br>&nbsp;&nbsp;&nbsp;&nbsp;- `@username` -> check bằng Username.<br>&nbsp;&nbsp;&nbsp;&nbsp;- Link -> trích xuất username -> check bằng Username.<br>&nbsp;&nbsp;&nbsp;&nbsp;- Số điện thoại `+` -> check bằng Phone.<br>&nbsp;&nbsp;&nbsp;&nbsp;- ID số -> check bằng ID số. |

#### TC-10.2: `/checkinfo` bằng Username/Link (Telethon + Gift Lookup)
| Mục | Chi tiết |
|---|---|
| **Hành động** | Gửi `/checkinfo @target` hoặc link của target. |
| **Kỳ vọng** | ✅ Chạy song song truy vấn info (`lookup_by_username`) và quà tặng (`get_user_gifts`).<br>✅ Tính toán chỉ số tín nhiệm của tài khoản:<br>&nbsp;&nbsp;&nbsp;&nbsp;- `X` (độ đầy đủ profile), `Y` (tổng số sao stars từ quà), `Z` (số lượng limited gifts).<br>✅ Xếp hạng phân cấp tài khoản (Siêu Cấp Vip Pro / Chất Lượng / Phổ Thông).<br>✅ Trả về giao diện HTML có kèm nút "👤 Profile". |

#### TC-10.3: `/checkinfo` bằng Số điện thoại
| Mục | Chi tiết |
|---|---|
| **Hành động** | Gửi `/checkinfo +84987654321`. |
| **Kỳ vọng** | ✅ Tìm kiếm user qua số điện thoại bằng Telethon.<br>✅ Hiển thị đầy đủ: SĐT tra, SĐT Telegram (nếu không ẩn), DC ID, Premium, Permanent Link, Bio, và các cờ (Verified/Scam/Fake). |

#### TC-10.4: `/checkinfo` bằng ID số (Rose Bot + Gift Lookup)
| Mục | Chi tiết |
|---|---|
| **Hành động** | Gửi `/checkinfo 123456789` (hoặc reply tin nhắn + `/checkinfo`). |
| **Kỳ vọng** | ✅ Gửi lệnh ẩn qua Rose Bot trong Group phụ trợ để lấy thông tin cơ bản (`query_rose_bot`).<br>✅ Gọi Telethon lấy danh sách Gifts theo ID song song.<br>✅ Tính điểm tín nhiệm, xếp hạng và xuất kết quả đẹp mắt bằng MarkdownV2. |

---

### 6. Netflix Free (/tv8, /netflix, /nflogin)

#### TC-11.1: Kích hoạt mã TV Netflix (`/tv8 <code>`)
| Mục | Chi tiết |
|---|---|
| **Hành động** | 1. Nhập mã 8 ký tự hợp lệ (`/tv8 1234-5678` hoặc `12345678`).<br>2. Nhập mã sai độ dài hoặc chứa ký tự đặc biệt.<br>3. Chạy khi kho cookie hết. |
| **Kỳ vọng** | ✅ Lần 1: Quét tìm cookie LIVE trong kho. Nếu thấy, thực hiện kích hoạt. Báo thành công, di chuyển cookie đã dùng sang thư mục `cookies_used`. Gửi thông báo chi tiết cho Admin.<br>❌ Lần 2: Báo lỗi sai định dạng mã code.<br>❌ Lần 3: Báo lỗi "Hết cookie!" yêu cầu liên hệ admin. |

#### TC-11.2: Xử lý Cookie LIVE/DIE trong lúc kích hoạt
| Mục | Chi tiết |
|---|---|
| **Hành động** | Chạy kích hoạt `/tv8` khi trong kho có cả cookie LIVE lẫn DIE xen kẽ. |
| **Kỳ vọng** | ✅ Gặp cookie DIE: Tự động di chuyển sang `cookies_used` hoặc xóa, in log và tiếp tục thử cookie tiếp theo.<br>✅ Gặp cookie LIVE: Dừng lại và thực hiện kích hoạt với cookie đó. |

#### TC-11.3: Tạo link đăng nhập Netflix (`/nflogin`)
| Mục | Chi tiết |
|---|---|
| **Hành động** | Gửi `/nflogin` trong private chat. |
| **Kỳ vọng** | ✅ Lấy cookie LIVE, trích xuất `NetflixId`.<br>✅ Gọi API lấy `nftoken` và thời gian hết hạn.<br>✅ Tạo link đăng nhập, hiển thị kèm thời gian hết hạn và nút Inline Button "📚 Đăng Nhập Netflix" để click trực tiếp. |

---

### 7. Các Lệnh Khác (/token, /notification)

#### TC-12.1: Kiểm tra trạng thái Token Telegram (`/token <token>`)
| Mục | Chi tiết |
|---|---|
| **Hành động** | Gửi `/token <bot_token>` với token hoạt động (LIVE) hoặc token hỏng (DIE). |
| **Kỳ vọng** | ✅ Token LIVE: Trả về ID, Name, Username của bot đó. Ghi token vào file `tokens_check_live.txt` và báo cho Admin.<br>❌ Token DIE: Trả về "❌ Token **DIE** hoặc đã hết hạn.". |

#### TC-12.2: Lệnh Broadcast Thông Báo (`/notification`)
| Mục | Chi tiết |
|---|---|
| **Hành động** | 1. Admin soạn tin nhắn (chứa ảnh/text/video) -> Reply tin nhắn đó + gõ `/notification`.<br>2. User thường dùng lệnh.<br>3. Chạy khi danh sách user trống. |
| **Kỳ vọng** | ✅ Lần 1: Copy và forward tin nhắn nguyên bản tới mọi user trong database `known_users.json`. Hiển thị tiến trình gửi. Thống kê kết quả gửi (Thành công, thất bại, đã block).<br>❌ Lần 2: Báo lỗi không có quyền truy cập.<br>❌ Lần 3: Báo lỗi "Chưa có người dùng nào". |

#### TC-12.3: Tự động dọn dẹp database khi Broadcast gặp user block
| Mục | Chi tiết |
|---|---|
| **Hành động** | Gửi tin nhắn cho user trong danh sách nhưng bị lỗi `blocked`, `deactivated` hoặc `chat not found`. |
| **Kỳ vọng** | ✅ Tự động gọi `remove_user(uid)` để xóa ID này khỏi database `known_users.json` để tối ưu hóa lần gửi sau.<br>✅ Cộng vào số lượng "Đã block/xóa" trong báo cáo gửi. |
