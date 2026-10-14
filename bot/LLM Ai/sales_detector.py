"""
KiGuard Sales Detector Module
Sử dụng mô hình AI đã huấn luyện kết hợp Rule-Engine để phân loại tin nhắn
bán hàng / rao vặt / dịch vụ theo thời gian thực với độ chính xác cao nhất.
"""
import os
import re
import unicodedata
import joblib

_DIR = os.path.dirname(__file__)
_MODEL_PATH = os.path.join(_DIR, "sales_classifier.pkl")
_VEC_PATH = os.path.join(_DIR, "tfidf_vectorizer.pkl")
_PHOBERT_DIR = os.path.join(_DIR, "phobert_kiguard_best_model")

_model = None
_vectorizer = None
_phobert_model = None
_phobert_tokenizer = None
_phobert_device = None
_engine_name = "None"


def clean_text(text: str) -> str:
    """
    Chuẩn hóa và làm sạch văn bản cho mô hình AI:
    - Chuẩn hóa NFKC: chuyển đổi font chữ nghệ thuật về chữ cái chuẩn.
    - Xóa ký tự điều khiển, ký tự vô hình.
    - Chuẩn hóa tiền tệ: $ -> usd, ₫ -> đ.
    - Xóa đường kẻ viền trang trí lặp lại (━━━, ───, ════, -----).
    - Xóa URL web dài.
    - Xóa Emoji & Icon hình vẽ.
    - Giữ lại chữ cái, số, tiếng Việt đầy đủ và ký tự cú pháp thiết yếu.
    """
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r'[\u200b-\u200f\ufeff\u202a-\u202e\u2060-\u206f\ufe00-\ufe0f\u00ad]', '', text)
    text = text.replace('$', ' usd ')
    text = text.replace('₫', ' đ ')
    text = re.sub(r'[━─═~=-]{2,}', ' ', text)
    text = re.sub(r'https?://\S+|t\.me/\S+|www\.\S+', ' ', text)
    emoji_regex = re.compile(
        r'['
        r'\U0001F1E0-\U0001F1FF\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF'
        r'\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF'
        r'\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF'
        r'\U000025A0-\U000025FF\U00002B00-\U00002BFF\U00002300-\U000023FF\U00002460-\U000024FF'
        r'\u2022\u2023\u25b6\u25c0\u2705\u274c\u2728\u270a-\u270f'
        r']+',
        flags=re.UNICODE
    )
    text = emoji_regex.sub(' ', text)
    text = text.lower()
    text = re.sub(r'[^a-z0-9\sàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệđìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ.,:/\-+%?!#@()_]', ' ', text)
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r',{2,}', ',', text)
    text = re.sub(r'\?{2,}', '?', text)
    text = re.sub(r'!{2,}', '!', text)
    text = re.sub(r'-{2,}', '-', text)
    text = re.sub(r'/{2,}', '/', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _load_engine():
    global _model, _vectorizer, _phobert_model, _phobert_tokenizer, _phobert_device, _engine_name

    # 1. Ưu tiên kiểm tra PhoBERT nếu người dùng đã tải thư mục mô hình về
    if _phobert_model is None and os.path.exists(_PHOBERT_DIR):
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            _phobert_tokenizer = AutoTokenizer.from_pretrained(_PHOBERT_DIR, use_fast=False)
            _phobert_model = AutoModelForSequenceClassification.from_pretrained(_PHOBERT_DIR)
            _phobert_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            _phobert_model.to(_phobert_device)
            _phobert_model.eval()
            _engine_name = "PhoBERT"
            print(f"🤖 [KiGuard] Loaded PhoBERT model on {_phobert_device}")
            return
        except Exception as e:
            print(f"⚠️ Không thể nạp PhoBERT: {e}, fallback sang TF-IDF...")

    # 2. Fallback sang mô hình TF-IDF + VotingClassifier
    if _model is None and os.path.exists(_MODEL_PATH) and os.path.exists(_VEC_PATH):
        try:
            _model = joblib.load(_MODEL_PATH)
            _vectorizer = joblib.load(_VEC_PATH)
            _engine_name = "TF-IDF + VotingClassifier"
            print("🤖 [KiGuard] Loaded TF-IDF + Ensemble Model")
        except Exception as e:
            print(f"⚠️ Không thể load mô hình AI TF-IDF: {e}")
            _model = None
            _vectorizer = None


# Danh sách các mẫu quy tắc cứng bảo vệ (Buyer Guard)
_BUYER_PATTERNS = [
    re.compile(r'^(?:em\s+|mình\s+|bác\s+nào\s+)?(?:cần\s+mua|tìm\s+mua|mua\s+hộ|e\s+tìm|tìm\s+acc|tìm\s+slot|tìm\s+gấp|kiếm\s+acc)\b', re.IGNORECASE),
    re.compile(r'^(?:ai\s+có|bác\s+nào\s+có|ae\s+có|ai\s+còn)\s+.*\s+(?:k\??|ko\??|không\??|k\s+ạ\??|ko\s+ạ\??|inbox\s+e|báo\s+giá\s+e)\s*$', re.IGNORECASE),
]

# Danh sách các mẫu quy tắc cứng xác nhận Bán hàng (Seller Patterns)
_SELLER_PATTERNS = [
    re.compile(r'#nghienplusmarket', re.IGNORECASE),
    re.compile(r'\b(?:sẵn\s+sll|bên\s+em\s+sẵn|nhận\s+nâng\s+chính\s+chủ|bán\s+hàng\s+tự\s+động|bot\s+order\s+ở\s+bio|order\s+nhanh\s+bot|bán\s+tut|nhận\s+kéo\s+mem|cần\s+sell)\b', re.IGNORECASE),
    re.compile(r'\b\d+k\b.*\b(?:bhf|kbh|bảo\s+hành|full\s+time|acc\s+cấp|chính\s+chủ|add\s+fam|add\s+team|slot\s+fam)\b', re.IGNORECASE),
    re.compile(r'\b(?:bhf|kbh)\b.*\b\d+k\b', re.IGNORECASE),
    re.compile(r'\b\d+k/\d+\s*(?:th|tháng|ngày|d|m|y|năm|slot|acc|1|con)\b', re.IGNORECASE),
]


def check_sales_detail(text: str) -> dict:
    """
    Phân tích chi tiết tin nhắn:
    Returns:
        dict {
            'is_sales': bool,
            'confidence': float (0.0 - 100.0),
            'engine': str,
            'clean_text': str
        }
    """
    if not text or len(text.strip()) < 2:
        return {'is_sales': False, 'confidence': 100.0, 'engine': 'Empty', 'clean_text': ''}

    cleaned = clean_text(text)
    if not cleaned or len(cleaned) < 2:
        return {'is_sales': False, 'confidence': 100.0, 'engine': 'Empty', 'clean_text': ''}

    # BƯỚC 1: Kiểm tra quy tắc cứng Người Mua (Buyer Guard)
    for bp in _BUYER_PATTERNS:
        if bp.search(cleaned) and not re.search(r'\b(?:\d+k/\d+|\d+k/tháng|bảng\s+giá)\b', cleaned):
            return {
                'is_sales': False,
                'confidence': 98.0,
                'engine': 'BuyerRule',
                'clean_text': cleaned
            }

    # BƯỚC 1.5: Kiểm tra quy tắc cứng Người Bán (Seller Rule)
    for sp in _SELLER_PATTERNS:
        if sp.search(cleaned):
            return {
                'is_sales': True,
                'confidence': 99.0,
                'engine': 'SellerRule',
                'clean_text': cleaned
            }

    _load_engine()

    # BƯỚC 2: Dự đoán bằng PhoBERT (nếu có)
    if _phobert_model is not None and _phobert_tokenizer is not None:
        try:
            import torch
            inputs = _phobert_tokenizer(cleaned, return_tensors='pt', truncation=True, max_length=256)
            inputs = {k: v.to(_phobert_device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = _phobert_model(**inputs)
                probs = torch.softmax(outputs.logits, dim=-1).squeeze().cpu().numpy()
                pred = int(probs.argmax())
                conf = float(probs[pred] * 100)
                return {
                    'is_sales': bool(pred == 1),
                    'confidence': round(conf, 2),
                    'engine': 'PhoBERT',
                    'clean_text': cleaned
                }
        except Exception as e:
            print(f"⚠️ Lỗi suy luận PhoBERT: {e}")

    # BƯỚC 3: Dự đoán bằng TF-IDF + Ensemble Model
    if _model is not None and _vectorizer is not None:
        try:
            vec = _vectorizer.transform([cleaned])
            pred = _model.predict(vec)[0]
            conf = 95.0
            if hasattr(_model, "predict_proba"):
                prob_arr = _model.predict_proba(vec)[0]
                conf = float(prob_arr[pred] * 100)
            return {
                'is_sales': bool(pred == 1),
                'confidence': round(conf, 2),
                'engine': 'TF-IDF+Ensemble',
                'clean_text': cleaned
            }
        except Exception as e:
            print(f"⚠️ Lỗi suy luận TF-IDF: {e}")

    # BƯỚC 4: Fallback Regex nếu không load được model
    has_seller = any(sp.search(cleaned) for sp in _SELLER_PATTERNS)
    return {
        'is_sales': bool(has_seller),
        'confidence': 80.0 if has_seller else 60.0,
        'engine': 'FallbackRegex',
        'clean_text': cleaned
    }


def check_is_sales(text: str) -> bool:
    """
    Hàm nhanh trả về True nếu là tin bán hàng, False nếu là tin thường.
    """
    res = check_sales_detail(text)
    return res['is_sales']


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    test_samples = [
        "Sẵn slot ChatGPT Plus inapp 40k bao hành 1 tháng #NghienPlusMarket",
        "Ai có acc canva k bán e với",
        "Hello anh em buổi chiều vui vẻ",
        "Nhận kéo mem telegram giá rẻ không tụt",
        "cần mua 5 acc wechat uy tín gdtg ạ",
        "Canva pro 15k 1 th",
        "kling AI sll ae cần ib"
    ]
    for s in test_samples:
        d = check_sales_detail(s)
        st = "🛒 RAO VẶT / BÁN HÀNG" if d['is_sales'] else "💬 BÌNH THƯỜNG"
        print(f"[{st}] ({d['confidence']}%, via {d['engine']}) -> {repr(s)}")
