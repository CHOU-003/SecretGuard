import sys
import os
# Thêm thư mục hiện tại vào Python Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix
from src.regex_scanner import scan_with_regex
from src.entropy_scanner import scan_with_regex_and_entropy

NON_FEATURE_COLUMNS = ["label", "_original_type"]

def evaluate_method_1(test_df):
    start_time = time.time()
    y_pred = []
    for text in test_df['text']:
        results = scan_with_regex(str(text))
        y_pred.append(1 if len(results) > 0 else 0)
    exec_time = (time.time() - start_time) * 1000 # miliseconds
    return y_pred, exec_time

def evaluate_method_2(test_df):
    start_time = time.time()
    y_pred = []
    for text in test_df['text']:
        results = scan_with_regex_and_entropy(str(text), entropy_threshold=4.0)
        y_pred.append(1 if len(results) > 0 else 0)
    exec_time = (time.time() - start_time) * 1000
    return y_pred, exec_time

def evaluate_method_3(test_df, model):
    start_time = time.time()
    X_test = test_df.drop(columns=[c for c in NON_FEATURE_COLUMNS if c in test_df.columns])
    y_pred = model.predict(X_test)
    exec_time = (time.time() - start_time) * 1000
    return y_pred, exec_time

def calculate_fpr(y_true, y_pred):
    cm = confusion_matrix(y_true, y_pred)
    if cm.shape == (2, 2):
        TN, FP, FN, TP = cm.ravel()
        return FP / (FP + TN) if (FP + TN) > 0 else 0.0
    return 0.0

def run_benchmark():
    test_df = pd.read_csv("data/test.csv")
    test_features_df = pd.read_csv("data/test_features.csv")
    y_true = test_df['label']
    clf = joblib.load("models/secret_ml_model.pkl")

    y_p1, time1 = evaluate_method_1(test_df)
    y_p2, time2 = evaluate_method_2(test_df)
    y_p3, time3 = evaluate_method_3(test_features_df, clf)

    methods = ["1. Regex", "2. Regex + Entropy", "3. Regex + Entropy + ML"]
    preds = [y_p1, y_p2, y_p3]
    times = [time1, time2, time3]

    print("\n" + "="*75)
    print("BẢNG KẾT QUẢ THỰC NGHIỆM SO SÁNH 3 PHƯƠNG PHÁP (TẬP TEST SET)")
    print("="*75)
    print(f"{'Phương pháp':<26} | {'Precision':<9} | {'Recall':<8} | {'F1-Score':<8} | {'FPR':<7} | {'Time (ms)':<9}")
    print("-" * 78)

    for name, y_pred, t in zip(methods, preds, times):
        prec = precision_score(y_true, y_pred, zero_division=0)
        rec = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        fpr = calculate_fpr(y_true, y_pred)
        print(f"{name:<26} | {prec*100:6.2f}%   | {rec*100:6.2f}%  | {f1*100:6.2f}%  | {fpr*100:5.2f}% | {t:7.2f} ms")

    print("="*75 + "\n")

if __name__ == "__main__":
    run_benchmark()