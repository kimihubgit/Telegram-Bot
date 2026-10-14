import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from pymongo import MongoClient
from bson import ObjectId

from app import config
from app.utils.helpers import extract_domain, clean_phone_number

# Thiết lập logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Database")

class DatabaseEngine:
    def __init__(self):
        self.is_mongo = False
        self.client = None
        self.db = None
        
        # Thư mục fallback JSON
        self.scammer_dir = Path(config.SCAMMER_DATA_DIR)
        self.websites_json_path = self.scammer_dir / "websites.json"
        
        # Thử kết nối MongoDB
        try:
            logger.info(f"🔌 Đang kiểm tra kết nối MongoDB tại: {config.MONGO_URI}...")
            self.client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=2000)
            self.db = self.client[config.MONGO_DB_NAME]
            # Ping thử
            self.client.admin.command('ping')
            self.is_mongo = True
            logger.info("✅ Đã kết nối MongoDB thành công! Sử dụng MongoDB làm cơ sở dữ liệu chính.")
            self._init_mongo_indexes()
        except Exception as e:
            logger.warning(f"⚠️ Không thể kết nối MongoDB: {e}")
            logger.warning("💡 Tự động kích hoạt cơ chế FALLBACK: Đọc/ghi dữ liệu qua các tệp JSON tại thư mục data/scammer/.")
            self._init_json_fallback()

    def _init_mongo_indexes(self):
        """Khởi tạo index cho các collection trong MongoDB"""
        try:
            # Index cho trang web độc hại
            self.db.scam_websites.create_index("domain", unique=True)
            self.db.scam_websites.create_index("status")
            
            # Index cho kẻ lừa đảo (scammers) để tìm kiếm nhanh
            # Index 1 cấp cho các trường thông tin liên lạc và thanh toán
            self.db.scammers.create_index("scammer_id", unique=True)
            self.db.scammers.create_index("status")
            self.db.scammers.create_index("contact.telegram.username")
            self.db.scammers.create_index("contact.telegram.id")
            self.db.scammers.create_index("contact.facebook.id")
            self.db.scammers.create_index("contact.facebook.link")
            self.db.scammers.create_index("contact.phone.full_number")
            self.db.scammers.create_index("contact.phone.national_number")
            self.db.scammers.create_index("contact.email.address")
            self.db.scammers.create_index("payments.bank.account_number")
            self.db.scammers.create_index("payments.bank.account_holder")
            self.db.scammers.create_index("payments.wallet.phone_number")
            self.db.scammers.create_index("payments.crypto.address")
            logger.info("⚡ Đã khởi tạo xong MongoDB Indexes.")
        except Exception as e:
            logger.error(f"❌ Lỗi khi khởi tạo MongoDB Indexes: {e}")

    def _init_json_fallback(self):
        """Khởi tạo dữ liệu JSON demo nếu chưa có tệp websites.json"""
        if not self.websites_json_path.exists():
            demo_websites = [
                {
                    "domain": "ludao.vn",
                    "category": "scam",
                    "description": "Giả mạo trang web nhận quà cước Viettel để lừa đảo tiền",
                    "threat_level": "high",
                    "status": "approved",
                    "reported_by": "System Fallback",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                },
                {
                    "domain": "nhantienmienphi.com",
                    "category": "phishing",
                    "description": "Trang web dụ dỗ nhập OTP tài khoản ngân hàng",
                    "threat_level": "high",
                    "status": "approved",
                    "reported_by": "System Fallback",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                },
                {
                    "domain": "fake-bank-login.net",
                    "category": "phishing",
                    "description": "Giao diện đăng nhập giống hệt VCB để chiếm đoạt tài khoản",
                    "threat_level": "high",
                    "status": "approved",
                    "reported_by": "System Fallback",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                },
                {
                    "domain": "scam-demo.com",
                    "category": "scam",
                    "description": "Tên miền demo lừa đảo dành cho kiểm thử",
                    "threat_level": "medium",
                    "status": "approved",
                    "reported_by": "System Fallback",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
            ]
            try:
                with open(self.websites_json_path, "w", encoding="utf-8") as f:
                    json.dump(demo_websites, f, indent=4, ensure_ascii=False)
                logger.info(f"📝 Đã tạo file website demo fallback tại: {self.websites_json_path}")
            except Exception as e:
                logger.error(f"❌ Lỗi tạo website fallback: {e}")

    # --- MÁY QUÉT WEBSITES ---
    
    def get_all_scam_websites(self) -> List[Dict[str, Any]]:
        """Lấy tất cả các website lừa đảo đã duyệt"""
        if self.is_mongo:
            results = list(self.db.scam_websites.find({"status": "approved"}))
            # Chuyển ObjectId sang string để trả về JSON
            for r in results:
                r["_id"] = str(r["_id"])
            return results
        else:
            if self.websites_json_path.exists():
                try:
                    with open(self.websites_json_path, "r", encoding="utf-8") as f:
                        websites = json.load(f)
                    return [w for w in websites if w.get("status") == "approved"]
                except Exception as e:
                    logger.error(f"Lỗi đọc file {self.websites_json_path}: {e}")
            return []

    def get_scam_domains(self) -> List[str]:
        """Chỉ lấy danh sách tên miền của website lừa đảo (đáp ứng định dạng của extension)"""
        websites = self.get_all_scam_websites()
        return [w["domain"] for w in websites if "domain" in w]

    def check_website(self, domain_to_check: str) -> Optional[Dict[str, Any]]:
        """Kiểm tra xem tên miền có thuộc danh sách lừa đảo không"""
        cleaned_domain = extract_domain(domain_to_check)
        if not cleaned_domain:
            return None

        if self.is_mongo:
            # Tìm kiếm khớp chính xác hoặc khớp tên miền phụ
            # VD: check "sub.ludao.vn", domain lưu là "ludao.vn"
            # Hoặc ngược lại (chứa trong nhau)
            # Dùng regex hoặc so khớp
            result = self.db.scam_websites.find_one({
                "status": "approved",
                "$or": [
                    {"domain": cleaned_domain},
                    {"domain": {"$regex": f"^{re_escape(cleaned_domain)}$", "$options": "i"}}
                ]
            })
            if not result:
                # Tìm xem có domain nào lưu trong db là hậu tố của cleaned_domain không
                # VD: cleaned_domain = "a.b.ludao.vn", db chứa "ludao.vn"
                # Ta quét tất cả (hoặc dùng regex thông minh)
                all_scams = self.db.scam_websites.find({"status": "approved"})
                for item in all_scams:
                    saved_domain = item["domain"].lower()
                    if cleaned_domain == saved_domain or cleaned_domain.endswith("." + saved_domain):
                        item["_id"] = str(item["_id"])
                        return item
                return None
            result["_id"] = str(result["_id"])
            return result
        else:
            websites = self.get_all_scam_websites()
            for item in websites:
                saved_domain = item["domain"].lower()
                if cleaned_domain == saved_domain or cleaned_domain.endswith("." + saved_domain):
                    return item
            return None

    def add_website(self, website_data: Dict[str, Any]) -> Dict[str, Any]:
        """Thêm một website lừa đảo mới"""
        domain = extract_domain(website_data.get("domain", ""))
        if not domain:
            raise ValueError("Tên miền không hợp lệ")

        website_data["domain"] = domain
        website_data["created_at"] = datetime.utcnow().isoformat() if not self.is_mongo else datetime.utcnow()
        website_data["updated_at"] = website_data["created_at"]
        website_data["status"] = website_data.get("status", "approved")

        if self.is_mongo:
            # Kiểm tra xem đã tồn tại chưa
            existing = self.db.scam_websites.find_one({"domain": domain})
            if existing:
                self.db.scam_websites.update_one(
                    {"domain": domain},
                    {"$set": {
                        "category": website_data.get("category", existing.get("category")),
                        "description": website_data.get("description", existing.get("description")),
                        "threat_level": website_data.get("threat_level", existing.get("threat_level")),
                        "status": website_data.get("status", existing.get("status")),
                        "updated_at": datetime.utcnow()
                    }}
                )
                res = self.db.scam_websites.find_one({"domain": domain})
                res["_id"] = str(res["_id"])
                return res
            else:
                inserted = self.db.scam_websites.insert_one(website_data)
                website_data["_id"] = str(inserted.inserted_id)
                return website_data
        else:
            websites = []
            if self.websites_json_path.exists():
                try:
                    with open(self.websites_json_path, "r", encoding="utf-8") as f:
                        websites = json.load(f)
                except Exception as e:
                    logger.error(f"Lỗi đọc file: {e}")

            # Cập nhật nếu đã có, hoặc thêm mới
            for i, w in enumerate(websites):
                if w["domain"].lower() == domain.lower():
                    websites[i].update(website_data)
                    # Chuyển đổi datetime sang string
                    if isinstance(websites[i]["created_at"], datetime):
                        websites[i]["created_at"] = websites[i]["created_at"].isoformat()
                    websites[i]["updated_at"] = datetime.utcnow().isoformat()
                    break
            else:
                websites.append(website_data)

            with open(self.websites_json_path, "w", encoding="utf-8") as f:
                json.dump(websites, f, indent=4, ensure_ascii=False)
            return website_data

    # --- MÁY QUÉT SCAMMERS ---

    def _load_all_scammers_from_json(self) -> List[Dict[str, Any]]:
        """Quét và tải toàn bộ các tệp JSON scammer từ thư mục data/scammer"""
        scammers = []
        if not self.scammer_dir.exists():
            return []
            
        for file_path in self.scammer_dir.glob("*.json"):
            # Bỏ qua tệp websites.json và user.json
            if file_path.name in ("websites.json", "user.json", "report.json"):
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Đảm bảo có scammer_id
                    if "scammer_id" not in data:
                        data["scammer_id"] = file_path.stem
                    # Hỗ trợ cấu hình status
                    if "status" not in data:
                        data["status"] = "approved"
                    scammers.append(data)
            except Exception as e:
                logger.error(f"Không thể đọc file JSON scammer {file_path.name}: {e}")
        return scammers

    def search_scammers(self, query: str) -> List[Dict[str, Any]]:
        """Tìm kiếm kẻ lừa đảo theo từ khóa"""
        if not query:
            return []
            
        query_clean = query.strip()
        query_lower = query_clean.lower()
        phone_clean = clean_phone_number(query_clean)

        if self.is_mongo:
            # Build MongoDB query
            mongo_query = {
                "status": "approved",
                "$or": [
                    # 1. Telegram
                    {"contact.telegram.username": {"$regex": query_clean, "$options": "i"}},
                    {"contact.telegram.id": query_clean},
                    {"contact.telegram.id": int(query_clean) if query_clean.isdigit() else -1},
                    
                    # 2. Facebook
                    {"contact.facebook.id": query_clean},
                    {"contact.facebook.link": {"$regex": query_clean, "$options": "i"}},
                    {"contact.facebook.name": {"$regex": query_clean, "$options": "i"}},
                    
                    # 3. Phone & Email
                    {"contact.phone.full_number": {"$regex": query_clean, "$options": "i"}},
                    {"contact.phone.national_number": {"$regex": query_clean, "$options": "i"}},
                    {"contact.email.address": {"$regex": query_clean, "$options": "i"}},
                    
                    # 4. Bank Payments
                    {"payments.bank.account_number": {"$regex": query_clean, "$options": "i"}},
                    {"payments.bank.account_holder": {"$regex": query_clean, "$options": "i"}},
                    
                    # 5. Wallets & Crypto
                    {"payments.wallet.phone_number": {"$regex": query_clean, "$options": "i"}},
                    {"payments.wallet.owner_name": {"$regex": query_clean, "$options": "i"}},
                    {"payments.crypto.address": {"$regex": query_clean, "$options": "i"}},
                    {"payments.binance.binance_id": query_clean},
                    
                    # 6. ID lừa đảo hoặc Mô tả
                    {"scammer_id": {"$regex": query_clean, "$options": "i"}},
                    {"incidents.description": {"$regex": query_clean, "$options": "i"}},
                    {"incident.description": {"$regex": query_clean, "$options": "i"}}
                ]
            }
            results = list(self.db.scammers.find(mongo_query))
            for r in results:
                r["_id"] = str(r["_id"])
            return results
        else:
            # Fallback JSON tìm kiếm trong bộ nhớ
            scammers = self._load_all_scammers_from_json()
            matches = []
            
            for s in scammers:
                if s.get("status") != "approved":
                    continue
                    
                match = False
                
                # Check scammer_id
                if query_lower in s.get("scammer_id", "").lower():
                    match = True
                
                # Check Contact Section
                contacts = s.get("contact", {})
                
                # Telegram
                for tg in contacts.get("telegram", []):
                    if tg.get("username") and query_lower in tg["username"].lower():
                        match = True
                    if tg.get("id") and str(tg["id"]) == query_clean:
                        match = True
                        
                # Facebook
                for fb in contacts.get("facebook", []):
                    if fb.get("link") and query_lower in fb["link"].lower():
                        match = True
                    if fb.get("name") and query_lower in fb["name"].lower():
                        match = True
                    if fb.get("id") and str(fb["id"]) == query_clean:
                        match = True

                # Phone
                for p in contacts.get("phone", []):
                    num = p.get("full_number", "")
                    nat = p.get("national_number", "")
                    if phone_clean and (phone_clean in clean_phone_number(num) or phone_clean in clean_phone_number(nat)):
                        match = True
                    if query_lower in num.lower():
                        match = True

                # Email
                for email in contacts.get("email", []):
                    if email.get("address") and query_lower in email["address"].lower():
                        match = True

                # Check Payments Section
                payments = s.get("payments", {})
                
                # Bank
                for bank in payments.get("bank", []):
                    if query_clean in bank.get("account_number", ""):
                        match = True
                    if bank.get("account_holder") and query_lower in bank["account_holder"].lower():
                        match = True

                # Wallet
                for wallet in payments.get("wallet", []):
                    if query_clean in wallet.get("phone_number", ""):
                        match = True
                    if wallet.get("owner_name") and query_lower in wallet["owner_name"].lower():
                        match = True

                # Crypto & Binance
                for crypto in payments.get("crypto", []):
                    if query_clean in crypto.get("address", ""):
                        match = True
                for binance in payments.get("binance", []):
                    if query_clean == str(binance.get("binance_id", "")):
                        match = True

                # Incident Descriptions
                for inc in s.get("incidents", s.get("incident", [])):
                    if inc.get("description") and query_lower in inc["description"].lower():
                        match = True

                if match:
                    matches.append(s)
                    
            return matches

    def get_scammer_by_id(self, scammer_id: str) -> Optional[Dict[str, Any]]:
        """Lấy chi tiết một kẻ lừa đảo theo ID"""
        if self.is_mongo:
            # Có thể tìm theo MongoDB ObjectId hoặc scammer_id dạng SCM-xxxxx
            result = None
            if ObjectId.is_valid(scammer_id):
                result = self.db.scammers.find_one({"_id": ObjectId(scammer_id)})
            if not result:
                result = self.db.scammers.find_one({"scammer_id": scammer_id})
                
            if result:
                result["_id"] = str(result["_id"])
            return result
        else:
            scammers = self._load_all_scammers_from_json()
            for s in scammers:
                if s.get("scammer_id") == scammer_id:
                    return s
            return None

    def add_scammer(self, scammer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Thêm một hồ sơ kẻ lừa đảo mới"""
        # Tạo ID nếu chưa có
        if not scammer_data.get("scammer_id"):
            # Lấy số tiếp theo
            if self.is_mongo:
                count = self.db.scammers.count_documents({})
            else:
                count = len(self._load_all_scammers_from_json())
            scammer_data["scammer_id"] = f"SCM-{str(count + 1).zfill(5)}"

        # Metadata
        current_time_iso = datetime.utcnow().isoformat()
        scammer_data["metadata"] = {
            "created_at": current_time_iso,
            "updated_at": current_time_iso
        }
        scammer_data["status"] = scammer_data.get("status", "approved")

        if self.is_mongo:
            # Lưu mongodb
            # Đảm bảo không trùng scammer_id
            existing = self.db.scammers.find_one({"scammer_id": scammer_data["scammer_id"]})
            if existing:
                # Cập nhật
                scammer_data["metadata"]["created_at"] = existing.get("metadata", {}).get("created_at", current_time_iso)
                self.db.scammers.replace_one({"scammer_id": scammer_data["scammer_id"]}, scammer_data)
                res = self.db.scammers.find_one({"scammer_id": scammer_data["scammer_id"]})
                res["_id"] = str(res["_id"])
                return res
            else:
                inserted = self.db.scammers.insert_one(scammer_data)
                scammer_data["_id"] = str(inserted.inserted_id)
                return scammer_data
        else:
            # Lưu dạng JSON file riêng biệt (VD: SCM-00002.json)
            file_name = f"{scammer_data['scammer_id']}.json"
            target_path = self.scammer_dir / file_name
            
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(scammer_data, f, indent=4, ensure_ascii=False)
                
            logger.info(f"💾 Đã lưu hồ sơ scammer fallback JSON tại: {target_path}")
            return scammer_data

def re_escape(s: str) -> str:
    """Escape các kí tự đặc biệt cho Regex"""
    return "".join(f"[{c}]" if c in ".+*?^$()[]{}|\\" else c for c in s)

# Khởi tạo instance database dùng chung toàn ứng dụng
db_engine = DatabaseEngine()
