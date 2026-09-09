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

from src.feature_extractor import extract_features
from src.regex_scanner import scan_with_regex

# Nạp .env riêng của secret-detector (BACKEND_URL, SERVICE_API_KEY)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

EXCLUDED_DIRS = {"venv", ".git", "node_modules", "data", "secret-detector", "dist", "build", "coverage", "__pycache__"}
EXCLUDED_FILENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
SCAN_EXTENSIONS = ('.js', '.py', '.json', '.env', '.yml', '.yaml', '.md', '.txt')

# Bắt cặp (biến/khoá) = giá trị nghi vấn -> capture riêng phần GIÁ TRỊ (group 2)
# để dùng làm "candidate" thật cho feature_extractor, thay vì đưa cả dòng vào.
ASSIGNMENT_PATTERN = re.compile(
    r'''(=|:)\s*['"]?([A-Za-z0-9+/_\-\.]{12,})['"]?'''
)


def find_candidate_value(line_str):
    """Trả về chuỗi giá trị nghi vấn (candidate) trong dòng, hoặc None nếu không có.
    Đây là lưới quét rộng (broad net) dựa trên cấu trúc gán biến, KHÔNG cần khớp
    đúng 1 loại secret cụ thể nào -> vẫn bắt được các secret không theo pattern
    biết trước (đây chính là giá trị mà tầng ML mang lại so với chỉ dùng Regex).
    """
    stripped = line_str.strip()
    if stripped.startswith(('import ', 'export ', 'require(')) and '=' not in stripped:
        return None
    if re.match(r'^[A-Za-z0-9_]+,?$', stripped):
        return None
    match = ASSIGNMENT_PATTERN.search(line_str)
    return match.group(2) if match else None


def is_excluded_path(file_path):
    parts = os.path.normpath(file_path).split(os.sep)
    if any(p in EXCLUDED_DIRS for p in parts):
        return True
    if os.path.basename(file_path) in EXCLUDED_FILENAMES:
        return True
    return False


def guess_secret_type(line_str, regex_type=None):
    # Ưu tiên loại đã được regex_scanner khớp chính xác
    if regex_type:
        return regex_type
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


def load_model_and_columns():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, "models", "secret_ml_model.pkl")
    columns_path = os.path.join(base_dir, "models", "feature_columns.pkl")

    if not os.path.exists(model_path):
        print("[ERROR] Chưa tìm thấy mô hình ML. Vui lòng chạy build_dataset.py -> build_features.py -> train_ml.py trước.")
        sys.exit(1)
    if not os.path.exists(columns_path):
        print("[ERROR] Chưa tìm thấy feature_columns.pkl. Vui lòng chạy lại train_ml.py (bản mới) để lưu đủ cả 2 file.")
        sys.exit(1)

    clf = joblib.load(model_path)
    feature_columns = joblib.load(columns_path)
    return clf, feature_columns


def build_feature_vector(candidate, line_content, file_path, regex_type, feature_columns):
    """Trích feature cho 1 candidate rồi align đúng thứ tự cột như lúc train
    (bắt buộc vì one-hot regex_type có thể thiếu/thừa cột so với lúc train)."""
    raw_features = extract_features(candidate, line_content, file_path, regex_type)
    df = pd.DataFrame([raw_features])
    df = pd.get_dummies(df, columns=['regex_type'])
    df = df.reindex(columns=feature_columns, fill_value=0)
    return df


def scan_files(file_paths, clf, feature_columns, warn_threshold=0.4):
    """Với mỗi dòng nghi vấn: lấy candidate (giá trị được gán) + regex_type
    (nếu regex_scanner khớp được loại nào đó), rồi đưa qua ML để chấm điểm.
    Trả về TẤT CẢ finding có prob >= warn_threshold (không chỉ cái vượt ngưỡng
    block), để còn phân loại blocked/warned."""
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

                    candidate = find_candidate_value(line_str)
                    if not candidate:
                        continue

                    # Regex_scanner chạy trên cả dòng để biết có khớp loại secret
                    # biết trước không (AWS/Slack/GitHub/Private Key...). Nếu không
                    # khớp gì, regex_type=None -> ML vẫn xử lý bình thường, đây
                    # chính là trường hợp ML "phát huy tác dụng" hơn Regex thuần.
                    regex_matches = scan_with_regex(line_str)
                    regex_type = regex_matches[0]["type"] if regex_matches else None

                    feature_df = build_feature_vector(candidate, line_str, file_path, regex_type, feature_columns)
                    prob = clf.predict_proba(feature_df)[0][1]

                    if prob >= warn_threshold:
                        confidence = round(prob * 100, 2)
                        findings.append({
                            "file": file_path,
                            "line": idx,
                            "content": line_str[:50],
                            "confidence": confidence,
                            "secret_type": guess_secret_type(line_str, regex_type),
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

    clf, feature_columns = load_model_and_columns()

    if args.mode == "staged":
        targets = get_staged_files(repo_dir)
    else:
        targets = []
        for root, dirs, files in os.walk(args.path):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for file in files:
                targets.append(os.path.join(root, file))

    findings = scan_files(targets, clf, feature_columns, warn_threshold=args.warn_threshold)
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