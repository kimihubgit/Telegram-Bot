import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.naive_bayes import MultinomialNB
from sklearn.ensemble import VotingClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score, precision_score, recall_score

import re
import unicodedata

def clean_text(text: str) -> str:
    """
    Chuẩn hóa và làm sạch văn bản cho mô hình AI:
    - Chuẩn hóa NFKC: chuyển đổi font chữ nghệ thuật (toán học, in đậm 𝐅𝐏𝐓, 𝐕𝐈𝐄𝐎𝐍) về chữ cái chuẩn.
    - Xóa ký tự điều khiển, ký tự vô hình (zero-width spaces, BOM, formatting characters).
    - Chuẩn hóa tiền tệ: $ -> usd, ₫ -> đ.
    - Xóa đường kẻ viền trang trí lặp lại (━━━, ───, ════, -----).
    - Xóa URL web dài (http://..., t.me/..., www...).
    - Xóa Emoji & Icon hình vẽ (🔥, 🎬, 🚀, 💎, ⚡, v.v.).
    - Giữ lại chữ cái, số, tiếng Việt đầy đủ và các ký tự cú pháp thiết yếu:
      . , : / - + % ? ! # @ ( ) _
    - Rút gọn dấu lặp liên tiếp và khoảng trắng thừa.
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

# 1. Đọc dữ liệu mở rộng chuẩn hoá duy nhất
data_path = os.path.join(os.path.dirname(__file__), "dataset.csv")
df = pd.read_csv(data_path)
print(f"Loaded {len(df)} samples from {data_path}")
print(df['label'].value_counts())

# Tiền xử lý: Làm sạch toàn bộ văn bản trước khi đưa vào mô hình
print("\n🧹 Đang khử nhiễu và xóa toàn bộ ký hiệu đặc biệt khỏi văn bản...")
X = df['text'].fillna("").apply(clean_text)
y = df['label'].astype(int)

# 2. Chia tập Train (80%) và Test (20%) có phân tầng (stratify)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"Train set: {len(X_train)} samples | Test set: {len(X_test)} samples")

# 3. Vectorizer TF-IDF kết hợp Word n-grams & Char n-grams để bắt từ lóng/giá tiền/viết tắt
word_vec = TfidfVectorizer(ngram_range=(1, 3), min_df=2, max_df=0.9, sublinear_tf=True)
char_vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), min_df=2, max_df=0.9, sublinear_tf=True)
vectorizer = FeatureUnion([('word', word_vec), ('char', char_vec)])

X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)
print(f"Vocabulary features size: {X_train_vec.shape[1]}")

# 4. Huấn luyện các mô hình
models = {
    "LinearSVC": LinearSVC(C=1.5, random_state=42),
    "LogisticRegression": LogisticRegression(C=6.0, max_iter=1000, random_state=42),
    "MultinomialNB": MultinomialNB(alpha=0.01)
}

print("\n--- 5-FOLD STRATIFIED CROSS VALIDATION (TRAIN SET) ---")
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

for name, model in models.items():
    cv_scores = cross_val_score(model, X_train_vec, y_train, cv=skf, scoring='f1')
    cv_acc = cross_val_score(model, X_train_vec, y_train, cv=skf, scoring='accuracy')
    print(f"[{name}] F1-Score: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f}) | Accuracy: {cv_acc.mean():.4f}")

# 5. Xây dựng Ensemble Voting Classifier kết hợp các mô hình
ensemble = VotingClassifier(
    estimators=[
        ('svc', LinearSVC(C=1.5, random_state=42)),
        ('lr', LogisticRegression(C=6.0, max_iter=1000, random_state=42)),
        ('nb', MultinomialNB(alpha=0.01))
    ],
    voting='hard'
)
ensemble.fit(X_train_vec, y_train)

# 6. Đánh giá trên tập TEST ĐỘC LẬP (Holdout 20%)
y_pred = ensemble.predict(X_test_vec)

acc = accuracy_score(y_test, y_pred)
prec = precision_score(y_test, y_pred)
rec = recall_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred)
cm = confusion_matrix(y_test, y_pred)

print("\n" + "="*50)
print("📊 KẾT QUẢ ĐÁNH GIÁ TRÊN TẬP TEST ĐỘC LẬP (HOLDOUT TEST)")
print("="*50)
print(f"🎯 Độ chính xác tổng thể (Accuracy): {acc*100:.2f}%")
print(f"🎯 Precision (Độ chuẩn xác khi báo là Sales): {prec*100:.2f}%")
print(f"🎯 Recall (Độ bao phủ, bắt kịp tin Sales):     {rec*100:.2f}%")
print(f"🎯 F1-Score (Trung bình điều hòa F1):         {f1*100:.2f}%")
print("\nConfusion Matrix [TN, FP / FN, TP]:")
print(cm)
print("\nChi tiết Classification Report:")
print(classification_report(y_test, y_pred, target_names=["Non-Sales (0)", "Sales (1)"]))

# 7. Lưu Model và Vectorizer để bot có thể tải dùng trực tiếp
save_dir = os.path.dirname(__file__)
joblib.dump(ensemble, os.path.join(save_dir, "sales_classifier.pkl"))
joblib.dump(vectorizer, os.path.join(save_dir, "tfidf_vectorizer.pkl"))
print("✅ Đã lưu sales_classifier.pkl và tfidf_vectorizer.pkl!")

# 8. Test thử với một số câu ngẫu nhiên
test_samples = [
    "Sẵn 5 slot ChatGPT Plus chính chủ 40k/tháng inbox em ngay",
    "Em cần tìm mua acc Canva Pro admin ai có pm",
    "Hôm nay trời mưa to quá lag mạng ae",
    "/clean_status",
    "Cảnh báo cẩn thận scammer lừa đảo trung gian",
    "Nhận up Youtube Premium 1 năm bao hành trọn đời chỉ 250k",
    "Cho em hỏi bot này lấy token kiểu gì vậy"
]

print("\n--- THỬ NGHIỆM DỰ ĐOÁN THỰC TẾ (ĐÃ KHỬ NHIỄU KÝ TỰ ĐẶC BIỆT) ---")
test_samples_cleaned = [clean_text(s) for s in test_samples]
test_vec = vectorizer.transform(test_samples_cleaned)
preds = ensemble.predict(test_vec)
for raw_text, clean_t, p in zip(test_samples, test_samples_cleaned, preds):
    label_str = "🛒 [BÁN HÀNG / RAO VẶT]" if p == 1 else "💬 [KHÔNG PHẢI BÁN HÀNG]"
    print(f"Gốc    : '{raw_text}'")
    print(f"Đã sạch: '{clean_t}' -> Dự đoán: {label_str}")
    print("-" * 50)
