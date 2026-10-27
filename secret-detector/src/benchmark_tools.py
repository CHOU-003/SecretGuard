"""
benchmark_tools.py — so sánh hệ thống với Gitleaks và TruffleHog trên CÙNG test set

Chạy SAU evaluate.py:
    python -m src.benchmark_tools [--gitleaks gitleaks] [--trufflehog trufflehog] [--threshold 0.7]

Cách so sánh công bằng:
  - Mỗi dòng của test.csv được ghi thành 1 file riêng:
        <workdir>/<chỉ-số-mẫu>/<file_path của mẫu>
    (giữ nguyên đuôi file và thư mục như tests/, docs/... để công cụ nhìn thấy
    cùng ngữ cảnh đường dẫn mà mô hình ML được thấy).
  - Một mẫu được tính là "dự đoán có secret" nếu công cụ báo >= 1 finding
    trong file của mẫu đó. Mọi công cụ đều chạy với cấu hình MẶC ĐỊNH.

Quy tắc an toàn (cố ý không cho tắt):
  - TruffleHog luôn chạy với --no-verification. Chế độ verify sẽ GỌI API thật
    (AWS, Slack, GitHub...) bằng chính chuỗi tìm được — với dữ liệu thật như
    CredData đó là truy cập trái phép.
  - Gitleaks luôn chạy với --redact để báo cáo không chứa secret.
  - Chỉ lưu chỉ số mẫu + tên rule/detector, KHÔNG lưu nội dung secret.
  - Thư mục tạm chứa các mẫu bị xoá sau khi chạy (trừ khi dùng --keep).

Hạn chế cần nêu trong báo cáo: các công cụ thiết kế để quét repo, không phải
để phân loại từng chuỗi rời; test set lại do chính nhóm thiết kế. Kết quả cho
thấy hành vi trên TẬP NÀY, không phải xếp hạng tổng quát giữa các công cụ.
"""

import os
import json
import shutil
import argparse
import subprocess
from collections import Counter

import joblib
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import precision_recall_curve, average_precision_score

from src.evaluate import (
    binary_metrics,
    fmt_pct,
    ppv_at_prevalence,
    regex_entropy_predictions,
    regex_predictions,
    save_fig,
    wilson_interval,
)
from src.train_ml import NON_FEATURE_COLUMNS

PREVALENCES = [0.01, 0.05]
COLORS = {
    "Regex": "tab:green",
    "Regex + Entropy": "tab:orange",
    "Gitleaks": "tab:purple",
    "TruffleHog": "tab:brown",
}


# ------------------------------------------------------ dựng mẫu thành file
def safe_relative_path(file_path):
    """Chuẩn hoá file_path thành đường dẫn tương đối an toàn (bỏ '..', '/', 'C:')."""
    if file_path is None or (isinstance(file_path, float) and np.isnan(file_path)):
        return "sample.txt"
    parts = [p.replace(":", "_") for p in str(file_path).replace("\\", "/").split("/")
             if p not in ("", ".", "..")]
    return os.path.join(*parts) if parts else "sample.txt"


def materialize_samples(test_raw, root):
    """Ghi mỗi mẫu test thành 1 file: root/<idx>/<file_path>. Nội dung = text + xuống dòng."""
    if os.path.exists(root):
        shutil.rmtree(root)
    has_path = "file_path" in test_raw.columns
    for idx, (_, row) in enumerate(test_raw.iterrows()):
        rel = safe_relative_path(row["file_path"]) if has_path else "sample.txt"
        path = os.path.join(root, f"{idx:05d}", rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(str(row["text"]) + "\n")


def sample_index_from_path(path, root):
    """Lấy chỉ số mẫu từ đường dẫn file mà công cụ báo cáo."""
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    first = rel.replace("\\", "/").split("/")[0]
    return int(first) if first.isdigit() else None


# ----------------------------------------------------------------- công cụ
def tool_available(binary):
    return shutil.which(binary) is not None or os.path.isfile(binary)


def tool_version(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (out.stdout + out.stderr).strip().splitlines()[0]
    except Exception:
        return "không rõ"


def run_gitleaks(binary, root, work_dir):
    """Trả về (tập chỉ số mẫu bị báo, Counter rule). Thử lệnh `dir` (mới), lùi về `detect --no-git` (cũ)."""
    report = os.path.join(work_dir, "gitleaks_report.json")
    common = ["--report-format", "json", "--report-path", report, "--no-banner", "--redact", "--exit-code", "0"]
    attempts = [
        [binary, "dir", root] + common,
        [binary, "detect", "--no-git", "--source", root] + common,
    ]
    last_err = ""
    for cmd in attempts:
        if os.path.exists(report):
            os.remove(report)
        # cwd=work_dir để Gitleaks không đọc nhầm .gitleaksignore của repo đang đứng
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=work_dir)
        if proc.returncode == 0:
            findings = []
            if os.path.exists(report):
                with open(report, encoding="utf-8") as f:
                    content = f.read().strip()
                findings = json.loads(content) if content else []
            hit, rules = set(), Counter()
            for item in findings:
                idx = sample_index_from_path(item.get("File", ""), root)
                if idx is not None:
                    hit.add(idx)
                    rules[item.get("RuleID", "?")] += 1
            return hit, rules
        last_err = proc.stderr.strip()[-300:]
    raise RuntimeError(f"Gitleaks lỗi: {last_err}")


def run_trufflehog(binary, root, work_dir):
    """Trả về (tập chỉ số mẫu bị báo, Counter detector). LUÔN --no-verification (xem docstring đầu file)."""
    cmd = [binary, "filesystem", root, "--json", "--no-verification", "--no-update"]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=work_dir)
    if proc.returncode != 0:
        raise RuntimeError(f"TruffleHog lỗi: {proc.stderr.strip()[-300:]}")
    hit, detectors = set(), Counter()
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        file_path = (item.get("SourceMetadata", {}).get("Data", {}).get("Filesystem", {}).get("file"))
        if not file_path:
            continue
        idx = sample_index_from_path(file_path, root)
        if idx is not None:
            hit.add(idx)
            detectors[item.get("DetectorName", "?")] += 1  # chỉ lấy tên detector, bỏ trường Raw
    return hit, detectors


# ---------------------------------------------------------------- phân tích
def per_type_errors(test_raw, predictions):
    """Bảng số lỗi theo (nhãn, loại mẫu) cho từng phương pháp.
    Nhãn 0: lỗi = báo nhầm (FP). Nhãn 1: lỗi = bỏ sót (FN)."""
    df = test_raw[["type", "label"]].copy()
    for name, pred in predictions.items():
        df[name] = (np.asarray(pred) != df["label"].to_numpy()).astype(int)
    grouped = df.groupby(["label", "type"])
    table = grouped.size().rename("so_mau").to_frame()
    for name in predictions:
        table[name] = grouped[name].sum()
    return table.reset_index()


def plot_comparison(y, proba, threshold, metrics, path):
    precision, recall, _ = precision_recall_curve(y, proba)
    fig, ax = plt.subplots(figsize=(7, 5.4))
    ax.plot(recall, precision, lw=2, color="tab:blue",
            label=f"ML — đường PR (PR-AUC = {average_precision_score(y, proba):.3f})")
    ml = metrics[f"ML (ngưỡng {threshold})"]
    ax.scatter([ml["recall"]], [ml["precision"]], marker="*", s=200, color="tab:red", zorder=6,
               label=f"ML tại ngưỡng {threshold}")
    for name, m in metrics.items():
        if name in COLORS:
            ax.scatter([m["recall"]], [m["precision"]], s=80, color=COLORS[name], zorder=5, label=name)
    ax.axhline(float(np.mean(y)), ls="--", color="gray", lw=1, label="Ngẫu nhiên")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("So sánh với công cụ thực tế (cùng tập test)")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left", fontsize=8)
    save_fig(fig, path)


def write_markdown(path, info, metrics, per_type, prevalence_rows, rule_hits):
    names = list(metrics.keys())
    lines = [
        "# So sánh với Gitleaks và TruffleHog (cùng tập test)",
        "",
        f"Số mẫu: {info['n_test']} | Tỉ lệ secret: {fmt_pct(info['prevalence'])} | Ngưỡng ML: {info['threshold']}",
        "",
        "Phiên bản công cụ: " + "; ".join(f"{k}: {v}" for k, v in info["versions"].items()),
        "",
        "Cấu hình mặc định cho mọi công cụ. TruffleHog chạy `--no-verification`, Gitleaks chạy `--redact`.",
        "",
        "## 1. Kết quả tổng hợp",
        "",
        "| Phương pháp | Precision | Recall | F1 | FPR | FP | FN |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in names:
        m = metrics[name]
        lines.append(f"| {name} | {fmt_pct(m['precision'])} | {fmt_pct(m['recall'])} | {fmt_pct(m['f1'])} | "
                     f"{fmt_pct(m['fpr'])} | {m['fp']} | {m['fn']} |")

    lines += ["", "## 2. Số lỗi theo loại mẫu", "",
              "Nhãn 0 = không phải secret (lỗi là báo nhầm). Nhãn 1 = secret thật (lỗi là bỏ sót).", "",
              "| Nhãn | Loại | Số mẫu | " + " | ".join(names) + " |",
              "|---|---|---|" + "---|" * len(names)]
    for _, row in per_type.iterrows():
        lines.append(f"| {row['label']} | {row['type']} | {row['so_mau']} | " +
                     " | ".join(str(int(row[n])) for n in names) + " |")

    lines += ["", "## 3. Precision kỳ vọng khi tỉ lệ secret ngoài đời thấp", "",
              "| Tỉ lệ secret | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for prev, row in prevalence_rows.items():
        lines.append(f"| {float(prev):.0%} | " + " | ".join(fmt_pct(row[n]) for n in names) + " |")

    if rule_hits:
        lines += ["", "## 4. Rule/detector được kích hoạt nhiều nhất", ""]
        for tool, counter in rule_hits.items():
            top = ", ".join(f"{r} ({c})" for r, c in counter.most_common(8))
            lines.append(f"- **{tool}**: {top}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# --------------------------------------------------------------------- chính
def run(args):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    models_dir = os.path.join(base_dir, "models")
    out_dir = os.path.join(base_dir, "reports")
    work_dir = os.path.join(out_dir, "_tool_work")
    root = os.path.join(work_dir, "samples")
    os.makedirs(out_dir, exist_ok=True)

    test_raw = pd.read_csv(os.path.join(data_dir, "test.csv"))
    test_feat = pd.read_csv(os.path.join(data_dir, "test_features.csv"))
    if len(test_raw) != len(test_feat):
        raise ValueError("test.csv và test_features.csv lệch số dòng — chạy lại build_features.py.")
    y = test_raw["label"].to_numpy()
    texts = test_raw["text"].astype(str).tolist()

    predictions, versions, rule_hits = {}, {}, {}

    # 1. Phương pháp của hệ thống
    predictions["Regex"] = regex_predictions(texts)
    predictions["Regex + Entropy"] = regex_entropy_predictions(texts)
    clf = joblib.load(os.path.join(models_dir, "secret_ml_model.pkl"))
    cols = joblib.load(os.path.join(models_dir, "feature_columns.pkl"))
    X = test_feat.drop(columns=[c for c in NON_FEATURE_COLUMNS if c in test_feat.columns]).reindex(columns=cols, fill_value=0)
    proba = clf.predict_proba(X)[:, 1]
    ml_name = f"ML (ngưỡng {args.threshold})"

    # 2. Công cụ bên ngoài
    gl_ok, th_ok = tool_available(args.gitleaks), tool_available(args.trufflehog)
    if not gl_ok:
        print(f"⚠️  Bỏ qua Gitleaks: không tìm thấy '{args.gitleaks}' (dùng --gitleaks <đường dẫn gitleaks.exe>).")
    if not th_ok:
        print(f"⚠️  Bỏ qua TruffleHog: không tìm thấy '{args.trufflehog}' (dùng --trufflehog <đường dẫn trufflehog.exe>).")

    if gl_ok or th_ok:
        try:
            print(f"Đang dựng {len(test_raw)} mẫu test thành file...")
            materialize_samples(test_raw, root)
            n = len(test_raw)
            if gl_ok:
                versions["Gitleaks"] = tool_version([args.gitleaks, "version"])
                print(f"Đang chạy Gitleaks ({versions['Gitleaks']})...")
                hit, rules = run_gitleaks(args.gitleaks, root, work_dir)
                predictions["Gitleaks"] = np.array([1 if i in hit else 0 for i in range(n)])
                rule_hits["Gitleaks"] = rules
            if th_ok:
                versions["TruffleHog"] = tool_version([args.trufflehog, "--version"])
                print(f"Đang chạy TruffleHog ({versions['TruffleHog']}), không verify...")
                hit, dets = run_trufflehog(args.trufflehog, root, work_dir)
                predictions["TruffleHog"] = np.array([1 if i in hit else 0 for i in range(n)])
                rule_hits["TruffleHog"] = dets
        finally:
            if not args.keep and os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)

    predictions[ml_name] = (proba >= args.threshold).astype(int)

    # 3. Số liệu
    metrics = {name: binary_metrics(y, pred) for name, pred in predictions.items()}
    prevalence = float(y.mean())
    per_type = per_type_errors(test_raw, predictions)
    prevalence_rows = {
        str(p): {name: ppv_at_prevalence(m["recall"], m["fpr"], p) for name, m in metrics.items()}
        for p in PREVALENCES
    }
    fpr_ci = {name: list(wilson_interval(m["fp"], m["fp"] + m["tn"])) for name, m in metrics.items()}

    # 4. Lưu kết quả (chỉ chỉ số + loại + dự đoán, không có nội dung mẫu)
    pred_df = pd.DataFrame({"idx": range(len(y)), "label": y, "type": test_raw["type"], "ml_proba": proba})
    for name, pred in predictions.items():
        pred_df[name] = pred
    pred_df.to_csv(os.path.join(out_dir, "tool_predictions_test.csv"), index=False)

    info = {"n_test": int(len(y)), "prevalence": prevalence, "threshold": args.threshold, "versions": versions}
    with open(os.path.join(out_dir, "tool_benchmark.json"), "w", encoding="utf-8") as f:
        json.dump({**info, "metrics": metrics, "fpr_ci_wilson": fpr_ci,
                   "precision_at_prevalence": prevalence_rows,
                   "rule_hits": {k: dict(v) for k, v in rule_hits.items()}},
                  f, ensure_ascii=False, indent=2)
    write_markdown(os.path.join(out_dir, "tool_benchmark.md"), info, metrics, per_type, prevalence_rows, rule_hits)
    plot_comparison(y, proba, args.threshold, metrics, os.path.join(out_dir, "tools_comparison.png"))

    # 5. In ra màn hình
    print("\n" + "=" * 86)
    print(f"SO SÁNH VỚI CÔNG CỤ THỰC TẾ | {len(y)} mẫu | tỉ lệ secret {fmt_pct(prevalence)}")
    print("=" * 86)
    print(f"{'Phương pháp':<26}{'Precision':>10}{'Recall':>9}{'F1':>9}{'FPR':>9}{'FP':>6}{'FN':>6}")
    for name, m in metrics.items():
        print(f"{name:<26}{fmt_pct(m['precision']):>10}{fmt_pct(m['recall']):>9}{fmt_pct(m['f1']):>9}"
              f"{fmt_pct(m['fpr']):>9}{m['fp']:>6}{m['fn']:>6}")
    print("\nSố lỗi theo loại mẫu (nhãn 0 = báo nhầm, nhãn 1 = bỏ sót):")
    show = per_type.copy()
    show["tong_loi"] = show[list(predictions)].sum(axis=1)
    print(show[show["tong_loi"] > 0].drop(columns="tong_loi").to_string(index=False))
    for tool, counter in rule_hits.items():
        print(f"\n{tool} — rule/detector hay kích hoạt: " + ", ".join(f"{r} ({c})" for r, c in counter.most_common(5)))
    print(f"\n✅ Đã lưu tool_benchmark.md/.json, tools_comparison.png, tool_predictions_test.csv vào: {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="So sánh với Gitleaks và TruffleHog")
    parser.add_argument("--gitleaks", default="gitleaks", help="Tên lệnh hoặc đường dẫn gitleaks(.exe)")
    parser.add_argument("--trufflehog", default="trufflehog", help="Tên lệnh hoặc đường dẫn trufflehog(.exe)")
    parser.add_argument("--threshold", type=float, default=0.7, help="Ngưỡng phân loại của ML")
    parser.add_argument("--keep", action="store_true", help="Giữ lại thư mục mẫu tạm để debug")
    run(parser.parse_args())
