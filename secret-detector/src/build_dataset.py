import os
import random
import string
import pandas as pd
from sklearn.model_selection import train_test_split

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
def generate_negative_samples():
    non_secrets = []
    # 1. UUIDs / Hashes (Dễ bị Entropy bắt nhầm)
    for _ in range(400):
        fake_hash = ''.join(random.choices("0123456789abcdef", k=40))
        non_secrets.append({"text": f"commit_hash = '{fake_hash}'", "label": 0, "type": "Git_Hash"})

    # 2. Code thông thường & Variable names
    for _ in range(300):
        var_line = "const totalSum = calculateTotal(items, taxRate);"
        non_secrets.append({"text": var_line, "label": 0, "type": "Code_Line"})

    # 3. URLs & Paths
    for _ in range(300):
        url = "https://api.example.com/v1/users/profile?format=json&lang=en"
        non_secrets.append({"text": url, "label": 0, "type": "URL"})

    # Bổ sung thêm mẫu code thông thường vào Negative Samples
    for _ in range(400):
        code_samples = [
            "import string, joblib, random, argparse",
            "return secrets or results or entropy",
            "if continue or pass in lines:",
            "![Tech Stack](https://img.shields.io/badge/React-17.0.2-blue)",
            "INSERT INTO comments (post_id, author, content) VALUES ($1, $2, $3)"
        ]
        non_secrets.append({"text": random.choice(code_samples), "label": 0, "type": "Normal_Code"})

    return non_secrets

def create_and_split_dataset():
    # 1. Thu thập dữ liệu
    data = generate_positive_secrets() + generate_negative_samples()
    df = pd.DataFrame(data)

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
    print("Đảm bảo không overlap dữ liệu giữa các tập!")

if __name__ == "__main__":
    create_and_split_dataset()