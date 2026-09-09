"""
train_ml.py
Đọc train_features.csv / val_features.csv / test_features.csv (đã trích feature
sẵn từ build_features.py), train + so sánh Random Forest vs XGBoost, lưu model
tốt hơn (theo ROC-AUC trên validation) vào models/secret_ml_model.pkl, kèm
models/feature_columns.pkl (bắt buộc để inference dùng đúng thứ tự cột, vì
one-hot regex_type có thể sinh số cột khác nhau giữa các lần build dataset).

Test set CHỈ được đánh giá 1 LẦN DUY NHẤT, sau khi đã chốt model + threshold
dựa trên validation set (không dùng test set để chọn model, tránh leakage
ngầm gián tiếp).
"""

import os
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, roc_auc_score, precision_recall_curve

# Các cột không phải feature, phải loại trước khi đưa vào model
NON_FEATURE_COLUMNS = ["label", "_original_type"]


def load_features(data_dir, split_name):
    path = os.path.join(data_dir, f"{split_name}_features.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Chưa thấy {path}. Chạy build_dataset.py rồi build_features.py trước."
        )
    df = pd.read_csv(path)
    X = df.drop(columns=[c for c in NON_FEATURE_COLUMNS if c in df.columns])
    y = df["label"]
    return X, y


def train_and_evaluate():
    print("=== BẮT ĐẦU HUẤN LUYỆN MÔ HÌNH MACHINE LEARNING ===\n")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    models_dir = os.path.join(base_dir, "models")
    os.makedirs(models_dir, exist_ok=True)

    X_train, y_train = load_features(data_dir, "train")
    X_val, y_val = load_features(data_dir, "val")

    # Val phải có đúng cột như train (đã được build_features.py align sẵn,
    # nhưng reindex lại đây cho chắc chắn nếu ai chạy tay từng phần)
    X_val = X_val.reindex(columns=X_train.columns, fill_value=0)

    print(f"Train: {len(X_train)} mẫu | Val: {len(X_val)} mẫu | Số feature: {X_train.shape[1]}")
    print(f"Tỉ lệ label=1 trong train: {y_train.mean():.2%}\n")

    # --- Random Forest ---
    print("=== Random Forest ===")
    rf_model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        class_weight="balanced",  # dataset thường mất cân bằng (secret thật ít hơn code thường)
        random_state=42,
    )
    rf_model.fit(X_train, y_train)
    rf_val_proba = rf_model.predict_proba(X_val)[:, 1]
    rf_val_pred = rf_model.predict(X_val)
    print(classification_report(y_val, rf_val_pred, target_names=["Non-Secret (0)", "Secret (1)"]))
    rf_auc = roc_auc_score(y_val, rf_val_proba)
    print(f"ROC-AUC (Validation): {rf_auc:.4f}\n")

    # --- XGBoost ---
    print("=== XGBoost ===")
    pos = (y_train == 1).sum()
    neg = (y_train == 0).sum()
    xgb_model = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=(neg / pos) if pos > 0 else 1.0,  # cân bằng lớp
        random_state=42,
        eval_metric="logloss",
    )
    xgb_model.fit(X_train, y_train)
    xgb_val_proba = xgb_model.predict_proba(X_val)[:, 1]
    xgb_val_pred = xgb_model.predict(X_val)
    print(classification_report(y_val, xgb_val_pred, target_names=["Non-Secret (0)", "Secret (1)"]))
    xgb_auc = roc_auc_score(y_val, xgb_val_proba)
    print(f"ROC-AUC (Validation): {xgb_auc:.4f}\n")

    # --- So sánh và chọn model tốt hơn theo ROC-AUC trên validation ---
    if xgb_auc >= rf_auc:
        best_name, best_model, best_proba = "XGBoost", xgb_model, xgb_val_proba
    else:
        best_name, best_model, best_proba = "Random Forest", rf_model, rf_val_proba

    print(f"🏆 Model được chọn: {best_name} (ROC-AUC val: {max(rf_auc, xgb_auc):.4f})\n")

    # --- Gợi ý ngưỡng phân loại dựa trên validation (chỉ để tham khảo,
    #     main.py vẫn dùng --threshold/--warn-threshold truyền qua CLI) ---
    precisions, recalls, thresholds = precision_recall_curve(y_val, best_proba)
    print("Gợi ý một vài ngưỡng (threshold -> precision / recall) để tham khảo khi chọn --threshold cho main.py:")
    for t in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        preds_t = (best_proba >= t).astype(int)
        tp = ((preds_t == 1) & (y_val == 1)).sum()
        fp = ((preds_t == 1) & (y_val == 0)).sum()
        fn = ((preds_t == 0) & (y_val == 1)).sum()
        prec = tp / (tp + fp) if (tp + fp) else 0
        rec = tp / (tp + fn) if (tp + fn) else 0
        print(f"  threshold={t:.1f} -> precision={prec:.3f}, recall={rec:.3f}")

    # --- Đánh giá cuối cùng trên test set (CHỈ 1 LẦN, sau khi đã chốt model) ---
    print("\n=== ĐÁNH GIÁ CUỐI CÙNG TRÊN TEST SET (1 lần duy nhất) ===")
    X_test, y_test = load_features(data_dir, "test")
    X_test = X_test.reindex(columns=X_train.columns, fill_value=0)
    test_pred = best_model.predict(X_test)
    test_proba = best_model.predict_proba(X_test)[:, 1]
    print(classification_report(y_test, test_pred, target_names=["Non-Secret (0)", "Secret (1)"]))
    print(f"ROC-AUC (Test): {roc_auc_score(y_test, test_proba):.4f}")

    # --- Lưu model + feature_columns ---
    joblib.dump(best_model, os.path.join(models_dir, "secret_ml_model.pkl"))
    joblib.dump(list(X_train.columns), os.path.join(models_dir, "feature_columns.pkl"))
    print(f"\n-> Đã lưu model ({best_name}) tại: models/secret_ml_model.pkl")
    print("-> Đã lưu thứ tự cột feature tại: models/feature_columns.pkl")


if __name__ == "__main__":
    train_and_evaluate()