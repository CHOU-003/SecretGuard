"""
benchmark_tools.py (v2) — so sánh với Gitleaks và TruffleHog trên CÙNG các dòng của CredData

Chạy SAU khi đã chốt model và ngưỡng (bằng validation):
    python -m src.benchmark_tools --gitleaks C:\\tools\\gitleaks.exe --trufflehog C:\\tools\\trufflehog.exe ^
        --model production --warn-threshold 0.5 --threshold 0.8
    python -m src.benchmark_tools --split val ...      # chạy thử trên validation, không chạm test

Cách so sánh công bằng:
  - Mỗi dòng của tập đánh giá (mặc định: split test của CredData) được ghi thành 1 file riêng:
        <workdir>/<chỉ-số-dòng>/<file_path của dòng>
    giữ nguyên thư mục và đuôi file (test/, lang/, .json, .yml...) để công cụ thấy cùng ngữ cảnh
    đường dẫn mà mô hình ML thấy.
  - Một dòng được tính là "dự đoán có secret" nếu công cụ báo >= 1 finding trong file của dòng đó.
    Mọi công cụ chạy với cấu hình MẶC ĐỊNH, đúng như một người dùng cài về chạy.
  - Hệ thống của bạn được báo cáo ở HAI mức: "cảnh báo" (>= --warn-threshold, cùng nghĩa với
    "công cụ có báo gì đó") và "chặn" (>= --threshold, mức làm commit bị từ chối).

Quy tắc an toàn (cố ý không cho tắt):
  - TruffleHog luôn chạy với --no-verification. Chế độ verify sẽ GỌI API thật bằng chính chuỗi
    tìm được; với dữ liệu thật như CredData đó là truy cập trái phép.
  - Gitleaks luôn chạy với --redact để báo cáo không chứa secret.
  - Chỉ lưu chỉ số dòng, nhãn, loại và dự đoán; KHÔNG lưu nội dung dòng.
  - Thư mục tạm chứa các dòng bị xoá sau khi chạy (trừ khi dùng --keep).

Hạn chế cần nêu trong báo cáo:
  - Các công cụ được thiết kế để quét cả repo (có ngữ cảnh nhiều dòng, xác minh key bằng API);
    ở đây chúng chỉ thấy 1 dòng và không được verify. Kết quả mô tả hành vi trên TẬP NÀY với
    cấu hình mặc định, không phải xếp hạng tổng quát giữa các công cụ.
  - Mô hình của bạn được train trên chính CredData (tập train) còn các công cụ kia thì không,
    nên so sánh này thiên về phía bạn. Phải nói rõ điều đó.
  - Nhãn CredData tính cả credential trong thư mục test là secret; công cụ có thể chủ ý bỏ qua.
  - Khoảng tin cậy chênh lệch F1 dùng bootstrap theo repo; độ lệch lớn giữa các repo làm khoảng rộng.
"""

import os
import json
import shutil
import argparse
import datetime
import subprocess
from collections import Counter

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import average_precision_score, precision_recall_curve

from src.evaluate import (
    SOURCE_LABELS,
    SOURCES,
    binary_metrics,
    fmt_pct,
    load_test_sets,
    ppv_at_prevalence,
    regex_entropy_predictions,
    regex_predictions,
    save_fig,
    wilson_interval,
)
from src.feature_extractor import is_test_path_fn
from src.scoring import load_model, score_lines

SEED = 42
PREVALENCES = [0.01, 0.05, 0.10]
COLORS = {
    "Regex": "tab:green",
    "Regex + Entropy": "tab:orange",
    "Chỉ trích candidate (không ML)": "tab:gray",
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
def f1_binary(y, pred):
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    return 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0


def cluster_bootstrap_f1_diff(y, pred_a, pred_b, groups, n_boot, seed=SEED):
    """Khoảng tin cậy 95% cho F1(a) - F1(b), resample theo repo. Trả về (điểm, thấp, cao)."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    idx_by_group = {g: np.where(groups == g)[0] for g in uniq}
    diffs = []
    for _ in range(n_boot):
        chosen = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_group[g] for g in chosen])
        diffs.append(f1_binary(y[idx], pred_a[idx]) - f1_binary(y[idx], pred_b[idx]))
    point = f1_binary(y, pred_a) - f1_binary(y, pred_b)
    return float(point), float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def category_tables(df, y, preds, min_n=30, top=10):
    """Tỉ lệ dòng bị báo theo (nhãn, Category). Nhãn 1: đây là recall. Nhãn 0: đây là FPR."""
    d = pd.DataFrame({"label": y, "type": df["type"].astype(str).to_numpy()})
    for name, p in preds.items():
        d[name] = p
    out = {}
    for label in (1, 0):
        g = d[d["label"] == label].groupby("type")
        sizes = g.size()
        keep = sizes[sizes >= min_n].sort_values(ascending=False).head(top).index
        tbl = g[list(preds)].mean().loc[keep]
        tbl.insert(0, "so_mau", sizes.loc[keep])
        out[label] = tbl
    return out


def context_metrics(y, paths, preds):
    """Recall và FPR của từng phương pháp, tách theo thư mục test/mẫu và thư mục khác."""
    in_test = np.array([is_test_path_fn(p) for p in paths])
    out = {}
    for ctx, mask in (("thư mục test/mẫu", in_test), ("thư mục khác", ~in_test)):
        if mask.sum() == 0:
            continue
        out[ctx] = {"so_dong": int(mask.sum()), "ti_le_secret": float(y[mask].mean()),
                    "methods": {n: binary_metrics(y[mask], p[mask]) for n, p in preds.items()}}
    return out


def benchmark_source(src, df, model, columns, tools, args, work_dir):
    texts = df["text"].astype(str).tolist()
    paths = df["file_path"].astype(str).tolist() if "file_path" in df.columns else [""] * len(df)
    y = df["label"].astype(int).to_numpy()
    groups = df["repo"].astype(str).to_numpy() if "repo" in df.columns else np.array([str(i) for i in range(len(df))])
    n = len(df)

    ls = score_lines(zip(texts, paths), model, columns)
    score = np.array([s.score for s in ls])
    n_cand = np.array([s.n_candidates for s in ls])

    preds, rule_hits = {}, {}
    preds["Regex"] = regex_predictions(texts)
    preds["Regex + Entropy"] = regex_entropy_predictions(texts)
    preds["Chỉ trích candidate (không ML)"] = (n_cand > 0).astype(int)

    if tools:
        src_work = os.path.join(work_dir, src)
        root = os.path.join(src_work, "samples")
        os.makedirs(src_work, exist_ok=True)
        print(f"[{src}] đang dựng {n} dòng thành file...")
        materialize_samples(df, root)
        if "Gitleaks" in tools:
            print(f"[{src}] đang chạy Gitleaks ({tools['Gitleaks']['version']})...")
            hit, rules = run_gitleaks(tools["Gitleaks"]["binary"], root, src_work)
            preds["Gitleaks"] = np.array([1 if i in hit else 0 for i in range(n)])
            rule_hits["Gitleaks"] = dict(rules)
        if "TruffleHog" in tools:
            print(f"[{src}] đang chạy TruffleHog ({tools['TruffleHog']['version']}), không verify...")
            hit, dets = run_trufflehog(tools["TruffleHog"]["binary"], root, src_work)
            preds["TruffleHog"] = np.array([1 if i in hit else 0 for i in range(n)])
            rule_hits["TruffleHog"] = dict(dets)

    warn_name = f"ML cảnh báo (≥{args.warn_threshold})"
    block_name = f"ML chặn (≥{args.threshold})"
    preds[warn_name] = (score >= args.warn_threshold).astype(int)
    preds[block_name] = (score >= args.threshold).astype(int)
    ml_names = [warn_name, block_name]

    metrics = {name: binary_metrics(y, p) for name, p in preds.items()}
    ci = {name: {"recall": list(wilson_interval(m["tp"], m["tp"] + m["fn"])),
                 "fpr": list(wilson_interval(m["fp"], m["fp"] + m["tn"]))} for name, m in metrics.items()}

    f1_diff = {}
    others = [n_ for n_ in preds if n_ not in ml_names]
    for ml in ml_names:
        f1_diff[ml] = {}
        for other in others:
            point, lo, hi = cluster_bootstrap_f1_diff(y, preds[ml], preds[other], groups, args.boot)
            f1_diff[ml][other] = {"diff": point, "ci": [lo, hi]}

    prevalence_sim = {
        str(p): {name: ppv_at_prevalence(m["recall"], m["fpr"], p) for name, m in metrics.items()}
        for p in PREVALENCES
    }
    cats = category_tables(df, y, {k: v for k, v in preds.items() if k in ("Regex", "Gitleaks", "TruffleHog", warn_name, block_name)})
    result = {
        "n_lines": n, "n_repos": int(len(np.unique(groups))), "prevalence": float(y.mean()),
        "warn_name": warn_name, "block_name": block_name,
        "metrics": metrics, "ci": ci, "f1_diff": f1_diff,
        "context": context_metrics(y, paths, preds),
        "categories": {str(k): v.reset_index().to_dict(orient="records") for k, v in cats.items()},
        "precision_at_prevalence": prevalence_sim, "rule_hits": rule_hits,
        "pr_auc_ml": float(average_precision_score(y, score)),
    }
    arrays = {"y": y, "score": score, "preds": preds,
              "frame": pd.DataFrame({"idx": range(n), "repo": groups, "label": y, "type": df["type"].astype(str).to_numpy(),
                                     "ml_score": np.round(score, 4), **{k: v for k, v in preds.items()}})}
    return result, arrays


# ------------------------------------------------------------------ đồ thị
def plot_comparison(results, arrays, path):
    fig, axes = plt.subplots(1, len(results), figsize=(9.6 * len(results), 5.6))
    axes = np.atleast_1d(axes)
    for ax, (src, r) in zip(axes, results.items()):
        y, score = arrays[src]["y"], arrays[src]["score"]
        prec, rec, _ = precision_recall_curve(y, score)
        ax.plot(rec, prec, lw=2, color="tab:blue", label=f"ML — đường PR (PR-AUC = {r['pr_auc_ml']:.3f})")
        for name, color in COLORS.items():
            if name in r["metrics"]:
                m = r["metrics"][name]
                ax.scatter([m["recall"]], [m["precision"]], s=80, color=color, zorder=5, label=name)
        for key, marker in ((r["warn_name"], "*"), (r["block_name"], "P")):
            m = r["metrics"][key]
            ax.scatter([m["recall"]], [m["precision"]], marker=marker, s=190, color="tab:red", zorder=6, label=key)
        ax.axhline(r["prevalence"], ls="--", color="gray", lw=1, label="Ngẫu nhiên")
        ax.set(xlabel="Recall", ylabel="Precision", xlim=(0, 1.02), ylim=(0, 1.02),
               title=f"So sánh với công cụ thực tế (cấp dòng)\n{SOURCE_LABELS[src]}")
        ax.grid(alpha=0.3)
        ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=8, frameon=False)  # ngoài khung, không che điểm
    save_fig(fig, path)


# ----------------------------------------------------------------- báo cáo
def write_markdown(path, info, results):
    L = [f"# So sánh với Gitleaks và TruffleHog ({'VALIDATION' if info['split'] == 'val' else 'TEST'})", "",
         f"Model: `{info['model']}` | cảnh báo ≥ {info['warn_threshold']} | chặn ≥ {info['threshold']}", "",
         "Phiên bản công cụ: " + ("; ".join(f"{k}: {v}" for k, v in info["versions"].items()) or "không có công cụ ngoài"), "",
         "Cấu hình mặc định cho mọi công cụ; TruffleHog chạy `--no-verification`, Gitleaks chạy `--redact`.", ""]
    for src, r in results.items():
        names = list(r["metrics"])
        L += [f"## {SOURCE_LABELS[src]} ({r['n_lines']} dòng, {r['n_repos']} repo, {fmt_pct(r['prevalence'])} là secret)", "",
              "| Phương pháp | Precision | Recall (95% CI) | F1 | FPR (95% CI) |", "|---|---|---|---|---|"]
        for name in names:
            m, c = r["metrics"][name], r["ci"][name]
            L.append(f"| {name} | {fmt_pct(m['precision'])} | {fmt_pct(m['recall'])} [{fmt_pct(c['recall'][0])}, {fmt_pct(c['recall'][1])}] | "
                     f"{fmt_pct(m['f1'])} | {fmt_pct(m['fpr'])} [{fmt_pct(c['fpr'][0])}, {fmt_pct(c['fpr'][1])}] |")
        L += ["", "**Chênh lệch F1 của ML so với từng phương pháp** (dương = ML tốt hơn; CI bootstrap theo repo; "
              "CI không chứa 0 nghĩa là chênh lệch vững khi lấy mẫu lại repo):", "",
              "| ML | so với | ΔF1 | 95% CI |", "|---|---|---|---|"]
        for ml, d in r["f1_diff"].items():
            for other, v in d.items():
                L.append(f"| {ml} | {other} | {v['diff'] * 100:+.2f} điểm | [{v['ci'][0] * 100:+.2f}, {v['ci'][1] * 100:+.2f}] |")

        L += ["", "**Theo ngữ cảnh đường dẫn** (Recall trên dòng secret / FPR trên dòng không phải secret):", "",
              "| Ngữ cảnh | Số dòng | Tỉ lệ secret | " + " | ".join(names) + " |", "|---|---|---|" + "---|" * len(names)]
        for ctx, v in r["context"].items():
            cells = " | ".join(f"{fmt_pct(v['methods'][n]['recall'])} / {fmt_pct(v['methods'][n]['fpr'])}" for n in names)
            L.append(f"| {ctx} | {v['so_dong']} | {fmt_pct(v['ti_le_secret'])} | {cells} |")

        for label, title in (("1", "Dòng secret theo Category (giá trị = tỉ lệ được phát hiện, tức recall)"),
                             ("0", "Dòng KHÔNG phải secret theo Category (giá trị = tỉ lệ bị báo nhầm, tức FPR)")):
            rows = r["categories"][label]
            if not rows:
                continue
            cols = [c for c in rows[0] if c not in ("type", "so_mau")]
            L += ["", f"**{title}:**", "", "| Category | Số dòng | " + " | ".join(cols) + " |", "|---|---|" + "---|" * len(cols)]
            for row in rows:
                L.append(f"| {row['type']} | {row['so_mau']} | " + " | ".join(fmt_pct(row[c]) for c in cols) + " |")

        L += ["", "**Precision kỳ vọng khi tỉ lệ secret ngoài đời thấp** (công thức Bayes, giả định TPR/FPR không đổi):", "",
              "| Tỉ lệ secret | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
        for p, row in r["precision_at_prevalence"].items():
            L.append(f"| {float(p):.0%} | " + " | ".join(fmt_pct(row[n]) for n in names) + " |")

        if r["rule_hits"]:
            L += ["", "**Rule/detector kích hoạt nhiều nhất:**", ""]
            for tool, counter in r["rule_hits"].items():
                top = ", ".join(f"{k} ({v})" for k, v in sorted(counter.items(), key=lambda kv: -kv[1])[:8])
                L.append(f"- **{tool}**: {top}")
        L.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


def print_console(info, results):
    for src, r in results.items():
        names = list(r["metrics"])
        print("\n" + "=" * 92)
        print(f"{SOURCE_LABELS[src]} | {'VALIDATION' if info['split'] == 'val' else 'TEST'} {r['n_lines']} dòng, "
              f"{r['n_repos']} repo, {fmt_pct(r['prevalence'])} là secret")
        print("=" * 92)
        print(f"{'Phương pháp':<34}{'Precision':>10}{'Recall':>9}{'F1':>9}{'FPR':>9}{'FP':>7}{'FN':>7}")
        for name in names:
            m = r["metrics"][name]
            print(f"{name:<34}{fmt_pct(m['precision']):>10}{fmt_pct(m['recall']):>9}{fmt_pct(m['f1']):>9}"
                  f"{fmt_pct(m['fpr']):>9}{m['fp']:>7}{m['fn']:>7}")
        print("\nChênh lệch F1 của ML so với từng phương pháp (điểm %, CI 95% bootstrap theo repo):")
        for ml, d in r["f1_diff"].items():
            for other, v in d.items():
                print(f"  {ml:<22} vs {other:<32} {v['diff'] * 100:+6.2f}  [{v['ci'][0] * 100:+.2f}, {v['ci'][1] * 100:+.2f}]")
        for ctx, v in r["context"].items():
            print(f"\n{ctx} ({v['so_dong']} dòng, {fmt_pct(v['ti_le_secret'])} secret) — recall / FPR:")
            print("  " + " | ".join(f"{n.split(' (')[0]}: {fmt_pct(v['methods'][n]['recall'])}/{fmt_pct(v['methods'][n]['fpr'])}" for n in names))
        for tool, counter in r["rule_hits"].items():
            print(f"\n{tool} — rule hay kích hoạt: " + ", ".join(f"{k} ({v})" for k, v in sorted(counter.items(), key=lambda kv: -kv[1])[:5]))


# --------------------------------------------------------------------- chính
def run(args):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir, reports_dir = os.path.join(base_dir, "data"), os.path.join(base_dir, "reports")
    work_dir = os.path.join(reports_dir, "_tool_work")
    os.makedirs(reports_dir, exist_ok=True)

    model, columns = load_model(args.model)
    sets = load_test_sets(data_dir, args.sources, args.split)
    if not sets:
        raise SystemExit("Không có dữ liệu để đánh giá. Chạy import_external.py / build_dataset.py trước.")

    tools, versions = {}, {}
    for name, binary, cmd in (("Gitleaks", args.gitleaks, [args.gitleaks, "version"]),
                              ("TruffleHog", args.trufflehog, [args.trufflehog, "--version"])):
        if tool_available(binary):
            versions[name] = tool_version(cmd)
            tools[name] = {"binary": binary, "version": versions[name]}
        else:
            print(f"⚠️  Bỏ qua {name}: không tìm thấy '{binary}' (dùng --{name.lower()} <đường dẫn .exe>).")

    if args.split == "test":
        with open(os.path.join(reports_dir, "test_access_log.txt"), "a", encoding="utf-8") as log:
            log.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}\tbenchmark_tools model={args.model}"
                      f"\tsources={','.join(sets)}\twarn={args.warn_threshold}\tblock={args.threshold}\n")

    results, arrays = {}, {}
    try:
        for src, df in sets.items():
            results[src], arrays[src] = benchmark_source(src, df, model, columns, tools, args, work_dir)
    finally:
        if not args.keep and os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)

    info = {"split": args.split, "model": args.model, "threshold": args.threshold,
            "warn_threshold": args.warn_threshold, "versions": versions}
    suffix = "" if args.split == "test" else "_val"
    with open(os.path.join(reports_dir, f"tool_benchmark{suffix}.json"), "w", encoding="utf-8") as fh:
        json.dump({**info, "results": results}, fh, ensure_ascii=False, indent=2)
    write_markdown(os.path.join(reports_dir, f"tool_benchmark{suffix}.md"), info, results)
    for src, a in arrays.items():
        a["frame"].to_csv(os.path.join(reports_dir, f"tool_predictions_{src}{suffix}.csv"), index=False)
    plot_comparison(results, arrays, os.path.join(reports_dir, f"tools_comparison{suffix}.png"))
    print_console(info, results)
    print(f"\n✅ Đã lưu tool_benchmark{suffix}.md/.json, tools_comparison{suffix}.png, tool_predictions_*{suffix}.csv vào: {reports_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="So sánh với Gitleaks và TruffleHog")
    parser.add_argument("--gitleaks", default="gitleaks", help="Tên lệnh hoặc đường dẫn gitleaks(.exe)")
    parser.add_argument("--trufflehog", default="trufflehog", help="Tên lệnh hoặc đường dẫn trufflehog(.exe)")
    parser.add_argument("--model", default="production", help="production hoặc tên thí nghiệm trong models/experiments/")
    parser.add_argument("--split", choices=["val", "test"], default="test")
    parser.add_argument("--sources", nargs="+", choices=list(SOURCES), default=["creddata"],
                        help="Mặc định chỉ CredData (dữ liệu thật); thêm synthetic nếu muốn đối chiếu")
    parser.add_argument("--threshold", type=float, default=0.7, help="Ngưỡng CHẶN của ML")
    parser.add_argument("--warn-threshold", type=float, default=0.4, help="Ngưỡng CẢNH BÁO của ML")
    parser.add_argument("--boot", type=int, default=500, help="Số lần bootstrap theo repo")
    parser.add_argument("--keep", action="store_true", help="Giữ lại thư mục mẫu tạm để debug")
    run(parser.parse_args())