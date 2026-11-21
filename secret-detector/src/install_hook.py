"""
install_hook.py — cài Git hook pre-commit cho SecretGuard

Chạy (từ bất kỳ đâu trong repo):
    python secret-detector/install_hook.py
    python secret-detector/install_hook.py --python C:\\path\\to\\python.exe    # chọn trình thông dịch khác
    python secret-detector/install_hook.py --uninstall

Hook gọi `secret-detector/main.py --mode staged` bằng Python của môi trường ảo `secret-detector/venv`
(Windows: venv/Scripts/python.exe, Linux và macOS: venv/bin/python), nên thư viện đã cài trong venv
được dùng đúng. Nếu thiếu venv, hook báo rõ cách khắc phục thay vì lỗi khó hiểu.

Hook nói đúng lý do commit bị hủy dựa vào mã thoát của engine:
    1 = phát hiện secret vượt ngưỡng chặn
    2 = lỗi của engine (thiếu mô hình, không phải git repo...)
Một lỗi Python chưa được xử lý cũng trả mã 1, nên với mã 1 hook luôn nhắc đọc thông báo phía trên.
Với mọi mã khác 0, hook hủy commit (fail closed): một cổng bảo mật không nên tự mở khi nó hỏng.

Hook nằm trong .git/hooks nên KHÔNG được Git theo dõi và không tự có khi người khác clone repo;
mỗi máy phải chạy script này một lần. Người dùng vẫn có thể bỏ qua hook bằng `git commit --no-verify`,
vì vậy bước quét trong CI (kèm branch protection) mới là điểm chặn bắt buộc.
"""

import os
import sys
import stat
import shutil
import argparse
import subprocess

MARKER = "SecretGuard pre-commit hook"

HOOK_TEMPLATE = """#!/bin/sh
# {marker} (tạo bởi secret-detector/install_hook.py; chạy lại script để cập nhật)
ROOT="$(git rev-parse --show-toplevel)"
PY="{python}"
case "$PY" in
  /*|[A-Za-z]:*) ;;                 # đường dẫn tuyệt đối: dùng nguyên
  *) PY="$ROOT/$PY" ;;              # đường dẫn tương đối: tính từ gốc repo
esac

if [ ! -f "$PY" ]; then
  echo "[SecretGuard] Không thấy Python của venv: $PY"
  echo "[SecretGuard] Tạo venv và cài thư viện: python -m venv secret-detector/venv && secret-detector/venv/<Scripts|bin>/pip install -r secret-detector/requirements.txt"
  exit 1
fi

echo "[SecretGuard] Đang kiểm tra secret trong các file sắp commit..."
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 "$PY" "$ROOT/secret-detector/main.py" --path "$ROOT" --mode staged
RESULT=$?

if [ "$RESULT" -eq 0 ]; then
  exit 0
elif [ "$RESULT" -eq 2 ]; then
  echo "[SecretGuard] Engine gặp lỗi (mã 2). Commit bị hủy để an toàn; xem thông báo [ERROR] phía trên."
else
  echo "[SecretGuard] Commit bị HỦY (mã $RESULT): phát hiện secret vượt ngưỡng chặn, hoặc engine lỗi chưa xử lý; xem thông báo phía trên."
  echo "[SecretGuard] Nếu là báo nhầm: thêm '# secretguard:ignore' cuối dòng hoặc liệt kê file trong .secretguardignore."
fi
exit 1
"""


def git_root():
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit("Không nằm trong một git repo. Hãy chạy lệnh này bên trong repo.")
    return os.path.normpath(result.stdout.strip())


def default_python_rel():
    sub = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return f"secret-detector/venv/{sub}"


def main():
    parser = argparse.ArgumentParser(description="Cài Git hook pre-commit cho SecretGuard")
    parser.add_argument("--python", default=None, help="Trình thông dịch Python để chạy engine (mặc định: venv của secret-detector)")
    parser.add_argument("--force", action="store_true", help="Ghi đè hook đã có (hook cũ được sao lưu thành pre-commit.backup)")
    parser.add_argument("--uninstall", action="store_true", help="Gỡ hook của SecretGuard")
    args = parser.parse_args()

    root = git_root()
    hooks_dir = os.path.join(root, ".git", "hooks")
    hook_path = os.path.join(hooks_dir, "pre-commit")
    os.makedirs(hooks_dir, exist_ok=True)

    existing = None
    if os.path.exists(hook_path):
        with open(hook_path, encoding="utf-8", errors="replace") as f:
            existing = f.read()

    if args.uninstall:
        if existing and MARKER in existing:
            os.remove(hook_path)
            print(f"✅ Đã gỡ hook: {hook_path}")
        else:
            print("Không có hook của SecretGuard để gỡ.")
        return

    if existing and MARKER not in existing:
        if not args.force:
            sys.exit(f"Đã có một hook pre-commit khác tại {hook_path}. Dùng --force để ghi đè (hook cũ sẽ được sao lưu).")
        shutil.copy2(hook_path, hook_path + ".backup")
        print(f"Đã sao lưu hook cũ: {hook_path}.backup")

    python = (args.python or default_python_rel()).replace("\\", "/")
    with open(hook_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(HOOK_TEMPLATE.format(marker=MARKER, python=python))
    os.chmod(hook_path, os.stat(hook_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    check = python if os.path.isabs(python) else os.path.join(root, python)
    print(f"✅ Đã cài hook: {hook_path}")
    print(f"   Python dùng để chạy engine: {python}")
    if not os.path.isfile(check):
        print(f"⚠️  Chưa thấy {check}. Hãy tạo venv và cài thư viện: "
              "python -m venv secret-detector/venv, rồi pip install -r secret-detector/requirements.txt")
    print("   Thử: tạo file chứa khóa giả, `git add` và `git commit`. Bỏ qua hook (không khuyến khích): git commit --no-verify")


if __name__ == "__main__":
    main()
