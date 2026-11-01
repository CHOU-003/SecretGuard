"""
evaluate.py (v2) — đánh giá CẤP DÒNG trên TEST SET của cả hai nguồn

Chạy SAU train_ml.py, khi đã chốt model dựa trên kết quả VALIDATION:
    python -m src.evaluate                                  # model chính thức (production)
    python -m src.evaluate --models creddata mixed synthetic   # so sánh nhiều thí nghiệm
    python -m src.evaluate --models creddata --split val       # quét ngưỡng trên VALIDATION (không chạm test)

Đơn vị đánh giá là DÒNG mã nguồn, đúng với thứ người dùng thấy:
    điểm của dòng = điểm cao nhất của các candidate trong dòng (scoring.score_lines)
    dòng bị cảnh báo khi điểm >= --threshold (mặc định 0.7, khớp main.py)
Dòng không có candidate nào có điểm 0 -> không bị cảnh báo. Nếu đó là dòng secret thật
thì đây là recall bị mất ở bước TRÍCH, không phải lỗi của ML; bảng "phễu recall" tách
riêng hai nguồn mất mát này.

Test set:
    synthetic : data/test.csv
    creddata  : các dòng split == 'test' trong data/external/creddata.csv

Đầu ra (reports/<model>/): evaluation_report.md, metrics.json, errors_<nguồn>.csv (nội dung
đã che), 5 đồ thị PNG. Nếu chạy nhiều model: reports/model_comparison.md.

Quy tắc dùng test:
  * Chốt model bằng validation (train_ml.py in sẵn) TRƯỚC khi chạy file này. Nếu chọn model
    hay chỉnh candidate dựa vào kết quả test thì test không còn độc lập.
  * Mỗi lần chạy trên test được ghi vào reports/test_access_log.txt để báo cáo nêu rõ số lần chạm test.
  * Chọn ngưỡng cảnh báo/chặn bằng `--split val` (bảng quét ngưỡng), KHÔNG chọn trên test.

Hạn chế cần nêu trong báo cáo:
  * CredData chỉ chứa các dòng nghi vấn mà công cụ đã gắn cờ rồi người duyệt (không phải
    mọi dòng của repo), nên tỉ lệ secret ở đây (~20%) cao hơn nhiều so với tỉ lệ thật.
    Mục "Precision khi tỉ lệ secret thấp" mô phỏng điều đó bằng công thức Bayes (giả định
    TPR/FPR không đổi khi đổi tỉ lệ lớp).
  * Nhãn hai nguồn khác định nghĩa (credential trong thư mục test: CredData = secret,
    dữ liệu tổng hợp = không phải), nên không gộp điểm hai nguồn thành một con số.
  * Khoảng tin cậy ROC/PR-AUC: bootstrap theo repo. Recall/FPR: Wilson (rộng nếu ít lỗi).
"""

import os
import json
import argparse
import datetime
from math import sqrt

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

from src.entropy_scanner import scan_with_regex_and_entropy
from src.feature_extractor import is_test_path_fn
from src.regex_scanner import scan_with_regex
from src.scoring import load_model, score_lines
from src.train_ml import expected_calibration_error

SEED = 42
PREVALENCES = [0.01, 0.02, 0.05, 0.10]
SWEEP_THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
SOURCES = ("synthetic", "creddata")
SOURCE_LABELS = {"synthetic": "Dữ liệu tổng hợp", "creddata": "CredData"}
COLORS = {"Regex": "tab:green", "Regex + Entropy": "tab:orange", "Chỉ trích candidate (không ML)": "tab:gray"}


# ------------------------------------------------------------- thống kê
def wilson_interval(k, n, z=1.96):
    """Khoảng tin cậy 95% Wilson cho tỉ lệ k/n."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def cluster_bootstrap_auc(y, score, groups, n_boot, seed=SEED):
    """Khoảng tin cậy 95% cho ROC-AUC và PR-AUC, resample theo repo."""
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
        roc.append(roc_auc_score(yb, score[idx]))
        pr.append(average_precision_score(yb, score[idx]))
    if not roc:
        return {"roc_auc_ci": [None, None], "pr_auc_ci": [None, None], "n_valid_boot": 0}
    return {
        "roc_auc_ci": [float(np.percentile(roc, 2.5)), float(np.percentile(roc, 97.5))],
        "pr_auc_ci": [float(np.percentile(pr, 2.5)), float(np.percentile(pr, 97.5))],
        "n_valid_boot": len(roc),
    }


def binary_metrics(y_true, pred):
    y_true, pred = np.asarray(y_true), np.asarray(pred)
    tp = int(((pred == 1) & (y_true == 1)).sum())
    fp = int(((pred == 1) & (y_true == 0)).sum())
    fn = int(((pred == 0) & (y_true == 1)).sum())
    tn = int(((pred == 0) & (y_true == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "fpr": fpr, "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def ppv_at_prevalence(tpr, fpr, prevalence):
    """Precision kỳ vọng khi tỉ lệ secret = prevalence (công thức Bayes)."""
    num = prevalence * tpr
    den = num + (1 - prevalence) * fpr
    return num / den if den > 0 else 0.0


def fmt_pct(x):
    return "n/a" if x is None else f"{x * 100:.2f}%"


# ------------------------------------------------------------- baseline
def regex_predictions(texts):
    return np.array([1 if scan_with_regex(str(t)) else 0 for t in texts])


def regex_entropy_predictions(texts, entropy_threshold=4.0):
    return np.array([1 if scan_with_regex_and_entropy(str(t), entropy_threshold) else 0 for t in texts])


def mask_text(text, secrets, width=120):
    """Che giá trị nghi vấn trong dòng khi xuất file lỗi. Không biết giá trị -> cắt ngắn."""
    shown = str(text)
    masked = False
    for s in secrets:
        if s and len(s) >= 4 and s in shown:
            shown, masked = shown.replace(s, "<VALUE>"), True
    if not masked and len(shown) > 12:
        shown = shown[:12] + "…[đã che]"
    return shown[:width] + ("…" if len(shown) > width else "")


def save_fig(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ------------------------------------------------------------ nạp test
def load_test_sets(data_dir, wanted, split="test"):
    sets = {}
    if "synthetic" in wanted:
        path = os.path.join(data_dir, f"{split}.csv")
        if os.path.exists(path):
            sets["synthetic"] = pd.read_csv(path, keep_default_na=False)
        else:
            print(f"⚠️  Bỏ qua 'synthetic': chưa có data/{split}.csv (build_dataset.py).")
    if "creddata" in wanted:
        path = os.path.join(data_dir, "external", "creddata.csv")
        if os.path.exists(path):
            df = pd.read_csv(path, keep_default_na=False)
            sets["creddata"] = df[df["split"] == split].reset_index(drop=True)
        else:
            print("⚠️  Bỏ qua 'creddata': chưa có data/external/creddata.csv (import_external.py).")
    return sets


# ------------------------------------------------------- đánh giá 1 nguồn
def evaluate_source(df, model, columns, threshold, n_boot):
    texts = df["text"].astype(str).tolist()
    paths = df["file_path"].astype(str).tolist() if "file_path" in df.columns else [""] * len(df)
    y = df["label"].astype(int).to_numpy()
    groups = df["repo"].astype(str).to_numpy() if "repo" in df.columns else np.array([str(i) for i in range(len(df))])

    line_scores = score_lines(zip(texts, paths), model, columns)
    score = np.array([s.score for s in line_scores])
    n_cand = np.array([s.n_candidates for s in line_scores])
    ml_name = f"ML (ngưỡng {threshold})"

    preds = {
        "Regex": regex_predictions(texts),
        "Regex + Entropy": regex_entropy_predictions(texts),
        "Chỉ trích candidate (không ML)": (n_cand > 0).astype(int),
        ml_name: (score >= threshold).astype(int),
    }
    metrics = {name: binary_metrics(y, p) for name, p in preds.items()}
    ml = metrics[ml_name]

    pos = y == 1
    funnel = {
        "dong_secret": int(pos.sum()),
        "co_candidate": int((pos & (n_cand > 0)).sum()),
        "bi_canh_bao": int((pos & (score >= threshold)).sum()),
    }

    shown = n_cand > 0  # dòng thực sự có điểm hiển thị cho người dùng
    prob = {
        "roc_auc": float(roc_auc_score(y, score)),
        "pr_auc": float(average_precision_score(y, score)),
        "n_lines_with_score": int(shown.sum()),
        "ece_lines_with_candidate": expected_calibration_error(y[shown], score[shown]) if shown.sum() else None,
        "brier_lines_with_candidate": float(brier_score_loss(y[shown], score[shown])) if shown.sum() else None,
    }
    ci = cluster_bootstrap_auc(y, score, groups, n_boot)
    ci["recall_ci_wilson"] = list(wilson_interval(ml["tp"], ml["tp"] + ml["fn"]))
    ci["fpr_ci_wilson"] = list(wilson_interval(ml["fp"], ml["fp"] + ml["tn"]))

    sweep = {str(t): binary_metrics(y, (score >= t).astype(int)) for t in SWEEP_THRESHOLDS}

    prevalence_sim = {
        str(p): {
            "ML": ppv_at_prevalence(ml["recall"], ml["fpr"], p),
            "ML (FPR cận trên 95%)": ppv_at_prevalence(ml["recall"], ci["fpr_ci_wilson"][1], p),
            "Regex": ppv_at_prevalence(metrics["Regex"]["recall"], metrics["Regex"]["fpr"], p),
            "Regex + Entropy": ppv_at_prevalence(metrics["Regex + Entropy"]["recall"], metrics["Regex + Entropy"]["fpr"], p),
        }
        for p in PREVALENCES
    }

    # lỗi theo loại mẫu
    ml_pred = preds[ml_name]
    by_type = (
        pd.DataFrame({"type": df["type"].astype(str), "label": y,
                      "loi_ML": (ml_pred != y).astype(int), "loi_Regex": (preds["Regex"] != y).astype(int)})
        .groupby(["label", "type"]).agg(so_mau=("label", "size"), loi_ML=("loi_ML", "sum"), loi_Regex=("loi_Regex", "sum"))
        .reset_index().sort_values("loi_ML", ascending=False)
    )

    # theo ngữ cảnh đường dẫn
    in_test = np.array([is_test_path_fn(p) for p in paths])
    by_path = {}
    for name, mask in (("thư mục test/mẫu", in_test), ("thư mục khác", ~in_test)):
        if mask.sum() == 0:
            continue
        m = binary_metrics(y[mask], ml_pred[mask])
        by_path[name] = {"so_dong": int(mask.sum()), "ti_le_secret": float(y[mask].mean()), **m}

    # file lỗi (đã che)
    wrong = np.where(ml_pred != y)[0]
    value_col = df["value"].astype(str).tolist() if "value" in df.columns else [""] * len(df)
    errors = pd.DataFrame([{
        "repo": groups[i], "file_path": paths[i], "type": df["type"].iloc[i], "label": int(y[i]),
        "loai_loi": "FP (báo nhầm)" if y[i] == 0 else "FN (bỏ sót)",
        "score": round(float(score[i]), 4), "co_candidate": int(n_cand[i] > 0),
        "nguon_candidate": line_scores[i].best.source if line_scores[i].best else "",
        "text_da_che": mask_text(texts[i], [value_col[i], line_scores[i].best.value if line_scores[i].best else ""]),
    } for i in wrong]).sort_values("score", ascending=False) if len(wrong) else pd.DataFrame()

    return {
        "n_lines": int(len(y)), "n_repos": int(len(np.unique(groups))), "prevalence": float(y.mean()),
        "ml_name": ml_name, "metrics": metrics, "probabilistic": prob, "confidence_intervals": ci,
        "funnel": funnel, "sweep": sweep, "precision_at_prevalence": prevalence_sim,
        "errors_by_type": by_type.to_dict(orient="records"), "by_path_context": by_path,
    }, {"y": y, "score": score, "n_cand": n_cand, "preds": preds, "errors": errors}


# ---------------------------------------------------------------- đồ thị
def _axes(n, w=5.8, h=5.0):
    fig, axes = plt.subplots(1, n, figsize=(w * n, h))
    return fig, np.atleast_1d(axes)


def plot_pr(results, arrays, threshold, path):
    fig, axes = _axes(len(results), w=6.2)
    for ax, (src, r) in zip(axes, results.items()):
        y, score = arrays[src]["y"], arrays[src]["score"]
        prec, rec, _ = precision_recall_curve(y, score)
        ax.plot(rec, prec, lw=2, color="tab:blue", label=f"ML (PR-AUC = {r['probabilistic']['pr_auc']:.3f})")
        ax.axhline(r["prevalence"], ls="--", color="gray", lw=1, label=f"Ngẫu nhiên ({r['prevalence']:.2f})")
        m = r["metrics"][r["ml_name"]]
        ax.scatter([m["recall"]], [m["precision"]], marker="*", s=200, color="tab:red", zorder=6, label=f"ML @ {threshold}")
        for name, color in COLORS.items():
            bm = r["metrics"][name]
            ax.scatter([bm["recall"]], [bm["precision"]], s=70, color=color, zorder=5, label=name)
        ax.set(xlabel="Recall", ylabel="Precision", xlim=(0, 1.02), ylim=(0, 1.02),
               title=f"Precision–Recall, cấp dòng\n{SOURCE_LABELS[src]}")
        ax.grid(alpha=0.3)
        ax.legend(loc="lower left", fontsize=7)
    save_fig(fig, path)


def plot_roc(results, arrays, path):
    fig, ax = plt.subplots(figsize=(5.6, 5.2))
    for src, r in results.items():
        fpr, tpr, _ = roc_curve(arrays[src]["y"], arrays[src]["score"])
        ax.plot(fpr, tpr, lw=2, label=f"{SOURCE_LABELS[src]} (AUC = {r['probabilistic']['roc_auc']:.3f})")
    ax.plot([0, 1], [0, 1], "--", color="gray", lw=1, label="Ngẫu nhiên")
    ax.set(xlabel="False Positive Rate", ylabel="True Positive Rate", title="Đường ROC, cấp dòng")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right", fontsize=8)
    save_fig(fig, path)


def plot_confusion(results, threshold, path):
    fig, axes = _axes(len(results), w=5.2, h=4.6)
    for ax, (src, r) in zip(axes, results.items()):
        m = r["metrics"][r["ml_name"]]
        cm = np.array([[m["tn"], m["fp"]], [m["fn"], m["tp"]]])
        ax.imshow(cm, cmap="Blues")
        rows = cm.sum(axis=1, keepdims=True)
        for i in range(2):
            for j in range(2):
                pct = cm[i, j] / rows[i, 0] if rows[i, 0] else 0
                ax.text(j, i, f"{cm[i, j]}\n({pct:.1%})", ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=11)
        ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
        ax.set_xticklabels(["Dự đoán:\nKhông", "Dự đoán:\nSecret"])
        ax.set_yticklabels(["Thực tế:\nKhông", "Thực tế:\nSecret"])
        ax.set_title(f"Ma trận nhầm lẫn (ngưỡng {threshold})\n{SOURCE_LABELS[src]}")
    save_fig(fig, path)


def plot_reliability(results, arrays, path, n_bins=10):
    fig, axes = _axes(len(results))
    for ax, (src, r) in zip(axes, results.items()):
        a = arrays[src]
        shown = a["n_cand"] > 0
        y, s = a["y"][shown], a["score"][shown]
        bins = np.linspace(0, 1, n_bins + 1)
        ids = np.clip(np.digitize(s, bins[1:-1]), 0, n_bins - 1)
        xs, ys, ns = [], [], []
        for b in range(n_bins):
            mask = ids == b
            if mask.any():
                xs.append(s[mask].mean()); ys.append(y[mask].mean()); ns.append(int(mask.sum()))
        ax.plot([0, 1], [0, 1], "--", color="gray", lw=1, label="Hiệu chỉnh hoàn hảo")
        ax.scatter(xs, ys, s=[20 + 6 * sqrt(n) for n in ns], color="tab:blue", alpha=0.8, label="Các bin (kích thước ∝ số mẫu)")
        ax.plot(xs, ys, color="tab:blue", lw=1)
        ax.set(xlabel="Điểm dòng trung bình", ylabel="Tỉ lệ dòng thật sự là secret",
               title=f"Độ tin cậy (chỉ dòng có candidate)\n{SOURCE_LABELS[src]}")
        ax.grid(alpha=0.3)
        ax.legend(loc="upper left", fontsize=7)
    save_fig(fig, path)


def plot_precision_vs_prevalence(results, path):
    fig, axes = _axes(len(results), w=6.0)
    grid = np.logspace(np.log10(0.005), np.log10(0.5), 60)
    styles = {"ML": "-", "Regex": "-", "Regex + Entropy": "--"}
    for ax, (src, r) in zip(axes, results.items()):
        for name, ls in styles.items():
            m = r["metrics"][r["ml_name"]] if name == "ML" else r["metrics"][name]
            ax.plot(grid, [ppv_at_prevalence(m["recall"], m["fpr"], p) for p in grid], lw=2, ls=ls,
                    label=name if name != "ML" else r["ml_name"])
        ax.axvline(r["prevalence"], ls=":", color="gray", lw=1)
        ax.set(xscale="log", xlabel="Tỉ lệ secret thực tế (thang log)", ylabel="Precision kỳ vọng", ylim=(0, 1.02),
               title=f"Precision khi tỉ lệ secret thấp\n{SOURCE_LABELS[src]}")
        ax.grid(alpha=0.3, which="both")
        ax.legend(loc="upper left", fontsize=7)
    save_fig(fig, path)


# ------------------------------------------------------------- báo cáo
def write_report(path, tag, threshold, results, split="test"):
    L = [f"# Báo cáo đánh giá cấp dòng ({'VALIDATION' if split == 'val' else 'TEST'}) — model `{tag}`", "",
         f"Ngưỡng cảnh báo: {threshold}. Điểm của dòng = điểm cao nhất của các candidate trong dòng.", ""]
    for src, r in results.items():
        ml, ci, pr = r["metrics"][r["ml_name"]], r["confidence_intervals"], r["probabilistic"]
        f = r["funnel"]
        L += [f"## {SOURCE_LABELS[src]} (test: {r['n_lines']} dòng, {r['n_repos']} repo, {fmt_pct(r['prevalence'])} là secret)", "",
              "| Phương pháp | Precision | Recall | F1 | FPR | FP | FN |", "|---|---|---|---|---|---|---|"]
        for name, m in r["metrics"].items():
            L.append(f"| {name} | {fmt_pct(m['precision'])} | {fmt_pct(m['recall'])} | {fmt_pct(m['f1'])} | "
                     f"{fmt_pct(m['fpr'])} | {m['fp']} | {m['fn']} |")
        auc_roc = ci["roc_auc_ci"]; auc_pr = ci["pr_auc_ci"]
        rng = lambda a: "n/a" if a[0] is None else f"[{a[0]:.4f}, {a[1]:.4f}]"
        L += ["", f"- ROC-AUC = {pr['roc_auc']:.4f}, 95% CI {rng(auc_roc)} (bootstrap theo repo)",
              f"- PR-AUC = {pr['pr_auc']:.4f}, 95% CI {rng(auc_pr)} (bootstrap theo repo)",
              f"- Recall ML = {fmt_pct(ml['recall'])}, 95% CI [{fmt_pct(ci['recall_ci_wilson'][0])}, {fmt_pct(ci['recall_ci_wilson'][1])}] (Wilson)",
              f"- FPR ML = {fmt_pct(ml['fpr'])}, 95% CI [{fmt_pct(ci['fpr_ci_wilson'][0])}, {fmt_pct(ci['fpr_ci_wilson'][1])}] (Wilson)",
              f"- ECE (dòng có candidate) = {pr['ece_lines_with_candidate']:.4f}" if pr["ece_lines_with_candidate"] is not None else "- ECE: n/a",
              "", "**Phễu recall** (mất mát nằm ở đâu):", "",
              "| Dòng secret | Có ≥1 candidate | Bị cảnh báo |", "|---|---|---|",
              f"| {f['dong_secret']} | {f['co_candidate']} ({fmt_pct(f['co_candidate'] / max(f['dong_secret'], 1))}) | "
              f"{f['bi_canh_bao']} ({fmt_pct(f['bi_canh_bao'] / max(f['dong_secret'], 1))}) |",
              "", "**Quét ngưỡng (ML):**", "", "| Ngưỡng | Precision | Recall | FPR |", "|---|---|---|---|"]
        for t, m in r["sweep"].items():
            L.append(f"| {t} | {fmt_pct(m['precision'])} | {fmt_pct(m['recall'])} | {fmt_pct(m['fpr'])} |")
        L += ["", "**Precision kỳ vọng khi tỉ lệ secret ngoài đời thấp:**", "",
              "| Tỉ lệ secret | ML | ML (FPR cận trên) | Regex | Regex + Entropy |", "|---|---|---|---|---|"]
        for p, row in r["precision_at_prevalence"].items():
            L.append(f"| {float(p):.0%} | {fmt_pct(row['ML'])} | {fmt_pct(row['ML (FPR cận trên 95%)'])} | "
                     f"{fmt_pct(row['Regex'])} | {fmt_pct(row['Regex + Entropy'])} |")
        L += ["", "**Theo ngữ cảnh đường dẫn (ML):**", "",
              "| Ngữ cảnh | Số dòng | Tỉ lệ secret | Precision | Recall | FPR |", "|---|---|---|---|---|---|"]
        for name, m in r["by_path_context"].items():
            L.append(f"| {name} | {m['so_dong']} | {fmt_pct(m['ti_le_secret'])} | {fmt_pct(m['precision'])} | "
                     f"{fmt_pct(m['recall'])} | {fmt_pct(m['fpr'])} |")
        top = [e for e in r["errors_by_type"] if e["loi_ML"] > 0][:12]
        L += ["", "**Loại mẫu bị lỗi nhiều nhất (ML):**", "", "| Nhãn | Loại | Số mẫu | Lỗi ML | Lỗi Regex |", "|---|---|---|---|---|"]
        for e in top:
            L.append(f"| {e['label']} | {e['type']} | {e['so_mau']} | {e['loi_ML']} | {e['loi_Regex']} |")
        L.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


def print_console(tag, threshold, results, split="test"):
    for src, r in results.items():
        ml, ci, pr, f = r["metrics"][r["ml_name"]], r["confidence_intervals"], r["probabilistic"], r["funnel"]
        print("\n" + "=" * 86)
        print(f"[{tag}] {SOURCE_LABELS[src]} | {'VALIDATION' if split == 'val' else 'test'} {r['n_lines']} dòng, {r['n_repos']} repo, {fmt_pct(r['prevalence'])} là secret")
        print("=" * 86)
        print(f"{'Phương pháp':<34}{'Precision':>10}{'Recall':>9}{'F1':>9}{'FPR':>9}{'FP':>6}{'FN':>6}")
        for name, m in r["metrics"].items():
            print(f"{name:<34}{fmt_pct(m['precision']):>10}{fmt_pct(m['recall']):>9}{fmt_pct(m['f1']):>9}"
                  f"{fmt_pct(m['fpr']):>9}{m['fp']:>6}{m['fn']:>6}")
        rng = lambda a: "n/a" if a[0] is None else f"[{a[0]:.4f}, {a[1]:.4f}]"
        print(f"\nROC-AUC {pr['roc_auc']:.4f} {rng(ci['roc_auc_ci'])} | PR-AUC {pr['pr_auc']:.4f} {rng(ci['pr_auc_ci'])}")
        print(f"Recall {fmt_pct(ml['recall'])} [{fmt_pct(ci['recall_ci_wilson'][0])}, {fmt_pct(ci['recall_ci_wilson'][1])}] | "
              f"FPR {fmt_pct(ml['fpr'])} [{fmt_pct(ci['fpr_ci_wilson'][0])}, {fmt_pct(ci['fpr_ci_wilson'][1])}]")
        print(f"Phễu recall: {f['dong_secret']} dòng secret -> {f['co_candidate']} có candidate "
              f"({fmt_pct(f['co_candidate'] / max(f['dong_secret'], 1))}) -> {f['bi_canh_bao']} bị cảnh báo "
              f"({fmt_pct(f['bi_canh_bao'] / max(f['dong_secret'], 1))})")
        for name, m in r["by_path_context"].items():
            print(f"  {name:<18}: {m['so_dong']:>5} dòng, {fmt_pct(m['ti_le_secret'])} secret | "
                  f"precision {fmt_pct(m['precision'])}, recall {fmt_pct(m['recall'])}, FPR {fmt_pct(m['fpr'])}")
        if split == "val":
            print("  Quét ngưỡng (cấp dòng, ML):")
            print(f"    {'ngưỡng':<8}{'precision':>11}{'recall':>9}{'FPR':>9}{'F1':>9}")
            for t, m in r["sweep"].items():
                print(f"    {t:<8}{fmt_pct(m['precision']):>11}{fmt_pct(m['recall']):>9}{fmt_pct(m['fpr']):>9}{fmt_pct(m['f1']):>9}")
        top = [e for e in r["errors_by_type"] if e["loi_ML"] > 0][:6]
        if top:
            print("  Lỗi nhiều nhất: " + "; ".join(f"{e['type']} (nhãn {e['label']}): {e['loi_ML']}/{e['so_mau']}" for e in top))


def write_comparison(path, threshold, all_results, split="test"):
    L = [f"# So sánh các model trên {'validation' if split == 'val' else 'test set'} (cấp dòng)", "",
         f"Ngưỡng {threshold}. Các model phải được chọn bằng validation trước khi xem bảng này.", ""]
    for src in SOURCES:
        rows = [(tag, res[src]) for tag, res in all_results.items() if src in res]
        if not rows:
            continue
        L += [f"## {SOURCE_LABELS[src]}", "", "| Model | PR-AUC | ROC-AUC | Precision | Recall | F1 | FPR |", "|---|---|---|---|---|---|---|"]
        for tag, r in rows:
            m, p = r["metrics"][r["ml_name"]], r["probabilistic"]
            L.append(f"| {tag} | {p['pr_auc']:.4f} | {p['roc_auc']:.4f} | {fmt_pct(m['precision'])} | "
                     f"{fmt_pct(m['recall'])} | {fmt_pct(m['f1'])} | {fmt_pct(m['fpr'])} |")
        L.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


# --------------------------------------------------------------------- chính
def main():
    parser = argparse.ArgumentParser(description="Đánh giá cấp dòng trên test set")
    parser.add_argument("--models", nargs="+", default=["production"], help="production hoặc tên thí nghiệm trong models/experiments/")
    parser.add_argument("--sources", nargs="+", choices=SOURCES, default=list(SOURCES))
    parser.add_argument("--split", choices=["val", "test"], default="test",
                        help="val = quét ngưỡng/so sánh trước khi chốt; test = đánh giá cuối")
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument("--boot", type=int, default=500, help="Số lần bootstrap theo repo")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir, reports_dir = os.path.join(base_dir, "data"), os.path.join(base_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    test_sets = load_test_sets(data_dir, args.sources, args.split)
    if not test_sets:
        raise SystemExit("Không có test set nào. Chạy build_dataset.py và/hoặc import_external.py trước.")

    if args.split == "test":  # chỉ ghi nhật ký khi chạm test; chạy trên val thì không
        with open(os.path.join(reports_dir, "test_access_log.txt"), "a", encoding="utf-8") as log:
            log.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}\tmodels={','.join(args.models)}"
                      f"\tsources={','.join(test_sets)}\tthreshold={args.threshold}\n")

    all_results = {}
    for tag in args.models:
        model, columns = load_model(tag)
        results, arrays = {}, {}
        for src, df in test_sets.items():
            print(f"[{tag}] đang chấm điểm {len(df)} dòng {args.split} của {SOURCE_LABELS[src]}...")
            results[src], arrays[src] = evaluate_source(df, model, columns, args.threshold, args.boot)
        all_results[tag] = results

        out = os.path.join(reports_dir, tag if args.split == "test" else f"{tag}_val")
        os.makedirs(out, exist_ok=True)
        for src, a in arrays.items():
            if len(a["errors"]):
                a["errors"].to_csv(os.path.join(out, f"errors_{src}.csv"), index=False)
        plot_pr(results, arrays, args.threshold, os.path.join(out, "pr_curve.png"))
        plot_roc(results, arrays, os.path.join(out, "roc_curve.png"))
        plot_confusion(results, args.threshold, os.path.join(out, "confusion_matrix.png"))
        plot_reliability(results, arrays, os.path.join(out, "reliability.png"))
        plot_precision_vs_prevalence(results, os.path.join(out, "precision_vs_prevalence.png"))
        with open(os.path.join(out, "metrics.json"), "w", encoding="utf-8") as fh:
            json.dump({"model": tag, "threshold": args.threshold, "results": results}, fh, ensure_ascii=False, indent=2)
        write_report(os.path.join(out, "evaluation_report.md"), tag, args.threshold, results, args.split)
        print_console(tag, args.threshold, results, args.split)
        print(f"\n✅ [{tag}] đã lưu 5 đồ thị, metrics.json, evaluation_report.md, errors_*.csv vào: {out}")

    if len(args.models) > 1:
        cmp_name = "model_comparison.md" if args.split == "test" else "model_comparison_val.md"
        write_comparison(os.path.join(reports_dir, cmp_name), args.threshold, all_results, args.split)
        print(f"\n✅ Bảng so sánh các model: {os.path.join(reports_dir, cmp_name)}")
    if args.split == "test":
        print("ℹ️  Mỗi lần chạy đã được ghi vào reports/test_access_log.txt (báo cáo nên nêu số lần chạm test).")


if __name__ == "__main__":
    main()