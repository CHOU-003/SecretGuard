import sys
import os
import re
import subprocess
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import argparse

import joblib

import pandas as pd
import requests
from dotenv import load_dotenv
from src.train_ml import extract_features

# Nạp .env riêng của secret-detector (BACKEND_URL, SERVICE_API_KEY)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

EXCLUDED_DIRS = {"venv", ".git", "node_modules", "data", "secret-detector", "dist", "build", "coverage", "__pycache__"}
EXCLUDED_FILENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
SCAN_EXTENSIONS = ('.js', '.py', '.json', '.env', '.yml', '.yaml', '.md', '.txt')

ASSIGNMENT_PATTERN = re.compile(
    r'''(=|:)\s*['"]?[A-Za-z0-9+/_\-\.]{12,}['"]?'''
)


def is_candidate_line(line_str):
    stripped = line_str.strip()
    if stripped.startswith(('import ', 'export ', 'require(')) and '=' not in stripped:
        return False
    if re.match(r'^[A-Za-z0-9_]+,?$', stripped):
        return False
    return bool(ASSIGNMENT_PATTERN.search(line_str))


def is_excluded_path(file_path):
    parts = os.path.normpath(file_path).split(os.sep)
    if any(p in EXCLUDED_DIRS for p in parts):
        return True
    if os.path.basename(file_path) in EXCLUDED_FILENAMES:
        return True
    return False


def guess_secret_type(line_str):
    upper = line_str.upper()
    if 'AWS' in upper and ('KEY' in upper or 'SECRET' in upper):
        return 'AWS_KEY'
    if 'GITHUB' in upper and 'TOKEN' in upper:
        return 'GITHUB_TOKEN'
    if 'JWT' in upper:
        return 'JWT'
    if re.search(r'(POSTGRES|MYSQL|MONGODB|DATABASE_URL|DB_CONNECTION|CONNECTION_STRING)', upper):
        return 'DB_CONNECTION'
    if 'API_KEY' in upper or 'APIKEY' in upper:
        return 'API_KEY'
    if 'PASSWORD' in upper or 'PASSWD' in upper:
        return 'PASSWORD'
    if 'SECRET' in upper:
        return 'GENERIC_SECRET'
    return 'UNKNOWN'


def risk_level_from_confidence(confidence_pct):
    if confidence_pct >= 85:
        return 'high'
    if confidence_pct >= 70:
        return 'medium'
    return 'low'


def get_staged_files(repo_dir):
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-status', '--diff-filter=ACMR'],
            cwd=repo_dir, capture_output=True, text=True, check=True,
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


def get_git_commit_hash(repo_dir):
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo_dir,
                                 capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception:
        return None


def get_git_branch(repo_dir):
    try:
        result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=repo_dir,
                                 capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception:
        return None


def scan_files(file_paths, warn_threshold=0.4):
    """Chấm điểm mọi dòng ứng viên, trả về TẤT CẢ finding có prob >= warn_threshold
    (không chỉ những cái vượt ngưỡng block), để còn phân loại blocked/warned."""
    model_path = os.path.join(os.path.dirname(__file__), "models", "secret_ml_model.pkl")
    if not os.path.exists(model_path):
        print("[ERROR] Chưa tìm thấy mô hình ML. Vui lòng chạy train_ml.py trước.")
        sys.exit(1)

    clf = joblib.load(model_path)
    findings = []

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

                    if prob >= warn_threshold:
                        confidence = round(prob * 100, 2)
                        findings.append({
                            "file": file_path,
                            "line": idx,
                            "content": line_str[:50],
                            "confidence": confidence,
                            "secret_type": guess_secret_type(line_str),
                            "risk_level": risk_level_from_confidence(confidence),
                        })
        except Exception:
            pass

    return findings


def determine_status(findings, block_threshold):
    if not findings:
        return "passed"
    max_conf = max(f["confidence"] for f in findings) / 100
    return "blocked" if max_conf >= block_threshold else "warned"


def print_report(findings, block_threshold):
    print("\n=== BÁO CÁO KIỂM TRA SECRET LEAKAGE ===")
    if not findings:
        print("✅ KHÔNG PHÁT HIỆN SECRET. PIPELINE AN TOÀN!")
        return

    print(f"⚠️  PHÁT HIỆN {len(findings)} NGUY CƠ LỘ SECRET!\n")
    for f in findings:
        tag = "❌ BLOCK" if (f["confidence"] / 100) >= block_threshold else "⚠️  WARN"
        print(f"  [{tag}] File: {f['file']} (Dòng {f['line']}) — {f['secret_type']}")
        print(f"      Nội dung: {f['content']}...")
        print(f"      Độ tin cậy rủi ro: {f['confidence']}%\n")


def post_scan_result(backend_url, api_key, project_name, commit_hash, branch, trigger_type, status, findings):
    if not backend_url or not api_key:
        print("⚠️  Bỏ qua ghi log về backend: thiếu BACKEND_URL hoặc SERVICE_API_KEY (kiểm tra secret-detector/.env)")
        return

    payload = {
        "project_name": project_name,
        "commit_hash": commit_hash,
        "branch": branch,
        "trigger_type": trigger_type,
        "status": status,
        "findings": [
            {
                "file_path": f["file"],
                "line_number": f["line"],
                "secret_type": f["secret_type"],
                "confidence_score": round(f["confidence"] / 100, 4),
                "risk_level": f["risk_level"],
            }
            for f in findings
        ],
    }

    try:
        resp = requests.post(
            f"{backend_url}/api/scans",
            json=payload,
            headers={"x-api-key": api_key},
            timeout=5,
        )
        if resp.status_code == 201:
            data = resp.json()
            print(f"📡 Đã ghi log scan vào backend (scan id: {data.get('id')})")
        else:
            print(f"⚠️  Backend từ chối ghi log scan: HTTP {resp.status_code} — {resp.text}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Không kết nối được backend để ghi log scan: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Secret Detection Engine")
    parser.add_argument("--path", type=str, default=".", help="Thư mục repo cần quét")
    parser.add_argument("--threshold", type=float, default=0.7, help="Ngưỡng BLOCK (0.0 - 1.0)")
    parser.add_argument("--warn-threshold", type=float, default=0.4, help="Ngưỡng CẢNH BÁO, thấp hơn threshold")
    parser.add_argument("--mode", choices=["staged", "full"], default="staged",
                         help="staged = chỉ quét file đã git add (pre-commit). full = quét toàn bộ thư mục (CI định kỳ).")
    parser.add_argument("--trigger-type", choices=["local_precommit", "ci_pipeline"], default="local_precommit")
    parser.add_argument("--project-name", type=str, default=None, help="Mặc định lấy tên thư mục repo")
    parser.add_argument("--backend-url", type=str, default=os.getenv("BACKEND_URL", "http://localhost:3000"))
    parser.add_argument("--api-key", type=str, default=os.getenv("SERVICE_API_KEY"))
    parser.add_argument("--no-report", action="store_true", help="Không gọi backend ghi log (chỉ scan tại chỗ)")
    args = parser.parse_args()

    repo_dir = os.path.abspath(args.path)
    project_name = args.project_name or os.path.basename(repo_dir)

    if args.mode == "staged":
        targets = get_staged_files(repo_dir)
    else:
        targets = []
        for root, dirs, files in os.walk(args.path):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for file in files:
                targets.append(os.path.join(root, file))

    findings = scan_files(targets, warn_threshold=args.warn_threshold)
    status = determine_status(findings, args.threshold)
    print_report(findings, args.threshold)

    # Theo đúng luồng thiết kế: dù block hay không, luôn gọi backend ghi log
    if not args.no_report:
        commit_hash = get_git_commit_hash(repo_dir)
        branch = get_git_branch(repo_dir)
        post_scan_result(
            args.backend_url, args.api_key, project_name,
            commit_hash, branch, args.trigger_type, status, findings,
        )

    if status == "blocked":
        print("⛔ LỖI: HỆ THỐNG ĐÃ TỰ ĐỘNG NGĂN CHẶN PROCESS / PIPELINE!")
        sys.exit(1)
    elif status == "warned":
        print("⚠️  Cảnh báo: có secret nghi vấn nhưng chưa vượt ngưỡng block. Commit vẫn được phép.")
        sys.exit(0)
    else:
        sys.exit(0)