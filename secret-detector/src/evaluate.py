"""
evaluate.py — đánh giá đầy đủ model đã train trên TEST SET

Chạy SAU train_ml.py:
    python -m src.evaluate [--threshold 0.7] [--boot 500]

Đầu ra (thư mục secret-detector/reports/):
    pr_curve.png             Precision-Recall (kèm Regex, Regex+Entropy)
    roc_curve.png            ROC
    confusion_matrix.png     Ma trận nhầm lẫn tại ngưỡng --threshold
    reliability.png          Biểu đồ hiệu chỉnh xác suất
    precision_vs_prevalence.png  Độ chính xác khi tỉ lệ secret ngoài đời thấp
    errors_test.csv          Các mẫu bị phân loại sai (nội dung đã che bớt)
    metrics.json             Toàn bộ số liệu
    evaluation_report.md     Bảng số liệu tóm tắt, dán thẳng vào báo cáo

Lưu ý trung thực:
  - Khoảng tin cậy ROC-AUC/PR-AUC dùng bootstrap THEO REPO (resample cả repo),
    chặt chẽ hơn bootstrap theo dòng vì các dòng cùng repo không độc lập.
  - FPR/Recall dùng khoảng tin cậy Wilson; số lỗi ít thì khoảng này rất rộng.
  - Mô phỏng tỉ lệ secret thấp dựa trên công thức Bayes với TPR/FPR đo được
    (giả định TPR/FPR không đổi khi đổi tỉ lệ lớp).
"""

import os
import json
import argparse
from math import sqrt

import joblib
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")  # không cần màn hình, chỉ lưu file PNG
import matplotlib.pyplot as plt
from sklearn.metrics import (
    average_precision_score,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

from src.entropy_scanner import scan_with_regex_and_entropy
from src.regex_scanner import scan_with_regex
from src.train_ml import NON_FEATURE_COLUMNS, compute_metrics

SEED = 42
PREVALENCES = [0.01, 0.02, 0.05, 0.10]


# ------------------------------------------------------------ thống kê
def wilson_interval(k, n, z=1.96):
    """Khoảng tin cậy 95% Wilson cho 1 tỉ lệ k/n."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def cluster_bootstrap_auc(y, proba, groups, n_boot, seed=SEED):
    """Khoảng tin cậy 95% cho ROC-AUC và PR-AUC, resample theo nhóm (repo)."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    idx_by_group = {g: np.where(groups == g)[0] for g in uniq}
    roc, pr = [], []
    for _ in range(n_boot):
        chosen = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_group[g] for g in chosen])
        yb = y[idx]
        if yb.min() == yb.max():
            continue
        roc.append(roc_auc_score(yb, proba[idx]))
        pr.append(average_precision_score(yb, proba[idx]))
    lo, hi = 2.5, 97.5
    return {
        "roc_auc_ci": [float(np.percentile(roc, lo)), float(np.percentile(roc, hi))],
        "pr_auc_ci": [float(np.percentile(pr, lo)), float(np.percentile(pr, hi))],
        "n_valid_boot": len(roc),
    }


def binary_metrics(y_true, pred):
    y_true = np.asarray(y_true)
    pred = np.asarray(pred)
    tp = int(((pred == 1) & (y_true == 1)).sum())
    fp = int(((pred == 1) & (y_true == 0)).sum())
    fn = int(((pred == 0) & (y_true == 1)).sum())
    tn = int(((pred == 0) & (y_true == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "fpr": fpr,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def ppv_at_prevalence(tpr, fpr, prevalence):
    """Precision kỳ vọng khi tỉ lệ secret = prevalence (công thức Bayes)."""
    num = prevalence * tpr
    den = num + (1 - prevalence) * fpr
    return num / den if den > 0 else 0.0


# ------------------------------------------------------------- baseline
def regex_predictions(texts):
    return np.array([1 if scan_with_regex(str(t)) else 0 for t in texts])


def regex_entropy_predictions(texts, entropy_threshold=4.0):
    return np.array([1 if scan_with_regex_and_entropy(str(t), entropy_threshold) else 0 for t in texts])


def redact(text, keep=10):
    """Che bớt nội dung khi xuất file lỗi (tránh lộ secret thật khi dùng dữ liệu thật)."""
    text = str(text)
    return text[:keep] + "…[đã che]" if len(text) > keep else text


# --------------------------------------------------------------- đồ thị
def save_fig(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_pr(y, proba, threshold, baselines, prevalence, path):
    precision, recall, thr = precision_recall_curve(y, proba)
    fig, ax = plt.subplots(figsize=(6.5, 5.2))
    ax.plot(recall, precision, lw=2, label=f"ML đã hiệu chỉnh (PR-AUC = {average_precision_score(y, proba):.3f})")
    ax.axhline(prevalence, ls="--", color="gray", lw=1, label=f"Ngẫu nhiên (tỉ lệ secret = {prevalence:.2f})")

    m = binary_metrics(y, (proba >= threshold).astype(int))
    ax.scatter([m["recall"]], [m["precision"]], marker="*", s=180, color="tab:red", zorder=5,
               label=f"ML tại ngưỡng {threshold}")
    colors = {"Regex": "tab:green", "Regex + Entropy": "tab:orange"}
    for name, bm in baselines.items():
        ax.scatter([bm["recall"]], [bm["precision"]], s=70, color=colors.get(name), zorder=5, label=name)

    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Đường Precision–Recall (tập test)")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left", fontsize=8)
    save_fig(fig, path)


def plot_roc(y, proba, path):
    fpr, tpr, _ = roc_curve(y, proba)
    fig, ax = plt.subplots(figsize=(5.5, 5.2))
    ax.plot(fpr, tpr, lw=2, label=f"ML (ROC-AUC = {roc_auc_score(y, proba):.3f})")
    ax.plot([0, 1], [0, 1], "--", color="gray", lw=1, label="Ngẫu nhiên")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("Đường ROC (tập test)")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right", fontsize=8)
    save_fig(fig, path)


def plot_confusion(m, threshold, path):
    cm = np.array([[m["tn"], m["fp"]], [m["fn"], m["tp"]]])
    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    ax.imshow(cm, cmap="Blues")
    row_sums = cm.sum(axis=1, keepdims=True)
    for i in range(2):
        for j in range(2):
            pct = cm[i, j] / row_sums[i, 0] if row_sums[i, 0] else 0
            ax.text(j, i, f"{cm[i, j]}\n({pct:.1%})", ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=12)
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Dự đoán:\nKhông", "Dự đoán:\nSecret"])
    ax.set_yticklabels(["Thực tế:\nKhông", "Thực tế:\nSecret"])
    ax.set_title(f"Ma trận nhầm lẫn (ngưỡng {threshold})")
    save_fig(fig, path)


def plot_reliability(y, proba, path, n_bins=10):
    y = np.asarray(y)
    bins = np.linspace(0, 1, n_bins + 1)
    ids = np.clip(np.digitize(proba, bins[1:-1]), 0, n_bins - 1)
    xs, ys, ns = [], [], []
    for b in range(n_bins):
        mask = ids == b
        if mask.any():
            xs.append(proba[mask].mean())
            ys.append(y[mask].mean())
            ns.append(int(mask.sum()))
    fig, ax = plt.subplots(figsize=(5.5, 5.2))
    ax.plot([0, 1], [0, 1], "--", color="gray", lw=1, label="Hiệu chỉnh hoàn hảo")
    ax.scatter(xs, ys, s=[20 + 6 * sqrt(n) for n in ns], color="tab:blue", alpha=0.8, label="Các bin (kích thước ∝ số mẫu)")
    ax.plot(xs, ys, color="tab:blue", lw=1)
    ax.set_xlabel("Xác suất dự đoán trung bình")
    ax.set_ylabel("Tỉ lệ secret thật")
    ax.set_title("Biểu đồ hiệu chỉnh xác suất (tập test)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=8)
    save_fig(fig, path)


def plot_precision_vs_prevalence(curves, test_prevalence, path):
    grid = np.logspace(np.log10(0.005), np.log10(0.5), 60)
    fig, ax = plt.subplots(figsize=(6.5, 5))
    styles = ["-", "-", "--"]  # Regex và Regex+Entropy gần trùng nhau -> nét đứt để vẫn thấy cả hai
    for (name, (tpr, fpr)), ls in zip(curves.items(), styles):
        ax.plot(grid, [ppv_at_prevalence(tpr, fpr, p) for p in grid], lw=2, ls=ls, label=name)
    ax.axvline(test_prevalence, ls=":", color="gray", lw=1)
    ax.text(test_prevalence, 0.03, " tỉ lệ trong tập test", rotation=90, fontsize=8, color="gray", va="bottom")
    ax.set_xscale("log")
    ax.set_xlabel("Tỉ lệ secret thực tế trong mã nguồn (thang log)")
    ax.set_ylabel("Precision kỳ vọng")
    ax.set_ylim(0, 1.02)
    ax.set_title("Precision khi tỉ lệ secret ngoài đời thấp")
    ax.grid(alpha=0.3, which="both")
    ax.legend(loc="upper left", fontsize=8)
    save_fig(fig, path)


# --------------------------------------------------------------- chính
def run(threshold, n_boot):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    models_dir = os.path.join(base_dir, "models")
    out_dir = os.path.join(base_dir, "reports")
    os.makedirs(out_dir, exist_ok=True)

    clf = joblib.load(os.path.join(models_dir, "secret_ml_model.pkl"))
    cols = joblib.load(os.path.join(models_dir, "feature_columns.pkl"))
    test_raw = pd.read_csv(os.path.join(data_dir, "test.csv"))
    test_feat = pd.read_csv(os.path.join(data_dir, "test_features.csv"))
    if len(test_raw) != len(test_feat):
        raise ValueError("test.csv và test_features.csv lệch số dòng — chạy lại build_features.py.")

    y = test_raw["label"].to_numpy()
    X = test_feat.drop(columns=[c for c in NON_FEATURE_COLUMNS if c in test_feat.columns]).reindex(columns=cols, fill_value=0)
    proba = clf.predict_proba(X)[:, 1]
    prevalence = float(y.mean())
    groups = test_raw["repo"].to_numpy() if "repo" in test_raw.columns else np.arange(len(y))

    # ---- số liệu ML ở ngưỡng 0.5 và ngưỡng triển khai
    prob_metrics = compute_metrics(y, proba, threshold=0.5)  # roc_auc, pr_auc, brier, log_loss, ece
    ml_at = {str(t): binary_metrics(y, (proba >= t).astype(int)) for t in sorted({0.5, threshold})}
    ml = ml_at[str(threshold)]
    ci = cluster_bootstrap_auc(y, proba, groups, n_boot)
    recall_ci = wilson_interval(ml["tp"], ml["tp"] + ml["fn"])
    fpr_ci = wilson_interval(ml["fp"], ml["fp"] + ml["tn"])

    # ---- baseline
    texts = test_raw["text"].astype(str).tolist()
    baselines = {
        "Regex": binary_metrics(y, regex_predictions(texts)),
        "Regex + Entropy": binary_metrics(y, regex_entropy_predictions(texts)),
    }

    # ---- mô phỏng tỉ lệ secret thấp
    tpr_ml = ml["recall"]
    sim = {}
    for p in PREVALENCES:
        sim[str(p)] = {
            "ML": ppv_at_prevalence(tpr_ml, ml["fpr"], p),
            "ML (FPR cận trên 95%)": ppv_at_prevalence(tpr_ml, fpr_ci[1], p),
            **{name: ppv_at_prevalence(b["recall"], b["fpr"], p) for name, b in baselines.items()},
        }

    # ---- phân tích lỗi theo loại mẫu
    t = test_raw.copy()
    t["proba"] = proba
    t["pred"] = (proba >= threshold).astype(int)
    errors = t[t["pred"] != t["label"]].copy()
    errors["text"] = errors["text"].map(redact)
    errors.sort_values("proba", ascending=False).to_csv(os.path.join(out_dir, "errors_test.csv"), index=False)
    by_type = (
        t.assign(wrong=(t["pred"] != t["label"]).astype(int))
        .groupby(["type", "label"])["wrong"].agg(["sum", "count"]).reset_index()
        .rename(columns={"sum": "so_loi", "count": "so_mau"})
    )

    # ---- đồ thị
    plot_pr(y, proba, threshold, baselines, prevalence, os.path.join(out_dir, "pr_curve.png"))
    plot_roc(y, proba, os.path.join(out_dir, "roc_curve.png"))
    plot_confusion(ml, threshold, os.path.join(out_dir, "confusion_matrix.png"))
    plot_reliability(y, proba, os.path.join(out_dir, "reliability.png"))
    curves = {
        f"ML (ngưỡng {threshold})": (ml["recall"], ml["fpr"]),
        "Regex": (baselines["Regex"]["recall"], baselines["Regex"]["fpr"]),
        "Regex + Entropy": (baselines["Regex + Entropy"]["recall"], baselines["Regex + Entropy"]["fpr"]),
    }
    plot_precision_vs_prevalence(curves, prevalence, os.path.join(out_dir, "precision_vs_prevalence.png"))

    # ---- lưu số liệu
    result = {
        "n_test": int(len(y)),
        "n_repos_test": int(len(np.unique(groups))),
        "test_prevalence": prevalence,
        "threshold": threshold,
        "ml_probabilistic": prob_metrics,
        "ml_binary": ml_at,
        "ml_confidence_intervals": {**ci, "recall_ci_wilson": list(recall_ci), "fpr_ci_wilson": list(fpr_ci)},
        "baselines": baselines,
        "precision_at_prevalence": sim,
        "errors_by_type": by_type.to_dict(orient="records"),
    }
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    write_markdown(result, by_type, os.path.join(out_dir, "evaluation_report.md"))
    print_console(result, by_type, out_dir)


def fmt_pct(x):
    return f"{x * 100:.2f}%"


def write_markdown(r, by_type, path):
    th = str(r["threshold"])
    ml = r["ml_binary"][th]
    ci = r["ml_confidence_intervals"]
    p = r["ml_probabilistic"]
    lines = [
        "# Báo cáo đánh giá (tập test)",
        "",
        f"Số mẫu: {r['n_test']} | Số repo: {r['n_repos_test']} | Tỉ lệ secret: {fmt_pct(r['test_prevalence'])} | Ngưỡng ML: {r['threshold']}",
        "",
        "## 1. So sánh 3 phương pháp",
        "",
        "| Phương pháp | Precision | Recall | F1 | FPR |",
        "|---|---|---|---|---|",
    ]
    for name, m in [("Regex", r["baselines"]["Regex"]),
                    ("Regex + Entropy", r["baselines"]["Regex + Entropy"]),
                    (f"Regex + Entropy + ML (ngưỡng {r['threshold']})", ml)]:
        lines.append(f"| {name} | {fmt_pct(m['precision'])} | {fmt_pct(m['recall'])} | {fmt_pct(m['f1'])} | {fmt_pct(m['fpr'])} |")
    lines += [
        "",
        "## 2. Chỉ số của mô hình ML",
        "",
        "| Chỉ số | Giá trị | Khoảng tin cậy 95% |",
        "|---|---|---|",
        f"| ROC-AUC | {p['roc_auc']:.4f} | [{ci['roc_auc_ci'][0]:.4f}, {ci['roc_auc_ci'][1]:.4f}] (bootstrap theo repo) |",
        f"| PR-AUC | {p['pr_auc']:.4f} | [{ci['pr_auc_ci'][0]:.4f}, {ci['pr_auc_ci'][1]:.4f}] (bootstrap theo repo) |",
        f"| Recall | {fmt_pct(ml['recall'])} | [{fmt_pct(ci['recall_ci_wilson'][0])}, {fmt_pct(ci['recall_ci_wilson'][1])}] (Wilson) |",
        f"| FPR | {fmt_pct(ml['fpr'])} | [{fmt_pct(ci['fpr_ci_wilson'][0])}, {fmt_pct(ci['fpr_ci_wilson'][1])}] (Wilson) |",
        f"| Brier | {p['brier']:.4f} | |",
        f"| ECE | {p['ece']:.4f} | |",
        "",
        f"Confusion matrix: TN={ml['tn']}, FP={ml['fp']}, FN={ml['fn']}, TP={ml['tp']}",
        "",
        "## 3. Precision khi tỉ lệ secret ngoài đời thấp",
        "",
        "| Tỉ lệ secret | ML | ML (FPR cận trên) | Regex | Regex + Entropy |",
        "|---|---|---|---|---|",
    ]
    for prev, row in r["precision_at_prevalence"].items():
        lines.append(f"| {float(prev):.0%} | {fmt_pct(row['ML'])} | {fmt_pct(row['ML (FPR cận trên 95%)'])} | "
                     f"{fmt_pct(row['Regex'])} | {fmt_pct(row['Regex + Entropy'])} |")
    lines += ["", "## 4. Lỗi theo loại mẫu", "", "| Loại | Nhãn | Số lỗi | Số mẫu |", "|---|---|---|---|"]
    for _, row in by_type[by_type["so_loi"] > 0].iterrows():
        lines.append(f"| {row['type']} | {row['label']} | {row['so_loi']} | {row['so_mau']} |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def print_console(r, by_type, out_dir):
    th = str(r["threshold"])
    ml = r["ml_binary"][th]
    ci = r["ml_confidence_intervals"]
    p = r["ml_probabilistic"]
    print("\n" + "=" * 78)
    print(f"ĐÁNH GIÁ TRÊN TEST SET | {r['n_test']} mẫu | {r['n_repos_test']} repo | tỉ lệ secret {fmt_pct(r['test_prevalence'])}")
    print("=" * 78)
    print(f"{'Phương pháp':<34}{'Precision':>10}{'Recall':>9}{'F1':>9}{'FPR':>9}")
    rows = [("Regex", r["baselines"]["Regex"]), ("Regex + Entropy", r["baselines"]["Regex + Entropy"]),
            (f"Regex + Entropy + ML (@{r['threshold']})", ml)]
    for name, m in rows:
        print(f"{name:<34}{fmt_pct(m['precision']):>10}{fmt_pct(m['recall']):>9}{fmt_pct(m['f1']):>9}{fmt_pct(m['fpr']):>9}")
    print(f"\nROC-AUC = {p['roc_auc']:.4f}  95% CI [{ci['roc_auc_ci'][0]:.4f}, {ci['roc_auc_ci'][1]:.4f}]")
    print(f"PR-AUC  = {p['pr_auc']:.4f}  95% CI [{ci['pr_auc_ci'][0]:.4f}, {ci['pr_auc_ci'][1]:.4f}]")
    print(f"Recall  = {fmt_pct(ml['recall'])}  95% CI [{fmt_pct(ci['recall_ci_wilson'][0])}, {fmt_pct(ci['recall_ci_wilson'][1])}]")
    print(f"FPR     = {fmt_pct(ml['fpr'])}  95% CI [{fmt_pct(ci['fpr_ci_wilson'][0])}, {fmt_pct(ci['fpr_ci_wilson'][1])}]")
    print(f"Brier = {p['brier']:.4f} | ECE = {p['ece']:.4f}")
    print(f"Confusion matrix: TN={ml['tn']} FP={ml['fp']} FN={ml['fn']} TP={ml['tp']}")

    print("\nPrecision kỳ vọng khi tỉ lệ secret ngoài đời thấp (công thức Bayes):")
    print(f"{'Tỉ lệ secret':<14}{'ML':>9}{'ML (xấu nhất)':>16}{'Regex':>9}{'Regex+Ent':>12}")
    for prev, row in r["precision_at_prevalence"].items():
        print(f"{float(prev):<14.0%}{fmt_pct(row['ML']):>9}{fmt_pct(row['ML (FPR cận trên 95%)']):>16}"
              f"{fmt_pct(row['Regex']):>9}{fmt_pct(row['Regex + Entropy']):>12}")

    bad = by_type[by_type["so_loi"] > 0]
    print("\nLỗi theo loại mẫu:")
    print(bad.to_string(index=False) if len(bad) else "  (không có lỗi)")
    print(f"\n✅ Đã lưu 5 đồ thị, metrics.json, evaluation_report.md, errors_test.csv vào: {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Đánh giá model trên test set")
    parser.add_argument("--threshold", type=float, default=0.7, help="Ngưỡng phân loại của ML (khớp --threshold của main.py)")
    parser.add_argument("--boot", type=int, default=500, help="Số lần bootstrap theo repo")
    args = parser.parse_args()
    run(args.threshold, args.boot)