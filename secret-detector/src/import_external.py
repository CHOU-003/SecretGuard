"""
import_external.py — nạp CredData (Samsung) vào schema của dự án

Chạy:
    python -m src.import_external --creddata-dir C:\\Users\\Acer\\CredData

Đầu vào : thư mục CredData đã chạy `python download_data.py` (có meta/ và data/).
Đầu ra  : data/external/creddata.csv với các cột
    text        dòng mã nguồn đầy đủ (đã strip, cắt tối đa --max-line-chars)
    label       1 nếu GroundTruth = T, ngược lại 0 (F và X)
    type        Category gốc của CredData (vd Password, Key, Secret:Token)
    repo        RepoName (CredData đã làm mờ thành mã băm)
    file_path   đường dẫn trong repo, đã bỏ tiền tố data/<repo>/ (vd test/ab12cd34.py)
    gt          nhãn gốc T / F / X
    value       giá trị credential theo ValueStart:ValueEnd (rỗng nếu không có/nhiều dòng)
    multiline   1 nếu credential trải nhiều dòng (text chỉ là dòng đầu)
    split       train / val / test — chia THEO REPO

Những điều cần biết khi dùng nhãn này (xem README của CredData):
  * T = trông giống credential thật. F = dương tính giả. X = giá trị test / ví dụ /
    placeholder. Ở đây gộp F và X thành 0, nhưng giữ cột `gt` để phân tích riêng.
  * Quy tắc gán nhãn số 1 của CredData: MỌI credential trong thư mục test đều là T.
    Điều này NGƯỢC với dữ liệu tổng hợp của dự án (giá trị giả trong test = 0).
    Đây là khác biệt về định nghĩa nhãn, không phải lỗi dữ liệu — phải nêu trong báo cáo.
  * Giá trị credential trong dữ liệu đã bị CredData làm mờ (thay bằng chuỗi ngẫu nhiên
    cùng bộ ký tự/độ dài, hoặc giá trị ví dụ với pattern cố định như AWS). Vẫn KHÔNG
    được thử dùng chúng, và nên che bớt khi đưa vào báo cáo.
  * File đầu ra đã chứa nội dung mã nguồn của các dự án có giấy phép riêng: đừng commit
    data/external/ lên Git (thêm vào .gitignore).
"""

import os
import glob
import argparse
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

SEED = 42
REQUIRED_COLUMNS = ["FilePath", "LineStart", "LineEnd", "GroundTruth", "ValueStart", "ValueEnd", "RepoName", "Category"]
GT_RANK = {"T": 2, "X": 1, "F": 0}  # trùng vị trí: ưu tiên T, rồi X, rồi F


# ------------------------------------------------------------------ meta
def load_meta(meta_dir):
    files = sorted(glob.glob(os.path.join(meta_dir, "*.csv")))
    if not files:
        raise FileNotFoundError(f"Không thấy file .csv nào trong {meta_dir}")
    meta = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in files], ignore_index=True)

    missing = [c for c in REQUIRED_COLUMNS if c not in meta.columns]
    if missing:
        raise ValueError(f"meta thiếu cột {missing}. Cấu trúc CredData có thể đã đổi.")

    for col in ("LineStart", "LineEnd", "ValueStart", "ValueEnd"):
        meta[col] = pd.to_numeric(meta[col], errors="coerce")
    meta = meta[meta["GroundTruth"].isin(GT_RANK)].copy()
    return meta, len(files)


def collapse_duplicates(meta):
    """Nhiều công cụ có thể cùng đánh dấu 1 dòng -> giữ 1 bản, ưu tiên T > X > F."""
    before = len(meta)
    meta = meta.assign(_rank=meta["GroundTruth"].map(GT_RANK))
    meta = meta.sort_values("_rank", ascending=False, kind="stable")
    meta = meta.drop_duplicates(subset=["FilePath", "LineStart", "LineEnd"], keep="first").drop(columns="_rank")
    return meta.sort_index(), before - len(meta)


# --------------------------------------------------------------- đọc file
def read_lines(path):
    """Đọc file thành danh sách dòng, đánh số từ 1 như trình soạn thảo
    (chuẩn hoá \\r\\n và \\r thành \\n; KHÔNG dùng splitlines() vì nó tách cả
    \\x0b, \\x0c, \\u2028... làm lệch số dòng so với CredData)."""
    with open(path, "rb") as f:
        text = f.read().decode("utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def short_path(file_path):
    """data/<repo>/<dir>/<file> -> <dir>/<file> (bỏ phần định danh repo)."""
    parts = str(file_path).split("/")
    return "/".join(parts[2:]) if len(parts) >= 3 and parts[0] == "data" else str(file_path)


def valid_offsets(row):
    vs, ve = row["ValueStart"], row["ValueEnd"]
    return (not pd.isna(vs)) and (not pd.isna(ve)) and vs >= 0 and ve > vs and row["LineStart"] == row["LineEnd"]


def build_rows(meta, root, max_chars):
    records, dropped = [], Counter()
    for file_path, rows in meta.groupby("FilePath", sort=False):
        abs_path = os.path.join(root, file_path)
        if not os.path.isfile(abs_path):
            dropped["thiếu file nguồn"] += len(rows)
            continue
        lines = read_lines(abs_path)

        for _, row in rows.iterrows():
            ls = row["LineStart"]
            if pd.isna(ls) or not (1 <= ls <= len(lines)):
                dropped["số dòng ngoài phạm vi file"] += 1
                continue
            raw = lines[int(ls) - 1]
            if not raw.strip():
                dropped["dòng rỗng"] += 1
                continue

            multiline = int(row["LineEnd"] != row["LineStart"])
            value = ""
            if valid_offsets(row):
                vs, ve = int(row["ValueStart"]), int(row["ValueEnd"])
                if ve <= len(raw):
                    value = raw[vs:ve]
                else:
                    dropped["offset vượt độ dài dòng"] += 1
                    continue

            if len(raw) > max_chars:
                if value and int(row["ValueEnd"]) > max_chars:
                    dropped["giá trị nằm ngoài phần cắt (dòng quá dài)"] += 1
                    continue
                raw_text = raw[:max_chars]
            else:
                raw_text = raw

            records.append({
                "text": raw_text.strip(),
                "label": int(row["GroundTruth"] == "T"),
                "type": row["Category"] or "Unknown",
                "repo": row["RepoName"],
                "file_path": short_path(file_path),
                "gt": row["GroundTruth"],
                "value": value,
                "multiline": multiline,
            })
    return pd.DataFrame(records), dropped


# ---------------------------------------------------------------- chia tập
def assign_splits(df, seed=SEED, tries=300, row_range=(0.10, 0.20), min_pos_share=0.10):
    """Chia repo vào train/val/test ~70/15/15. Thử nhiều seed cho tới khi val và test
    đều chiếm 10–20% số dòng VÀ ≥10% số dòng T (tránh tập test gần như không có secret)."""
    n_pos = max(int(df["label"].sum()), 1)
    for t in range(tries):
        gss1 = GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=seed + t)
        train_idx, temp_idx = next(gss1.split(df, groups=df["repo"]))
        temp = df.iloc[temp_idx]
        gss2 = GroupShuffleSplit(n_splits=1, test_size=0.50, random_state=seed + t)
        val_rel, test_rel = next(gss2.split(temp, groups=temp["repo"]))

        parts = {"val": temp.iloc[val_rel], "test": temp.iloc[test_rel]}
        ok = all(row_range[0] <= len(p) / len(df) <= row_range[1] and p["label"].sum() / n_pos >= min_pos_share
                 for p in parts.values())
        if ok:
            split = pd.Series("train", index=df.index)
            split.loc[parts["val"].index] = "val"
            split.loc[parts["test"].index] = "test"
            return split, seed + t
    raise RuntimeError("Không tìm được cách chia repo thoả điều kiện; nới row_range/min_pos_share.")


# ------------------------------------------------------------------ báo cáo
def print_summary(df, n_meta_files, dup_removed, dropped):
    print("\n" + "=" * 70)
    print("TÓM TẮT NẠP CREDDATA")
    print("=" * 70)
    print(f"File meta: {n_meta_files} | dòng sau khi gộp trùng: {len(df) + sum(dropped.values())} "
          f"(đã gộp {dup_removed} dòng trùng vị trí)")
    if dropped:
        print("Dòng bị loại:")
        for reason, n in dropped.most_common():
            print(f"  - {reason}: {n}")
    print(f"Dòng giữ lại: {len(df)} | số repo: {df['repo'].nunique()}")
    print(f"Nhãn gốc: " + ", ".join(f"{k}={v}" for k, v in df['gt'].value_counts().items()))
    print(f"Tỉ lệ secret (T) trong các dòng nghi vấn: {df['label'].mean():.1%}")
    print(f"Dòng nhiều dòng: {int(df['multiline'].sum())} | T có offset giá trị hợp lệ: "
          f"{int(((df['label'] == 1) & (df['value'] != '')).sum())}/{int(df['label'].sum())}")

    top_dir = df["file_path"].str.split("/").str[0]
    tbl = pd.crosstab(top_dir, df["label"]).rename(columns={0: "không", 1: "secret"})
    tbl["%secret"] = (tbl["secret"] / tbl.sum(axis=1) * 100).round(1)
    print("\nThư mục đầu của file_path vs nhãn (10 thư mục lớn nhất):")
    print(tbl.sort_values(["không", "secret"], ascending=False).head(10).to_string())

    print("\nChia theo repo:")
    for name in ("train", "val", "test"):
        part = df[df["split"] == name]
        print(f"  {name:<5}: {len(part):>6} dòng | {part['repo'].nunique():>3} repo | "
              f"tỉ lệ secret = {part['label'].mean():.1%}")
    repo_sets = {n: set(df[df["split"] == n]["repo"]) for n in ("train", "val", "test")}
    overlap = (repo_sets["train"] & repo_sets["val"]) | (repo_sets["train"] & repo_sets["test"]) | (repo_sets["val"] & repo_sets["test"])
    print("✅ Không repo nào nằm ở 2 tập." if not overlap else f"⚠️  OVERLAP {len(overlap)} repo!")


def main():
    parser = argparse.ArgumentParser(description="Nạp CredData vào schema dự án")
    parser.add_argument("--creddata-dir", required=True, help="Thư mục gốc CredData (chứa meta/ và data/)")
    parser.add_argument("--max-line-chars", type=int, default=1500, help="Cắt dòng dài hơn mức này")
    parser.add_argument("--out", default=None, help="Mặc định: data/external/creddata.csv")
    args = parser.parse_args()

    root = os.path.abspath(args.creddata_dir)
    if not os.path.isdir(os.path.join(root, "meta")) or not os.path.isdir(os.path.join(root, "data")):
        raise SystemExit(f"{root} thiếu thư mục meta/ hoặc data/. Đã chạy download_data.py chưa?")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = args.out or os.path.join(base_dir, "data", "external", "creddata.csv")

    meta, n_files = load_meta(os.path.join(root, "meta"))
    meta, dup_removed = collapse_duplicates(meta)
    print(f"Đọc {len(meta)} dòng nhãn từ {n_files} file meta. Đang đọc file nguồn...")

    df, dropped = build_rows(meta, root, args.max_line_chars)
    if df.empty:
        raise SystemExit("Không có dòng nào đọc được. Kiểm tra --creddata-dir và việc đã chạy download_data.py.")

    df["split"], used_seed = assign_splits(df)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_csv(out_path, index=False)

    print_summary(df, n_files, dup_removed, dropped)
    print(f"\n(seed chia tập = {used_seed})")
    print(f"✅ Đã lưu: {out_path}")


if __name__ == "__main__":
    main()