import json
import pandas as pd


def extract_clean_text(text_field):
    """Hàm xử lý việc text lúc là chuỗi, lúc là list trong JSON Telegram"""
    if isinstance(text_field, str):
        return text_field
    elif isinstance(text_field, list):
        clean_parts = []
        for part in text_field:
            if isinstance(part, str):
                clean_parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                # Giữ lại text bên trong các object chứa hashtag, bold, link...
                clean_parts.append(part["text"])
        return "".join(clean_parts)
    return ""


# 1. Đọc file JSON export từ Telegram
with open("result.json", "r", encoding="utf-8") as f:
    data = json.load(f)

cleaned_data = []

# 2. Duyệt qua từng tin nhắn
for msg in data.get("messages", []):
    # Chỉ lấy tin nhắn dạng text thông thường (bỏ qua thông báo hệ thống như join/leave group)
    if msg.get("type") == "message":
        raw_text = msg.get("text", "")
        clean_text = extract_clean_text(raw_text).strip()

        # Bỏ qua tin nhắn trống hoặc quá ngắn
        if len(clean_text) > 1:
            cleaned_data.append(
                {
                    "message_id": msg.get("id"),
                    "date": msg.get("date"),
                    "text": clean_text,
                }
            )

# 3. Chuyển thành DataFrame và lưu lại
df = pd.DataFrame(cleaned_data)
df.to_csv("telegram_clean.csv", index=False, encoding="utf-8-sig")
print(f"Đã trích xuất thành công {len(df)} tin nhắn sạch!")