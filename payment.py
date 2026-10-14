"""
KiGuard Autobank Payment Daemon
Khởi chạy tiến trình polling liên tục để quét các tài khoản thanh toán
và lưu lịch sử giao dịch vào cơ sở dữ liệu MongoDB.
"""

import os
import time
from pymongo import MongoClient
from dotenv import load_dotenv

# Tải cấu hình từ .env
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "autobank")

# Import các dịch vụ Bank
from autobank.bank.mbbank import MBBankService
from autobank.binance.binance import BinancePayService


def main():
    print("==================================================")
    print("   💰 KIGUARD AUTOBANK POLLING DAEMON STARTED   ")
    print("==================================================")
    
    # 1. Kết nối MongoDB
    try:
        print(f"🔌 Đang kết nối tới MongoDB: {MONGO_URI}...")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        # Ping thử xem có kết nối được không
        client.admin.command('ping')
        print("✅ Kết nối MongoDB thành công!")
    except Exception as e:
        print(f"❌ Không thể kết nối MongoDB: {e}")
        print("💡 Vui lòng kiểm tra lại MongoDB Service trong Docker-compose hoặc cấu hình URI!")
        return

    # 2. Khởi tạo các dịch vụ thanh toán
    mbbank_service = MBBankService(db)
    binance_service = BinancePayService(db)
    
    # 3. Chạy vòng lặp polling
    poll_interval = int(os.getenv("AUTOBANK_POLL_INTERVAL", "30"))
    print(f"⚙️ Bắt đầu quét lịch sử giao dịch mỗi {poll_interval} giây...")
    
    try:
        while True:
            print(f"\n🔄 [{time.strftime('%Y-%m-%d %H:%M:%S')}] Đang quét lịch sử giao dịch...")
            
            # --- QUÉT MBBANK ---
            try:
                new_mb = mbbank_service.process_and_save()
                if new_mb > 0:
                    print(f"   🎉 Đã phát hiện và lưu thành công {new_mb} giao dịch MBBank mới!")
            except Exception as e:
                print(f"   ❌ Lỗi khi xử lý quét MBBank: {e}")
                
            # --- QUÉT BINANCE PAY ---
            try:
                new_binance = binance_service.process_and_save()
                if new_binance > 0:
                    print(f"   🎉 Đã phát hiện và lưu thành công {new_binance} giao dịch Binance mới!")
            except Exception as e:
                print(f"   ❌ Lỗi khi xử lý quét Binance Pay: {e}")
                
            # Đợi lượt quét tiếp theo
            time.sleep(poll_interval)
            
    except KeyboardInterrupt:
        print("\n🛑 Tiến trình Polling đã dừng bởi người dùng (Ctrl+C). Tạm biệt!")
    finally:
        client.close()


if __name__ == "__main__":
    main()
