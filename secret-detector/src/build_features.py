"""
build_dataset.py
Áp feature_extractor.py lên train.csv / val.csv / test.csv hiện có,
xuất ra train_features.csv / val_features.csv / test_features.csv.

Input hiện tại: mỗi dòng dataset là 1 "candidate" đã được chuẩn bị sẵn
(cột text, label, type) — text có thể là 1 token trần (vd token Slack)
hoặc 1 dòng code đầy đủ (vd dòng gán biến, dòng code bình thường).

QUAN TRỌNG: regex_type dùng làm feature được TỰ TÍNH LẠI bằng
regex_scanner.scan_with_regex(), KHÔNG đọc trực tiếp từ cột `type` có sẵn
trong CSV — vì cột `type` đó chính là nhãn phân loại con người gán tay,
nếu đưa thẳng vào feature sẽ gây data leakage (model học "ăn gian" theo
đáp án có sẵn, lúc chạy thật trên code mới sẽ không có cột này để tra).
"""

import os
import pandas as pd

from src.feature_extractor import extract_features
from src.regex_scanner import scan_with_regex


def infer_regex_type(text: str):
    """Chạy regex_scanner thật lên text, lấy loại pattern đầu tiên khớp được
    (giống hệt cách main.py sẽ làm lúc inference thật)."""
    matches = scan_with_regex(text)
    if matches:
        return matches[0]["type"]
    return None


def build_feature_dataset(raw_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in raw_df.iterrows():
        text = str(row["text"])
        label = row["label"]

        regex_type = infer_regex_type(text)

        # Dataset hiện tại không có cột file_path riêng -> mặc định rỗng
        # (is_test_path sẽ luôn = 0 cho tới khi dataset có cột file_path thật)
        features = extract_features(
            candidate=text,
            line_content=text,
            file_path="",
            regex_type=regex_type,
        )
        features["label"] = label
        features["_original_type"] = row.get("type", None)  # giữ lại để debug, KHÔNG dùng làm feature
        rows.append(features)

    return pd.DataFrame(rows)


def align_columns(train_df, other_df):
    """Đảm bảo val/test có đúng cột (sau one-hot) như train, thiếu thì fill 0."""
    feature_cols = [c for c in train_df.columns if c not in ("label", "_original_type")]
    other_aligned = other_df.reindex(columns=feature_cols + ["label", "_original_type"], fill_value=0)
    return other_aligned


def main():
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

    train_raw = pd.read_csv(os.path.join(data_dir, "train.csv"))
    val_raw = pd.read_csv(os.path.join(data_dir, "val.csv"))
    test_raw = pd.read_csv(os.path.join(data_dir, "test.csv"))

    print("Đang trích feature cho train.csv...")
    train_df = build_feature_dataset(train_raw)
    print("Đang trích feature cho val.csv...")
    val_df = build_feature_dataset(val_raw)
    print("Đang trích feature cho test.csv...")
    test_df = build_feature_dataset(test_raw)

    # One-hot encode regex_type
    train_df = pd.get_dummies(train_df, columns=["regex_type"])
    val_df = pd.get_dummies(val_df, columns=["regex_type"])
    test_df = pd.get_dummies(test_df, columns=["regex_type"])

    # Val/test phải có đúng cột như train (phòng thiếu 1 loại regex_type nào đó)
    val_df = align_columns(train_df, val_df)
    test_df = align_columns(train_df, test_df)

    train_df.to_csv(os.path.join(data_dir, "train_features.csv"), index=False)
    val_df.to_csv(os.path.join(data_dir, "val_features.csv"), index=False)
    test_df.to_csv(os.path.join(data_dir, "test_features.csv"), index=False)

    print(f"\n✅ Đã lưu: train_features.csv ({len(train_df)} dòng, {len(train_df.columns)} cột)")
    print(f"✅ Đã lưu: val_features.csv ({len(val_df)} dòng)")
    print(f"✅ Đã lưu: test_features.csv ({len(test_df)} dòng)")
    print("\nCác cột feature:", [c for c in train_df.columns if c not in ('label', '_original_type')])


if __name__ == "__main__":
    main()