import re

# Danh sách các luật Regex nhận diện Secret phổ biến
PATTERNS = {
    "AWS Access Key": r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}",
    "Generic API Key": r"(?i)(?:api_key|apikey|secret|token|password)\s*[:=]\s*['\"]([A-Za-z0-9_\-]{16,})['\"]",
    "Slack Token": r"xox[baprs]-[0-9]{10,13}-[a-zA-Z0-9]{24,32}",
    "GitHub Personal Token": r"gh[pousr]_[A-Za-z0-9_]{36,255}",
    "Private Key": r"-----BEGIN (?:RSA|OPENSSH|DSA|EC)? PRIVATE KEY-----"
}

def scan_with_regex(text):
    """
    Phương pháp 1: Chỉ sử dụng Biểu thức chính quy (Regex)
    Trả về danh sách các secret phát hiện được.
    """
    results = []
    for secret_type, pattern in PATTERNS.items():
        matches = re.finditer(pattern, text)
        for match in matches:
            results.append({
                "type": secret_type,
                "matched_text": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "method": "Regex"
            })
    return results