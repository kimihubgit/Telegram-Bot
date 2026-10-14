from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

from app import config
from app.database import db_engine
from app.routers import websites, scammers

# Khởi tạo ứng dụng FastAPI với mô tả chi tiết
app = FastAPI(
    title="KiGuard Anti-Scam API",
    description=(
        "Hệ thống backend truy vấn tên miền độc hại, website lừa đảo, "
        "và hồ sơ các tài khoản scam bẩn (Telegram, Facebook, SĐT, STK Ngân hàng, Ví Crypto...)\n\n"
        "**Tính năng chính:**\n"
        "* Đồng bộ thời gian thực danh sách đen tên miền độc hại cho Chrome Extension KiGuard.\n"
        "* Tra cứu nhanh mức độ an toàn của một URL/Tên miền.\n"
        "* Tìm kiếm thông tin liên lạc, tài khoản thanh toán của kẻ lừa đảo.\n"
        "* Báo cáo website và đối tượng lừa đảo mới.\n"
        "* Cơ chế hybrid: Tự động chạy offline lưu tệp JSON nếu không có MongoDB."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Cấu hình CORS Middleware để cho phép Frontend hoặc Chrome Extension gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Trong thực tế, có thể cấu hình danh sách cụ thể
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các router
app.include_router(websites.router, prefix="/api/scam-websites", tags=["Scam Websites (Tên miền độc hại)"])
app.include_router(scammers.router, prefix="/api/scammers", tags=["Scammers (Đối tượng lừa đảo)"])

@app.get("/", summary="Xem trạng thái hệ thống và thống kê tổng quan")
def root_status() -> Dict[str, Any]:
    """
    Trả về thông tin trạng thái hoạt động của Backend, chế độ kết nối cơ sở dữ liệu, 
    và các số liệu thống kê hiện tại.
    """
    # Lấy thống kê
    scam_websites_count = len(db_engine.get_scam_domains())
    
    if db_engine.is_mongo:
        scammers_count = db_engine.db.scammers.count_documents({"status": "approved"})
        db_mode = "MongoDB (Chính thức)"
    else:
        scammers_count = len(db_engine._load_all_scammers_from_json())
        db_mode = "JSON Files (Offline Fallback)"
        
    return {
        "status": "online",
        "app_name": "KiGuard Backend Services",
        "version": "1.0.0",
        "database_mode": db_mode,
        "statistics": {
            "approved_scam_websites": scam_websites_count,
            "approved_scammers_profiles": scammers_count
        },
        "docs": {
            "swagger_ui": "/docs",
            "redoc": "/redoc"
        }
    }
