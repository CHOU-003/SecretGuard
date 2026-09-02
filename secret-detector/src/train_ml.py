import os
import math
import string
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score

def calculate_entropy(text):
    if not text:
        return 0
    entropy = 0
    for x in set(text):
        p_x = float(text.count(x)) / len(text)
        entropy -= p_x * math.log(p_x, 2)
    return round(entropy, 4)

def extract_features(df):
    """
    Trích xuất các đặc trưng (Features) từ chuỗi văn bản để đưa vào mô hình ML
    """
    features = []
    for text in df['text']:
        text_str = str(text)
        length = len(text_str)
        entropy = calculate_entropy(text_str)
        
        # Đếm các loại ký tự
        digits = sum(c.isdigit() for c in text_str)
        letters = sum(c.isalpha() for c in text_str)
        specials = length - digits - letters
        
        digit_ratio = digits / length if length > 0 else 0
        letter_ratio = letters / length if length > 0 else 0
        special_ratio = specials / length if length > 0 else 0
        
        # Kiểm tra sự xuất hiện của các từ khóa nhạy cảm
        has_secret_kw = 1 if any(kw in text_str.lower() for kw in ['secret', 'key', 'token', 'api', 'passwd', 'password', 'akia']) else 0

        features.append([
            length,
            entropy,
            digit_ratio,
            letter_ratio,
            special_ratio,
            has_secret_kw
        ])
        
    return np.array(features)

def train_and_evaluate():
    print("=== BẮT ĐẦU HUẤN LUYỆN MÔ HÌNH MACHINE LEARNING ===")
    
    # 1. Đọc dữ liệu từ 3 tập riêng biệt
    train_df = pd.read_csv("data/train.csv")
    val_df = pd.read_csv("data/val.csv")
    
    # 2. Trích xuất đặc trưng
    X_train = extract_features(train_df)
    y_train = train_df['label']
    
    X_val = extract_features(val_df)
    y_val = val_df['label']
    
    # 3. Khởi tạo và huấn luyện Random Forest Classifier
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    
    # 4. Đánh giá trên tập Validation
    y_val_pred = clf.predict(X_val)
    acc = accuracy_score(y_val, y_val_pred)
    print(f"\n[Validation Set] Accuracy: {acc * 100:.2f}%\n")
    print(classification_report(y_val, y_val_pred, target_names=['Non-Secret (0)', 'Secret (1)']))
    
    # 5. Lưu mô hình đã train vào thư mục models/
    os.makedirs("models", exist_ok=True)
    joblib.dump(clf, "models/secret_ml_model.pkl")
    print("-> Đã lưu mô hình thành công tại: models/secret_ml_model.pkl")

if __name__ == "__main__":
    train_and_evaluate()