import math
from src.regex_scanner import scan_with_regex

def calculate_shannon_entropy(data):
    """
    Tính độ hỗn loạn thông tin Shannon (Shannon Entropy).
    Chuỗi ngẫu nhiên (như mật khẩu/token) thường có Entropy cao (> 3.5 - 4.5).
    """
    if not data:
        return 0
    entropy = 0
    for x in set(data):
        p_x = float(data.count(x)) / len(data)
        entropy -= p_x * math.log(p_x, 2)
    return entropy

def scan_with_regex_and_entropy(text, entropy_threshold=4.0):
    """
    Phương pháp 2: Kết hợp Regex + Shannon Entropy
    Giảm bớt các trường hợp Regex quét nhầm các chuỗi thông thường có độ ngẫu nhiên thấp.
    """
    regex_candidates = scan_with_regex(text)
    filtered_results = []
    
    for item in regex_candidates:
        matched_str = item["matched_text"]
        entropy_val = calculate_shannon_entropy(matched_str)
        item["entropy"] = round(entropy_val, 3)
        item["method"] = "Regex + Entropy"
        
        # Chỉ giữ lại nếu độ ngẫu nhiên đạt ngưỡng quy định
        if entropy_val >= entropy_threshold:
            filtered_results.append(item)
            
    return filtered_results