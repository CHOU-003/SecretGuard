"""
train_ml.py (v4) — train + hiệu chỉnh xác suất ở mức CANDIDATE

Chạy SAU build_features.py:
    python -m src.train_ml --train-on creddata         # train trên CredData
    python -m src.train_ml --train-on synthetic        # train trên dữ liệu tổng hợp
    python -m src.train_ml --train-on both             # train trên cả hai
    python -m src.train_ml --promote creddata          # đưa 1 thí nghiệm thành model chính thức

Mỗi lần train ghi vào models/experiments/<tag>/ (tag mặc định = giá trị --train-on),
KHÔNG đè model đang dùng. Chỉ khi bạn chốt phương án, --promote mới copy sang
models/secret_ml_model.pkl, models/feature_columns.pkl, models/model_card.json
(những file main.py đọc).

Quy trình:
  1. Đọc data/features/<nguồn>_{train,val}.csv (mỗi hàng là 1 candidate).
  2. Train Random Forest và XGBoost, mỗi loại ở 3 dạng: raw, sigmoid, isotonic.
     Calibration dùng cross-validation TRÊN TẬP TRAIN, chia fold THEO REPO.
  3. Chọn model ĐÃ hiệu chỉnh có LOG LOSS thấp nhất trên val của các nguồn dùng để
     train. Log loss phạt nặng việc quá tự tin mà sai, đúng mục tiêu "99% phải thật
     sự là 99%". (Brier của các model chênh nhau ở mức nhiễu; isotonic hay thắng
     Brier nhưng cho xác suất cứng 0/1 nên log loss tệ.)
  4. In chỉ số của model được chọn trên val của MỌI nguồn có sẵn, kể cả nguồn không
     dùng để train -> thấy rõ khoảng cách giữa các miền dữ liệu (zero-shot).

File này KHÔNG đụng tới tập test. Tập test chỉ dùng ở evaluate.py, trên model đã chốt.
Nếu chọn phương án dựa vào kết quả test của nhiều thí nghiệm thì test không còn là
tập độc lập nữa.

Lưu ý khi diễn giải: nhãn của 2 nguồn có định nghĩa khác nhau.
  creddata : mọi credential trong thư mục test đều là secret (quy tắc của CredData).
  synthetic: giá trị giả trong thư mục test là KHÔNG phải secret.
"""

import os
import json
import shutil
import argparse
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
    confusion_matrix,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from xgboost import XGBClassifier

from src.feature_extractor import META_COLUMNS

SEED = 42
N_CV_FOLDS = 5
CALIBRATION_METHODS = ["sigmoid", "isotonic"]
SOURCES = ("synthetic", "creddata")
TRAIN_SETS = {"synthetic": ["synthetic"], "creddata": ["creddata"], "both": ["synthetic", "creddata"]}
NON_FEATURE_COLUMNS = list(META_COLUMNS)  # tên cũ, giữ để các script khác còn import được

LABEL_SEMANTICS = {
    "creddata": "T = trông giống credential thật; credential trong thư mục test cũng là T (quy tắc CredData). F và X gộp thành 0.",
    "synthetic": "Dữ liệu tổng hợp; giá trị giả/placeholder trong thư mục test và tài liệu là 0.",
}


# ------------------------------------------------------------------ dữ liệu
def features_path(data_dir, source, split):
    return os.path.join(data_dir, "features", f"{source}_{split}.csv")


def load_frame(data_dir, source, split, required=False):
    path = features_path(data_dir, source, split)
    if not os.path.exists(path):
        if required:
            raise FileNotFoundError(f"Chưa thấy {path}. Chạy build_features.py (và import_external.py cho creddata) trước.")
        return None
    return pd.read_csv(path)


def split_xy(df, columns=None):
    X = df.drop(columns=[c for c in META_COLUMNS if c in df.columns])
    if columns is not None:
        X = X.reindex(columns=columns, fill_value=0)
    return X, df["label"].astype(int), df["_repo"].astype(str).to_numpy()


def concat_sources(data_dir, sources, split, required):
    frames = [load_frame(data_dir, s, split, required=required) for s in sources]
    frames = [f for f in frames if f is not None]
    return pd.concat(frames, ignore_index=True) if frames else None


# ------------------------------------------------------------------- chỉ số
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
        "precision": float(precision), "recall": float(recall), "f1": float(f1),
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
    y_true = np.asarray(y_true)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ids = np.clip(np.digitize(proba, bins[1:-1]), 0, n_bins - 1)
    print(f"{'Khoảng điểm':<14} {'Số mẫu':>7} {'Điểm TB':>9} {'Secret thật':>12}")
    for b in range(n_bins):
        mask = ids == b
        if mask.any():
            print(f"[{bins[b]:.1f}, {bins[b + 1]:.1f}{']' if b == n_bins - 1 else ')'}  "
                  f"{int(mask.sum()):>7} {proba[mask].mean():>9.3f} {y_true[mask].mean():>12.3f}")


# ------------------------------------------------------------------ mô hình
def build_base_models(y_train):
    pos, neg = int((y_train == 1).sum()), int((y_train == 0).sum())
    return {
        "RandomForest": RandomForestClassifier(
            n_estimators=200, max_depth=12, min_samples_leaf=2, class_weight="balanced",
            random_state=SEED, n_jobs=-1,
        ),
        "XGBoost": XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.08,
            scale_pos_weight=(neg / pos) if pos else 1.0,
            random_state=SEED, eval_metric="logloss", n_jobs=-1,
        ),
    }


def make_group_splits(X, y, groups):
    n_groups = len(set(groups))
    if n_groups < N_CV_FOLDS:
        raise ValueError(f"Chỉ có {n_groups} repo, ít hơn số fold ({N_CV_FOLDS}).")
    splits = list(GroupKFold(n_splits=N_CV_FOLDS).split(X, y, groups))
    for i, (_, cal_idx) in enumerate(splits):
        if y.iloc[cal_idx].nunique() < 2:
            raise ValueError(f"Fold calibration {i} chỉ có 1 lớp; giảm N_CV_FOLDS.")
    return splits, f"GroupKFold theo repo ({n_groups} repo, {N_CV_FOLDS} fold)"


def average_importances(model, columns):
    """Độ quan trọng feature, trung bình qua các fold calibration."""
    estimators = []
    if hasattr(model, "calibrated_classifiers_"):
        for cc in model.calibrated_classifiers_:
            est = getattr(cc, "estimator", None) or getattr(cc, "base_estimator", None)
            if est is not None:
                estimators.append(est)
    else:
        estimators = [model]
    imps = np.mean([e.feature_importances_ for e in estimators], axis=0)
    return pd.Series(imps, index=columns).sort_values(ascending=False)


# --------------------------------------------------------------------- chính
def train(args):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    tag = args.tag or args.train_on
    out_dir = os.path.join(base_dir, "models", "experiments", tag)
    os.makedirs(out_dir, exist_ok=True)

    train_sources = TRAIN_SETS[args.train_on]
    train_df = concat_sources(data_dir, train_sources, "train", required=True)
    X_train, y_train, groups = split_xy(train_df)
    columns = list(X_train.columns)
    select_df = concat_sources(data_dir, train_sources, "val", required=True)
    X_sel, y_sel, _ = split_xy(select_df, columns)

    print(f"=== TRAIN ({args.train_on}) | tag = {tag} ===")
    print(f"Train: {len(X_train)} candidate, {len(set(groups))} repo, {X_train.shape[1]} feature, "
          f"{y_train.mean():.1%} là secret")
    print(f"Val dùng để chọn model: {len(X_sel)} candidate ({y_sel.mean():.1%} là secret)")

    splits, split_desc = make_group_splits(X_train, y_train, groups)
    print(f"Calibration CV: {split_desc}\n")

    candidates = {}
    for model_name in build_base_models(y_train):
        raw = build_base_models(y_train)[model_name].fit(X_train, y_train)
        candidates[f"{model_name} (raw)"] = (raw, False)
        for method in CALIBRATION_METHODS:
            estimator = build_base_models(y_train)[model_name]
            calibrated = CalibratedClassifierCV(estimator, method=method, cv=splits)
            calibrated.fit(X_train, y_train)
            candidates[f"{model_name} + {method}"] = (calibrated, True)
            print(f"  đã train {model_name} + {method}")

    sel_rows = {n: compute_metrics(y_sel, m.predict_proba(X_sel)[:, 1]) for n, (m, _) in candidates.items()}
    print("\n=== SO SÁNH TRÊN VALIDATION (mức candidate) ===")
    print_metrics_table(sel_rows)

    calibrated_names = [n for n, (_, is_cal) in candidates.items() if is_cal]
    best_name = min(calibrated_names, key=lambda n: (sel_rows[n]["log_loss"], -sel_rows[n]["pr_auc"]))
    best_model = candidates[best_name][0]
    print(f"\n🏆 Model được chọn: {best_name}  (log loss val = {sel_rows[best_name]['log_loss']:.4f})")

    # Chỉ số trên val của MỌI nguồn có sẵn (kể cả nguồn không dùng để train)
    by_source = {}
    print("\n--- Model được chọn trên validation của từng nguồn ---")
    for src in SOURCES:
        vdf = load_frame(data_dir, src, "val")
        if vdf is None or vdf["label"].nunique() < 2:
            continue
        Xv, yv, _ = split_xy(vdf, columns)
        m = compute_metrics(yv, best_model.predict_proba(Xv)[:, 1])
        by_source[src] = m
        tag_txt = "(đã train)" if src in train_sources else "(CHƯA train — zero-shot)"
        print(f"{src:<10} {tag_txt:<26} PR-AUC={m['pr_auc']:.4f} ROC-AUC={m['roc_auc']:.4f} "
              f"LogLoss={m['log_loss']:.4f} ECE={m['ece']:.4f} | @0.5: P={m['precision']:.3f} R={m['recall']:.3f} FPR={m['fpr']:.3f}")

    sel_proba = best_model.predict_proba(X_sel)[:, 1]
    print("\n--- Bảng độ tin cậy trên val dùng để chọn model ---")
    print_reliability(y_sel, sel_proba)

    print("\n--- Ngưỡng tham khảo (mức candidate, val) ---")
    for t in [0.3, 0.5, 0.7, 0.8, 0.9]:
        m = compute_metrics(y_sel, sel_proba, threshold=t)
        print(f"  threshold={t:.1f} -> precision={m['precision']:.3f}, recall={m['recall']:.3f}, FPR={m['fpr']:.3f}")

    imps = average_importances(best_model, columns)
    print("\n--- 10 feature quan trọng nhất ---")
    for name, val in imps.head(10).items():
        print(f"  {name:<34} {val:.3f}")

    model_path = os.path.join(out_dir, "model.pkl")
    # compress=3: nén không mất dữ liệu, giảm vài lần dung lượng (file model sẽ nằm trong repo
    # để CI dùng; GitHub chặn file > 100 MB và mỗi lần retrain đều nằm lại trong lịch sử git)
    joblib.dump(best_model, model_path, compress=3)
    joblib.dump(columns, os.path.join(out_dir, "feature_columns.pkl"))
    size_mb = os.path.getsize(model_path) / 1e6
    card = {
        "tag": tag,
        "trained_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "train_on": args.train_on,
        "selected_model": best_name,
        "selection_criterion": "log_loss trên validation của nguồn dùng để train",
        "sklearn_version": sklearn.__version__,
        "n_train_candidates": int(len(X_train)),
        "n_train_repos": int(len(set(groups))),
        "n_features": len(columns),
        "training_prevalence": float(y_train.mean()),
        "calibration_cv": split_desc,
        "label_semantics": {s: LABEL_SEMANTICS[s] for s in train_sources},
        "validation_metrics_selection": sel_rows,
        "validation_metrics_by_source": by_source,
        "top_features": {k: float(v) for k, v in imps.head(10).items()},
        "note": "Chưa đánh giá trên test; dùng evaluate.py.",
    }
    with open(os.path.join(out_dir, "model_card.json"), "w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=2)
    print(f"\n-> Đã lưu vào models/experiments/{tag}/ (model.pkl {size_mb:.1f} MB, feature_columns.pkl, model_card.json)")
    if size_mb > 50:
        print("⚠️  model.pkl > 50 MB: GitHub cảnh báo từ 50 MB và chặn từ 100 MB. Cân nhắc XGBoost, "
              "giảm n_estimators/max_depth, hoặc Git LFS.")
    print(f"   Muốn dùng cho main.py: python -m src.train_ml --promote {tag}")


def promote(tag):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_dir = os.path.join(base_dir, "models")
    src_dir = os.path.join(models_dir, "experiments", tag)
    if not os.path.isdir(src_dir):
        raise SystemExit(f"Không thấy thí nghiệm '{tag}' trong {os.path.join(models_dir, 'experiments')}.")
    for src_name, dst_name in [("model.pkl", "secret_ml_model.pkl"),
                               ("feature_columns.pkl", "feature_columns.pkl"),
                               ("model_card.json", "model_card.json")]:
        shutil.copy2(os.path.join(src_dir, src_name), os.path.join(models_dir, dst_name))
    print(f"✅ Đã đưa thí nghiệm '{tag}' thành model chính thức trong {models_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train + hiệu chỉnh xác suất")
    parser.add_argument("--train-on", choices=list(TRAIN_SETS), default="creddata")
    parser.add_argument("--tag", default=None, help="Tên thí nghiệm (mặc định = --train-on)")
    parser.add_argument("--promote", metavar="TAG", help="Copy thí nghiệm TAG thành model chính thức rồi thoát")
    args = parser.parse_args()
    if args.promote:
        promote(args.promote)
    else:
        train(args)