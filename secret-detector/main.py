import sys
import os
import re
import subprocess
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import argparse
import joblib
import pandas as pd
from src.train_ml import extract_features

# Thư mục bị loại trừ khỏi scan — so khớp CHÍNH XÁC tên thư mục,
# không dùng substring ("data" in root) vì dễ khớp nhầm (metadata, userdata, AppData...)
EXCLUDED_DIRS = {"venv", ".git", "node_modules", "data", "secret-detector", "dist", "build", "coverage", "__pycache__"}

# File luôn bỏ qua: lock file chứa hash checksum (npm/yarn/pnpm), không phải secret
EXCLUDED_FILENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}

SCAN_EXTENSIONS = ('.js', '.py', '.json', '.env', '.yml', '.yaml', '.md', '.txt')

# Một dòng chỉ được coi là "ứng viên secret" nếu nó trông giống PHÉP GÁN GIÁ TRỊ:
#   KEY = 'value...'   KEY: "value..."   KEY=value_no_quote
# Loại trừ các dòng chỉ khai báo tên (import/destructuring), ví dụ:
#   generateAccessToken,
#   const { getProjectById } = require(...)
ASSIGNMENT_PATTERN = re.compile(
    r'''(=|:)\s*['"]?[A-Za-z0-9+/_\-\.]{12,}['"]?'''
)


def is_candidate_line(line_str):
    stripped = line_str.strip()
    if stripped.startswith(('import ', 'export ', 'require(')) and '=' not in stripped:
        return False
    if re.match(r'^[A-Za-z0-9_]+,?$', stripped):  # chỉ 1 identifier + dấu phẩy, không có giá trị
        return False
    return bool(ASSIGNMENT_PATTERN.search(line_str))


def is_excluded_path(file_path):
    parts = os.path.normpath(file_path).split(os.sep)
    if any(p in EXCLUDED_DIRS for p in parts):
        return True
    if os.path.basename(file_path) in EXCLUDED_FILENAMES:
        return True
    return False


def get_staged_files(repo_dir):
    """Lấy danh sách file đã git add (staged), loại bỏ file đã bị xoá (status D)."""
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-status', '--diff-filter=ACMR'],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[ERROR] Không đọc được danh sách file staged qua git: {e}")
        sys.exit(1)

    files = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        _, path = line.split('\t', 1)
        files.append(os.path.join(repo_dir, path))
    return files


def scan_files(file_paths, threshold=0.7):
    model_path = os.path.join(os.path.dirname(__file__), "models", "secret_ml_model.pkl")
    if not os.path.exists(model_path):
        print("[ERROR] Chưa tìm thấy mô hình ML. Vui lòng chạy train_ml.py trước.")
        sys.exit(1)

    clf = joblib.load(model_path)
    detected_secrets = []

    for file_path in file_paths:
        if not file_path.endswith(SCAN_EXTENSIONS):
            continue
        if is_excluded_path(file_path):
            continue
        if not os.path.exists(file_path):
            continue

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                for idx, line in enumerate(lines, 1):
                    line_str = line.strip()
                    if not line_str or len(line_str) < 10:
                        continue

                    if not is_candidate_line(line_str):
                        continue

                    df_temp = pd.DataFrame([{"text": line_str}])
                    features = extract_features(df_temp)
                    prob = clf.predict_proba(features)[0][1]

                    if prob >= threshold:
                        detected_secrets.append({
                            "file": file_path,
                            "line": idx,
                            "content": line_str[:50],
                            "confidence": round(prob * 100, 2)
                        })
        except Exception:
            pass

    return detected_secrets


def report_and_exit(detected_secrets):
    print("\n=== BÁO CÁO KIỂM TRA SECRET LEAKAGE ===")
    if detected_secrets:
        print(f"❌ PHÁT HIỆN {len(detected_secrets)} NGUY CƠ LỘ SECRET!\n")
        for secret in detected_secrets:
            print(f"  [!] File: {secret['file']} (Dòng {secret['line']})")
            print(f"      Nội dung: {secret['content']}...")
            print(f"      Độ tin cậy Rủi ro: {secret['confidence']}%\n")
        print("⛔ LỖI: HỆ THỐNG ĐÃ TỰ ĐỘNG NGĂN CHẶN PROCESS / PIPELINE!")
        sys.exit(1)
    else:
        print("✅ KHÔNG PHÁT HIỆN SECRET. PIPELINE AN TOÀN!")
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Secret Detection Engine")
    parser.add_argument("--path", type=str, default=".", help="Thư mục repo (dùng khi --mode full)")
    parser.add_argument("--threshold", type=float, default=0.7, help="Ngưỡng rủi ro (0.0 - 1.0)")
    parser.add_argument(
        "--mode",
        choices=["staged", "full"],
        default="staged",
        help="staged = chỉ quét file đã git add (dùng cho pre-commit hook, mặc định). "
             "full = quét toàn bộ thư mục (dùng cho CI/CD scan định kỳ, không phụ thuộc staging)."
    )
    args = parser.parse_args()

    if args.mode == "staged":
        repo_dir = os.path.abspath(args.path)
        targets = get_staged_files(repo_dir)
    else:
        targets = []
        for root, dirs, files in os.walk(args.path):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for file in files:
                targets.append(os.path.join(root, file))

    secrets_found = scan_files(targets, args.threshold)
    report_and_exit(secrets_found)