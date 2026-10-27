"""
build_dataset.py (v2)

Sinh dataset tổng hợp (synthetic) theo schema mới:
    text, label, type, repo, file_path

Khác bản v1:
  1. Có cột `repo` và `file_path` -> chia train/val/test THEO REPOSITORY
     (GroupShuffleSplit), không chia theo dòng, đúng cam kết trong đề cương.
  2. Tập false positive "khó": key mẫu trong tài liệu (AKIA...EXAMPLE),
     placeholder (your_api_key_here), hash/checksum, UUID, Base64 của chuỗi
     thường, giá trị giả trong file test/mock.
  3. Positive "regex-blind": secret thật KHÔNG theo prefix biết trước
     (INTERNAL_TOKEN, DB_PASSWORD, hex/base64 ngẫu nhiên...) để tầng ML có
     chỗ chứng minh giá trị so với Regex thuần.
  4. Cố định seed -> dataset tái lập được (reproducible).

Lưu ý trung thực cho báo cáo: đây vẫn là dữ liệu TỔNG HỢP. Dữ liệu thật
(SecretBench...) sẽ được nạp thêm ở bước import_external.py.
"""

import os
import random
import string
import hashlib
import uuid
import base64

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

SEED = 42
random.seed(SEED)

NUM_REPOS = 80
# Tỉ lệ secret THẬT nằm trong thư mục test (đời thực vẫn có leak trong test/)
# -> tránh việc đường dẫn test/ trở thành "đáp án" tuyệt đối cho nhãn 0
TEST_PATH_LEAK_RATE = 0.08

SOURCE_PATHS = [
    "src/config.js", "src/app.py", "backend/.env", "config/settings.py",
    "deploy/docker-compose.yml", "src/services/auth.js", "backend/server.js",
    "src/utils/helpers.py", "config/production.json", "scripts/deploy.py",
]
TEST_PATHS = [
    "tests/test_auth.py", "test/mock_data.json", "src/__mocks__/api.js",
    "examples/sample.env", "fixtures/config.yml", "tests/conftest.py",
]
DOC_PATHS = ["README.md", "docs/setup.md", "docs/api.md", "docs/notes.txt"]
PLACEHOLDER_PATHS = ["README.md", "docs/setup.md", "config/sample.env", "examples/config.yml"]


# ---------------------------------------------------------------- helpers
def random_word(min_len=4, max_len=10):
    return ''.join(random.choices(string.ascii_lowercase, k=random.randint(min_len, max_len)))


def rand_alnum(k):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=k))


def rand_hex(k):
    return ''.join(random.choices("0123456789abcdef", k=k))


# Key ID của AWS thật chỉ dùng bảng chữ cái base32: A-Z và 2-7 (không có 0, 1, 8, 9).
# Gitleaks cũng dùng đúng bảng này trong regex aws-access-token.
AWS_ALPHABET = string.ascii_uppercase + "234567"


def rand_aws_chars(k):
    return ''.join(random.choices(AWS_ALPHABET, k=k))


def rand_b64(k):
    return ''.join(random.choices(string.ascii_letters + string.digits + "+/", k=k))


REPOS = [f"org{i % 12}/{random_word(4, 8)}-{i:02d}" for i in range(NUM_REPOS)]


def make_sample(text, label, type_, paths):
    return {
        "text": text,
        "label": label,
        "type": type_,
        "repo": random.choice(REPOS),
        "file_path": random.choice(paths),
    }


def positive_paths():
    """Đa số secret thật nằm ở source, một phần nhỏ lọt vào thư mục test."""
    return TEST_PATHS if random.random() < TEST_PATH_LEAK_RATE else SOURCE_PATHS


# ------------------------------------------------------- positives (label 1)
def generate_positive_secrets():
    secrets = []

    # 1. AWS Access Keys (có prefix -> Regex bắt được)
    for _ in range(300):
        key = "AKIA" + rand_aws_chars(16)
        secrets.append(make_sample(key, 1, "AWS_Key", positive_paths()))

    # 2. Generic API secrets
    for _ in range(400):
        token = "secret_key_" + rand_alnum(32)
        secrets.append(make_sample(f"const API_SECRET = '{token}'", 1, "Generic_Secret", positive_paths()))

    # 3. Slack tokens
    for _ in range(300):
        slack = (f"xoxb-{random.randint(10**9, 10**12)}-"
                 f"{random.randint(10**9, 10**12)}-" + rand_alnum(24))
        secrets.append(make_sample(slack, 1, "Slack_Token", positive_paths()))

    # 4. GitHub personal tokens
    for _ in range(200):
        gh = "ghp_" + rand_alnum(36)
        secrets.append(make_sample(gh, 1, "GitHub_Token", positive_paths()))

    # 5. REGEX-BLIND: secret thật nhưng KHÔNG khớp prefix/pattern nào biết trước
    names = ["INTERNAL_TOKEN", "SERVICE_KEY", "AUTH_SECRET", "DB_PASSWORD",
             "ENCRYPTION_KEY", "SIGNING_SECRET", "WEBHOOK_SECRET", "SESSION_SECRET"]
    for _ in range(400):
        name = random.choice(names)
        kind = random.choice(["alnum", "hex", "b64", "password"])
        if kind == "alnum":
            value = rand_alnum(random.randint(28, 40))
        elif kind == "hex":
            value = rand_hex(random.choice([32, 40, 64]))
        elif kind == "b64":
            value = rand_b64(random.randint(32, 44))
        else:
            value = ''.join(random.choices(string.ascii_letters + string.digits + "@#$%^&*!",
                                           k=random.randint(12, 20)))
        text = random.choice([
            f'{name} = "{value}"',
            f"{name}: {value}",
            f"export {name}='{value}'",
        ])
        secrets.append(make_sample(text, 1, "Custom_Secret", positive_paths()))

    return secrets


# ------------------------------------------------------- negatives (label 0)
def generate_negative_samples():
    non_secrets = []

    # 1. Git hash / SHA1 (dễ bị Entropy bắt nhầm)
    for _ in range(250):
        h = rand_hex(40)
        text = random.choice([f"commit_hash = '{h}'", f"sha1: {h}"])
        non_secrets.append(make_sample(text, 0, "Git_Hash", SOURCE_PATHS + DOC_PATHS))

    # 2. Checksum SHA256 (lockfile/integrity)
    for _ in range(150):
        digest = hashlib.sha256(random_word(8, 16).encode()).hexdigest()
        text = random.choice([f'"checksum": "{digest}"', f"integrity: sha256-{digest}"])
        non_secrets.append(make_sample(text, 0, "Checksum", SOURCE_PATHS))

    # 3. UUID
    for _ in range(200):
        u = uuid.UUID(int=random.getrandbits(128), version=4)
        text = f"{random_word(3, 8)}_id = '{u}'"
        non_secrets.append(make_sample(text, 0, "UUID", SOURCE_PATHS))

    # 4. Base64 của chuỗi văn bản thường
    for _ in range(200):
        plain = " ".join(random_word() for _ in range(4))
        b64 = base64.b64encode(plain.encode()).decode()
        text = f'{random_word(3, 8)}_data = "{b64}"'
        non_secrets.append(make_sample(text, 0, "Base64_Text", SOURCE_PATHS))

    # 5. Placeholder kiểu your_api_key_here
    placeholder_values = ["your_api_key_here", "YOUR_API_KEY", "<your-token>", "changeme",
                          "xxxxxxxxxxxxxxxx", "REPLACE_WITH_YOUR_SECRET",
                          "insert-your-key-here", "your_secret_here"]
    var_names = ["API_KEY", "SECRET_KEY", "AUTH_TOKEN", "DB_PASSWORD"]
    for _ in range(300):
        var = f"{random_word(3, 6).upper()}_{random.choice(var_names)}"
        text = f'{var} = "{random.choice(placeholder_values)}"'
        non_secrets.append(make_sample(text, 0, "Placeholder", PLACEHOLDER_PATHS))

    # 6. Key mẫu trong tài liệu chính thức (AWS docs...) và biến thể
    non_secrets.append(make_sample("AKIAIOSFODNN7EXAMPLE", 0, "Doc_Example", DOC_PATHS))
    non_secrets.append(make_sample("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", 0, "Doc_Example", DOC_PATHS))
    for _ in range(150):
        if random.random() < 0.5:
            text = "AKIA" + rand_aws_chars(9) + "EXAMPLE"
        else:
            text = f"aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/{rand_alnum(6)}EXAMPLEKEY"
        non_secrets.append(make_sample(text, 0, "Doc_Example", DOC_PATHS))

    # 7. Giá trị giả trong file test/mock (có marker fake_/mock_/dummy_/test_)
    mock_names = ["API_KEY", "AUTH_TOKEN", "SECRET", "SERVICE_TOKEN"]
    markers = ["fake_", "mock_", "dummy_", "test_", "example_"]
    for _ in range(300):
        text = f'{random.choice(mock_names)} = "{random.choice(markers)}{rand_alnum(24)}"'
        non_secrets.append(make_sample(text, 0, "Test_Mock", TEST_PATHS))

    # 8. Code thông thường (random hoá để không trùng lặp)
    code_line_templates = [
        lambda: f"const {random_word()} = calculateTotal({random_word()}, {random_word()});",
        lambda: f"let {random_word()} = {random_word()}.filter(x => x.{random_word()} > {random.randint(1, 999)});",
        lambda: f"function {random_word()}({random_word()}, {random_word()}) {{ return {random_word()} + {random_word()}; }}",
        lambda: f"for (let {random_word()} = 0; {random_word()} < {random_word()}.length; {random_word()}++) {{ }}",
        lambda: f"if ({random_word()}.length === {random.randint(0, 5)}) {{ return null; }}",
        lambda: f"const {random_word()} = await {random_word()}.find{random_word().capitalize()}({{ id: {random.randint(1, 9999)} }});",
    ]
    for _ in range(300):
        non_secrets.append(make_sample(random.choice(code_line_templates)(), 0, "Code_Line", SOURCE_PATHS))

    # 9. URL
    url_domains = ["api.example.com", "service.internal", "cdn.example.org", "auth.example.net", "shop.example.io"]
    url_paths = ["users", "orders", "products", "sessions", "profile", "invoices", "reviews", "payments"]
    for _ in range(300):
        url = (f"https://{random.choice(url_domains)}/v{random.randint(1, 3)}/"
               f"{random.choice(url_paths)}/{random.randint(1, 99999)}"
               f"?format=json&lang={random.choice(['en', 'vi', 'fr', 'ja'])}")
        non_secrets.append(make_sample(url, 0, "URL", SOURCE_PATHS + DOC_PATHS))

    # 10. Code/markdown/SQL khác
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
        non_secrets.append(make_sample(random.choice(normal_code_templates)(), 0, "Normal_Code", SOURCE_PATHS + DOC_PATHS))

    return non_secrets


# --------------------------------------------------------------- split
def split_by_repo(df):
    """Chia 70/15/15 THEO REPOSITORY: một repo chỉ nằm trong đúng 1 tập."""
    gss1 = GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=SEED)
    train_idx, temp_idx = next(gss1.split(df, groups=df["repo"]))
    train_df = df.iloc[train_idx]
    temp_df = df.iloc[temp_idx]

    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.50, random_state=SEED)
    val_idx, test_idx = next(gss2.split(temp_df, groups=temp_df["repo"]))
    val_df = temp_df.iloc[val_idx]
    test_df = temp_df.iloc[test_idx]
    return train_df, val_df, test_df


def verify_split(train_df, val_df, test_df):
    ok = True
    names = {"train": train_df, "val": val_df, "test": test_df}

    # 1. Không overlap repo
    repo_sets = {k: set(v["repo"]) for k, v in names.items()}
    for a, b in [("train", "val"), ("train", "test"), ("val", "test")]:
        inter = repo_sets[a] & repo_sets[b]
        if inter:
            ok = False
            print(f"⚠️  OVERLAP REPO {a}∩{b}: {len(inter)} repo")

    # 2. Không overlap text
    text_sets = {k: set(v["text"]) for k, v in names.items()}
    for a, b in [("train", "val"), ("train", "test"), ("val", "test")]:
        inter = text_sets[a] & text_sets[b]
        if inter:
            ok = False
            print(f"⚠️  OVERLAP TEXT {a}∩{b}: {len(inter)} dòng")

    # 3. Mỗi tập phải có đủ 2 lớp
    for k, v in names.items():
        if v["label"].nunique() < 2:
            ok = False
            print(f"⚠️  Tập {k} chỉ có 1 lớp label!")

    if ok:
        print("✅ Xác nhận: không overlap repo, không overlap text, mỗi tập đủ 2 lớp.")
    return ok


def create_and_split_dataset():
    data = generate_positive_secrets() + generate_negative_samples()
    df = pd.DataFrame(data)

    # Bỏ trùng text y hệt (để không lọt cùng 1 dòng vào nhiều tập)
    before = len(df)
    df = df.drop_duplicates(subset=["text"]).reset_index(drop=True)
    if before != len(df):
        print(f"ℹ️  Đã loại {before - len(df)} dòng trùng text trước khi chia tập.")

    train_df, val_df, test_df = split_by_repo(df)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    train_df.to_csv(os.path.join(data_dir, "train.csv"), index=False)
    val_df.to_csv(os.path.join(data_dir, "val.csv"), index=False)
    test_df.to_csv(os.path.join(data_dir, "test.csv"), index=False)

    print("\n=== TẠO DATASET THÀNH CÔNG (chia theo repository) ===")
    for name, part in [("Train", train_df), ("Val", val_df), ("Test", test_df)]:
        print(f"- {name:<5}: {len(part):>5} mẫu | {part['repo'].nunique():>2} repo | "
              f"tỉ lệ secret = {part['label'].mean():.1%}")

    print("\nPhân bố theo loại (type) toàn bộ dataset:")
    print(df.groupby(["label", "type"]).size().to_string())
    print()
    verify_split(train_df, val_df, test_df)


if __name__ == "__main__":
    create_and_split_dataset()