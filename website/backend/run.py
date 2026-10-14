import uvicorn
from app import config

if __name__ == "__main__":
    print(f"🚀 Đang khởi động hệ thống backend KiGuard tại http://{config.HOST}:{config.PORT}...")
    print(f"📚 Tài liệu API (Swagger UI): http://{config.HOST}:{config.PORT}/docs")
    print(f"🔄 Chế độ Hot-Reload: {'BẬT' if config.DEBUG else 'TẮT'}")
    
    uvicorn.run(
        "app.main:app", 
        host=config.HOST, 
        port=config.PORT, 
        reload=config.DEBUG
    )
