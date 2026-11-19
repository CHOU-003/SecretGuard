# So sánh với Gitleaks và TruffleHog (TEST)

Model: `production` | cảnh báo ≥ 0.5 | chặn ≥ 0.8

Phiên bản công cụ: Gitleaks: 8.30.1; TruffleHog: trufflehog 3.99.7

Cấu hình mặc định cho mọi công cụ; TruffleHog chạy `--no-verification`, Gitleaks chạy `--redact`.

## CredData (7438 dòng, 51 repo, 22.30% là secret)

| Phương pháp | Precision | Recall (95% CI) | F1 | FPR (95% CI) |
|---|---|---|---|---|
| Regex | 87.20% | 17.24% [15.50%, 19.13%] | 28.79% | 0.73% [0.54%, 0.98%] |
| Regex + Entropy | 65.38% | 1.02% [0.64%, 1.63%] | 2.02% | 0.16% [0.08%, 0.30%] |
| Chỉ trích candidate (không ML) | 27.80% | 94.64% [93.44%, 95.62%] | 42.97% | 70.57% [69.38%, 71.73%] |
| Gitleaks | 92.16% | 25.50% [23.46%, 27.65%] | 39.94% | 0.62% [0.45%, 0.86%] |
| TruffleHog | 38.46% | 1.21% [0.78%, 1.85%] | 2.34% | 0.55% [0.39%, 0.78%] |
| ML cảnh báo (≥0.5) | 82.30% | 64.20% [61.86%, 66.47%] | 72.13% | 3.96% [3.49%, 4.50%] |
| ML chặn (≥0.8) | 87.84% | 48.34% [45.94%, 50.75%] | 62.36% | 1.92% [1.60%, 2.31%] |

**Chênh lệch F1 của ML so với từng phương pháp** (dương = ML tốt hơn; CI bootstrap theo repo; CI không chứa 0 nghĩa là chênh lệch vững khi lấy mẫu lại repo):

| ML | so với | ΔF1 | 95% CI |
|---|---|---|---|
| ML cảnh báo (≥0.5) | Regex | +43.34 điểm | [+24.36, +49.92] |
| ML cảnh báo (≥0.5) | Regex + Entropy | +70.11 điểm | [+50.91, +75.64] |
| ML cảnh báo (≥0.5) | Chỉ trích candidate (không ML) | +29.16 điểm | [+18.66, +41.81] |
| ML cảnh báo (≥0.5) | Gitleaks | +32.19 điểm | [+11.94, +46.06] |
| ML cảnh báo (≥0.5) | TruffleHog | +69.79 điểm | [+50.23, +74.91] |
| ML chặn (≥0.8) | Regex | +33.58 điểm | [-0.57, +44.04] |
| ML chặn (≥0.8) | Regex + Entropy | +60.35 điểm | [+27.65, +67.47] |
| ML chặn (≥0.8) | Chỉ trích candidate (không ML) | +19.39 điểm | [+3.28, +30.20] |
| ML chặn (≥0.8) | Gitleaks | +22.42 điểm | [-11.69, +38.74] |
| ML chặn (≥0.8) | TruffleHog | +60.03 điểm | [+26.96, +67.06] |

**Theo ngữ cảnh đường dẫn** (Recall trên dòng secret / FPR trên dòng không phải secret):

| Ngữ cảnh | Số dòng | Tỉ lệ secret | Regex | Regex + Entropy | Chỉ trích candidate (không ML) | Gitleaks | TruffleHog | ML cảnh báo (≥0.5) | ML chặn (≥0.8) |
|---|---|---|---|---|---|---|---|---|---|
| thư mục test/mẫu | 4295 | 31.20% | 20.45% / 1.08% | 0.82% / 0.14% | 95.30% / 71.61% | 27.39% / 1.22% | 0.60% / 0.58% | 64.25% / 7.38% | 48.73% / 3.59% |
| thư mục khác | 3143 | 10.15% | 3.76% / 0.35% | 1.88% / 0.18% | 91.85% / 69.48% | 17.55% / 0.00% | 3.76% / 0.53% | 63.95% / 0.39% | 46.71% / 0.18% |

**Dòng secret theo Category (giá trị = tỉ lệ được phát hiện, tức recall):**

| Category | Số dòng | Regex | Gitleaks | TruffleHog | ML cảnh báo (≥0.5) | ML chặn (≥0.8) |
|---|---|---|---|---|---|---|
| UUID | 584 | 0.00% | 0.00% | 0.00% | 93.66% | 82.19% |
| Password | 154 | 2.60% | 9.09% | 0.00% | 16.88% | 4.55% |
| Secret | 144 | 11.11% | 63.19% | 0.00% | 50.00% | 31.25% |
| PEM Private Key | 124 | 94.35% | 0.00% | 0.00% | 0.00% | 0.00% |
| Token | 116 | 7.76% | 33.62% | 0.00% | 68.97% | 40.52% |
| AWS Client ID | 106 | 100.00% | 76.42% | 0.00% | 100.00% | 45.28% |
| Token:UUID | 84 | 0.00% | 100.00% | 0.00% | 100.00% | 100.00% |
| Auth | 65 | 0.00% | 20.00% | 9.23% | 26.15% | 9.23% |
| Key | 53 | 0.00% | 45.28% | 0.00% | 35.85% | 16.98% |

**Dòng KHÔNG phải secret theo Category (giá trị = tỉ lệ bị báo nhầm, tức FPR):**

| Category | Số dòng | Regex | Gitleaks | TruffleHog | ML cảnh báo (≥0.5) | ML chặn (≥0.8) |
|---|---|---|---|---|---|---|
| Key | 2545 | 0.04% | 0.59% | 0.00% | 1.61% | 0.20% |
| Password | 992 | 1.31% | 0.10% | 0.00% | 1.61% | 0.30% |
| Token | 776 | 1.16% | 1.03% | 0.00% | 1.16% | 0.13% |
| API | 430 | 0.00% | 0.23% | 0.00% | 3.02% | 0.00% |
| Auth | 290 | 0.00% | 1.72% | 0.00% | 2.76% | 0.00% |
| Secret | 179 | 1.12% | 0.56% | 0.00% | 1.12% | 0.56% |
| UUID | 177 | 0.00% | 0.00% | 0.00% | 46.89% | 32.20% |
| CMD Password | 58 | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| Credential | 47 | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |

**Precision kỳ vọng khi tỉ lệ secret ngoài đời thấp** (công thức Bayes, giả định TPR/FPR không đổi):

| Tỉ lệ secret | Regex | Regex + Entropy | Chỉ trích candidate (không ML) | Gitleaks | TruffleHog | ML cảnh báo (≥0.5) | ML chặn (≥0.8) |
|---|---|---|---|---|---|---|---|
| 1% | 19.33% | 6.23% | 1.34% | 29.25% | 2.15% | 14.06% | 20.27% |
| 5% | 55.52% | 25.72% | 6.59% | 68.30% | 10.28% | 46.02% | 56.98% |
| 10% | 72.49% | 42.23% | 12.97% | 81.97% | 19.48% | 64.29% | 73.66% |

**Rule/detector kích hoạt nhiều nhất:**

- **Gitleaks**: generic-api-key (335), aws-access-token (153), jwt (20), gcp-api-key (7), hashicorp-tf-password (3), curl-auth-header (1)
- **TruffleHog**: URI (17), Postgres (17), GoogleGeminiAPIKey (7), Docker (5), FTP (2), JWT (2), GCP (1), MongoDB (1)

