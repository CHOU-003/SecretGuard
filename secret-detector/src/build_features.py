"""
build_features.py (v3) — feature ở mức CANDIDATE, dùng chung đường xử lý với main.py

Chạy SAU build_dataset.py và/hoặc import_external.py:
    python -m src.build_features                 # mọi nguồn đang có
    python -m src.build_features --sources creddata

Đầu vào (mỗi dòng = 1 dòng mã nguồn đã gán nhãn):
    synthetic : data/train.csv, val.csv, test.csv          (build_dataset.py)
    creddata  : data/external/creddata.csv (cột split)     (import_external.py)

Đầu ra: data/features/<nguồn>_<tập>.csv — MỖI HÀNG LÀ 1 CANDIDATE.

Cách gán nhãn cho candidate:
    * Dòng nhãn 0 (F, X)  -> mọi candidate của dòng đều là 0.
    * Dòng nhãn 1 mà nguồn có cột `value` (CredData):
        - biết vị trí giá trị thật -> candidate nào phủ >=50% giá trị là 1, các
          candidate khác trong dòng là 0;
        - KHÔNG biết giá trị (không có offset, hoặc nhiều dòng) -> bỏ dòng khỏi dữ
          liệu train, vì gán bừa sẽ tạo nhãn nhiễu. Dòng này vẫn được đếm ở bước
          đánh giá cấp dòng (evaluate.py) là secret thật.
    * Dòng nhãn 1 mà nguồn KHÔNG có cột `value` (dữ liệu tổng hợp) -> mọi candidate
      của dòng là 1 (mỗi mẫu tổng hợp chỉ chứa đúng 1 secret).

Dòng nhãn 1 mà bộ trích không sinh được candidate nào phủ giá trị = "bỏ sót ở bước
trích" — đếm riêng, vì ML không thể cứu được những dòng này.
"""

import os
import argparse
from collections import Counter

import pandas as pd

from src.candidate import extract_candidates, covers_value
from src.feature_extractor import META_COLUMNS, encode_features, extract_features

SPLITS = ("train", "val", "test")
SOURCES = ("synthetic", "creddata")


# ----------------------------------------------------------------- nạp nguồn
def load_source(name, data_dir):
    """Trả về DataFrame có cột split, hoặc None nếu nguồn chưa có."""
    if name == "synthetic":
        frames = []
        for split in SPLITS:
            path = os.path.join(data_dir, f"{split}.csv")
            if not os.path.exists(path):
                return None
            part = pd.read_csv(path, keep_default_na=False)
            part["split"] = split
            frames.append(part)
        return pd.concat(frames, ignore_index=True)

    path = os.path.join(data_dir, "external", "creddata.csv")
    if not os.path.exists(path):
        return None
    return pd.read_csv(path, keep_default_na=False)


# ------------------------------------------------------------- dựng hàng
def build_split_rows(df, stats):
    has_value = "value" in df.columns
    rows = []

    for line_id, rec in enumerate(df.to_dict("records")):
        text = str(rec["text"])
        label = int(rec["label"])
        path = str(rec.get("file_path", "") or "")
        stats["lines"] += 1
        stats["lines_pos"] += label

        cands = extract_candidates(text)
        if not cands:
            stats["lines_without_candidate"] += 1
            stats["pos_lines_no_candidate"] += label
            continue

        if label == 1 and has_value:
            value = str(rec.get("value", "") or "")
            at = text.find(value) if value else -1
            if at < 0:
                stats["pos_lines_value_unknown_skipped"] += 1
                continue
            flags = [covers_value(c, at, at + len(value)) for c in cands]
            if not any(flags):
                stats["pos_lines_extractor_miss"] += 1
            cand_labels = [int(f) for f in flags]
        else:
            cand_labels = [label] * len(cands)

        for c, cl in zip(cands, cand_labels):
            row = encode_features(extract_features(c.value, text, path, c.regex_type, source=c.source, start=c.start))
            row.update({
                "label": cl,
                "_original_type": rec.get("type", ""),
                "_repo": rec.get("repo", ""),
                "_line_id": line_id,
                "_source": c.source,
            })
            rows.append(row)

    return pd.DataFrame(rows)


def feature_columns_of(df):
    return [c for c in df.columns if c not in META_COLUMNS]


# --------------------------------------------------------------- báo cáo
def print_source_report(name, results, stats_by_split):
    print(f"\n=== Nguồn: {name} ===")
    header = (f"{'tập':<6}{'dòng':>8}{'dòng T':>8}{'không có cand':>15}{'T không có cand':>17}"
              f"{'T bỏ sót':>10}{'T bỏ qua':>10}{'candidate':>11}{'cand=1':>9}")
    print(header)
    for split in SPLITS:
        if split not in results:
            continue
        s, df = stats_by_split[split], results[split]
        print(f"{split:<6}{s['lines']:>8}{s['lines_pos']:>8}{s['lines_without_candidate']:>15}"
              f"{s['pos_lines_no_candidate']:>17}{s['pos_lines_extractor_miss']:>10}"
              f"{s['pos_lines_value_unknown_skipped']:>10}{len(df):>11}{int(df['label'].sum()):>9}")
    print("  (T bỏ sót = dòng T có candidate nhưng không cái nào phủ giá trị thật; "
          "T bỏ qua = không biết giá trị nên không dùng để train)")

    train = results.get("train")
    if train is not None and len(train):
        print("\n  Tỉ lệ candidate là secret theo is_test_path (tập train):")
        tbl = train.groupby("is_test_path")["label"].agg(["mean", "count"])
        for flag, r in tbl.iterrows():
            print(f"    is_test_path={int(flag)}: {r['mean']:.1%} là secret  ({int(r['count'])} candidate)")
        print("  Candidate theo nguồn trích: " +
              ", ".join(f"{k}={v}" for k, v in Counter(train['_source']).most_common()))


def main():
    parser = argparse.ArgumentParser(description="Trích feature ở mức candidate")
    parser.add_argument("--sources", nargs="+", choices=SOURCES, default=list(SOURCES))
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    out_dir = os.path.join(data_dir, "features")
    os.makedirs(out_dir, exist_ok=True)

    built_any = False
    for name in args.sources:
        df = load_source(name, data_dir)
        if df is None:
            print(f"⚠️  Bỏ qua nguồn '{name}': chưa có dữ liệu "
                  f"({'build_dataset.py' if name == 'synthetic' else 'import_external.py'}).")
            continue

        results, stats_by_split = {}, {}
        for split in SPLITS:
            part = df[df["split"] == split]
            if part.empty:
                continue
            print(f"[{name}] đang trích feature tập {split} ({len(part)} dòng)...")
            stats = Counter()
            feats = build_split_rows(part, stats)
            results[split], stats_by_split[split] = feats, stats
            feats.to_csv(os.path.join(out_dir, f"{name}_{split}.csv"), index=False)

        print_source_report(name, results, stats_by_split)
        cols = feature_columns_of(next(iter(results.values())))
        print(f"\n  Số feature: {len(cols)}")
        built_any = True

    if not built_any:
        raise SystemExit("Không có nguồn nào để xử lý. Chạy build_dataset.py hoặc import_external.py trước.")
    print(f"\n✅ Đã lưu vào: {out_dir}")
    print("⚠️  train_ml.py bản cũ đọc data/train_features.csv nên KHÔNG đọc được file mới này; "
          "dùng bản train_ml.py kế tiếp.")


if __name__ == "__main__":
    main()