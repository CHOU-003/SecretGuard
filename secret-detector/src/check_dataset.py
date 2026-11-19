"""
check_dataset.py — kiểm tra tính toàn vẹn của dữ liệu trước khi báo cáo

Chạy:
    python -m src.check_dataset                    # mọi nguồn đang có
    python -m src.check_dataset --sources creddata

Các kiểm tra, cho từng nguồn dữ liệu:
  1. Kích thước, số repo, tỉ lệ secret của từng tập train/val/test.
  2. OVERLAP REPO giữa các cặp tập. Phải bằng 0 (nguyên tắc chia theo repository).
  3. OVERLAP NỘI DUNG: số dòng của val/test có văn bản y hệt một dòng trong train (và val/test với nhau),
     kèm số trường hợp cùng văn bản nhưng KHÁC nhãn. Chia theo repo bảo đảm không trùng repo, nhưng
     không bảo đảm không trùng dòng: nhiều dòng mẫu (cấu hình mặc định, dòng chú thích...) lặp lại giữa
     các dự án. Dòng trùng khiến mô hình "thuộc lòng" thay vì tổng quát hóa.
  4. Trùng lặp bên trong từng tập, và xung đột nhãn trên toàn bộ dữ liệu.

Kết luận từng kiểm tra: PASS / THÔNG TIN / CẢNH BÁO. Tỉ lệ trùng nội dung cao KHÔNG làm kết quả sai,
nhưng phải được nêu trong báo cáo; nếu quá cao (mặc định > 5% dòng test), cần đánh giá lại trên tập test
đã loại các dòng trùng với train.

Kết quả ghi vào reports/dataset_check.json.
"""

import os
import json
import argparse
from itertools import combinations

import pandas as pd

SPLITS = ("train", "val", "test")
SOURCES = ("synthetic", "creddata")
WARN_TEXT_SHARE = 0.05  # > 5% dòng val/test trùng văn bản với train -> cảnh báo


def load_source(data_dir, name):
    if name == "synthetic":
        frames = []
        for split in SPLITS:
            path = os.path.join(data_dir, f"{split}.csv")
            if not os.path.exists(path):
                return None
            part = pd.read_csv(path, keep_default_na=False)
            part["split"] = split
            frames.append(part)
        df = pd.concat(frames, ignore_index=True)
    else:
        path = os.path.join(data_dir, "external", "creddata.csv")
        if not os.path.exists(path):
            return None
        df = pd.read_csv(path, keep_default_na=False)
    df["text_key"] = df["text"].astype(str).str.strip()
    df["label"] = df["label"].astype(int)
    df["repo"] = df["repo"].astype(str) if "repo" in df.columns else ""
    return df


def size_table(df):
    rows = {}
    for s in SPLITS:
        part = df[df["split"] == s]
        rows[s] = {"dong": int(len(part)), "repo": int(part["repo"].nunique()),
                   "ti_le_secret": float(part["label"].mean()) if len(part) else 0.0,
                   "dong_duy_nhat": int(part["text_key"].nunique())}
    return rows


def repo_overlap(df):
    out = {}
    repos = {s: set(df[df["split"] == s]["repo"]) for s in SPLITS}
    for a, b in combinations(SPLITS, 2):
        out[f"{a}-{b}"] = len(repos[a] & repos[b])
    return out


def text_overlap(df, a, b):
    """Dòng của tập b có văn bản trùng một dòng của tập a; và trong đó bao nhiêu dòng khác nhãn."""
    A, B = df[df["split"] == a], df[df["split"] == b]
    labels_a = A.groupby("text_key")["label"].agg(set)
    in_a = B["text_key"].isin(labels_a.index)
    shared = B[in_a]
    conflicts = int(sum(row.label not in labels_a[row.text_key] for row in shared.itertuples()))
    return {"dong_trung": int(in_a.sum()), "ti_le_dong": float(in_a.mean()) if len(B) else 0.0,
            "van_ban_duy_nhat_trung": int(shared["text_key"].nunique()),
            "khac_nhan": conflicts, "ti_le_secret_trong_dong_trung": float(shared["label"].mean()) if len(shared) else None}


def within_dupes(df):
    out = {}
    for s in SPLITS:
        part = df[df["split"] == s]
        out[s] = float(1 - part["text_key"].nunique() / len(part)) if len(part) else 0.0
    return out


def label_conflicts(df):
    n = df.groupby("text_key")["label"].nunique()
    return int((n > 1).sum())


def verdict(passed, info=False):
    return "PASS" if passed else ("THÔNG TIN" if info else "CẢNH BÁO")


def check_source(name, df):
    sizes = size_table(df)
    repos = repo_overlap(df)
    text = {f"{a}->{b}": text_overlap(df, a, b) for a, b in (("train", "val"), ("train", "test"), ("val", "test"))}
    dupes = within_dupes(df)
    conflicts = label_conflicts(df)

    repo_ok = all(v == 0 for v in repos.values())
    text_share = max(text["train->val"]["ti_le_dong"], text["train->test"]["ti_le_dong"])
    two_classes = all(0 < sizes[s]["ti_le_secret"] < 1 for s in SPLITS)

    checks = {
        "overlap_repo_bang_0": verdict(repo_ok),
        "moi_tap_du_2_lop": verdict(two_classes),
        "trung_noi_dung_train_voi_val_test": verdict(text_share <= WARN_TEXT_SHARE, info=text_share == 0 or text_share <= WARN_TEXT_SHARE),
        "xung_dot_nhan_toan_bo": verdict(conflicts == 0, info=True),
    }
    return {"source": name, "sizes": sizes, "repo_overlap": repos, "text_overlap": text,
            "within_split_duplicate_share": dupes, "label_conflict_texts": conflicts, "checks": checks}


def print_report(r):
    print("\n" + "=" * 78)
    print(f"NGUỒN: {r['source']}")
    print("=" * 78)
    print(f"{'Tập':<8}{'Dòng':>9}{'Repo':>7}{'Tỉ lệ secret':>15}{'Dòng duy nhất':>16}{'Trùng nội bộ':>14}")
    for s in SPLITS:
        z = r["sizes"][s]
        print(f"{s:<8}{z['dong']:>9}{z['repo']:>7}{z['ti_le_secret']:>14.1%}{z['dong_duy_nhat']:>16}{r['within_split_duplicate_share'][s]:>13.1%}")
    print("\nOverlap REPO giữa các tập (phải bằng 0): " + ", ".join(f"{k}={v}" for k, v in r["repo_overlap"].items()))
    print("\nOverlap NỘI DUNG (dòng của tập sau có văn bản y hệt một dòng của tập trước):")
    print(f"  {'Cặp':<14}{'Dòng trùng':>12}{'Tỉ lệ':>9}{'Văn bản duy nhất':>19}{'Khác nhãn':>11}{'%secret trong dòng trùng':>26}")
    for k, v in r["text_overlap"].items():
        sec = "n/a" if v["ti_le_secret_trong_dong_trung"] is None else f"{v['ti_le_secret_trong_dong_trung']:.1%}"
        print(f"  {k:<14}{v['dong_trung']:>12}{v['ti_le_dong']:>8.1%}{v['van_ban_duy_nhat_trung']:>19}{v['khac_nhan']:>11}{sec:>26}")
    print(f"\nVăn bản xuất hiện với CẢ HAI nhãn trong toàn bộ dữ liệu: {r['label_conflict_texts']}")
    print("\nKết luận:")
    for k, v in r["checks"].items():
        print(f"  [{v}] {k}")
    share = r["text_overlap"]["train->test"]["ti_le_dong"]
    if share > WARN_TEXT_SHARE:
        print(f"\n⚠️  {share:.1%} dòng test có văn bản trùng với train (> {WARN_TEXT_SHARE:.0%}). Nên báo cáo thêm kết quả trên "
              "tập test đã loại các dòng trùng, và ghi rõ trong phần hạn chế.")
    elif share > 0:
        print(f"\nℹ️  {share:.1%} dòng test trùng văn bản với train: mức thấp, nên nêu trong báo cáo.")


def main():
    parser = argparse.ArgumentParser(description="Kiểm tra overlap và tính toàn vẹn của dữ liệu")
    parser.add_argument("--sources", nargs="+", choices=SOURCES, default=list(SOURCES))
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    results = {}
    for name in args.sources:
        df = load_source(os.path.join(base_dir, "data"), name)
        if df is None:
            print(f"⚠️  Bỏ qua '{name}': chưa có dữ liệu.")
            continue
        results[name] = check_source(name, df)
        print_report(results[name])

    if not results:
        raise SystemExit("Không có nguồn dữ liệu nào.")
    os.makedirs(os.path.join(base_dir, "reports"), exist_ok=True)
    with open(os.path.join(base_dir, "reports", "dataset_check.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n✅ Đã lưu reports/dataset_check.json")


if __name__ == "__main__":
    main()
