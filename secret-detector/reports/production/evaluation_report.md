# Báo cáo đánh giá cấp dòng (TEST) — model `production`

Ngưỡng cảnh báo: 0.8. Điểm của dòng = điểm cao nhất của các candidate trong dòng.

## CredData (test: 7438 dòng, 51 repo, 22.30% là secret)

| Phương pháp | Precision | Recall | F1 | FPR | FP | FN |
|---|---|---|---|---|---|---|
| Regex | 87.20% | 17.24% | 28.79% | 0.73% | 42 | 1373 |
| Regex + Entropy | 65.38% | 1.02% | 2.02% | 0.16% | 9 | 1642 |
| Chỉ trích candidate (không ML) | 27.80% | 94.64% | 42.97% | 70.57% | 4078 | 89 |
| ML (ngưỡng 0.8) | 87.84% | 48.34% | 62.36% | 1.92% | 111 | 857 |

- ROC-AUC = 0.8712, 95% CI [0.8001, 0.9086] (bootstrap theo repo)
- PR-AUC = 0.7734, 95% CI [0.5578, 0.8525] (bootstrap theo repo)
- Recall ML = 48.34%, 95% CI [45.94%, 50.75%] (Wilson)
- FPR ML = 1.92%, 95% CI [1.60%, 2.31%] (Wilson)
- ECE (dòng có candidate) = 0.0657

**Phễu recall** (mất mát nằm ở đâu):

| Dòng secret | Có ≥1 candidate | Bị cảnh báo |
|---|---|---|
| 1659 | 1570 (94.64%) | 802 (48.34%) |

**Quét ngưỡng (ML):**

| Ngưỡng | Precision | Recall | FPR |
|---|---|---|---|
| 0.3 | 76.71% | 71.49% | 6.23% |
| 0.4 | 80.45% | 67.45% | 4.71% |
| 0.5 | 82.30% | 64.20% | 3.96% |
| 0.6 | 83.05% | 61.12% | 3.58% |
| 0.7 | 85.30% | 57.02% | 2.82% |
| 0.8 | 87.84% | 48.34% | 1.92% |
| 0.9 | 85.75% | 37.73% | 1.80% |

**Precision kỳ vọng khi tỉ lệ secret ngoài đời thấp:**

| Tỉ lệ secret | ML | ML (FPR cận trên) | Regex | Regex + Entropy |
|---|---|---|---|---|
| 1% | 20.27% | 17.46% | 19.33% | 6.23% |
| 2% | 33.93% | 29.95% | 32.62% | 11.84% |
| 5% | 56.98% | 52.44% | 55.52% | 25.72% |
| 10% | 73.66% | 69.95% | 72.49% | 42.23% |

**Theo ngữ cảnh đường dẫn (ML):**

| Ngữ cảnh | Số dòng | Tỉ lệ secret | Precision | Recall | FPR |
|---|---|---|---|---|---|
| thư mục test/mẫu | 4295 | 31.20% | 86.03% | 48.73% | 3.59% |
| thư mục khác | 3143 | 10.15% | 96.75% | 46.71% | 0.18% |

**Loại mẫu bị lỗi nhiều nhất (ML):**

| Nhãn | Loại | Số mẫu | Lỗi ML | Lỗi Regex |
|---|---|---|---|---|
| 1 | Password | 154 | 147 | 150 |
| 1 | PEM Private Key | 124 | 124 | 7 |
| 1 | UUID | 584 | 104 | 584 |
| 1 | Secret | 144 | 99 | 128 |
| 1 | Token | 116 | 69 | 107 |
| 1 | Auth | 65 | 59 | 65 |
| 1 | AWS Client ID | 106 | 58 | 0 |
| 0 | UUID | 177 | 57 | 0 |
| 1 | Key | 53 | 44 | 53 |
| 0 | UUID:Key | 19 | 19 | 0 |
| 0 | Key:UUID | 18 | 18 | 0 |
| 1 | OTP / 2FA Secret | 16 | 16 | 16 |

