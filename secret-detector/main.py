"""
main.py (v3) — Secret Detection Engine: quét, chặn và ghi log

Dùng ở 2 nơi (giao diện dòng lệnh giữ nguyên so với bản trước):
    pre-commit hook :  python main.py --path . --threshold 0.7            (mặc định --mode staged)
    CI / GitHub Actions: python main.py --path . --mode full --trigger-type ci_pipeline

Luồng: lấy danh sách file -> chấm điểm TỪNG DÒNG bằng scoring.score_lines (cùng đường xử lý
với evaluate.py: trích candidate -> feature -> model đã hiệu chỉnh -> lấy điểm cao nhất) ->
phân loại passed/warned/blocked -> LUÔN ghi log về backend (trừ khi --no-report) -> exit 1
nếu blocked.

Những chỗ khác bản trước, và lý do:
  * Không còn tự trích candidate/feature riêng trong file này. Trước đây main.py và lúc train
    nhìn thấy hai thứ khác nhau, nên số liệu đánh giá không phản ánh hệ thống chạy thật.
  * Mode staged đọc nội dung từ INDEX (`git show :file`), không đọc working tree. Nếu bạn
    sửa file sau khi `git add`, thứ sắp được commit mới là thứ cần quét.
  * Đường dẫn dùng để loại trừ và để chấm điểm là đường dẫn TƯƠNG ĐỐI so với repo. Trước đây
    dùng đường dẫn tuyệt đối nên chỉ cần repo nằm trong thư mục tên `build/` hay `tests/`
    là toàn bộ file bị loại hoặc bị coi là file test.
  * Không in nguyên giá trị secret ra console/log CI: log CI thường được nhiều người đọc và
    lưu lâu. Giá trị được che thành `Sq***(17)`.
  * Khi chạy trên CI, lấy commit/branch từ biến môi trường của CI (checkout trên CI thường
    ở trạng thái detached HEAD nên `git rev-parse --abbrev-ref HEAD` chỉ ra "HEAD").

Loại trừ CÓ KIỂM SOÁT (để một dòng báo nhầm không làm pipeline đỏ mãi):
  * Thêm chú thích `secretguard:ignore` vào cuối dòng cần bỏ qua, ví dụ:
        API_KEY = "dummy-value-for-docs"  # secretguard:ignore
  * Hoặc liệt kê đường dẫn/mẫu glob (so với gốc repo) trong file `.secretguardignore`, mỗi dòng một mục;
    dòng bắt đầu bằng # là chú thích; mục kết thúc bằng / loại cả thư mục.
  Số dòng/file bị bỏ qua luôn được in ra để việc lạm dụng cơ chế này không bị che giấu.

Giới hạn đã biết: ở mode staged, commit_hash ghi vào backend là commit CHA (HEAD) vì commit
mới chưa tồn tại lúc pre-commit chạy.
"""

import sys
import os
import re
import argparse
import fnmatch
import subprocess

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
from dotenv import load_dotenv

from src.scoring import load_model, score_lines

# Nạp .env riêng của secret-detector (BACKEND_URL, SERVICE_API_KEY)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

EXCLUDED_DIRS = {"venv", ".venv", ".git", "node_modules", "data", "secret-detector", "dist", "build", "coverage", "__pycache__"}
EXCLUDED_FILENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
SCAN_EXTENSIONS = (
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".json", ".env", ".yml", ".yaml", ".md", ".txt",
    ".ini", ".cfg", ".conf", ".toml", ".properties", ".xml", ".sh", ".sql", ".tf", ".java", ".go", ".rb", ".php", ".cs",
)

REGEX_TYPE_LABELS = {
    "AWS Access Key": "AWS_KEY",
    "GitHub Personal Token": "GITHUB_TOKEN",
    "Slack Token": "SLACK_TOKEN",
    "Private Key": "PRIVATE_KEY",
}


IGNORE_MARKER = "secretguard:ignore"
IGNORE_FILE = ".secretguardignore"


def load_ignore_patterns(root):
    path = os.path.join(root, IGNORE_FILE)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]


def is_ignored_path(rel_path, patterns):
    rel = rel_path.replace("\\", "/")
    for pat in patterns:
        if pat.endswith("/"):
            if rel.startswith(pat) or f"/{pat}" in f"/{rel}":
                return True
        elif fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(os.path.basename(rel), pat):
            return True
    return False


# ------------------------------------------------------------- lọc file
def is_excluded_path(rel_path):
    parts = rel_path.replace("\\", "/").split("/")
    if any(p in EXCLUDED_DIRS for p in parts[:-1]):
        return True
    return parts[-1] in EXCLUDED_FILENAMES


def should_scan(rel_path):
    base = os.path.basename(rel_path).lower()
    return base.endswith(SCAN_EXTENSIONS) or base.startswith(".env")


# ------------------------------------------------------------------ git
def run_git(args, cwd, binary=False):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=not binary, check=False)


def get_git_root(path):
    result = run_git(["rev-parse", "--show-toplevel"], cwd=path)
    if result.returncode != 0:
        print(f"[ERROR] {path} không nằm trong một git repo: {result.stderr.strip()}")
        sys.exit(1)
    return os.path.normpath(result.stdout.strip())


def list_staged_files(root):
    """Đường dẫn (tương đối so với root repo) của các file được thêm/sửa trong index."""
    result = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"], cwd=root, binary=True)
    if result.returncode != 0:
        print(f"[ERROR] Không đọc được danh sách file staged qua git: {result.stderr.decode('utf-8', 'replace').strip()}")
        sys.exit(1)
    names = result.stdout.decode("utf-8", errors="replace").split("\0")
    return [n for n in names if n]


def read_staged_blob(root, rel_path, max_bytes):
    """Nội dung file trong INDEX (thứ sắp được commit). None nếu không đọc được hoặc quá lớn."""
    result = run_git(["show", f":{rel_path}"], cwd=root, binary=True)
    if result.returncode != 0 or len(result.stdout) > max_bytes:
        return None
    return result.stdout.decode("utf-8", errors="replace")


def read_working_file(abs_path, max_bytes):
    try:
        if os.path.getsize(abs_path) > max_bytes:
            return None
        with open(abs_path, "rb") as f:
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return None


def collect_items(args, root_for_git, ignore_patterns):
    """Trả về (danh sách (đường_dẫn_tương_đối, nội_dung), số file quá lớn/không đọc được, số file bị ignore)."""
    max_bytes = args.max_file_kb * 1024
    items, skipped, ignored = [], 0, 0

    if args.mode == "staged":
        for rel in list_staged_files(root_for_git):
            if is_excluded_path(rel) or not should_scan(rel):
                continue
            if is_ignored_path(rel, ignore_patterns):
                ignored += 1
                continue
            content = read_staged_blob(root_for_git, rel, max_bytes)
            if content is None:
                skipped += 1
                continue
            items.append((rel, content))
    else:
        base = os.path.abspath(args.path)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
            for name in filenames:
                abs_path = os.path.join(dirpath, name)
                rel = os.path.relpath(abs_path, base).replace(os.sep, "/")
                if is_excluded_path(rel) or not should_scan(rel):
                    continue
                if is_ignored_path(rel, ignore_patterns):
                    ignored += 1
                    continue
                content = read_working_file(abs_path, max_bytes)
                if content is None:
                    skipped += 1
                    continue
                items.append((rel, content))
    return items, skipped, ignored


def get_git_commit_hash(repo_dir, trigger_type):
    if trigger_type == "ci_pipeline":
        for var in ("GITHUB_SHA", "CI_COMMIT_SHA"):
            if os.getenv(var):
                return os.getenv(var)
    result = run_git(["rev-parse", "HEAD"], cwd=repo_dir)
    return result.stdout.strip() if result.returncode == 0 else None


def get_git_branch(repo_dir, trigger_type):
    if trigger_type == "ci_pipeline":
        for var in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME", "CI_COMMIT_REF_NAME"):
            if os.getenv(var):
                return os.getenv(var)
    result = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir)
    return result.stdout.strip() if result.returncode == 0 else None


# ------------------------------------------------------------- chấm điểm
def guess_secret_type(line, cand):
    """Nhãn loại secret hiển thị trên dashboard. Ưu tiên pattern regex đã khớp chính xác."""
    if cand.regex_type in REGEX_TYPE_LABELS:
        return REGEX_TYPE_LABELS[cand.regex_type]
    if cand.source == "url":
        return "URL_CREDENTIALS"
    upper = line.upper()
    if "AWS" in upper and ("KEY" in upper or "SECRET" in upper):
        return "AWS_KEY"
    if "GITHUB" in upper and "TOKEN" in upper:
        return "GITHUB_TOKEN"
    if "JWT" in upper:
        return "JWT"
    if re.search(r"(POSTGRES|MYSQL|MONGODB|DATABASE_URL|DB_CONNECTION|CONNECTION_STRING)", upper):
        return "DB_CONNECTION"
    if "API_KEY" in upper or "APIKEY" in upper:
        return "API_KEY"
    if "PASSWORD" in upper or "PASSWD" in upper:
        return "PASSWORD"
    if "SECRET" in upper:
        return "GENERIC_SECRET"
    if "TOKEN" in upper:
        return "TOKEN"
    if "KEY" in upper:
        return "API_KEY"
    return "UNKNOWN"


def risk_level_from_confidence(confidence_pct):
    if confidence_pct >= 85:
        return "high"
    if confidence_pct >= 70:
        return "medium"
    return "low"


def mask_line(line, cand, width=90):
    """Che giá trị secret trong dòng để in ra console/log: giữ 2 ký tự đầu và độ dài."""
    v = cand.value
    masked = f"{v[:2]}***({len(v)})" if len(v) >= 4 else "***"
    shown = (line[:cand.start] + masked + line[cand.end:]).strip()
    return shown[:width] + ("…" if len(shown) > width else "")


def scan_items(items, model, columns, warn_threshold):
    findings, n_lines, n_ignored_lines = [], 0, 0
    for rel, content in items:
        lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        n_lines += len(lines)
        scores = score_lines(((ln, rel) for ln in lines), model, columns)
        for idx, (ln, ls) in enumerate(zip(lines, scores), 1):
            if ls.best is None or ls.score < warn_threshold:
                continue
            if IGNORE_MARKER in ln:
                n_ignored_lines += 1
                continue
            confidence = round(ls.score * 100, 2)
            findings.append({
                "file": rel,
                "line": idx,
                "content": mask_line(ln, ls.best),
                "confidence": confidence,
                "secret_type": guess_secret_type(ln, ls.best),
                "risk_level": risk_level_from_confidence(confidence),
            })
    return findings, n_lines, n_ignored_lines


def determine_status(findings, block_threshold):
    if not findings:
        return "passed"
    max_conf = max(f["confidence"] for f in findings) / 100
    return "blocked" if max_conf >= block_threshold else "warned"


def print_report(findings, block_threshold, n_files, n_lines, skipped, ignored_files=0, ignored_lines=0):
    print("\n=== BÁO CÁO KIỂM TRA SECRET LEAKAGE ===")
    print(f"Đã quét {n_files} file, {n_lines} dòng" + (f" (bỏ qua {skipped} file quá lớn/không đọc được)" if skipped else ""))
    if ignored_files or ignored_lines:
        print(f"ℹ️  Loại trừ có chủ đích: {ignored_files} file (.secretguardignore), {ignored_lines} dòng ({IGNORE_MARKER})")
    if not findings:
        print("✅ KHÔNG PHÁT HIỆN SECRET. PIPELINE AN TOÀN!")
        return

    print(f"⚠️  PHÁT HIỆN {len(findings)} NGUY CƠ LỘ SECRET!\n")
    for f in sorted(findings, key=lambda x: -x["confidence"]):
        tag = "❌ BLOCK" if (f["confidence"] / 100) >= block_threshold else "⚠️  WARN"
        print(f"  [{tag}] File: {f['file']} (Dòng {f['line']}) — {f['secret_type']}")
        print(f"      Nội dung: {f['content']}")
        print(f"      Độ tin cậy rủi ro: {f['confidence']}%\n")


# --------------------------------------------------------------- backend
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


def default_project_name(root, trigger_type):
    repo = os.getenv("GITHUB_REPOSITORY")  # dạng owner/name
    if trigger_type == "ci_pipeline" and repo:
        return repo.split("/")[-1]
    return os.path.basename(os.path.abspath(root))


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Secret Detection Engine")
    parser.add_argument("--path", type=str, default=".", help="Thư mục repo cần quét")
    parser.add_argument("--threshold", type=float, default=0.8, help="Ngưỡng BLOCK (0.0 - 1.0); chọn từ bảng quét ngưỡng trên validation")
    parser.add_argument("--warn-threshold", type=float, default=0.5, help="Ngưỡng CẢNH BÁO, thấp hơn threshold")
    parser.add_argument("--mode", choices=["staged", "full"], default="staged",
                        help="staged = chỉ quét file đã git add (pre-commit). full = quét toàn bộ thư mục (CI).")
    parser.add_argument("--trigger-type", choices=["local_precommit", "ci_pipeline"], default="local_precommit")
    parser.add_argument("--project-name", type=str, default=None, help="Mặc định lấy tên repo")
    parser.add_argument("--model", type=str, default="production",
                        help="production, hoặc tên thí nghiệm trong models/experiments/ (để thử mà chưa promote)")
    parser.add_argument("--max-file-kb", type=int, default=1024, help="Bỏ qua file lớn hơn mức này (KB)")
    parser.add_argument("--backend-url", type=str, default=os.getenv("BACKEND_URL", "http://localhost:3000"))
    parser.add_argument("--api-key", type=str, default=os.getenv("SERVICE_API_KEY"))
    parser.add_argument("--no-report", action="store_true", help="Không gọi backend ghi log (chỉ scan tại chỗ)")
    args = parser.parse_args()

    try:
        model, columns = load_model(args.model)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    repo_dir = os.path.abspath(args.path)
    git_root = get_git_root(repo_dir) if (args.mode == "staged" or not args.no_report) else repo_dir
    project_name = args.project_name or default_project_name(git_root, args.trigger_type)

    ignore_patterns = load_ignore_patterns(git_root)
    items, skipped, ignored_files = collect_items(args, git_root, ignore_patterns)
    findings, n_lines, ignored_lines = scan_items(items, model, columns, warn_threshold=args.warn_threshold)
    status = determine_status(findings, args.threshold)
    print_report(findings, args.threshold, len(items), n_lines, skipped, ignored_files, ignored_lines)

    # Theo đúng luồng thiết kế: dù block hay không, luôn gọi backend ghi log
    if not args.no_report:
        post_scan_result(
            args.backend_url, args.api_key, project_name,
            get_git_commit_hash(git_root, args.trigger_type),
            get_git_branch(git_root, args.trigger_type),
            args.trigger_type, status, findings,
        )

    if status == "blocked":
        print("⛔ LỖI: HỆ THỐNG ĐÃ TỰ ĐỘNG NGĂN CHẶN PROCESS / PIPELINE!")
        sys.exit(1)
    elif status == "warned":
        print("⚠️  Cảnh báo: có secret nghi vấn nhưng chưa vượt ngưỡng block. Commit vẫn được phép.")
        sys.exit(0)
    else:
        sys.exit(0)