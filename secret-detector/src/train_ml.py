"""
train_ml.py (v3) — train + hiệu chỉnh xác suất (probability calibration)

Quy trình:
  1. Đọc train/val/test_features.csv (từ build_features.py).
  2. Train Random Forest và XGBoost (bản "raw", để so sánh).
  3. Hiệu chỉnh xác suất bằng CalibratedClassifierCV (sigmoid và isotonic).
     Calibration dùng cross-validation TRÊN TẬP TRAIN, chia fold THEO REPO
     (GroupKFold) -> tập val vẫn nguyên vẹn để đo độ hiệu chỉnh một cách
     trung thực và chọn model.
  4. Chọn model đã hiệu chỉnh có LOG LOSS thấp nhất trên val. Lý do: log loss phạt
     rất nặng các dự đoán quá tự tin mà sai (đúng mục tiêu "99.9% phải thật sự là 99.9%").
     Brier của các model chênh nhau ở mức nhiễu nên không dùng để quyết định;
     isotonic hay thắng Brier nhưng cho xác suất cứng 0/1 khiến log loss rất cao.
  5. Đánh giá trên test set ĐÚNG 1 LẦN, lưu model + feature_columns.pkl +
     model_card.json (siêu dữ liệu để versioning/retrain sau này).

Lưu ý khi diễn giải "độ tin cậy": calibration làm xác suất đúng theo tỉ lệ
secret của dữ liệu train (training_prevalence trong model_card.json). Ngoài
đời tỉ lệ secret thấp hơn nhiều, nên với cùng 1 điểm số, độ chính xác thực tế
sẽ thấp hơn -> đây là giới hạn cần nêu trong báo cáo.
"""

import os
import json
import datetime

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, StratifiedKFold
from xgboost import XGBClassifier

SEED = 42
N_CV_FOLDS = 5
NON_FEATURE_COLUMNS = ["label", "_original_type"]
CALIBRATION_METHODS = ["sigmoid", "isotonic"]


# ------------------------------------------------------------------ data
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


def load_train_groups(data_dir, n_rows):
    """Lấy cột repo của train.csv (cùng thứ tự dòng với train_features.csv)
    để chia fold theo repo. Không có thì trả None."""
    path = os.path.join(data_dir, "train.csv")
    if not os.path.exists(path):
        return None
    raw = pd.read_csv(path)
    if "repo" not in raw.columns or len(raw) != n_rows:
        return None
    return raw["repo"].to_numpy()


def make_cv_splits(X, y, groups):
    if groups is not None:
        splits = list(GroupKFold(n_splits=N_CV_FOLDS).split(X, y, groups))
        how = f"GroupKFold theo repo ({len(set(groups))} repo)"
    else:
        splits = list(StratifiedKFold(N_CV_FOLDS, shuffle=True, random_state=SEED).split(X, y))
        how = "StratifiedKFold (không có cột repo -> chia theo dòng)"

    # Mỗi fold dùng để calibrate phải có đủ 2 lớp
    for i, (_, cal_idx) in enumerate(splits):
        if y.iloc[cal_idx].nunique() < 2:
            raise ValueError(f"Fold calibration {i} chỉ có 1 lớp, hãy giảm N_CV_FOLDS.")
    return splits, how


# --------------------------------------------------------------- metrics
def expected_calibration_error(y_true, proba, n_bins=10):
    y_true = np.asarray(y_true)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ids = np.clip(np.digitize(proba, bins[1:-1]), 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        mask = ids == b
        if mask.any():
            ece += mask.mean() * abs(y_true[mask].mean() - proba[mask].mean())
    return float(ece)


def compute_metrics(y_true, proba, threshold=0.5):
    y_true = np.asarray(y_true)
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "fpr": float(fp / (fp + tn)) if (fp + tn) else 0.0,
        "roc_auc": float(roc_auc_score(y_true, proba)),
        "pr_auc": float(average_precision_score(y_true, proba)),
        "brier": float(brier_score_loss(y_true, proba)),
        "log_loss": float(log_loss(y_true, proba, labels=[0, 1])),
        "ece": expected_calibration_error(y_true, proba),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
    }


def print_metrics_table(rows):
    header = f"{'Model':<28} {'ROC-AUC':>8} {'PR-AUC':>8} {'Brier':>8} {'LogLoss':>8} {'ECE':>8} {'F1@0.5':>8}"
    print(header)
    print("-" * len(header))
    for name, m in rows.items():
        print(f"{name:<28} {m['roc_auc']:>8.4f} {m['pr_auc']:>8.4f} {m['brier']:>8.4f} "
              f"{m['log_loss']:>8.4f} {m['ece']:>8.4f} {m['f1']:>8.4f}")


def print_reliability(y_true, proba, n_bins=10):
    """Bảng độ tin cậy: xác suất dự đoán trung bình vs tỉ lệ secret thật trong từng bin."""
    y_true = np.asarray(y_true)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ids = np.clip(np.digitize(proba, bins[1:-1]), 0, n_bins - 1)
    print(f"{'Khoảng điểm':<14} {'Số mẫu':>7} {'Điểm TB':>9} {'Secret thật':>12}")
    for b in range(n_bins):
        mask = ids == b
        if mask.any():
            print(f"[{bins[b]:.1f}, {bins[b + 1]:.1f}{']' if b == n_bins - 1 else ')'}  "
                  f"{int(mask.sum()):>7} {proba[mask].mean():>9.3f} {y_true[mask].mean():>12.3f}")


# ---------------------------------------------------------------- models
def build_base_models(y_train):
    pos = int((y_train == 1).sum())
    neg = int((y_train == 0).sum())
    return {
        "RandomForest": RandomForestClassifier(
            n_estimators=200, max_depth=10, class_weight="balanced",
            random_state=SEED, n_jobs=-1,
        ),
        "XGBoost": XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            scale_pos_weight=(neg / pos) if pos else 1.0,
            random_state=SEED, eval_metric="logloss", n_jobs=-1,
        ),
    }


def train_and_evaluate():
    print("=== HUẤN LUYỆN + HIỆU CHỈNH XÁC SUẤT ===\n")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    models_dir = os.path.join(base_dir, "models")
    os.makedirs(models_dir, exist_ok=True)

    X_train, y_train = load_features(data_dir, "train")
    X_val, y_val = load_features(data_dir, "val")
    X_val = X_val.reindex(columns=X_train.columns, fill_value=0)

    groups = load_train_groups(data_dir, len(X_train))
    splits, split_desc = make_cv_splits(X_train, y_train, groups)

    print(f"Train: {len(X_train)} mẫu | Val: {len(X_val)} mẫu | Số feature: {X_train.shape[1]}")
    print(f"Tỉ lệ secret trong train: {y_train.mean():.2%}")
    print(f"Calibration CV: {split_desc}\n")

    # 1. Model raw (fit trên toàn bộ train) + model đã hiệu chỉnh (CV trên train)
    candidates = {}
    for model_name, estimator in build_base_models(y_train).items():
        raw = build_base_models(y_train)[model_name].fit(X_train, y_train)
        candidates[f"{model_name} (raw)"] = (raw, False)
        for method in CALIBRATION_METHODS:
            calibrated = CalibratedClassifierCV(estimator, method=method, cv=splits)
            calibrated.fit(X_train, y_train)
            candidates[f"{model_name} + {method}"] = (calibrated, True)

    # 2. So sánh trên validation
    val_rows = {
        name: compute_metrics(y_val, model.predict_proba(X_val)[:, 1])
        for name, (model, _) in candidates.items()
    }
    print("=== SO SÁNH TRÊN VALIDATION ===")
    print_metrics_table(val_rows)

    # 3. Chọn model ĐÃ hiệu chỉnh có log loss thấp nhất (hòa thì PR-AUC cao hơn)
    calibrated_names = [n for n, (_, is_cal) in candidates.items() if is_cal]
    best_name = min(calibrated_names, key=lambda n: (val_rows[n]["log_loss"], -val_rows[n]["pr_auc"]))
    best_model = candidates[best_name][0]
    print(f"\n🏆 Model được chọn: {best_name}  (log loss val = {val_rows[best_name]['log_loss']:.4f})")

    best_val_proba = best_model.predict_proba(X_val)[:, 1]
    print("\n--- Bảng độ tin cậy trên VALIDATION (điểm dự đoán vs tỉ lệ secret thật) ---")
    print_reliability(y_val, best_val_proba)

    print("\n--- Ngưỡng tham khảo cho main.py (--threshold / --warn-threshold) ---")
    for t in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        m = compute_metrics(y_val, best_val_proba, threshold=t)
        print(f"  threshold={t:.1f} -> precision={m['precision']:.3f}, "
              f"recall={m['recall']:.3f}, FPR={m['fpr']:.3f}")

    # 4. Đánh giá cuối trên test (1 lần duy nhất, sau khi đã chốt model)
    print("\n=== ĐÁNH GIÁ CUỐI TRÊN TEST SET (1 lần duy nhất) ===")
    X_test, y_test = load_features(data_dir, "test")
    X_test = X_test.reindex(columns=X_train.columns, fill_value=0)
    test_proba = best_model.predict_proba(X_test)[:, 1]
    test_metrics = compute_metrics(y_test, test_proba)
    print(classification_report(y_test, (test_proba >= 0.5).astype(int),
                                target_names=["Non-Secret (0)", "Secret (1)"], zero_division=0))
    print(f"ROC-AUC={test_metrics['roc_auc']:.4f} | PR-AUC={test_metrics['pr_auc']:.4f} | "
          f"Brier={test_metrics['brier']:.4f} | ECE={test_metrics['ece']:.4f} | FPR={test_metrics['fpr']:.4f}")
    print(f"Confusion matrix (test): TN={test_metrics['tn']} FP={test_metrics['fp']} "
          f"FN={test_metrics['fn']} TP={test_metrics['tp']}")

    # 5. Lưu model + feature_columns + model_card
    joblib.dump(best_model, os.path.join(models_dir, "secret_ml_model.pkl"))
    joblib.dump(list(X_train.columns), os.path.join(models_dir, "feature_columns.pkl"))
    card = {
        "trained_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "selected_model": best_name,
        "sklearn_version": sklearn.__version__,
        "n_train": int(len(X_train)),
        "n_val": int(len(X_val)),
        "n_test": int(len(X_test)),
        "n_features": int(X_train.shape[1]),
        "training_prevalence": float(y_train.mean()),
        "calibration_cv": split_desc,
        "validation_metrics": {n: val_rows[n] for n in val_rows},
        "test_metrics_at_0.5": test_metrics,
    }
    with open(os.path.join(models_dir, "model_card.json"), "w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=2)

    print("\n-> Đã lưu: models/secret_ml_model.pkl, models/feature_columns.pkl, models/model_card.json")


if __name__ == "__main__":
    train_and_evaluate()