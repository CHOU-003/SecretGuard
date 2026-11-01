"""
scoring.py — đường chấm điểm cấp DÒNG, dùng chung cho evaluate.py và main.py

Một dòng mã nguồn được chấm như sau:
    dòng -> extract_candidates() -> với mỗi candidate: extract_features() + encode_features()
         -> model.predict_proba() -> điểm của dòng = điểm CAO NHẤT trong các candidate

Dòng không có candidate nào có điểm 0.0 (hệ thống không đưa ra cảnh báo cho dòng đó).

Tính theo LÔ: gom feature của mọi candidate rồi gọi predict_proba một lần. Gọi từng
candidate một chậm hơn hàng chục lần với model calibrated.

Ai muốn chấm điểm dòng mã (main.py, evaluate.py, benchmark...) đều phải gọi score_lines()
ở đây; không tự dựng feature riêng, để lúc train và lúc chạy thật luôn nhìn cùng một thứ.
"""

import os
from dataclasses import dataclass

import joblib
import pandas as pd

from src.candidate import Candidate, extract_candidates
from src.feature_extractor import encode_features, extract_features


@dataclass(frozen=True)
class LineScore:
    score: float                  # điểm cao nhất trong các candidate (0.0 nếu không có)
    n_candidates: int
    best: Candidate = None        # candidate có điểm cao nhất


def models_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")


def load_model(tag=None):
    """tag = None hoặc 'production' -> model chính thức (models/secret_ml_model.pkl);
    ngược lại -> models/experiments/<tag>/. Trả về (model, feature_columns)."""
    root = models_dir()
    if tag in (None, "production"):
        model_path = os.path.join(root, "secret_ml_model.pkl")
        columns_path = os.path.join(root, "feature_columns.pkl")
    else:
        exp = os.path.join(root, "experiments", tag)
        model_path = os.path.join(exp, "model.pkl")
        columns_path = os.path.join(exp, "feature_columns.pkl")
    for path in (model_path, columns_path):
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Không thấy {path}. Train bằng `python -m src.train_ml --train-on ...` "
                f"rồi (nếu cần) `--promote <tag>`."
            )
    return joblib.load(model_path), joblib.load(columns_path)


def score_lines(items, model, columns):
    """items: iterable gồm (text, file_path). Trả về list[LineScore] cùng thứ tự."""
    per_line, rows, owners = [], [], []
    for i, (text, file_path) in enumerate(items):
        text = "" if text is None else str(text)
        cands = extract_candidates(text)
        per_line.append(len(cands))
        for c in cands:
            raw = extract_features(c.value, text, file_path or "", c.regex_type, source=c.source, start=c.start)
            rows.append(encode_features(raw))
            owners.append((i, c))

    results = [LineScore(0.0, n, None) for n in per_line]
    if not rows:
        return results

    X = pd.DataFrame(rows).reindex(columns=columns, fill_value=0)
    proba = model.predict_proba(X)[:, 1]
    for (i, cand), p in zip(owners, proba):
        current = results[i]
        if current.best is None or p > current.score:
            results[i] = LineScore(float(p), current.n_candidates, cand)
    return results