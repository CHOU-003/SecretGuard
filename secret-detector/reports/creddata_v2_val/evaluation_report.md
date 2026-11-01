# Báo cáo đánh giá cấp dòng (VALIDATION) — model `creddata_v2`

Ngưỡng cảnh báo: 0.7. Điểm của dòng = điểm cao nhất của các candidate trong dòng.

## CredData (test: 11775 dòng, 50 repo, 15.91% là secret)

| Phương pháp | Precision | Recall | F1 | FPR | FP | FN |
|---|---|---|---|---|---|---|
| Regex | 73.89% | 8.92% | 15.91% | 0.60% | 59 | 1706 |
| Regex + Entropy | 88.00% | 3.52% | 6.78% | 0.09% | 9 | 1807 |
| Chỉ trích candidate (không ML) | 17.39% | 88.63% | 29.07% | 79.64% | 7886 | 213 |
| ML (ngưỡng 0.7) | 71.33% | 44.90% | 55.11% | 3.41% | 338 | 1032 |

- ROC-AUC = 0.8285, 95% CI [0.7935, 0.8827] (bootstrap theo repo)
- PR-AUC = 0.6442, 95% CI [0.5836, 0.8048] (bootstrap theo repo)
- Recall ML = 44.90%, 95% CI [42.66%, 47.16%] (Wilson)
- FPR ML = 3.41%, 95% CI [3.07%, 3.79%] (Wilson)
- ECE (dòng có candidate) = 0.0528

**Phễu recall** (mất mát nằm ở đâu):

| Dòng secret | Có ≥1 candidate | Bị cảnh báo |
|---|---|---|
| 1873 | 1660 (88.63%) | 841 (44.90%) |

**Quét ngưỡng (ML):**

| Ngưỡng | Precision | Recall | FPR |
|---|---|---|---|
| 0.3 | 57.76% | 64.55% | 8.93% |
| 0.4 | 62.86% | 60.81% | 6.80% |
| 0.5 | 64.81% | 55.95% | 5.75% |
| 0.6 | 63.53% | 51.15% | 5.55% |
| 0.7 | 71.33% | 44.90% | 3.41% |
| 0.8 | 78.48% | 36.41% | 1.89% |
| 0.9 | 85.37% | 24.29% | 0.79% |

**Precision kỳ vọng khi tỉ lệ secret ngoài đời thấp:**

| Tỉ lệ secret | ML | ML (FPR cận trên) | Regex | Regex + Entropy |
|---|---|---|---|---|
| 1% | 11.73% | 10.69% | 13.13% | 28.14% |
| 2% | 21.16% | 19.47% | 23.39% | 44.17% |
| 5% | 40.91% | 38.41% | 44.06% | 67.11% |
| 10% | 59.38% | 56.83% | 62.44% | 81.16% |

**Theo ngữ cảnh đường dẫn (ML):**

| Ngữ cảnh | Số dòng | Tỉ lệ secret | Precision | Recall | FPR |
|---|---|---|---|---|---|
| thư mục test/mẫu | 3220 | 35.40% | 85.66% | 38.77% | 3.56% |
| thư mục khác | 8555 | 8.57% | 60.18% | 54.43% | 3.38% |

**Loại mẫu bị lỗi nhiều nhất (ML):**

| Nhãn | Loại | Số mẫu | Lỗi ML | Lỗi Regex |
|---|---|---|---|---|
| 1 | Password | 387 | 348 | 377 |
| 0 | UUID | 1386 | 205 | 0 |
| 1 | NTLM Token:Bearer Authorization:Auth | 104 | 104 | 104 |
| 1 | URL Credentials | 100 | 90 | 100 |
| 1 | UUID | 312 | 87 | 312 |
| 1 | JWK | 76 | 47 | 76 |
| 1 | Key | 158 | 45 | 158 |
| 1 | PEM Private Key | 42 | 42 | 21 |
| 0 | Key | 2451 | 30 | 1 |
| 1 | JSON Web Token | 35 | 27 | 35 |
| 0 | Password | 2483 | 24 | 10 |
| 1 | Token | 81 | 22 | 65 |

