# 📂 Cấu Trúc Thư Mục — Telegram Bot

> Cập nhật lần cuối: 19/05/2026

```
Telegram Bot/
├── main.py                              ← Entry point khởi động bot
├── .env                                 ← Cấu hình môi trường (secrets)
├── .env.example                         ← Mẫu cấu hình
├── .gitignore                           ← Git ignore rules
├── requirements.txt                     ← Python dependencies
│
├── bot/                                 ← Source code chính
│   ├── config.py                        ← Load cấu hình từ .env
│   ├── connection.py                    ← Kết nối Telethon MTProto (start, stop, get_client)
│   │
│   ├── commands/                        ← Các lệnh bot (auto-load bởi loader.py)
│   │   ├── start.py                     ← /start, /help, /me, /myid + Admin Panel
│   │   ├── check.py                     ← /check (thông tin user chi tiết qua Telethon)
│   │   ├── checkinfo.py                 ← /checkinfo (OSINT sâu qua Rose Bot + Star Gift)
│   │   ├── bin.py                       ← /bin (tra cứu BIN thẻ ngân hàng)
│   │   ├── token.py                     ← /token (check bot token live/die)
│   │   ├── netflix.py                   ← /tv, /netflix (Netflix TV code + cookie login)
│   │   ├── scribd.py                    ← /scribd (download tài liệu Scribd)
│   │   ├── banlist.py                   ← /banlist add/remove/check/list (admin only)
│   │   ├── badwords.py                  ← Auto-filter từ tục + mute + cảnh báo
│   │   ├── ban_guard.py                 ← Ban Guard Ultimate: chặn user bị ban + quét forward + auto-update info
│   │   ├── group_monitor.py             ← Giám sát join/leave nhóm + auto-ban
│   │   ├── notification.py              ← /notification (broadcast cho tất cả user)
│   │   └── tracker.py                   ← Theo dõi user tương tác private chat
│   │
│   ├── handlers/
│   │   └── loader.py                    ← Auto-load tất cả command modules + gán group priority
│   │
│   ├── services/                        ← Logic nghiệp vụ (business logic)
│   │   ├── banlist_service.py           ← CRUD danh sách cấm (banlist.json)
│   │   ├── group_member_tracker.py      ← Lưu lịch sử thành viên nhóm (members.json) — v2 nested format
│   │   ├── user_tracker.py              ← Theo dõi user đã tương tác với bot (known_users.json)
│   │   ├── user_service.py              ← Xử lý thông tin user (Bot API + Telethon)
│   │   ├── telethon_user.py             ← Resolve user + lấy thông tin sâu qua MTProto
│   │   │
│   │   ├── checkinfo/                   ← Service cho /checkinfo (OSINT)
│   │   │   ├── __init__.py
│   │   │   ├── gifts.py                 ← Lấy Star Gift qua Telethon
│   │   │   ├── rose_query.py            ← Query Rose Bot qua Telethon
│   │   │   └── telethon_lookup.py       ← Tra cứu thông tin user chi tiết
│   │   │
│   │   └── netflix/                     ← Service cho Netflix commands
│   │       ├── __init__.py
│   │       ├── tvcode.py                ← Nhập TV code bằng cookie
│   │       └── nflogin.py               ← Đăng nhập Netflix + kiểm tra tài khoản
│   │
│   ├── sessions/                        ← Telethon session files (.session)
│   │
│   └── utils/                           ← Tiện ích dùng chung
│       ├── format.py                    ← Escape MarkdownV2, tạo link
│       ├── logger.py                    ← Ghi log command/action theo ngày
│       └── rate_limiter.py              ← Rate limit + daily limit decorator
│
├── data/                                ← Dữ liệu runtime (JSON, CSV)
│   ├── bad_words.json                   ← Danh sách từ cấm
│   ├── banlist.json                     ← Danh sách user/channel/group bị ban
│   ├── bin-list-data.csv                ← Database BIN thẻ ngân hàng (~27MB)
│   ├── captcha.json                     ← Cấu hình captcha
│   ├── known_users.json                 ← User đã tương tác với bot (private chat)
│   ├── members.json                     ← Lịch sử thành viên nhóm (nested format v2)
│   ├── questions.json                   ← Câu hỏi captcha
│   ├── s.json                           ← File mẫu cấu trúc dữ liệu member
│   ├── tokens_check_live.txt            ← Danh sách bot token cần check
│   ├── user_violations.json             ← Số lần vi phạm từ tục theo user
│   │
│   ├── cookies/                         ← Kho cookie Netflix (chưa dùng)
│   ├── cookies_used/                    ← Cookie Netflix đã sử dụng
│   └── fake/                            ← Fake data theo quốc gia
│       ├── JP/
│       ├── US/
│       └── VN/
│
├── docs/                                ← Tài liệu dự án
│   ├── readme.md                        ← README chính (tính năng, cài đặt, cấu hình)
│   ├── TreeFolder.md                    ← Cấu trúc thư mục (file này)
│   └── TestCase.md                      ← Test cases cho Ban Guard & Member Tracker
│
├── ai/                                  ← AI/ML — Phân loại dữ liệu Telegram
│   ├── suli.py                          ← Script xử lý dữ liệu
│   ├── apply_manual_labels.py           ← Script gán nhãn thủ công
│   ├── apply_manual_labels_chunk1-9.py  ← Các chunk gán nhãn (1→9)
│   ├── telegram_clean.csv               ← Dataset Telegram đã làm sạch
│   ├── telegram_clean2.csv              ← Dataset bổ sung
│   ├── telegram_labeled_sample.csv      ← Mẫu đã gán nhãn
│   ├── result.json                      ← Kết quả phân loại (~35MB)
│   └── result2.json                     ← Kết quả bổ sung
│
├── docker/                              ← Docker config (trống — chưa triển khai)
│
└── log/                                 ← Log hoạt động theo ngày
    ├── 2026-05-16.log
    ├── 2026-05-17.log
    ├── 2026-05-18.log
    └── 2026-05-19.log
```