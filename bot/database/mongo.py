import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
from pymongo import MongoClient

# Tải cấu hình từ .env
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "telegram")

client = None
db = None

try:
    print(f"🔌 Đang kết nối tới MongoDB: {MONGO_URI}...")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    client.admin.command('ping')
    print("✅ Kết nối MongoDB thành công từ bot module!")
except Exception as e:
    print(f"❌ Không thể kết nối MongoDB từ bot: {e}")
    print("💡 Vui lòng đảm bảo MongoDB service đang chạy và cấu hình MONGO_URI chính xác.")
    db = None

