import os
import hmac
import hashlib
import requests
import time
from pymongo.database import Database


class BinancePayService:
    def __init__(self, db: Database):
        self.db = db
        # Bộ sưu tập (collection) lưu trữ lịch sử giao dịch Binance Pay
        self.collection = db["binance_transactions"]
        
        # Tạo index duy nhất trên mã giao dịch (transaction_id) để chống nạp trùng ở cấp DB
        self.collection.create_index("transaction_id", unique=True)
        
    def _get_mock_transactions(self) -> list[dict]:
        """Trả về dữ liệu mock mẫu để kiểm thử nếu chưa set API Key"""
        return [
            {
                "transaction_id": "BNC98765432101",
                "amount": 15.5,
                "currency": "USDT",
                "description": "KGBK 6671951119 DONATE",
                "payer_id": "87654321",
                "status": "PAID",
                "date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "gateway": "Binance"
            }
        ]

    def fetch_history(self) -> list[dict]:
        """
        Truy vấn danh sách lịch sử giao dịch Binance Pay chính thức.
        Sử dụng Binance Personal Spot API endpoint: GET /sapi/v1/pay/transactions
        Được ký bằng chữ ký bảo mật HMAC-SHA256 chuẩn Binance.
        """
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_secret = os.getenv("BINANCE_API_SECRET", "")
        
        if not api_key or not api_secret:
            print("   ⚠️ BINANCE_API_KEY hoặc BINANCE_API_SECRET chưa được cấu hình ở file .env!")
            print("   💡 Đang sử dụng dữ liệu giả lập (Mock Data) để kiểm thử...")
            return self._get_mock_transactions()
            
        url = "https://api.binance.com/sapi/v1/pay/transactions"
        timestamp = int(time.time() * 1000)
        
        # 1. Tạo query string chuẩn và ký số HMAC-SHA256 bằng Secret Key
        query_params = f"timestamp={timestamp}&recvWindow=5000"
        signature = hmac.new(
            api_secret.encode("utf-8"),
            query_params.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        full_url = f"{url}?{query_params}&signature={signature}"
        headers = {
            "X-MBX-APIKEY": api_key
        }
        
        try:
            response = requests.get(full_url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"   ❌ Lỗi truy vấn API Binance (HTTP {response.status_code}): {response.text}")
                return []
                
            res_data = response.json()
            if res_data.get("code") != "000000":
                print(f"   ❌ API Binance báo lỗi: {res_data.get('message')}")
                return []
                
            raw_txs = res_data.get("data", [])
            transactions = []
            
            for tx in raw_txs:
                # Chỉ lọc các giao dịch NHẬN tiền (RECEIVE) nạp vào ví
                if tx.get("fundsType") != "RECEIVE":
                    continue
                    
                # Chuyển đổi timestamp ms sang ngày giờ dễ đọc
                tx_time_ms = tx.get("transactionTime", 0)
                formatted_date = time.strftime(
                    "%Y-%m-%d %H:%M:%S", 
                    time.localtime(tx_time_ms / 1000.0)
                )
                
                transactions.append({
                    "transaction_id": str(tx.get("transactionId")),
                    "amount": float(tx.get("amount", 0)),
                    "currency": tx.get("currency", "USDT"),
                    "description": tx.get("note", ""),  # Note chính là lời nhắn quyên góp của user!
                    "payer_id": str(tx.get("senderPayId", "")),
                    "status": "PAID",
                    "date": formatted_date,
                    "gateway": "Binance"
                })
                
            return transactions
            
        except Exception as e:
            print(f"   ❌ Lỗi kết nối API Binance: {e}")
            return []

    def process_and_save(self) -> int:
        """
        Gọi fetch_history để lấy danh sách giao dịch Binance, đối chiếu chống trùng lặp,
        và lưu trữ các giao dịch mới hoàn toàn vào MongoDB.
        
        Returns:
            Số lượng giao dịch Binance mới được thêm vào DB thành công
        """
        # 1. Lấy lịch sử giao dịch
        transactions = self.fetch_history()
        if not transactions:
            print("   ℹ️ Không có giao dịch nào được trả về từ Binance API.")
            return 0
            
        new_transactions_inserted = 0
        
        # 2. Xử lý từng giao dịch
        for tx in transactions:
            tx_id = tx.get("transaction_id")
            if not tx_id:
                continue
                
            # Chỉ xử lý các giao dịch ở trạng thái hoàn tất thành công (PAID / SUCCESS)
            status = tx.get("status", "").upper()
            if status not in ("PAID", "SUCCESS"):
                continue
                
            # Kiểm tra xem giao dịch này đã tồn tại trong MongoDB chưa
            exists = self.collection.find_one({"transaction_id": tx_id})
            if not exists:
                # Đây là giao dịch mới hoàn toàn -> tiến hành lưu vào MongoDB
                tx["created_at"] = time.time()  # Thời điểm lưu vào DB
                
                try:
                    self.collection.insert_one(tx)
                    new_transactions_inserted += 1
                    print(f"   ➕ Đã phát hiện giao dịch Binance MỚI: {tx_id} | +{tx['amount']} {tx['currency']} | Lời nhắn: '{tx['description']}'")
                except Exception as e:
                    print(f"   ⚠️ Lỗi ghi giao dịch Binance {tx_id} vào MongoDB: {e}")
                    
        return new_transactions_inserted
