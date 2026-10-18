# Báo cáo đánh giá (tập test)

Số mẫu: 596 | Số repo: 12 | Tỉ lệ secret: 40.77% | Ngưỡng ML: 0.7

## 1. So sánh 3 phương pháp

| Phương pháp | Precision | Recall | F1 | FPR |
|---|---|---|---|---|
| Regex | 72.66% | 79.84% | 76.08% | 20.68% |
| Regex + Entropy | 73.43% | 62.55% | 67.56% | 15.58% |
| Regex + Entropy + ML (ngưỡng 0.7) | 97.54% | 97.94% | 97.74% | 1.70% |

## 2. Chỉ số của mô hình ML

| Chỉ số | Giá trị | Khoảng tin cậy 95% |
|---|---|---|
| ROC-AUC | 0.9987 | [0.9972, 0.9998] (bootstrap theo repo) |
| PR-AUC | 0.9980 | [0.9955, 0.9997] (bootstrap theo repo) |
| Recall | 97.94% | [95.27%, 99.12%] (Wilson) |
| FPR | 1.70% | [0.78%, 3.66%] (Wilson) |
| Brier | 0.0111 | |
| ECE | 0.0091 | |

Confusion matrix: TN=347, FP=6, FN=5, TP=238

## 3. Precision khi tỉ lệ secret ngoài đời thấp

| Tỉ lệ secret | ML | ML (FPR cận trên) | Regex | Regex + Entropy |
|---|---|---|---|---|
| 1% | 36.79% | 21.29% | 3.75% | 3.90% |
| 2% | 54.04% | 35.33% | 7.30% | 7.57% |
| 5% | 75.20% | 58.49% | 16.89% | 17.44% |
| 10% | 86.49% | 74.84% | 30.02% | 30.85% |

## 4. Lỗi theo loại mẫu

| Loại | Nhãn | Số lỗi | Số mẫu |
|---|---|---|---|
| AWS_Key | 1 | 4 | 48 |
| Custom_Secret | 1 | 1 | 73 |
| Doc_Example | 0 | 6 | 18 |
