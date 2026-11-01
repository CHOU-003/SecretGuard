"""
candidate.py — bộ trích "candidate" DÙNG CHUNG cho train, đánh giá và main.py

Vì sao cần file này: trước đây build_features.py tính feature trên CẢ DÒNG mẫu,
còn main.py lại tính trên GIÁ TRỊ được gán -> mô hình lúc train và lúc chạy thật
nhìn thấy 2 thứ khác nhau; token đứng một mình (không có dấu = hay :) thì main.py
không bao giờ xét tới. Giờ mọi nơi đều gọi extract_candidates(line).

Mỗi dòng sinh ra 0..N candidate từ 4 nguồn (ưu tiên từ trên xuống, candidate sau
bị bỏ nếu chồng lấn candidate trước):
    regex       khớp pattern trong regex_scanner.PATTERNS (AWS, Slack, GitHub...)
    url         mật khẩu trong chuỗi kết nối  scheme://user:PASSWORD@host
    assignment  giá trị gán cho khoá:  key = "value", key: value, KEY=value
    token       chuỗi dài, entropy cao đứng một mình (bắt token không có ngữ cảnh gán)

Các hằng số MIN_* bên dưới là chỗ để chỉnh sau khi đo bằng:
    python -m src.candidate --evaluate data/external/creddata.csv --split train
CHỈ chỉnh dựa trên tập train (hoặc val). Đừng nhìn tập test để chỉnh candidate.
"""

import re
import sys
import argparse
from dataclasses import dataclass
from collections import Counter

from src.regex_scanner import PATTERNS
from src.entropy_scanner import calculate_shannon_entropy

MAX_LINE_CHARS = 3000          # dòng dài hơn (file minify...) bị bỏ qua
MAX_CANDIDATES_PER_LINE = 8
MIN_QUOTED_LEN = 6             # giá trị trong dấu nháy
MIN_UNQUOTED_LEN = 8           # giá trị không có dấu nháy
MIN_URL_PASSWORD_LEN = 3
MIN_BARE_LEN = 20
MIN_BARE_ENTROPY = 3.2

_COMPILED_REGEX = {name: re.compile(pattern) for name, pattern in PATTERNS.items()}
_QUOTED = re.compile(r"""(?:=>|:=|=|:)\s*(?P<q>['"`])(?P<v>[^\n]+?)(?P=q)""")
_UNQUOTED = re.compile(r"""(?:=|:)\s*(?!//)(?P<v>[^\s'"`,;{}()\[\]<>]+)""")
_URL_PASSWORD = re.compile(r"""[A-Za-z][A-Za-z0-9+.\-]*://[^/\s:@]+:(?P<v>[^@\s/]+)@""")
_BARE_TOKEN = re.compile(r"""(?<![A-Za-z0-9+/_\-=.])(?P<v>[A-Za-z0-9+/_\-=]{%d,})(?![A-Za-z0-9+/_\-=])""" % MIN_BARE_LEN)


@dataclass(frozen=True)
class Candidate:
    value: str
    start: int
    end: int
    source: str                 # regex | url | assignment | token
    regex_type: str = None      # tên pattern nếu source == "regex"


def covers_value(candidate, v_start, v_end, min_overlap=0.5):
    """Candidate có phủ ít nhất min_overlap độ dài giá trị thật [v_start, v_end) không?
    Dùng chung cho gán nhãn candidate (build_features) và đo độ phủ (--evaluate)."""
    overlap = min(candidate.end, v_end) - max(candidate.start, v_start)
    return overlap >= min_overlap * (v_end - v_start)


def _overlaps(start, end, accepted):
    return any(start < c.end and c.start < end for c in accepted)


def extract_candidates(line, include_bare_tokens=True):
    """Trả về danh sách Candidate của 1 dòng (đã khử chồng lấn, tối đa MAX_CANDIDATES_PER_LINE)."""
    line = "" if line is None else str(line)
    if not line.strip() or len(line) > MAX_LINE_CHARS:
        return []

    accepted = []

    def add(value, start, end, source, regex_type=None):
        if len(accepted) >= MAX_CANDIDATES_PER_LINE or not value:
            return
        if not _overlaps(start, end, accepted):
            accepted.append(Candidate(value, start, end, source, regex_type))

    # 1. regex đã biết (lấy group 1 nếu pattern có nhóm, vd Generic API Key -> chỉ phần giá trị)
    for name, rx in _COMPILED_REGEX.items():
        for m in rx.finditer(line):
            if m.lastindex:
                add(m.group(1), m.start(1), m.end(1), "regex", name)
            else:
                add(m.group(0), m.start(), m.end(), "regex", name)

    # 2. mật khẩu trong URL kết nối
    for m in _URL_PASSWORD.finditer(line):
        if len(m.group("v")) >= MIN_URL_PASSWORD_LEN:
            add(m.group("v"), m.start("v"), m.end("v"), "url")

    # 3. giá trị được gán: có dấu nháy trước, không dấu nháy sau
    for m in _QUOTED.finditer(line):
        if len(m.group("v")) >= MIN_QUOTED_LEN:
            add(m.group("v"), m.start("v"), m.end("v"), "assignment")
    for m in _UNQUOTED.finditer(line):
        if len(m.group("v")) >= MIN_UNQUOTED_LEN:
            add(m.group("v"), m.start("v"), m.end("v"), "assignment")

    # 4. token dài đứng một mình: phải có cả chữ lẫn số và entropy đủ cao (loại đường dẫn, tên biến)
    if include_bare_tokens:
        for m in _BARE_TOKEN.finditer(line):
            v = m.group("v")
            if (any(c.isalpha() for c in v) and any(c.isdigit() for c in v)
                    and calculate_shannon_entropy(v) >= MIN_BARE_ENTROPY):
                add(v, m.start("v"), m.end("v"), "token")

    return sorted(accepted, key=lambda c: c.start)


# ======================================================================
# Chế độ đo: python -m src.candidate --evaluate <csv> [--split train]
# ======================================================================
def _redact_example(text, value, width=110):
    shown = text.replace(value, "<VALUE>") if value else text
    return shown[:width] + ("…" if len(shown) > width else "")


def evaluate(csv_path, split, n_examples):
    import pandas as pd

    df = pd.read_csv(csv_path, keep_default_na=False)
    if split and "split" in df.columns:
        df = df[df["split"] == split]
        print(f"Đo trên tập '{split}': {len(df)} dòng")
    elif split:
        print("CSV không có cột split -> đo trên toàn bộ file.")
    has_value = "value" in df.columns

    rows = [extract_candidates(str(t)) for t in df["text"]]
    df = df.assign(n_cands=[len(c) for c in rows], has_cand=[len(c) > 0 for c in rows])

    pos, neg = df[df["label"] == 1], df[df["label"] == 0]
    print("\n--- Chi phí và độ phủ cấp DÒNG ---")
    print(f"Dòng secret (nhãn 1) có >=1 candidate : {pos['has_cand'].mean():.1%}  ({int(pos['has_cand'].sum())}/{len(pos)})")
    print(f"Dòng không phải secret có >=1 candidate: {neg['has_cand'].mean():.1%}  (đây là phần ML phải loại bỏ)")
    print(f"Số candidate trung bình / dòng        : secret {pos['n_cands'].mean():.2f} | không {neg['n_cands'].mean():.2f}")

    source_counter = Counter(c.source for cands in rows for c in cands)
    print("Candidate theo nguồn: " + ", ".join(f"{k}={v}" for k, v in source_counter.most_common()))

    if not has_value:
        print("\n(CSV không có cột `value` nên bỏ qua đo độ phủ đúng giá trị.)")
        return

    # Độ phủ giá trị: có candidate chồng lấn >= 50% độ dài giá trị thật không?
    covered, locatable, covered_by, missed = 0, 0, Counter(), []
    for (_, r), cands in zip(df.iterrows(), rows):
        value = str(r["value"])
        if r["label"] != 1 or not value:
            continue
        pos_in_text = str(r["text"]).find(value)
        if pos_in_text < 0:
            continue
        locatable += 1
        v_start, v_end = pos_in_text, pos_in_text + len(value)
        hits = [c for c in cands if covers_value(c, v_start, v_end)]
        if hits:
            covered += 1
            for src in {c.source for c in hits}:
                covered_by[src] += 1
        else:
            missed.append(r)

    print("\n--- Độ phủ GIÁ TRỊ THẬT (chỉ dòng T có offset) ---")
    print(f"Định vị được giá trị trong dòng: {locatable} dòng T")
    print(f"Candidate bắt trúng giá trị      : {covered / max(locatable, 1):.1%}  ({covered}/{locatable})")
    print("Nguồn bắt trúng (một dòng có thể do nhiều nguồn): "
          + ", ".join(f"{k}={v}" for k, v in covered_by.most_common()))

    if missed:
        miss_types = Counter(str(r["type"]) for r in missed)
        print("\nDòng T bị bỏ sót theo Category: " + ", ".join(f"{k}={v}" for k, v in miss_types.most_common(8)))
        print(f"\n{min(n_examples, len(missed))} ví dụ bị bỏ sót (giá trị đã che bằng <VALUE>):")
        for r in missed[:n_examples]:
            print(f"  [{r['type']}] {_redact_example(str(r['text']), str(r['value']))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bộ trích candidate dùng chung")
    parser.add_argument("--evaluate", metavar="CSV", help="Đo độ phủ/chi phí trên 1 file dataset")
    parser.add_argument("--split", default="train", help="Chỉ đo tập này nếu CSV có cột split (mặc định: train)")
    parser.add_argument("--examples", type=int, default=10, help="Số ví dụ bị bỏ sót cần in")
    parser.add_argument("--line", help="Thử trích candidate trên 1 dòng văn bản")
    args = parser.parse_args()

    if args.line:
        for c in extract_candidates(args.line):
            print(f"[{c.source}{'/' + c.regex_type if c.regex_type else ''}] {c.value!r} ({c.start}:{c.end})")
    elif args.evaluate:
        evaluate(args.evaluate, args.split, args.examples)
    else:
        parser.print_help()
        sys.exit(1)