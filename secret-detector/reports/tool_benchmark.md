# So sánh với Gitleaks và TruffleHog (cùng tập test)

Số mẫu: 596 | Tỉ lệ secret: 40.77% | Ngưỡng ML: 0.7

Phiên bản công cụ: Gitleaks: 8.30.1; TruffleHog: trufflehog 3.99.7

Cấu hình mặc định cho mọi công cụ. TruffleHog chạy `--no-verification`, Gitleaks chạy `--redact`.

## 1. Kết quả tổng hợp

| Phương pháp | Precision | Recall | F1 | FPR | FP | FN |
|---|---|---|---|---|---|---|
| Regex | 72.66% | 79.84% | 76.08% | 20.68% | 73 | 49 |
| Regex + Entropy | 73.43% | 62.55% | 67.56% | 15.58% | 55 | 91 |
| Gitleaks | 92.04% | 76.13% | 83.33% | 4.53% | 16 | 58 |
| TruffleHog | 100.00% | 9.47% | 17.29% | 0.00% | 0 | 220 |
| ML (ngưỡng 0.7) | 97.54% | 97.94% | 97.74% | 1.70% | 6 | 5 |

## 2. Số lỗi theo loại mẫu

Nhãn 0 = không phải secret (lỗi là báo nhầm). Nhãn 1 = secret thật (lỗi là bỏ sót).

| Nhãn | Loại | Số mẫu | Regex | Regex + Entropy | Gitleaks | TruffleHog | ML (ngưỡng 0.7) |
|---|---|---|---|---|---|---|---|
| 0 | Base64_Text | 21 | 0 | 0 | 0 | 0 | 0 |
| 0 | Checksum | 30 | 0 | 0 | 0 | 0 | 0 |
| 0 | Code_Line | 40 | 0 | 0 | 0 | 0 | 0 |
| 0 | Doc_Example | 18 | 10 | 0 | 0 | 0 | 6 |
| 0 | Git_Hash | 36 | 0 | 0 | 0 | 0 | 0 |
| 0 | Normal_Code | 48 | 0 | 0 | 0 | 0 | 0 |
| 0 | Placeholder | 59 | 26 | 18 | 0 | 0 | 0 |
| 0 | Test_Mock | 37 | 37 | 37 | 16 | 0 | 0 |
| 0 | URL | 38 | 0 | 0 | 0 | 0 | 0 |
| 0 | UUID | 26 | 0 | 0 | 0 | 0 | 0 |
| 1 | AWS_Key | 48 | 0 | 42 | 41 | 48 | 4 |
| 1 | Custom_Secret | 73 | 49 | 49 | 17 | 73 | 1 |
| 1 | Generic_Secret | 58 | 0 | 0 | 0 | 58 | 0 |
| 1 | GitHub_Token | 23 | 0 | 0 | 0 | 0 | 0 |
| 1 | Slack_Token | 41 | 0 | 0 | 0 | 41 | 0 |

## 3. Precision kỳ vọng khi tỉ lệ secret ngoài đời thấp

| Tỉ lệ secret | Regex | Regex + Entropy | Gitleaks | TruffleHog | ML (ngưỡng 0.7) |
|---|---|---|---|---|---|
| 1% | 3.75% | 3.90% | 14.51% | 100.00% | 36.79% |
| 5% | 16.89% | 17.44% | 46.92% | 100.00% | 75.20% |

## 4. Rule/detector được kích hoạt nhiều nhất

- **Gitleaks**: generic-api-key (130), slack-legacy-bot-token (41), github-pat (23), aws-access-token (7)
- **TruffleHog**: Github (23)
