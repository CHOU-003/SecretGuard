"""
build_features.py (v2)

Đọc train.csv / val.csv / test.csv (schema: text, label, type, repo, file_path)
rồi xuất train_features.csv / val_features.csv / test_features.csv.

Thay đổi so với v1:
  - Dùng cột `file_path` THẬT của dataset cho feature is_test_path
    (v1 luôn truyền "" nên feature này luôn = 0).
  - Cột `repo` KHÔNG đưa vào file features (chỉ dùng để chia tập, đưa vào
    model sẽ thành leakage). Cột `type` chỉ giữ dưới tên `_original_type`
    để debug/phân tích lỗi, KHÔNG phải feature.
  - In thống kê kiểm tra: regex_type theo nhãn (để thấy phần "regex-blind")
    và tỉ lệ is_test_path theo nhãn (để chắc đường dẫn không phải đáp án).

QUAN TRỌNG: regex_type được TỰ TÍNH bằng regex_scanner (giống lúc inference
ở main.py), không đọc từ cột `type` — đọc từ `type` là data leakage.
"""

import os
import pandas as pd

from src.feature_extractor import extract_features
from src.regex_scanner import scan_with_regex

META_COLUMNS = ("label", "_original_type")


def infer_regex_type(text: str):
    """Loại pattern đầu tiên mà regex_scanner khớp được, hoặc None."""
    matches = scan_with_regex(text)
    return matches[0]["type"] if matches else None


def clean_path(value) -> str:
    """CSV có thể trả NaN cho file_path rỗng -> chuẩn hoá về chuỗi rỗng."""
    if pd.isna(value):
        return ""
    return str(value)


def build_feature_dataset(raw_df: pd.DataFrame) -> pd.DataFrame:
    has_path = "file_path" in raw_df.columns
    if not has_path:
        print("⚠️  Dataset không có cột file_path -> is_test_path sẽ luôn = 0.")

    rows = []
    for _, row in raw_df.iterrows():
        text = str(row["text"])
        features = extract_features(
            candidate=text,
            line_content=text,
            file_path=clean_path(row["file_path"]) if has_path else "",
            regex_type=infer_regex_type(text),
        )
        features["label"] = row["label"]
        features["_original_type"] = row.get("type", None)  # chỉ để debug
        rows.append(features)

    return pd.DataFrame(rows)


def align_columns(train_df: pd.DataFrame, other_df: pd.DataFrame) -> pd.DataFrame:
    """Ép val/test có đúng cột như train (thiếu thì fill 0)."""
    return other_df.reindex(columns=train_df.columns, fill_value=0)


def print_sanity_report(name: str, raw_features: pd.DataFrame):
    """Thống kê trước khi one-hot: giúp phát hiện shortcut/leakage sớm."""
    print(f"\n--- Kiểm tra nhanh tập {name} ---")
    print("Tỉ lệ is_test_path theo nhãn (nếu 0 vs 1 quá lệch -> đường dẫn là đáp án):")
    print(raw_features.groupby("label")["is_test_path"].mean().round(3).to_string())
    print("\nregex_type theo nhãn (cột 'none' ở nhãn 1 = secret mà Regex không thấy):")
    print(pd.crosstab(raw_features["regex_type"], raw_features["label"]).to_string())


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")

    raw = {}
    for split in ("train", "val", "test"):
        path = os.path.join(data_dir, f"{split}.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Chưa thấy {path}. Chạy build_dataset.py trước.")
        raw[split] = pd.read_csv(path)

    built = {}
    for split in ("train", "val", "test"):
        print(f"Đang trích feature cho {split}.csv ({len(raw[split])} dòng)...")
        built[split] = build_feature_dataset(raw[split])

    print_sanity_report("train", built["train"])

    # One-hot regex_type, rồi ép val/test theo đúng cột của train
    encoded = {s: pd.get_dummies(df, columns=["regex_type"]) for s, df in built.items()}
    encoded["val"] = align_columns(encoded["train"], encoded["val"])
    encoded["test"] = align_columns(encoded["train"], encoded["test"])

    for split, df in encoded.items():
        if df.isna().any().any():
            raise ValueError(f"Tập {split} có NaN trong feature, kiểm tra lại dữ liệu đầu vào.")
        df.to_csv(os.path.join(data_dir, f"{split}_features.csv"), index=False)

    feature_cols = [c for c in encoded["train"].columns if c not in META_COLUMNS]
    print(f"\n✅ Đã lưu: train_features.csv ({len(encoded['train'])} dòng), "
          f"val_features.csv ({len(encoded['val'])}), test_features.csv ({len(encoded['test'])})")
    print(f"Số feature: {len(feature_cols)}")
    print("Các cột feature:", feature_cols)


if __name__ == "__main__":
    main()