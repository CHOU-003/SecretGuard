"""
measure_time.py — đo thời gian xử lý của các phương pháp phát hiện

Chạy:
    python -m src.measure_time                       # đo trên 5.000 dòng validation của CredData
    python -m src.measure_time --gitleaks C:\\tools\\gitleaks\\gitleaks.exe --trufflehog C:\\tools\\trufflehog\\trufflehog.exe

Thời gian KHÔNG phụ thuộc nhãn nên mặc định đo trên tập validation (không chạm test).

Các phép đo:
  1. Thông lượng từng phương pháp trên cùng các dòng: Regex; Regex + Entropy; chỉ trích candidate;
     toàn bộ pipeline ML. Báo cáo mili-giây trên 1.000 dòng (trung vị của --repeat lần chạy, sau 1 lần
     chạy khởi động).
  2. Phân rã pipeline ML: trích candidate, tính feature, dựng bảng, dự đoán của mô hình.
  3. Độ trễ khi quét MỘT FILE cỡ --file-lines dòng (đúng tình huống pre-commit): trung vị và p95.
  4. Thời gian nạp mô hình.
  5. Thời gian chạy `main.py` từ đầu đến cuối trên một repo nhỏ (gồm khởi động Python, import thư viện,
     nạp mô hình, quét) = thời gian người dùng thực sự phải chờ ở mỗi lần commit.
  6. Nếu truyền đường dẫn Gitleaks/TruffleHog: thời gian quét CÙNG thư mục đó của hai công cụ.
     TruffleHog luôn chạy --no-verification (không gọi API thật), Gitleaks chạy --redact.

Lưu ý khi diễn giải: thời gian phụ thuộc máy (CPU, ổ đĩa, antivirus). Ghi cấu hình máy vào báo cáo.
Hai công cụ ngoài là chương trình Go biên dịch sẵn, còn pipeline của đề tài chạy trên Python nên mỗi
lần chạy phải trả thêm chi phí khởi động trình thông dịch và nạp mô hình.
"""

import os
import re
import sys
import json
import time
import random
import shutil
import argparse
import platform
import tempfile
import statistics
import subprocess

import numpy as np
import pandas as pd

from src.candidate import extract_candidates
from src.entropy_scanner import scan_with_regex_and_entropy
from src.feature_extractor import encode_features, extract_features
from src.regex_scanner import scan_with_regex
from src.scoring import load_model, score_lines

SEED = 42


# ----------------------------------------------------------------- dữ liệu
def load_lines(data_dir, source, split, max_lines):
    if source == "creddata":
        path = os.path.join(data_dir, "external", "creddata.csv")
        df = pd.read_csv(path, keep_default_na=False)
        df = df[df["split"] == split]
    else:
        df = pd.read_csv(os.path.join(data_dir, f"{split}.csv"), keep_default_na=False)
    if len(df) > max_lines:
        df = df.sample(max_lines, random_state=SEED)
    texts = df["text"].astype(str).tolist()
    paths = df["file_path"].astype(str).tolist() if "file_path" in df.columns else [""] * len(df)
    return texts, paths


def timed(fn, repeat):
    """Một lần chạy khởi động (bỏ), rồi repeat lần đo. Trả về danh sách giây."""
    fn()
    out = []
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        out.append(time.perf_counter() - t)
    return out


def summarize(seconds, n_lines):
    med = statistics.median(seconds)
    return {"median_s": med, "min_s": min(seconds), "max_s": max(seconds),
            "ms_per_1000_lines": med / n_lines * 1000 * 1000, "lines_per_s": n_lines / med}


# ---------------------------------------------------------------- phân rã
def profile_phases(texts, paths, model, columns):
    t0 = time.perf_counter()
    cands = [extract_candidates(t) for t in texts]
    t1 = time.perf_counter()
    rows = []
    for text, path, cs in zip(texts, paths, cands):
        for c in cs:
            rows.append(encode_features(extract_features(c.value, text, path or "", c.regex_type,
                                                         source=c.source, start=c.start)))
    t2 = time.perf_counter()
    X = pd.DataFrame(rows).reindex(columns=columns, fill_value=0) if rows else None
    t3 = time.perf_counter()
    if X is not None:
        model.predict_proba(X)
    t4 = time.perf_counter()
    return {"trich_candidate_s": t1 - t0, "tinh_feature_s": t2 - t1, "dung_bang_s": t3 - t2,
            "du_doan_s": t4 - t3, "so_candidate": len(rows)}


# ------------------------------------------------------- chạy chương trình
def make_mini_repo(texts, n_files=20, lines_per_file=200):
    """Dựng một repo nhỏ từ các dòng thật để đo end-to-end. Trả về (thư mục, số file)."""
    root = tempfile.mkdtemp(prefix="sg_timing_")
    rng = random.Random(SEED)
    for i in range(n_files):
        chunk = rng.sample(texts, min(lines_per_file, len(texts)))
        with open(os.path.join(root, f"file_{i:02d}.py"), "w", encoding="utf-8") as f:
            f.write("\n".join(chunk) + "\n")
    return root, n_files


def run_wall(cmd, repeat, cwd=None):
    """Đo thời gian chạy một lệnh ngoài: 1 lần khởi động rồi repeat lần. Trả về (danh sách giây, stdout lần cuối)."""
    def once():
        t = time.perf_counter()
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        return time.perf_counter() - t, p
    once()
    times, last = [], None
    for _ in range(repeat):
        s, last = once()
        times.append(s)
    return times, last


def tool_version(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (out.stdout + out.stderr).strip().splitlines()[0]
    except Exception:
        return "không rõ"


def fmt_ms(x):
    return f"{x:,.1f}"


# --------------------------------------------------------------------- chính
def main():
    parser = argparse.ArgumentParser(description="Đo thời gian xử lý")
    parser.add_argument("--model", default="production")
    parser.add_argument("--source", choices=["creddata", "synthetic"], default="creddata")
    parser.add_argument("--split", choices=["val", "test"], default="val")
    parser.add_argument("--max-lines", type=int, default=5000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--file-lines", type=int, default=200, help="Cỡ file điển hình khi đo độ trễ một file")
    parser.add_argument("--repo-path", default=None, help="Thư mục repo thật để đo end-to-end (mặc định: repo nhỏ dựng tự động)")
    parser.add_argument("--gitleaks", default=None)
    parser.add_argument("--trufflehog", default=None)
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    reports_dir = os.path.join(base_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    texts, paths = load_lines(os.path.join(base_dir, "data"), args.source, args.split, args.max_lines)
    n = len(texts)
    model, columns = load_model(args.model)
    machine = {"he_dieu_hanh": platform.platform(), "cpu": platform.processor() or "không rõ",
               "so_nhan_logic": os.cpu_count(), "python": platform.python_version()}
    print(f"Đo trên {n} dòng ({args.source}/{args.split}), lặp {args.repeat} lần. Máy: {machine}\n")

    # 1. Thông lượng từng phương pháp
    methods = {
        "Regex": lambda: [scan_with_regex(t) for t in texts],
        "Regex + Entropy": lambda: [scan_with_regex_and_entropy(t, 4.0) for t in texts],
        "Chỉ trích candidate": lambda: [extract_candidates(t) for t in texts],
        "Pipeline ML đầy đủ": lambda: score_lines(zip(texts, paths), model, columns),
    }
    throughput = {}
    for name, fn in methods.items():
        print(f"đang đo: {name}...")
        throughput[name] = summarize(timed(fn, args.repeat), n)

    # 2. Phân rã pipeline
    consistent = sum(len(extract_candidates(t)) for t in texts[:300]) == sum(
        s.n_candidates for s in score_lines(zip(texts[:300], paths[:300]), model, columns))
    profile_phases(texts[:200], paths[:200], model, columns)  # khởi động
    phases_runs = [profile_phases(texts, paths, model, columns) for _ in range(args.repeat)]
    phases = {k: statistics.median(r[k] for r in phases_runs) for k in phases_runs[0] if k != "so_candidate"}
    phases["so_candidate"] = phases_runs[0]["so_candidate"]

    # 3. Độ trễ một file
    rng = random.Random(SEED)
    k = min(args.file_lines, n)
    lat = []
    for _ in range(60):
        start = rng.randint(0, max(n - k, 0))
        chunk_t, chunk_p = texts[start:start + k], paths[start:start + k]
        t = time.perf_counter()
        score_lines(zip(chunk_t, chunk_p), model, columns)
        lat.append((time.perf_counter() - t) * 1000)
    file_latency = {"lines": k, "median_ms": statistics.median(lat), "p95_ms": float(np.percentile(lat, 95))}

    # 4. Nạp mô hình
    load_times = []
    for _ in range(3):
        t = time.perf_counter()
        load_model(args.model)
        load_times.append(time.perf_counter() - t)

    # 5 và 6. End-to-end trên một thư mục
    if args.repo_path:
        repo, n_files, tmp_created = os.path.abspath(args.repo_path), None, False
    else:
        repo, n_files = make_mini_repo(texts)
        tmp_created = True
    end_to_end = {}
    try:
        main_py = os.path.join(base_dir, "main.py")
        cmd = [sys.executable, main_py, "--path", repo, "--mode", "full", "--no-report", "--model", args.model]
        print("đang đo: main.py end-to-end...")
        times, last = run_wall(cmd, args.repeat)
        m = re.search(r"Đã quét (\d+) file, (\d+) dòng", last.stdout or "")
        scanned = {"files": int(m.group(1)), "lines": int(m.group(2))} if m else {}
        end_to_end["main.py (Python, gồm khởi động và nạp mô hình)"] = {**summarize(times, scanned.get("lines", 1)), "scanned": scanned}

        report_tmp = os.path.join(tempfile.gettempdir(), "sg_gitleaks_timing.json")
        if args.gitleaks and shutil.which(args.gitleaks) or (args.gitleaks and os.path.isfile(args.gitleaks)):
            print("đang đo: Gitleaks...")
            gcmd = [args.gitleaks, "dir", repo, "--no-banner", "--redact", "--exit-code", "0",
                    "--report-format", "json", "--report-path", report_tmp]
            t, _ = run_wall(gcmd, args.repeat, cwd=tempfile.gettempdir())
            end_to_end[f"Gitleaks ({tool_version([args.gitleaks, 'version'])})"] = summarize(t, scanned.get("lines", 1))
        if args.trufflehog and (shutil.which(args.trufflehog) or os.path.isfile(args.trufflehog)):
            print("đang đo: TruffleHog...")
            tcmd = [args.trufflehog, "filesystem", repo, "--json", "--no-verification", "--no-update"]
            t, _ = run_wall(tcmd, args.repeat, cwd=tempfile.gettempdir())
            end_to_end[f"TruffleHog ({tool_version([args.trufflehog, '--version'])}, không verify)"] = summarize(t, scanned.get("lines", 1))
    finally:
        if tmp_created:
            shutil.rmtree(repo, ignore_errors=True)

    result = {"machine": machine, "n_lines": n, "source": args.source, "split": args.split, "repeat": args.repeat,
              "throughput": throughput, "pipeline_phases": phases, "pipeline_consistent": bool(consistent),
              "file_latency": file_latency, "model_load_s": {"min": min(load_times), "median": statistics.median(load_times)},
              "end_to_end": end_to_end, "end_to_end_target": args.repo_path or f"repo nhỏ tự dựng ({n_files} file x ~200 dòng)"}
    with open(os.path.join(reports_dir, "timing.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------ in kết quả
    print("\n" + "=" * 78)
    print(f"1. THÔNG LƯỢNG ({n} dòng; trung vị {args.repeat} lần)")
    print("=" * 78)
    print(f"{'Phương pháp':<26}{'ms / 1.000 dòng':>18}{'dòng / giây':>16}{'chậm hơn Regex':>16}")
    base = throughput["Regex"]["ms_per_1000_lines"]
    for name, s in throughput.items():
        print(f"{name:<26}{fmt_ms(s['ms_per_1000_lines']):>18}{s['lines_per_s']:>16,.0f}{s['ms_per_1000_lines'] / base:>15.1f}x")

    total = sum(v for k2, v in phases.items() if k2.endswith("_s"))
    print("\n2. PHÂN RÃ PIPELINE ML (trên cùng các dòng)")
    for key, label in (("trich_candidate_s", "Trích candidate"), ("tinh_feature_s", "Tính feature"),
                       ("dung_bang_s", "Dựng bảng"), ("du_doan_s", "Dự đoán (mô hình)")):
        print(f"  {label:<22}{phases[key] * 1000:>10,.0f} ms  ({phases[key] / total:>5.1%})")
    print(f"  Số candidate: {phases['so_candidate']} (trung bình {phases['so_candidate'] / n:.2f} / dòng)"
          f" | khớp với scoring.score_lines: {'có' if consistent else 'KHÔNG — kiểm tra lại'}")

    print(f"\n3. ĐỘ TRỄ MỘT FILE {file_latency['lines']} dòng: trung vị {file_latency['median_ms']:.1f} ms, p95 {file_latency['p95_ms']:.1f} ms")
    print(f"4. NẠP MÔ HÌNH: {statistics.median(load_times) * 1000:.0f} ms (trung vị)")
    print(f"\n5-6. END-TO-END trên {result['end_to_end_target']}")
    for name, s in end_to_end.items():
        extra = f"  (quét {s['scanned']['files']} file, {s['scanned']['lines']} dòng)" if "scanned" in s and s["scanned"] else ""
        print(f"  {name:<58}{s['median_s']:>7.2f} s{extra}")
    print(f"\n✅ Đã lưu reports/timing.json")


if __name__ == "__main__":
    main()
