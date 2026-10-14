"""
KiGuard Autobank - MBBank Integration
Mô-đun chịu trách nhiệm truy vấn lịch sử giao dịch của Ngân hàng MBBank,
phân tích cú pháp và lưu trữ giao dịch mới vào MongoDB.
"""

import time
from pymongo.database import Database


class MBBankService:
    def __init__(self, db: Database):
        self.db = db
        # Bộ sưu tập (collection) lưu trữ lịch sử giao dịch ngân hàng
        self.collection = db["bank_transactions"]
        
        # Tạo index duy nhất trên mã giao dịch (transaction_id) để bảo vệ chống trùng lặp ở mức DB
        self.collection.create_index("transaction_id", unique=True)
        
    def fetch_history(self) -> list[dict]:
        """
        [NƠI BẠN DÁN CODE GET LỊCH SỬ GIAO DỊCH MBBANK CỦA BẠN]
        
        Phương thức này sẽ truy vấn API của MBBank (hoặc cào dữ liệu) để lấy danh sách giao dịch mới nhất.
        
        Yêu cầu kết quả trả về:
            Trả về một danh sách các dict chứa các thông tin tối thiểu sau:
            [
                {
                    "transaction_id": "FT26xxxxxxxx", # Mã giao dịch duy nhất của MBBank
                    "amount": 50000.0,               # Số tiền chuyển khoản (float hoặc int)
                    "description": "KGBK 6671951119", # Lời nhắn/Nội dung chuyển khoản
                    "date": "2026-05-25 18:00:00",    # Thời gian giao dịch (chuỗi hoặc datetime)
                    "gateway": "MBBank"               # Cổng ngân hàng
                },
                ...
            ]
        """
        # ======================================================================
        # TODO: Dán mã lấy lịch sử giao dịch MBBank của bạn tại đây.
        # Dưới đây là dữ liệu giả lập mẫu để kiểm thử quy trình và MongoDB:
        # ======================================================================
        print("   🔍 Đang lấy dữ liệu giao dịch từ API MBBank...")
        
        # Mẫu giao dịch giả lập (Bạn hãy thay thế phần này bằng code gọi API thật của bạn)
        mock_transactions = [
            {
                "transaction_id": "MBFT000001",
                "amount": 100000.0,
                "description": "KGBK 6671951119 CK QUYEN GOP",
                "date": "2026-05-25 18:00:00",
                "gateway": "MBBank"
            },
            {
                "transaction_id": "MBFT000002",
                "amount": 50000.0,
                "description": "KGBK 999999999 CK DONATE",
                "date": "2026-05-25 18:05:00",
                "gateway": "MBBank"
            }
        ]
        
        # Hãy return danh sách kết quả thật từ API của bạn ở đây:
        return mock_transactions

    def process_and_save(self) -> int:
        """
        Gọi fetch_history để lấy danh sách giao dịch, đối chiếu chống trùng lặp,
        và lưu trữ các giao dịch mới hoàn toàn vào MongoDB.
        
        Returns:
            Số lượng giao dịch mới được thêm vào DB thành công
        """
        # 1. Lấy lịch sử giao dịch
        transactions = self.fetch_history()
        if not transactions:
            print("   ℹ️ Không có giao dịch nào được trả về từ API.")
            return 0
            
        new_transactions_inserted = 0
        
        # 2. Xử lý từng giao dịch
        for tx in transactions:
            tx_id = tx.get("transaction_id")
            if not tx_id:
                continue
                
            # Kiểm tra xem giao dịch này đã tồn tại trong MongoDB chưa
            exists = self.collection.find_one({"transaction_id": tx_id})
            if not exists:
                # Đây là giao dịch mới hoàn toàn -> tiến hành lưu vào MongoDB
                tx["created_at"] = time.time()  # Thời điểm lưu vào DB
                
                try:
                    self.collection.insert_one(tx)
                    new_transactions_inserted += 1
                    print(f"   ➕ Đã phát hiện giao dịch MỚI: {tx_id} | +{tx['amount']:,}đ | Lời nhắn: '{tx['description']}'")
                except Exception as e:
                    print(f"   ⚠️ Lỗi ghi giao dịch {tx_id} vào MongoDB: {e}")
                    
        return new_transactions_inserted
