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

# Các prefix đặc trưng hay gặp ở secret thật (tăng tín hiệu, không phải luật cứng)
KNOWN_PREFIXES = ('AKIA', 'ghp_', 'gho_', 'ghu_', 'ghs_', 'sk-', 'xox', 'AIza')

# Từ khóa nghi vấn xuất hiện trên dòng chứa candidate
SUSPICIOUS_KEYWORDS = ['key', 'secret', 'token', 'password', 'passwd', 'api', 'auth']

# Thư mục hay chứa false positive (test/mock/sample key giả)
TEST_PATH_SEGMENTS = ('test', 'mock', 'example', 'sample', 'fixture', 'spec')


def extract_features(candidate: str, line_content: str, file_path: str, regex_type: str = None) -> dict:
    """
    Trích 1 dict feature cho 1 candidate string.

    candidate    : chuỗi secret nghi vấn (matched_text từ regex_scanner), KHÔNG phải cả dòng
    line_content : nội dung cả dòng chứa candidate (để lấy ngữ cảnh: từ khóa, comment...)
    file_path    : đường dẫn file (để biết có phải test/mock file không)
    regex_type   : tên loại pattern đã khớp (vd "AWS Access Key"), None nếu candidate
                   không xuất phát từ regex_scanner (vd tầng ML-only)
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

    file_path_lower = (file_path or "").lower()
    is_test_path = any(seg in file_path_lower for seg in TEST_PATH_SEGMENTS)

    is_comment = (line_content or "").strip().startswith(('//', '#', '/*', '*'))

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

        # Nhóm 4 — từ regex/entropy scanner có sẵn
        'regex_type': regex_type or 'none',
    }


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