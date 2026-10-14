import os
from pathlib import Path
from dotenv import load_dotenv

# Tìm thư mục gốc của project (c:\Users\vkhai\OneDrive\Desktop\Telegram Bot)
# Backend đang ở: website/backend/app/config.py -> đi lên 3 cấp
CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent.parent  # website/backend
PROJECT_ROOT = BACKEND_DIR.parent.parent  # Telegram Bot

# Load .env từ thư mục gốc hoặc thư mục backend
env_paths = [
    PROJECT_ROOT / ".env",
    BACKEND_DIR / ".env",
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break
else:
    load_dotenv()  # Fallback load default .env

# Cấu hình MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "telegram")

# Thư mục chứa data JSON fallback
# Nếu không kết nối được Mongo, sẽ đọc/ghi vào thư mục data này
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
if not DEFAULT_DATA_DIR.exists():
    DEFAULT_DATA_DIR = BACKEND_DIR / "data"
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = Path(os.getenv("DATA_DIR", str(DEFAULT_DATA_DIR)))
SCAMMER_DATA_DIR = DATA_DIR / "scammer"
SCAMMER_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Cấu hình API Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
