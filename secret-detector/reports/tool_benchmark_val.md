# So sánh với Gitleaks và TruffleHog (VALIDATION)

Model: `creddata_v2` | cảnh báo ≥ 0.5 | chặn ≥ 0.8

Phiên bản công cụ: Gitleaks: 8.30.1; TruffleHog: trufflehog 3.99.7

Cấu hình mặc định cho mọi công cụ; TruffleHog chạy `--no-verification`, Gitleaks chạy `--redact`.

## CredData (11775 dòng, 50 repo, 15.91% là secret)

| Phương pháp | Precision | Recall (95% CI) | F1 | FPR (95% CI) |
|---|---|---|---|---|
| Regex | 73.89% | 8.92% [7.71%, 10.29%] | 15.91% | 0.60% [0.46%, 0.77%] |
| Regex + Entropy | 88.00% | 3.52% [2.78%, 4.46%] | 6.78% | 0.09% [0.05%, 0.17%] |
| Chỉ trích candidate (không ML) | 17.39% | 88.63% [87.11%, 89.99%] | 29.07% | 79.64% [78.84%, 80.42%] |
| Gitleaks | 89.58% | 20.66% [18.89%, 22.55%] | 33.58% | 0.45% [0.34%, 0.61%] |
| TruffleHog | 24.71% | 1.12% [0.73%, 1.71%] | 2.15% | 0.65% [0.51%, 0.82%] |
| ML cảnh báo (≥0.5) | 64.81% | 55.95% [53.69%, 58.19%] | 60.06% | 5.75% [5.30%, 6.22%] |
| ML chặn (≥0.8) | 78.48% | 36.41% [34.26%, 38.62%] | 49.74% | 1.89% [1.64%, 2.18%] |

**Chênh lệch F1 của ML so với từng phương pháp** (dương = ML tốt hơn; CI bootstrap theo repo; CI không chứa 0 nghĩa là chênh lệch vững khi lấy mẫu lại repo):

| ML | so với | ΔF1 | 95% CI |
|---|---|---|---|
| ML cảnh báo (≥0.5) | Regex | +44.14 điểm | [+34.56, +56.20] |
| ML cảnh báo (≥0.5) | Regex + Entropy | +53.28 điểm | [+48.11, +61.12] |
| ML cảnh báo (≥0.5) | Chỉ trích candidate (không ML) | +30.98 điểm | [+13.59, +43.30] |
| ML cảnh báo (≥0.5) | Gitleaks | +26.48 điểm | [+17.18, +37.80] |
| ML cảnh báo (≥0.5) | TruffleHog | +57.91 điểm | [+51.26, +69.86] |
| ML chặn (≥0.8) | Regex | +33.83 điểm | [+23.62, +41.08] |
| ML chặn (≥0.8) | Regex + Entropy | +42.97 điểm | [+30.75, +51.62] |
| ML chặn (≥0.8) | Chỉ trích candidate (không ML) | +20.67 điểm | [-7.73, +36.92] |
| ML chặn (≥0.8) | Gitleaks | +16.17 điểm | [+6.62, +23.46] |
| ML chặn (≥0.8) | TruffleHog | +47.60 điểm | [+34.18, +57.79] |

**Theo ngữ cảnh đường dẫn** (Recall trên dòng secret / FPR trên dòng không phải secret):

| Ngữ cảnh | Số dòng | Tỉ lệ secret | Regex | Regex + Entropy | Chỉ trích candidate (không ML) | Gitleaks | TruffleHog | ML cảnh báo (≥0.5) | ML chặn (≥0.8) |
|---|---|---|---|---|---|---|---|---|---|
| thư mục test/mẫu | 3220 | 35.40% | 8.77% / 1.68% | 4.82% / 0.38% | 86.58% / 57.84% | 17.28% / 1.49% | 0.44% / 2.64% | 52.46% / 4.57% | 31.40% / 2.36% |
| thư mục khác | 8555 | 8.57% | 9.14% / 0.31% | 1.50% / 0.01% | 91.81% / 85.44% | 25.92% / 0.18% | 2.18% / 0.12% | 61.39% / 6.06% | 44.20% / 1.76% |

**Dòng secret theo Category (giá trị = tỉ lệ được phát hiện, tức recall):**

| Category | Số dòng | Regex | Gitleaks | TruffleHog | ML cảnh báo (≥0.5) | ML chặn (≥0.8) |
|---|---|---|---|---|---|---|
| Password | 387 | 2.58% | 8.01% | 0.26% | 25.84% | 3.36% |
| UUID | 312 | 0.00% | 0.00% | 0.00% | 76.28% | 66.35% |
| Key | 158 | 0.00% | 47.47% | 0.00% | 84.81% | 68.35% |
| NTLM Token:Bearer Authorization:Auth | 104 | 0.00% | 0.00% | 0.00% | 33.65% | 0.00% |
| URL Credentials | 100 | 0.00% | 0.00% | 14.00% | 12.00% | 8.00% |
| Token | 81 | 19.75% | 48.15% | 0.00% | 83.95% | 55.56% |
| JWK | 76 | 0.00% | 0.00% | 0.00% | 38.16% | 32.89% |
| NKEY Seed | 58 | 0.00% | 0.00% | 0.00% | 98.28% | 72.41% |
| Token:UUID | 57 | 8.77% | 100.00% | 0.00% | 100.00% | 91.23% |
| Secret | 45 | 42.22% | 51.11% | 0.00% | 86.67% | 53.33% |

**Dòng KHÔNG phải secret theo Category (giá trị = tỉ lệ bị báo nhầm, tức FPR):**

| Category | Số dòng | Regex | Gitleaks | TruffleHog | ML cảnh báo (≥0.5) | ML chặn (≥0.8) |
|---|---|---|---|---|---|---|
| Password | 2483 | 0.40% | 0.16% | 0.04% | 1.57% | 0.32% |
| Key | 2451 | 0.04% | 0.78% | 0.00% | 1.35% | 1.14% |
| UUID | 1386 | 0.00% | 0.00% | 0.00% | 28.28% | 6.93% |
| API | 1236 | 0.00% | 0.00% | 0.00% | 0.24% | 0.00% |
| Token | 690 | 2.46% | 0.72% | 0.00% | 2.03% | 0.00% |
| Auth | 685 | 0.15% | 1.31% | 0.00% | 2.19% | 0.88% |
| Secret | 307 | 2.61% | 0.33% | 0.00% | 0.98% | 0.33% |
| Auth:Token | 110 | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| URL Credentials | 88 | 0.00% | 0.00% | 52.27% | 14.77% | 10.23% |
| Credential | 81 | 0.00% | 0.00% | 0.00% | 1.23% | 0.00% |

**Precision kỳ vọng khi tỉ lệ secret ngoài đời thấp** (công thức Bayes, giả định TPR/FPR không đổi):

| Tỉ lệ secret | Regex | Regex + Entropy | Chỉ trích candidate (không ML) | Gitleaks | TruffleHog | ML cảnh báo (≥0.5) | ML chặn (≥0.8) |
|---|---|---|---|---|---|---|---|
| 1% | 13.13% | 28.14% | 1.11% | 31.47% | 1.72% | 8.95% | 16.30% |
| 5% | 44.06% | 67.11% | 5.53% | 70.53% | 8.37% | 33.88% | 50.37% |
| 10% | 62.44% | 81.16% | 11.00% | 83.48% | 16.16% | 51.97% | 68.18% |

**Rule/detector kích hoạt nhiều nhất:**

- **Gitleaks**: generic-api-key (356), jwt (53), aws-access-token (20), curl-auth-header (5), postman-api-token (2), curl-auth-user (1)
- **TruffleHog**: URI (69), Postgres (6), MongoDB (4), JWT (3), FTP (3), JDBC (1), Postman (1)

