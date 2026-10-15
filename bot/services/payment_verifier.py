"""
KiGuard Automated Payment & Donation Verifier
Chịu trách nhiệm tự động xác nhận thanh toán/quyên góp:
1. Xác thực giao dịch USDT (TRC-20) tự động qua API Tronscan (Thời gian thực).
2. Nhận Webhook từ các cổng thanh toán ngân hàng VN (Casso.vn, Sepay.vn...) qua cổng HTTP Server chạy ngầm.
3. Phòng chống nạp kép (Double Spend / Replay Attack) bằng dữ liệu claimed_payments.json.
"""

import os
import re
import json
import asyncio
import threading
import requests
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

# Đường dẫn file lưu trữ để tránh xác nhận trùng lặp
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CLAIMED_FILE = DATA_DIR / "claimed_payments.json"

# Lock ghi file phòng tránh race conditions
_db_lock = threading.Lock()


from bot.database.mongo import db


def _load_claimed() -> dict:
    """Tải danh sách các mã giao dịch đã được xác nhận thành công"""
    if db is not None:
        try:
            doc = db.claimed_payments.find_one({"_id": "claimed_payments"})
            if doc:
                return {
                    "trc20_txids": doc.get("trc20_txids", []),
                    "bank_tids": doc.get("bank_tids", [])
                }
        except Exception as e:
            print(f"⚠️ Lỗi đọc claimed_payments từ MongoDB: {e}")

    # Fallback an toàn khi MongoDB không chạy
    with _db_lock:
        if CLAIMED_FILE.exists():
            try:
                with open(CLAIMED_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Lỗi đọc fallback claimed_payments.json: {e}")
    return {"trc20_txids": [], "bank_tids": []}


def _save_claimed(data: dict):
    """Lưu danh sách giao dịch đã xác nhận để chống nạp kép"""
    if db is not None:
        try:
            db.claimed_payments.replace_one(
                {"_id": "claimed_payments"},
                {
                    "_id": "claimed_payments",
                    "trc20_txids": data.get("trc20_txids", []),
                    "bank_tids": data.get("bank_tids", [])
                },
                upsert=True
            )
            return
        except Exception as e:
            print(f"⚠️ Lỗi ghi claimed_payments vào MongoDB: {e}")

    # Fallback an toàn ghi vào file JSON
    with _db_lock:
        try:
            CLAIMED_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp_file = CLAIMED_FILE.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            temp_file.replace(CLAIMED_FILE)
        except Exception as e:
            print(f"⚠️ Lỗi ghi fallback claimed_payments.json: {e}")


# ==============================================================================
#  1. XÁC MINH GIAO DỊCH USDT (TRC-20) QUA BLOCKCHAIN TRON
# ==============================================================================

async def verify_trc20_usdt(txid: str, target_address: str) -> dict:
    """
    Xác minh mã giao dịch (TxID) USDT TRC-20 thông qua API công khai của Tronscan.
    Returns: {"success": bool, "amount": float, "error": str}
    """
    txid = txid.strip()
    if not re.match(r"^[a-fA-F0-9]{64}$", txid):
        return {"success": False, "amount": 0, "error": "Mã giao dịch (TxID) không đúng định dạng (Phải có 64 ký tự Hex)."}

    # Kiểm tra chống nạp kép (Replay Attack)
    claimed_data = _load_claimed()
    if txid in claimed_data.get("trc20_txids", []):
        return {"success": False, "amount": 0, "error": "Mã giao dịch này đã được xác nhận trước đó. Không thể nạp kép!"}

    # Gọi Tronscan API bằng requests (được bọc trong asyncio.to_thread để tránh nghẽn bot)
    url = f"https://apilist.tronscanapi.com/api/transaction-info?hash={txid}"
    try:
        response = await asyncio.to_thread(requests.get, url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if response.status_code != 200:
            return {"success": False, "amount": 0, "error": f"Không thể kết nối API Tronscan (HTTP {response.status_code})."}
        
        data = response.json()
    except Exception as e:
        return {"success": False, "amount": 0, "error": f"Lỗi kết nối Blockchain: {e}"}

    if not data or "hash" not in data:
        return {"success": False, "amount": 0, "error": "Không tìm thấy giao dịch này trên Blockchain Tron. Vui lòng đợi 1-2 phút sau khi chuyển khoản."}

    # 1. Kiểm tra trạng thái giao dịch
    if data.get("contractRet") != "SUCCESS":
        return {"success": False, "amount": 0, "error": "Giao dịch này bị thất bại hoặc bị đảo ngược trên Blockchain."}

    if not data.get("confirmed"):
        return {"success": False, "amount": 0, "error": "Giao dịch chưa được các Node xác nhận (Unconfirmed). Vui lòng đợi vài giây."}

    # 2. Kiểm tra địa chỉ hợp đồng (USDT TRC20 Contract)
    contract_addr = data.get("contract_address", "")
    if contract_addr != "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t":
        return {"success": False, "amount": 0, "error": "Giao dịch này không phải gửi đồng USDT TRC-20."}

    # 3. Kiểm tra phương thức gọi (phải là transfer)
    trigger = data.get("trigger_info", {})
    method = trigger.get("method", "")
    if "transfer" not in method.lower():
        return {"success": False, "amount": 0, "error": "Hành động giao dịch không phải chuyển tiền (Transfer)."}

    # 4. Kiểm tra ví nhận tiền
    params = trigger.get("parameter", {})
    receiver = params.get("_to", "")
    if receiver.lower() != target_address.lower():
        return {"success": False, "amount": 0, "error": f"Ví nhận không khớp với ví của Bot (Người nhận trên Blockchain: {receiver})."}

    # 5. Lấy số tiền (USDT có 6 chữ số thập phân)
    raw_val = params.get("_value", "0")
    try:
        amount = float(raw_val) / 1_000_000.0
    except Exception:
        return {"success": False, "amount": 0, "error": "Lỗi định dạng giá trị số lượng USDT."}

    # Lưu lại để tránh nạp kép
    claimed_data["trc20_txids"].append(txid)
    _save_claimed(claimed_data)

    return {"success": True, "amount": amount, "error": ""}


# ==============================================================================
#  2. WEBHOOK RECEIVER SERVER CHO BANK VIỆT NAM (CASSO & SEPAY)
# ==============================================================================

class PaymentWebhookHandler(BaseHTTPRequestHandler):
    """Bộ xử lý HTTP nhận Webhook thanh toán ngân hàng"""
    
    def log_message(self, format, *args):
        # Tắt log in ra màn hình để tránh làm bẩn Console của bot
        pass

    def do_POST(self):
        # Trả về 200 OK ngay lập tức cho đối tác (Casso/Sepay) để tránh họ gửi lại
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "success"}')

        # Đọc dữ liệu JSON
        try:
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode("utf-8"))
        except Exception as e:
            print(f"⚠️ Lỗi đọc webhook payload: {e}")
            return

        # Gọi luồng xử lý giao dịch ngầm
        asyncio.run_coroutine_threadsafe(
            self.process_webhook_payload(payload),
            self.server.bot_loop
        )

    async def process_webhook_payload(self, payload: dict):
        """Xử lý phân tích giao dịch Ngân Hàng"""
        transactions = []
        
        # 1. Cấu trúc Casso.vn (chứa danh sách giao dịch trong "data")
        if "data" in payload and isinstance(payload["data"], list):
            for tx in payload["data"]:
                transactions.append({
                    "tid": str(tx.get("id") or tx.get("tid", "")),
                    "amount": int(tx.get("amount", 0)),
                    "description": tx.get("description", ""),
                    "gateway": tx.get("bank_sub_acc_id", "Bank")
                })
        # 2. Cấu trúc Sepay.vn (gửi trực tiếp 1 giao dịch ở tầng top-level)
        elif "transferAmount" in payload or "content" in payload:
            transactions.append({
                "tid": str(payload.get("id") or payload.get("referenceCode", "")),
                "amount": int(payload.get("transferAmount", 0)),
                "description": payload.get("content", ""),
                "gateway": payload.get("gateway", "Bank")
            })

        for tx in transactions:
            tid = tx["tid"]
            amount = tx["amount"]
            desc = tx["description"]
            
            if not tid or amount <= 0:
                continue

            # Kiểm tra chống nạp kép
            claimed_data = _load_claimed()
            if tid in claimed_data.get("bank_tids", []):
                continue

            # Quét UserID từ nội dung chuyển khoản bằng Regex
            # Người dùng gõ: KGBK <UserID> (ví dụ: KGBK 6671951119)
            match = re.search(r"KGBK\s*(\d+)", desc, re.IGNORECASE)
            if not match:
                # Fallback: quét thử xem có dãy số 8-11 chữ số nào khớp với người dùng không
                match = re.search(r"\b(\d{8,11})\b", desc)

            if match:
                user_id = int(match.group(1))
                
                # Ghi nhận giao dịch đã xử lý thành công
                claimed_data["bank_tids"].append(tid)
                _save_claimed(claimed_data)

                # Gửi thông báo chúc mừng trực tiếp đến người dùng và Admin
                await self.notify_success(user_id, amount, desc, tid)
            else:
                # Giao dịch không kèm UserID -> chỉ thông báo cho Admin biết có tiền vào nhưng không tự động xác định được
                await self.notify_admin_unmatched(amount, desc, tid)

    async def notify_success(self, user_id: int, amount: int, desc: str, tid: str):
        """Gửi thông báo thành công cho người quyên góp và Admin"""
        bot = self.server.bot_instance
        
        # 1. Gửi cho Người quyên góp
        try:
            user_msg = (
                "🎉 <b>XÁC NHẬN QUYÊN GÓP THÀNH CÔNG!</b> 💝\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Hệ thống đã tự động nhận diện khoản ủng hộ của bạn qua Ngân Hàng:\n\n"
                f"• <b>Số tiền:</b> <code>{amount:,} VNĐ</code>\n"
                f"• <b>Nội dung:</b> <code>{desc}</code>\n"
                f"• <b>Mã giao dịch (TID):</b> <code>{tid}</code>\n\n"
                "🙏 <i>Cảm ơn tấm lòng vàng của bạn rất nhiều! Sự hỗ trợ này sẽ được sử dụng trực tiếp "
                "để thanh toán chi phí duy trì máy chủ giúp KiGuard Bot luôn chạy mượt mà và miễn phí.</i>"
            )
            await bot.send_message(chat_id=user_id, text=user_msg, parse_mode="HTML")
            print(f"✅ Auto-verified Donation: {amount:,}đ from User {user_id} (TID: {tid})")
        except Exception as e:
            print(f"⚠️ Lỗi gửi thông báo thành công cho User {user_id}: {e}")

        # 2. Gửi thông báo cho Admin biết
        from bot.config import Config
        admin_ids = Config.get_notification_admin_ids()
        
        admin_msg = (
            "💰 <b>PHÁT HIỆN QUYÊN GÓP MỚI (TỰ ĐỘNG XÁC NHẬN)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Người gửi:</b> <a href='tg://user?id={user_id}'>UserID {user_id}</a>\n"
            f"💵 <b>Số tiền:</b> <code>{amount:,} VNĐ</code>\n"
            f"📝 <b>Nội dung:</b> <code>{desc}</code>\n"
            f"🔑 <b>Mã GD:</b> <code>{tid}</code>\n"
            "🟢 <i>Trạng thái: Đã gửi lời cảm ơn tự động thành công!</i>"
        )
        
        for aid in admin_ids:
            try:
                await bot.send_message(chat_id=aid, text=admin_msg, parse_mode="HTML")
            except Exception:
                pass

    async def notify_admin_unmatched(self, amount: int, desc: str, tid: str):
        """Thông báo cho Admin nếu nhận được tiền nhưng nội dung không có User ID"""
        bot = self.server.bot_instance
        from bot.config import Config
        admin_ids = Config.get_notification_admin_ids()
        
        admin_msg = (
            "⚠️ <b>CÓ TIỀN VÀO NHƯNG KHÔNG TỰ ĐỘNG NHẬN DIỆN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 <b>Số tiền:</b> <code>{amount:,} VNĐ</code>\n"
            f"📝 <b>Nội dung:</b> <code>{desc}</code>\n"
            f"🔑 <b>Mã GD:</b> <code>{tid}</code>\n\n"
            "💡 <i>Nội dung chuyển khoản không chứa UserID hoặc sai cú pháp (KGBK <UserID>). "
            "Admin vui lòng kiểm tra thủ công để cảm ơn người dùng.</i>"
        )
        for aid in admin_ids:
            try:
                await bot.send_message(chat_id=aid, text=admin_msg, parse_mode="HTML")
            except Exception:
                pass


def start_webhook_server(bot, loop):
    """
    Khởi chạy Webhook Server ngân hàng chạy ngầm trên luồng riêng biệt.
    Không gây ảnh hưởng đến hiệu năng và luồng chính của bot.
    """
    port = int(os.getenv("DONATE_PORT", "8080"))
    
    def run_server():
        try:
            server = HTTPServer(("0.0.0.0", port), PaymentWebhookHandler)
            server.bot_instance = bot
            server.bot_loop = loop
            
            print(f"🚀 Webhook Payment Server đang chạy ngầm trên Port: {port}...")
            server.serve_forever()
        except Exception as e:
            print(f"❌ Không thể chạy Webhook Payment Server trên port {port}: {e}")
            print("💡 Có thể port đã bị chiếm dụng hoặc bạn cần quyền Admin (Windows) để mở port.")

    # Chạy ngầm hoàn toàn
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
