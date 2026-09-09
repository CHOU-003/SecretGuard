import os
import random
import string
import pandas as pd
from sklearn.model_selection import train_test_split


def random_word(min_len=4, max_len=10):
    return ''.join(random.choices(string.ascii_lowercase, k=random.randint(min_len, max_len)))


# Hàm sinh chuỗi ngẫu nhiên giả lập Secret (Label 1)
def generate_positive_secrets():
    secrets = []
    # 1. AWS Access Keys
    for _ in range(300):
        key = "AKIA" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        secrets.append({"text": key, "label": 1, "type": "AWS_Key"})

    # 2. Generic API Keys/Tokens
    for _ in range(400):
        token = "secret_key_" + ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        secrets.append({"text": f"const API_SECRET = '{token}'", "label": 1, "type": "Generic_Secret"})

    # 3. Slack Tokens
    for _ in range(300):
        slack = f"xoxb-{random.randint(1000000000, 9999999999)}-" + ''.join(random.choices(string.ascii_letters + string.digits, k=24))
        secrets.append({"text": slack, "label": 1, "type": "Slack_Token"})

    return secrets


# Hàm sinh các chuỗi KHÔNG phải Secret (Label 0)
# ĐÃ SỬA: mỗi mẫu đều random hoá tên biến/giá trị/path để tránh trùng lặp y hệt
# giữa nhiều mẫu -> tránh cùng 1 dòng text lọt vào cả train/val/test (data leakage)
def generate_negative_samples():
    non_secrets = []

    # 1. UUIDs / Hashes (Dễ bị Entropy bắt nhầm) - hash random nên đã tự unique sẵn
    for _ in range(400):
        fake_hash = ''.join(random.choices("0123456789abcdef", k=40))
        non_secrets.append({"text": f"commit_hash = '{fake_hash}'", "label": 0, "type": "Git_Hash"})

    # 2. Code thông thường & Variable names - RANDOM HOÁ theo template
    code_line_templates = [
        lambda: f"const {random_word()} = calculateTotal({random_word()}, {random_word()});",
        lambda: f"let {random_word()} = {random_word()}.filter(x => x.{random_word()} > {random.randint(1, 999)});",
        lambda: f"function {random_word()}({random_word()}, {random_word()}) {{ return {random_word()} + {random_word()}; }}",
        lambda: f"for (let {random_word()} = 0; {random_word()} < {random_word()}.length; {random_word()}++) {{ }}",
        lambda: f"if ({random_word()}.length === {random.randint(0, 5)}) {{ return null; }}",
        lambda: f"const {random_word()} = await {random_word()}.find{random_word().capitalize()}({{ id: {random.randint(1, 9999)} }});",
    ]
    for _ in range(300):
        line = random.choice(code_line_templates)()
        non_secrets.append({"text": line, "label": 0, "type": "Code_Line"})

    # 3. URLs & Paths - RANDOM HOÁ domain/path/id/query
    url_domains = ["api.example.com", "service.internal", "cdn.example.org", "auth.example.net", "shop.example.io"]
    url_paths = ["users", "orders", "products", "sessions", "profile", "invoices", "reviews", "payments"]
    url_langs = ["en", "vi", "fr", "ja"]
    for _ in range(300):
        url = (
            f"https://{random.choice(url_domains)}/v{random.randint(1, 3)}/"
            f"{random.choice(url_paths)}/{random.randint(1, 99999)}"
            f"?format=json&lang={random.choice(url_langs)}"
        )
        non_secrets.append({"text": url, "label": 0, "type": "URL"})

    # 4. Bổ sung code thông thường khác - RANDOM HOÁ thay vì chọn cố định trong 5 mẫu
    normal_code_templates = [
        lambda: f"import {random_word()}, {random_word()}, {random_word()}",
        lambda: f"return {random_word()} or {random_word()} or {random_word()}",
        lambda: f"if {random_word()} or {random_word()} in {random_word()}:",
        lambda: f"![{random_word().capitalize()}](https://img.shields.io/badge/{random_word()}-{random.randint(1, 20)}.{random.randint(0, 9)}.{random.randint(0, 9)}-blue)",
        lambda: f"INSERT INTO {random_word()} ({random_word()}, {random_word()}, {random_word()}) VALUES ($1, $2, $3)",
        lambda: f"# TODO: refactor {random_word()} before release",
        lambda: f"class {random_word().capitalize()}Controller: pass",
    ]
    for _ in range(400):
        line = random.choice(normal_code_templates)()
        non_secrets.append({"text": line, "label": 0, "type": "Normal_Code"})

    return non_secrets


def create_and_split_dataset():
    # 1. Thu thập dữ liệu
    data = generate_positive_secrets() + generate_negative_samples()
    df = pd.DataFrame(data)

    # Loại bỏ trùng lặp y hệt còn sót (phòng hờ, dù template đã random hoá)
    before = len(df)
    df = df.drop_duplicates(subset=["text"]).reset_index(drop=True)
    removed = before - len(df)
    if removed:
        print(f"⚠️  Đã loại bỏ {removed} dòng trùng lặp y hệt trước khi chia tập.")

    # Trộn ngẫu nhiên dữ liệu
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    # 2. Chia tập dữ liệu (Stratified Split để giữ cân bằng tỉ lệ label)
    # Tỉ lệ: 70% Train, 15% Validation, 15% Test
    train_df, temp_df = train_test_split(df, test_size=0.30, random_state=42, stratify=df['label'])
    val_df, test_df = train_test_split(temp_df, test_size=0.50, random_state=42, stratify=temp_df['label'])

    # 3. Lưu vào thư mục data/
    os.makedirs("data", exist_ok=True)
    train_df.to_csv("data/train.csv", index=False)
    val_df.to_csv("data/val.csv", index=False)
    test_df.to_csv("data/test.csv", index=False)

    print("=== TẠO DATASET THÀNH CÔNG ===")
    print(f"- Tập Train      (70%): {len(train_df)} mẫu")
    print(f"- Tập Validation (15%): {len(val_df)} mẫu")
    print(f"- Tập Test       (15%): {len(test_df)} mẫu")

    # Kiểm tra thật sự không overlap text giữa 3 tập
    train_set, val_set, test_set = set(train_df['text']), set(val_df['text']), set(test_df['text'])
    overlap_tv = train_set & val_set
    overlap_tt = train_set & test_set
    overlap_vt = val_set & test_set
    if overlap_tv or overlap_tt or overlap_vt:
        print(f"⚠️  VẪN CÒN OVERLAP: train∩val={len(overlap_tv)}, train∩test={len(overlap_tt)}, val∩test={len(overlap_vt)}")
    else:
        print("✅ Xác nhận: KHÔNG có dòng text trùng nhau giữa train/val/test.")


if __name__ == "__main__":
    create_and_split_dataset()