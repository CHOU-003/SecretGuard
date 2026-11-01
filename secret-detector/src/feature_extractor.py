"""
feature_extractor.py
Trích xuất feature cho mô hình ML phân loại secret thật vs false positive.

Input: 1 candidate string (chuỗi secret đã được regex_scanner khớp ra),
       kèm ngữ cảnh (dòng chứa nó, đường dẫn file, loại regex đã khớp).

Lưu ý quan trọng: hàm extract_features() ở đây PHẢI được dùng giống hệt
ở cả train_ml.py (lúc train) lẫn main.py (lúc inference thật).
Nếu 2 nơi tính feature khác nhau dù chỉ 1 chi tiết, model sẽ dự đoán sai
hoàn toàn khi chạy thật dù accuracy lúc train rất cao.
"""

import re
from src.entropy_scanner import calculate_shannon_entropy
from src.regex_scanner import PATTERNS

# Các prefix đặc trưng hay gặp ở secret thật (tăng tín hiệu, không phải luật cứng)
KNOWN_PREFIXES = ('AKIA', 'ghp_', 'gho_', 'ghu_', 'ghs_', 'sk-', 'xox', 'AIza')

# Từ khóa nghi vấn xuất hiện trên dòng chứa candidate
SUSPICIOUS_KEYWORDS = ['key', 'secret', 'token', 'password', 'passwd', 'api', 'auth']

# Token trong đường dẫn cho thấy đây là file test/mock/mẫu (hay chứa key giả).
# So khớp theo TỪNG THÀNH PHẦN đường dẫn, không so chuỗi con, để tránh nhầm
# 'latest/', 'inspector/' (chứa 'test', 'spec') thành thư mục test.
TEST_PATH_TOKENS = {
    'test', 'tests', 'mock', 'mocks', 'example', 'examples',
    'sample', 'samples', 'fixture', 'fixtures', 'spec', 'specs',
}


def is_test_path_fn(file_path: str) -> bool:
    tokens = re.split(r'[\\/._\-\s]+', (file_path or '').lower())
    return any(t in TEST_PATH_TOKENS for t in tokens)


# --- Feature ngữ cảnh/hình dạng giá trị (v2) --------------------------------------------
# Tên khoá đứng NGAY TRƯỚC giá trị: "DB_PASSWORD = '...'" khác "label_password = 'Mật khẩu'".
# keyword_hits cũ chỉ đếm từ khoá trên cả dòng nên không phân biệt được hai trường hợp này.
_KEY_BEFORE_VALUE = re.compile(
    r"""([A-Za-z_][\w.\-\[\]]*)['"`\]]*\s*(?:=>|:=|==|=|:)\s*(?:[A-Za-z_][\w.:]*\()?['"`]*\s*$"""
)
KEY_SECRET_TOKENS = {
    "pass", "passwd", "password", "passphrase", "pwd", "secret", "token", "key", "apikey", "auth",
    "credential", "credentials", "cred", "creds", "private", "salt", "bearer", "jwt",
}
KEY_UI_TOKENS = {
    "label", "text", "msg", "message", "title", "placeholder", "hint", "description", "desc",
    "prompt", "error", "err", "caption", "tooltip", "locale", "lang", "i18n", "translation", "help",
}
CANDIDATE_SOURCES = ("regex", "url", "assignment", "token")  # khớp candidate.Candidate.source


def _name_tokens(name: str) -> set:
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)  # camelCase -> camel_Case
    return {t for t in re.split(r"[^A-Za-z0-9]+", name.lower()) if t}


def _key_before(line_content: str, start):
    """Tên khoá ngay trước giá trị, hoặc '' nếu không có ngữ cảnh gán."""
    if start is None or start <= 0:
        return ""
    m = _KEY_BEFORE_VALUE.search(line_content[:start][-100:])
    return m.group(1) if m else ""


def _longest_run_ratio(text: str) -> float:
    if not text:
        return 0.0
    best = run = 1
    for a, b in zip(text, text[1:]):
        run = run + 1 if a == b else 1
        best = max(best, run)
    return best / len(text)


def extract_features(candidate: str, line_content: str, file_path: str, regex_type: str = None,
                     source: str = None, start: int = None) -> dict:
    """
    Trích 1 dict feature cho 1 candidate string.

    candidate    : chuỗi secret nghi vấn (matched_text từ regex_scanner), KHÔNG phải cả dòng
    line_content : nội dung cả dòng chứa candidate (để lấy ngữ cảnh: từ khóa, comment...)
    file_path    : đường dẫn file (để biết có phải test/mock file không)
    regex_type   : tên loại pattern đã khớp (vd "AWS Access Key"), None nếu candidate
                   không xuất phát từ regex_scanner (vd tầng ML-only)
    source       : nguồn trích candidate (regex | url | assignment | token), None nếu không rõ
    start        : vị trí bắt đầu của candidate trong line_content (để lấy tên khoá đứng trước)
    """
    candidate = candidate or ""
    length = len(candidate)

    digit_count = sum(c.isdigit() for c in candidate)
    upper_count = sum(c.isupper() for c in candidate)
    lower_count = sum(c.islower() for c in candidate)
    special_count = sum(not c.isalnum() for c in candidate)
    hex_charset_count = sum(c in '0123456789abcdefABCDEF' for c in candidate)

    is_base64_charset = bool(re.fullmatch(r'[A-Za-z0-9+/=]+', candidate)) if candidate else False
    matches_known_prefix = candidate.startswith(KNOWN_PREFIXES)

    line_lower = (line_content or "").lower()
    keyword_hits = sum(kw in line_lower for kw in SUSPICIOUS_KEYWORDS)

    is_test_path = is_test_path_fn(file_path)

    is_comment = (line_content or "").strip().startswith(('//', '#', '/*', '*'))

    # Ngữ cảnh khoá và hình dạng giá trị (v2)
    line = line_content or ""
    key = _key_before(line, start)
    key_tokens = _name_tokens(key) if key else set()
    c = candidate
    char_classes = (any(ch.islower() for ch in c) + any(ch.isupper() for ch in c)
                    + any(ch.isdigit() for ch in c) + any(not ch.isalnum() for ch in c))
    looks_code = any(ch in c for ch in "()[]{};") or "->" in c or "::" in c
    is_template = (c.startswith(("$", "%", "{{", "<", "#{", "@{"))
                   or re.search(r"process\.env|os\.environ|getenv|ENV\[", c) is not None)
    is_path_or_url = "://" in c or c.startswith(("/", "./", "../", "~/")) or "\\" in c

    return {
        # Nhóm 1 — thống kê chuỗi
        'length': length,
        'entropy': calculate_shannon_entropy(candidate),  # tái dùng entropy_scanner, không viết lại
        'char_diversity': len(set(candidate)) / length if length else 0,
        'digit_ratio': digit_count / length if length else 0,
        'upper_ratio': upper_count / length if length else 0,
        'lower_ratio': lower_count / length if length else 0,
        'special_ratio': special_count / length if length else 0,

        # Nhóm 2 — cấu trúc/pattern
        'is_base64_charset': int(is_base64_charset),
        'matches_known_prefix': int(matches_known_prefix),
        'hex_ratio': hex_charset_count / length if length else 0,

        # Nhóm 3 — ngữ cảnh (giảm false positive)
        'keyword_hits': keyword_hits,
        'is_test_path': int(is_test_path),
        'is_comment': int(is_comment),

        # Nhóm 5 — ngữ cảnh khoá và hình dạng giá trị (v2)
        'key_present': int(bool(key)),
        'key_secret_word': int(bool(key_tokens & KEY_SECRET_TOKENS)),
        'key_ui_word': int(bool(key_tokens & KEY_UI_TOKENS)),
        'is_quoted': int(start is not None and start > 0 and line[start - 1] in "'\"`"),
        'val_has_space': int(" " in c),
        'val_is_identifier': int(re.fullmatch(r"[A-Za-z_][A-Za-z_.]*", c) is not None),
        'val_looks_code': int(looks_code),
        'val_is_template': int(is_template),
        'val_is_path_or_url': int(is_path_or_url),
        'val_is_numeric': int(c.isdigit()),
        'val_char_classes': int(char_classes),
        'val_max_run_ratio': _longest_run_ratio(c),
        'line_length': len(line.strip()),  # strip: lúc train dòng đã strip, lúc chạy thật thì chưa

        # Nhóm 4 — từ regex/entropy scanner có sẵn
        'regex_type': regex_type or 'none',
        'source': source,
    }


# Danh sách loại regex CỐ ĐỊNH (lấy từ regex_scanner) -> số cột one-hot không phụ thuộc
# dữ liệu train/val/test chứa loại nào. Tên cột giữ dạng "regex_type_<tên>" như get_dummies cũ.
REGEX_TYPES = list(PATTERNS.keys()) + ["none"]

# Cột meta trong file feature: dùng để phân tích/chia nhóm, KHÔNG được đưa vào model.
META_COLUMNS = ("label", "_original_type", "_repo", "_line_id", "_source")


def encode_features(raw: dict) -> dict:
    """dict từ extract_features() -> dict phẳng đã one-hot regex_type, sẵn sàng cho model.
    Dùng giống hệt ở build_features.py (lúc train) và main.py (lúc chạy thật)."""
    row = {k: v for k, v in raw.items() if k not in ("regex_type", "source")}
    rtype = raw.get("regex_type") or "none"
    for t in REGEX_TYPES:
        row[f"regex_type_{t}"] = int(rtype == t)
    for src in CANDIDATE_SOURCES:
        row[f"source_{src}"] = int(raw.get("source") == src)
    return row


if __name__ == "__main__":
    # Test nhanh vài case tay để kiểm tra feature có hợp lý không
    samples = [
        {
            "candidate": "AKIAIOSFODNN7EXAMPLE",
            "line_content": "aws_access_key_id = AKIAIOSFODNN7EXAMPLE",
            "file_path": "backend/.env",
            "regex_type": "AWS Access Key",
        },
        {
            "candidate": "12345678-abcd-uuid-example-000000000000",
            "line_content": "# fake uuid for test",
            "file_path": "tests/mock_data.py",
            "regex_type": None,
        },
    ]
    for s in samples:
        f = extract_features(**s)
        print(s["candidate"], "->", f)