"""
Bộ công cụ các phiên bản làm sạch dữ liệu văn bản (Data Cleaning Pipelines)
Phục vụ thử nghiệm và huấn luyện mô hình AI phát hiện tin nhắn bán hàng / rao vặt Telegram.

Bao gồm 4 phiên bản làm sạch từ nhẹ đến chuyên sâu:
- V1: Light Clean (Nhẹ nhất, giữ nguyên emoji, chữ hoa, câu cú - Thích hợp Transformer/PhoBERT hiện đại)
- V2: Standard Clean (Chuẩn hóa NFKC, gỡ emoji, chuẩn tiền tệ, hạ thường, lọc URL - Phổ thông cho mọi model)
- V3: Deep Clean (Siêu sạch, khử @username, ID số telegram, cảnh báo scam boilerplate, dấu câu rác)
- V4: Sales Specialized (Tối ưu hóa riêng biệt cho tin bán hàng: chuẩn hóa viết tắt bh, ib, sll, slot, đơn vị giá 200k, 1th, 1m)
"""

import re
import unicodedata
from typing import Dict, Callable

# Regex biểu tượng cảm xúc (Emoji & Special Unicode Glyphs)
EMOJI_REGEX = re.compile(
    r'['
    r'\U0001F1E0-\U0001F1FF\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF'
    r'\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF'
    r'\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF'
    r'\U000025A0-\U000025FF\U00002B00-\U00002BFF\U00002300-\U000023FF\U00002460-\U000024FF'
    r'\u2022\u2023\u25b6\u25c0\u2705\u274c\u2728\u270a-\u270f'
    r']+',
    flags=re.UNICODE
)

# Ký tự vô hình / điều khiển đặc biệt
INVISIBLE_CHARS_REGEX = re.compile(r'[\u200b-\u200f\ufeff\u202a-\u202e\u2060-\u206f\ufe00-\ufe0f\u00ad]')


def clean_v1_light(text: str) -> str:
    """
    [Phiên bản V1 - Light Clean]:
    - Chuẩn hóa Unicode NFKC (đưa font chữ kiểu nghệ thuật về chữ cái chuẩn).
    - Loại bỏ ký tự tàng hình (zero-width spaces).
    - Gom gọn khoảng trắng thừa và dòng trống.
    - GIỮ NGUYÊN: Chữ hoa/thường, Emoji, URL, dấu câu đầy đủ.
    -> Phù hợp nhất cho PhoBERT hoặc Large Language Models có thể học ngữ cảnh tự nhiên.
    """
    if not isinstance(text, str) or not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = INVISIBLE_CHARS_REGEX.sub("", text)
    # Gom khoảng trắng
    text = " ".join(text.split())
    return text.strip()


def clean_v2_standard(text: str) -> str:
    """
    [Phiên bản V2 - Standard Clean]:
    - Chuẩn hóa NFKC & xóa ký tự vô hình.
    - Chuẩn hóa tiền tệ: $ -> usd, ₫ -> đ.
    - Xóa đường kẻ viền trang trí lặp lại (━━━, ───, ════, -----).
    - Xóa URL web & link Telegram (https://..., t.me/..., www...).
    - Khử hoàn toàn Emoji & Icon hình vẽ.
    - Chuyển về chữ thường (lowercase).
    - Rút gọn dấu câu lặp lại (.... -> ., !!! -> !, ??? -> ?).
    -> Phù hợp tiêu chuẩn cho TF-IDF + LogisticRegression / PhoBERT cơ bản.
    """
    if not isinstance(text, str) or not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = INVISIBLE_CHARS_REGEX.sub("", text)
    text = text.replace("$", " usd ")
    text = text.replace("₫", " đ ")
    text = re.sub(r"[━─═~=-]{2,}", " ", text)
    text = re.sub(r"https?://\S+|t\.me/\S+|www\.\S+", " ", text)
    text = EMOJI_REGEX.sub(" ", text)
    text = text.lower()
    # Giữ lại chữ cái, số, tiếng Việt và dấu câu quan trọng
    text = re.sub(r"[^a-z0-9\sàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệđìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ.,:/\-+%?!#@()_]", " ", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r",{2,}", ",", text)
    text = re.sub(r"\?{2,}", "?", text)
    text = re.sub(r"!{2,}", "!", text)
    text = re.sub(r"-{2,}", "-", text)
    text = " ".join(text.split())
    return text.strip()


def clean_v3_deep(text: str) -> str:
    """
    [Phiên bản V3 - Deep Clean (Siêu sạch)]:
    - Kế thừa V2 (khử emoji, URL, chuẩn hóa NFKC).
    - Lọc bỏ username Telegram (@username).
    - Lọc bỏ ID Telegram trong ngoặc đơn, vd: (5442136592).
    - Lọc các câu cảnh báo scam boilerplate từ bot hệ thống.
    - Xóa hầu hết dấu câu rác, chỉ giữ lại chữ tiếng Việt, chữ cái, số và khoảng trắng.
    -> Phù hợp cho mô hình Naive Bayes, Word2Vec, TF-IDF cần từ điển từ thuần khiết nhất.
    """
    if not isinstance(text, str) or not text:
        return ""
    # Lọc mẫu cảnh báo bot scam lặp lại nhiều lần
    if "cẩn thận khi giao dịch nhé nên giao dịch trung gian qua admin" in text:
        return ""

    text = clean_v2_standard(text)
    # Xóa @username
    text = re.sub(r"@[a-zA-Z0-9_]+", " ", text)
    # Xóa ID số trong ngoặc: (123456789)
    text = re.sub(r"\(\d{6,15}\)", " ", text)
    # Xóa các ký tự đặc biệt còn lại, chỉ để lại chữ, số và space
    text = re.sub(r"[^a-z0-9\sàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệđìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]", " ", text)
    text = " ".join(text.split())
    return text.strip()


def clean_v4_sales(text: str) -> str:
    """
    [Phiên bản V4 - Sales Specialized Clean (Chuyên biệt Bán Hàng)]:
    - Kế thừa V2.
    - Chuẩn hóa các thuật ngữ viết tắt trong mua bán/giao dịch:
        + bhf -> bảo hành full
        + bh -> bảo hành
        + ib, inb, inbox -> liên hệ inbox
        + sll -> số lượng lớn
        + acc -> tài khoản
        + vpo -> văn phòng
        + gd -> giao dịch
        + sth, th -> tháng
    - Chuẩn hóa đơn vị giá tiền và thời hạn:
        + vd: 340k -> 340 nghìn
        + vd: 1th -> 1 tháng
        + vd: 1m, 2m2 -> 1 triệu, 2.2 triệu
        + vd: 24h -> 24 giờ
    - Tách biệt rõ ràng từ khóa sản phẩm để mô hình bắt trọng số cao nhất.
    -> Đề xuất sử dụng để tăng độ nhạy (Recall) cho tin bán hàng lách chữ.
    """
    if not isinstance(text, str) or not text:
        return ""
    if "cẩn thận khi giao dịch nhé nên giao dịch trung gian qua admin" in text:
        return ""

    text = clean_v2_standard(text)

    # Chuẩn hóa giá tiền và đơn vị
    # 340k / 340 k -> 340 nghìn
    text = re.sub(r"\b(\d+)\s*k\b", r"\1 nghìn", text)
    # 1th / 1 th -> 1 tháng
    text = re.sub(r"\b(\d+)\s*th\b", r"\1 tháng", text)
    # 24h / 48h -> 24 giờ
    text = re.sub(r"\b(\d+)\s*h\b", r"\1 giờ", text)
    # 1m -> 1 triệu, 1m6 -> 1.6 triệu
    text = re.sub(r"\b(\d+)m(\d+)\b", r"\1.\2 triệu", text)
    text = re.sub(r"\b(\d+)\s*m\b", r"\1 triệu", text)

    # Chuẩn hóa từ lóng / viết tắt bán hàng
    slang_map = {
        r"\bbhf\b": "bảo hành full",
        r"\bbh\b": "bảo hành",
        r"\bib\b": "inbox",
        r"\binb\b": "inbox",
        r"\bsll\b": "số lượng lớn",
        r"\bacc\b": "tài khoản",
        r"\baccs\b": "tài khoản",
        r"\bvpo\b": "văn phòng",
        r"\bgd\b": "giao dịch",
        r"\bpass lại\b": "bán lại",
        r"\bpass\b": "bán lại",
        r"\bslot\b": "suất slot",
        r"\bchính chủ\b": "chính chủ uy tín",
        r"\bko\b": "không",
        r"\bk\b": "không",
        r"\bdc\b": "được",
    }
    for pattern, replacement in slang_map.items():
        text = re.sub(pattern, replacement, text)

    text = " ".join(text.split())
    return text.strip()


def get_all_cleaners() -> Dict[str, Dict[str, object]]:
    """Trả về từ điển chứa thông tin tất cả các hàm clean có sẵn"""
    return {
        "v1_light": {
            "name": "V1 - Light Clean",
            "func": clean_v1_light,
            "desc": "Nhẹ nhàng, giữ nguyên emoji, URLs, chữ hoa, câu cú tự nhiên. Lý tưởng cho PhoBERT/LLM."
        },
        "v2_standard": {
            "name": "V2 - Standard Clean",
            "func": clean_v2_standard,
            "desc": "Tiêu chuẩn, khử emoji, xóa URLs, chuẩn hóa tiền tệ ($ -> usd, ₫ -> đ), chữ thường. Ổn định nhất."
        },
        "v3_deep": {
            "name": "V3 - Deep Clean",
            "func": clean_v3_deep,
            "desc": "Siêu sạch, khử @username, ID số telegram, lọc cảnh báo bot, xóa sạch dấu câu rác."
        },
        "v4_sales": {
            "name": "V4 - Sales Specialized Clean",
            "func": clean_v4_sales,
            "desc": "Chuyên biệt cho tin bán hàng: dịch viết tắt (bh, bhf, ib, sll), quy đổi giá (k -> nghìn, m -> triệu, th -> tháng)."
        }
    }
