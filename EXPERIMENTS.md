# Thực nghiệm và kết quả

Số liệu mang nhãn **validation** và **test** đều đã được đo thật; tập test chỉ được chạm sau khi chốt mô hình và ngưỡng (mục 9). Thời gian xử lý (mục 10) đo trên một máy cá nhân, nên chỉ có giá trị tham khảo.

## 1. Giao thức đánh giá

- **Dữ liệu:** CredData, chia theo repository (234 repo train, 50 validation, 51 test). Xem [DATASET.md](DATASET.md).
- **Hai mức đo.** Mức *candidate* (mỗi chuỗi nghi vấn là một mẫu) dùng để chọn mô hình. Mức *dòng* (điểm của dòng là điểm cao nhất trong các candidate của dòng) mô tả đúng thứ người dùng thấy, và dùng để chọn ngưỡng. Một dòng secret mà bộ trích không sinh được candidate nào bị tính là bỏ sót.
- **Chọn mô hình và ngưỡng trên validation.** Tập test chỉ chạm ở bước cuối, và mỗi lần chạm ghi vào `reports/test_access_log.txt`.
- **Validation đã dùng cho nhiều vòng quyết định:** hai vòng thiết kế feature, chọn mô hình, chọn ngưỡng. Số trên validation có thể lạc quan hơn một chút so với dữ liệu hoàn toàn chưa thấy; số trên test mới là bằng chứng độc lập.
- **Độ bất định:** khoảng tin cậy Wilson cho recall và FPR; bootstrap theo repo (500 lần) cho AUC và cho chênh lệch F1.
- **Seed** cố định 42; mỗi mô hình có `model_card.json`.

## 2. Mô hình và feature (mức candidate, validation)

### Tác dụng của nhóm feature ngữ cảnh

| Chỉ số | 19 feature | 36 feature | Thay đổi |
| --- | --- | --- | --- |
| PR-AUC | 0,538 | 0,692 | +0,154 |
| ROC-AUC | 0,909 | 0,943 | +0,033 |
| Log loss | 0,2346 | 0,1915 | giảm 18% |
| ECE | 0,0609 | 0,0352 | giảm 42% |
| Precision / Recall / FPR tại 0,5 | 0,503 / 0,674 / 0,080 | 0,595 / 0,661 / 0,054 | precision tăng, recall giữ |

Cải thiện xuất hiện ở cả sáu biến thể mô hình (PR-AUC của Random Forest thô: 0,465 lên 0,638; của XGBoost thô: 0,502 lên 0,670), nên không phải do may mắn ở một mô hình. 13 feature mới mô tả tên khóa đứng ngay trước giá trị và hình dạng của giá trị.

### Sáu mô hình với 36 feature

| Mô hình | ROC-AUC | PR-AUC | Brier | Log loss | ECE |
| --- | --- | --- | --- | --- | --- |
| Random Forest (thô) | 0,9332 | 0,6382 | 0,0780 | 0,2589 | 0,1044 |
| Random Forest và sigmoid | 0,9284 | 0,6192 | 0,0695 | 0,2259 | 0,0365 |
| Random Forest và isotonic | 0,9289 | 0,6244 | 0,0676 | 0,2165 | 0,0432 |
| XGBoost (thô) | 0,9443 | 0,6701 | 0,0742 | 0,2618 | 0,0577 |
| XGBoost và sigmoid | 0,9428 | 0,6947 | 0,0629 | 0,2042 | 0,0376 |
| **XGBoost và isotonic (được chọn)** | 0,9425 | 0,6916 | 0,0608 | **0,1915** | 0,0352 |

Mô hình được chọn theo log loss trên validation (hiệu chỉnh bằng cross-validation 5 fold chia theo repo). Tệp mô hình: 2,1 MB.

## 3. Khoảng cách giữa dữ liệu tổng hợp và dữ liệu thật

| Huấn luyện trên | Validation tổng hợp (ROC-AUC / PR-AUC) | Validation CredData (ROC-AUC / PR-AUC) |
| --- | --- | --- |
| Dữ liệu tổng hợp | 0,998 / 0,998 | **0,491 / 0,117** |
| CredData (19 feature) | 0,744 / 0,697 | 0,909 / 0,538 |
| Trộn cả hai (19 feature) | 0,986 / 0,987 | 0,903 / 0,535 |

Mô hình học từ dữ liệu tổng hợp ngang đoán bừa trên dữ liệu thật (PR-AUC 0,117 xấp xỉ tỉ lệ secret 10,7% của validation). Trộn thêm dữ liệu tổng hợp không cải thiện. Mô hình cuối chỉ huấn luyện trên CredData.

## 4. So sánh ở mức dòng, validation

11.775 dòng, 50 repo, 15,9% là secret.

| Phương pháp | Precision | Recall | F1 | FPR |
| --- | --- | --- | --- | --- |
| Regex | 73,89% | 8,92% | 15,91% | 0,60% |
| Regex và entropy | 88,00% | 3,52% | 6,78% | 0,09% |
| Chỉ trích candidate (không ML) | 17,39% | 88,63% | 29,07% | 79,64% |
| Gitleaks 8.30.1 | 89,58% | 20,66% | 33,58% | 0,45% |
| TruffleHog 3.99.7 (không xác minh) | 24,71% | 1,12% | 2,15% | 0,65% |
| **SecretGuard, mức cảnh báo (≥ 0,5)** | 64,81% | 55,95% | 60,06% | 5,75% |
| **SecretGuard, mức chặn (≥ 0,8)** | 78,48% | 36,41% | 49,74% | 1,89% |

ROC-AUC của SecretGuard ở mức dòng: 0,8285 (khoảng tin cậy 0,7935 đến 0,8827); PR-AUC: 0,6442 (0,5836 đến 0,8048).

Chênh lệch F1 của SecretGuard so với từng phương pháp (điểm phần trăm, khoảng tin cậy 95% bootstrap theo repo):

| So với | Mức cảnh báo | Mức chặn |
| --- | --- | --- |
| Regex | +44,14 [+34,56; +56,20] | +33,83 [+23,62; +41,08] |
| Regex và entropy | +53,28 [+48,11; +61,12] | +42,97 [+30,75; +51,62] |
| Chỉ trích candidate | +30,98 [+13,59; +43,30] | +20,67 [−7,73; +36,92] |
| Gitleaks | +26,48 [+17,18; +37,80] | +16,17 [+6,62; +23,46] |
| TruffleHog | +57,91 [+51,26; +69,86] | +47,60 [+34,18; +57,79] |

**Cách đọc công bằng:**

- Regex cũ chỉ bắt 8,9% dòng secret trên dữ liệu thật (62,4% trên dữ liệu tổng hợp): nhiều dòng thật là mật khẩu tự đặt, không có định dạng nào để khớp.
- Tầng ML kéo FPR từ 79,6% (chỉ trích candidate) xuống 5,75% ở mức cảnh báo, đổi lại recall giảm từ 88,6% xuống 56,0%.
- **Gitleaks chính xác hơn và báo nhầm ít hơn** (precision 89,6%, FPR 0,45%) nhưng chỉ bắt 20,7%. F1 của SecretGuard cao hơn vì F1 coi precision và recall ngang nhau; người chỉ chấp nhận rất ít báo nhầm vẫn có lý do chọn Gitleaks.
- **TruffleHog bị thiệt do thiết lập đo:** nó dựa vào bộ phát hiện theo dịch vụ và bước xác minh bằng API, mà ở đây bắt buộc tắt xác minh và chỉ cho nó thấy một dòng.
- **Ở mức chặn, SecretGuard chưa vượt "chỉ trích candidate" một cách vững chắc về F1** (khoảng tin cậy chứa 0).
- **So sánh thiên về SecretGuard:** mô hình được huấn luyện trên chính phân phối của CredData, còn hai công cụ kia thì không.

Tách theo ngữ cảnh đường dẫn (recall / FPR):

| Phương pháp | Thư mục test và mẫu (3.220 dòng, 35,4% secret) | Thư mục khác (8.555 dòng, 8,6% secret) |
| --- | --- | --- |
| Regex | 8,77% / 1,68% | 9,14% / 0,31% |
| Gitleaks | 17,28% / 1,49% | 25,92% / 0,18% |
| TruffleHog | 0,44% / 2,64% | 2,18% / 0,12% |
| SecretGuard cảnh báo | 52,46% / 4,57% | 61,39% / 6,06% |
| SecretGuard chặn | 31,40% / 2,36% | 44,20% / 1,76% |

Rule được kích hoạt nhiều nhất: Gitleaks: `generic-api-key` (356), `jwt` (53), `aws-access-token` (20); TruffleHog: `URI` (69), `Postgres` (6), `MongoDB` (4).

## 5. Chọn ngưỡng (mức dòng, validation)

| Ngưỡng | Precision | Recall | FPR | F1 |
| --- | --- | --- | --- | --- |
| 0,3 | 57,76% | 64,55% | 8,93% | 60,97% |
| 0,4 | 62,86% | 60,81% | 6,80% | 61,82% |
| **0,5 (cảnh báo)** | 64,81% | 55,95% | 5,75% | 60,06% |
| 0,6 | 63,53% | 51,15% | 5,55% | 56,67% |
| 0,7 | 71,33% | 44,90% | 3,41% | 55,11% |
| **0,8 (chặn)** | 78,48% | 36,41% | 1,89% | 49,74% |
| 0,9 | 85,37% | 24,29% | 0,79% | 37,82% |

F1 cao nhất ở 0,4, nhưng ngưỡng cảnh báo là 0,5 để đổi một ít recall lấy precision cao hơn. Ngưỡng chặn 0,8 cân bằng giữa việc ít chặn nhầm (FPR 1,9%) và vẫn bắt được một phần đáng kể (recall 36,4%); ngưỡng 0,9 chặt hơn nhưng chỉ chặn khoảng một phần tư số secret. Đây là quyết định chính sách dựa trên đánh đổi, không phải đáp án duy nhất. Ngưỡng 0,7 mặc định ban đầu được kế thừa từ phiên bản cũ và chưa từng được chọn cho mô hình này. Precision ở 0,6 thấp hơn ở 0,5 do các bậc phẳng của hiệu chỉnh isotonic.

## 6. Độ tin cậy của điểm (mức candidate, validation)

| Khoảng điểm | Số candidate | Điểm trung bình | Tỉ lệ secret thật |
| --- | --- | --- | --- |
| 0,0 – 0,1 | 10.827 | 0,014 | 0,016 |
| 0,1 – 0,2 | 723 | 0,145 | 0,129 |
| 0,2 – 0,3 | 435 | 0,253 | 0,209 |
| 0,3 – 0,4 | 285 | 0,341 | 0,225 |
| 0,4 – 0,5 | 203 | 0,443 | 0,424 |
| 0,5 – 0,6 | 112 | 0,540 | 0,804 |
| 0,6 – 0,7 | 367 | 0,674 | 0,300 |
| 0,7 – 0,8 | 345 | 0,751 | 0,432 |
| 0,8 – 0,9 | 335 | 0,846 | 0,639 |
| 0,9 – 1,0 | 519 | 0,955 | 0,838 |

ECE tổng thể thấp (0,035) vì phần lớn candidate nằm ở dải điểm thấp và được hiệu chỉnh tốt. Ở các dải cao mô hình quá tự tin: điểm 0,955 chỉ ứng với khoảng 84% là secret thật. Giả thuyết (chưa kiểm chứng riêng): lệch tỉ lệ lớp giữa các repo, 22,4% candidate là secret ở tập train nhưng chỉ 10,7% ở validation. **Không diễn giải điểm là xác suất tuyệt đối**; chỉ nói điểm cao hơn thì khả năng là secret cao hơn.

## 7. Phân tích lỗi (validation, ngưỡng 0,7)

Phễu recall: 1.873 dòng secret; 1.660 dòng (88,6%) có ít nhất một candidate, tức 11,4% mất ngay ở bước trích; 841 dòng (44,9%) bị cảnh báo ở ngưỡng 0,7.

| Loại (nhãn) | Số lỗi / số dòng | Nhận xét |
| --- | --- | --- |
| `Password` (secret) | 348 / 387 | Loại lớn nhất, bỏ sót nhiều nhất; mật khẩu là chuỗi tùy ý, ít dấu hiệu hình thức |
| `NTLM Token`, `Bearer Authorization` (secret) | 104 / 104 | Bỏ sót hoàn toàn; giả thuyết: bộ trích không sinh candidate cho `Authorization: Bearer <token>` |
| `URL Credentials` (secret) | 90 / 100 | Mật khẩu nhúng trong URL |
| `UUID` (không phải secret) | 205 / 1.386 | Báo nhầm UUID |
| `UUID` (secret) | 87 / 312 | Cùng loại mẫu xuất hiện ở cả hai nhãn |
| `JWK` (secret) | 47 / 76 | Khóa dạng JSON |

Ba nguyên nhân cần phân biệt: lỗi của bộ trích (dòng không có candidate), lỗi của mô hình (có candidate nhưng điểm thấp) và nhiễu nhãn (cùng loại mẫu mang cả hai nhãn). Chỉ giả thuyết về nhóm `Bearer` và `Authorization` được xem là lỗi của bộ trích; các giả thuyết khác chưa được kiểm chứng riêng.

## 8. Precision khi tỉ lệ secret ngoài đời thấp

Theo công thức Bayes `Precision(π) = π·TPR / (π·TPR + (1−π)·FPR)` với TPR và FPR đo trên validation:

| Tỉ lệ secret | Cảnh báo (≥ 0,5) | Chặn (≥ 0,8) | Chặn (≥ 0,9) |
| --- | --- | --- | --- |
| 1% | 8,9% | 16,3% | 23,7% |
| 5% | 33,9% | 50,3% | 61,8% |
| 10% | 51,9% | 68,2% | 77,4% |
| 15,9% (validation) | 64,8% | 78,5% | 85,3% |

Con số này vừa bi quan vừa lạc quan: các dòng "không phải secret" của CredData đã bị công cụ khác gắn cờ nên khó hơn dòng mã bình thường (FPR trên toàn bộ mã nhiều khả năng thấp hơn), còn tỉ lệ secret trong toàn bộ mã thấp hơn rất nhiều. Kết luận định tính vẫn vững: khi secret hiếm, phần lớn cảnh báo của bất kỳ hệ thống nào có FPR vài phần trăm sẽ là báo nhầm; vì vậy dùng hai ngưỡng và có cơ chế loại trừ có kiểm soát.

## 9. Kết quả cuối trên tập test

Chạy sau khi đã chốt mô hình và ngưỡng (không đổi sau khi xem kết quả). Theo `reports/test_access_log.txt`, tập test được chạm 2 lần, cùng ngày 18/11/2026 và cùng cấu hình: một lần cho `src.evaluate` và một lần cho `src.benchmark_tools` (mỗi lệnh chạy một lần).

```bash
python -m src.evaluate --models production --sources creddata --threshold 0.8
python -m src.benchmark_tools --model production --sources creddata --gitleaks <gitleaks.exe> --trufflehog <trufflehog.exe> --warn-threshold 0.5 --threshold 0.8
```

Tập test: 7.438 dòng, 51 repo, 22,30% là secret (validation: 15,9%). Ba phương pháp theo yêu cầu đề tài. Phương pháp 3 là pipeline đầy đủ: regex vừa là một nguồn candidate vừa là feature, entropy là feature, và mô hình ML phân loại. Hai hàng cuối là đối chứng bên ngoài.

| Phương pháp | Precision | Recall | F1 | FPR |
| --- | --- | --- | --- | --- |
| 1. Regex | 87,20% | 17,24% | 28,79% | 0,73% |
| 2. Regex và entropy | 65,38% | 1,02% | 2,02% | 0,16% |
| 3. Pipeline đầy đủ, mức cảnh báo (≥ 0,5) | 82,30% | 64,20% | 72,13% | 3,96% |
| 3. Pipeline đầy đủ, mức chặn (≥ 0,8) | 87,84% | 48,34% | 62,36% | 1,92% |
| Gitleaks 8.30.1 | 92,16% | 25,50% | 39,94% | 0,62% |
| TruffleHog 3.99.7 (không xác minh) | 38,46% | 1,21% | 2,34% | 0,55% |

ROC-AUC mức dòng: 0,8712 (khoảng tin cậy 0,8001 đến 0,9086); PR-AUC: 0,7734 (0,5578 đến 0,8525). Ở mức chặn: recall 48,34% (Wilson 45,94% đến 50,75%), FPR 1,92% (1,60% đến 2,31%).

Chênh lệch F1 của pipeline so với từng phương pháp (điểm phần trăm, khoảng tin cậy 95% bootstrap theo repo):

| So với | Mức cảnh báo | Mức chặn |
| --- | --- | --- |
| Regex | +43,34 [+24,36; +49,92] | +33,58 [−0,57; +44,04] |
| Regex và entropy | +70,11 [+50,91; +75,64] | +60,35 [+27,65; +67,47] |
| Chỉ trích candidate | +29,16 [+18,66; +41,81] | +19,39 [+3,28; +30,20] |
| Gitleaks | +32,19 [+11,94; +46,06] | +22,42 [−11,69; +38,74] |
| TruffleHog | +69,79 [+50,23; +74,91] | +60,03 [+26,96; +67,06] |

Tách theo ngữ cảnh đường dẫn (recall / FPR):

| Phương pháp | Thư mục test và mẫu (4.295 dòng, 31,20% secret) | Thư mục khác (3.143 dòng, 10,15% secret) |
| --- | --- | --- |
| Regex | 20,45% / 1,08% | 3,76% / 0,35% |
| Regex và entropy | 0,82% / 0,14% | 1,88% / 0,18% |
| Chỉ trích candidate | 95,30% / 71,61% | 91,85% / 69,48% |
| Gitleaks | 27,39% / 1,22% | 17,55% / 0,00% |
| TruffleHog | 0,60% / 0,58% | 3,76% / 0,53% |
| Pipeline cảnh báo | 64,25% / 7,38% | 63,95% / 0,39% |
| Pipeline chặn | 48,73% / 3,59% | 46,71% / 0,18% |

Ở mức chặn, precision / recall theo ngữ cảnh: thư mục test và mẫu 86,03% / 48,73%; thư mục khác 96,75% / 46,71%.

Phễu recall: 1.659 dòng secret; 1.570 dòng (94,64%) có ít nhất một candidate, tức 5,36% mất ngay ở bước trích; 802 dòng (48,34%) đạt mức chặn.

Lỗi nhiều nhất ở mức chặn (số lỗi / số dòng): `Password` 147/154; `PEM Private Key` 124/124; `UUID` (nhãn không phải secret) 104/584; `Secret` 99/144; `Token` 69/116; `Auth` 59/65.

Rule được kích hoạt nhiều nhất: Gitleaks: `generic-api-key` (335), `aws-access-token` (153), `jwt` (20); TruffleHog: `URI` (17), `Postgres` (17), `GoogleGeminiAPIKey` (7).

**Cách đọc:**

- Kết quả test không thấp hơn validation: ở mức cảnh báo, recall 64,2% (validation 56,0%) và FPR 3,96% (validation 5,75%). Không so trực tiếp precision giữa hai tập vì tỉ lệ secret khác nhau (22,3% so với 15,9%).
- Ở mức cảnh báo, pipeline vượt mọi phương pháp so sánh về F1, khoảng tin cậy không chứa 0.
- Ở mức chặn, F1 vượt Regex và Gitleaks **chưa vững**: khoảng tin cậy chứa 0 (cận dưới −0,57 và −11,69). Gitleaks vẫn có precision cao hơn (92,2% so với 87,8%) và FPR thấp hơn (0,62% so với 1,92%), nhưng recall chỉ bằng một nửa (25,5% so với 48,3%).
- Pipeline mạnh nhất ở thư mục không phải test và mẫu: recall 64,0% với FPR chỉ 0,39% ở mức cảnh báo. Ở thư mục test và mẫu FPR cao hơn nhiều (7,38%), phù hợp với việc bộ dữ liệu coi credential trong thư mục test là secret.
- `PEM Private Key` bị bỏ sót hoàn toàn (124/124), loại lỗi này không nổi bật ở validation. Giả thuyết (chưa kiểm chứng): khóa PEM nhiều dòng, còn bộ trích chỉ thấy từng dòng nên không sinh được candidate hữu ích.
- TruffleHog bị thiệt do thiết lập đo (tắt xác minh, chỉ thấy một dòng). So sánh vẫn thiên về pipeline vì mô hình được huấn luyện trên phân phối CredData.

## 10. Thời gian xử lý

Đo bằng `python -m src.measure_time` (không chạm test; đo trên tập validation, 5.000 dòng). Thời gian phụ thuộc máy nên ghi cấu hình: CPU Intel64 Family 6 Model 186 Stepping 2 (GenuineIntel), 16 luồng logic, RAM 16 GB, Windows 11 (10.0.26200), Python 3.14.0; trung vị của 3 lần chạy.

**Tiêu chí (NFR6), đặt trước khi đo:** một lần commit điển hình (tối đa 20 file, mỗi file khoảng 200 dòng) hoàn tất bước quét trong không quá 5 giây.

```bash
python -m src.measure_time --model production --gitleaks <gitleaks.exe> --trufflehog <trufflehog.exe>
# đo trên repo thật (nên là bản clone mới, không có node_modules, giống môi trường CI):
python -m src.measure_time --model production --repo-path <thư mục repo> --gitleaks <gitleaks.exe> --trufflehog <trufflehog.exe>
```

Hai lệnh trên được chạy riêng, nên bảng dưới ghi hai lần đo:

- **Lần A:** repo mẫu tự dựng (20 file, khoảng 200 dòng mỗi file).
- **Lần B:** `--repo-path D:\Test\SecretGuard`.

Hai lần cho kết quả lệch nhau khoảng 2 lần dù cùng code và cùng dữ liệu, nên số tuyệt đối chỉ có ý nghĩa như một khoảng, không phải một giá trị chính xác.

### 10.1 Thông lượng (cùng 5.000 dòng)

| Phương pháp | Lần A: ms / 1.000 dòng | Lần A: dòng / giây | Lần B: ms / 1.000 dòng | Lần B: dòng / giây |
| --- | --- | --- | --- | --- |
| Regex | 42,0 | 23.807 | 22,1 | 45.168 |
| Regex và entropy | 44,4 | 22.500 | 22,1 | 45.334 |
| Chỉ trích candidate | 103,1 | 9.699 | 57,0 | 17.530 |
| Pipeline ML đầy đủ | 449,9 | 2.223 | 235,2 | 4.252 |

Pipeline ML chậm hơn Regex khoảng 10,6 đến 10,7 lần ở cả hai lần đo.

### 10.2 Phân rã pipeline ML

| Giai đoạn | Lần A: ms (tỉ lệ) | Lần B: ms (tỉ lệ) |
| --- | --- | --- |
| Trích candidate | 580 (26,3%) | 325 (28,9%) |
| Tính feature | 1.263 (57,4%) | 618 (55,0%) |
| Dựng bảng | 109 (4,9%) | 38 (3,4%) |
| Dự đoán (mô hình) | 250 (11,3%) | 142 (12,7%) |

Có 6.040 candidate (trung bình 1,21 candidate mỗi dòng); kết quả khớp với `scoring.score_lines`. Giai đoạn chiếm nhiều thời gian nhất là tính feature (55% đến 57%).

### 10.3 Độ trễ thực tế

| Phép đo | Lần A | Lần B |
| --- | --- | --- |
| Quét một file 200 dòng (trung vị / p95) | 160,0 ms / 219,4 ms | 80,9 ms / 88,9 ms |
| Nạp mô hình | 144 ms | 73 ms |
| `main.py` từ đầu đến cuối (gồm khởi động Python và nạp mô hình) | 7,82 s (20 file, khoảng 200 dòng mỗi file) | 5,27 s (`D:\Test\SecretGuard`, 79 file, 3.330 dòng) |
| Gitleaks 8.30.1 trên cùng thư mục | 61,71 s | 403,46 s |
| TruffleHog 3.99.7 (không xác minh) trên cùng thư mục | 2,07 s | 9,96 s |
| Một lần `git commit` thực tế có hook (trung vị 3 lần) | 2,43 s (3,11 / 2,43 / 2,19 s; 20 file, 4.020 dòng) | không áp dụng |

Kết luận: **đạt tiêu chí 5 giây** trên phép đo sát tiêu chí nhất: một lần `git commit` có hook với 20 file, 4.020 dòng mất trung vị 2,43 s (khoảng 2,19 đến 3,11 s). Số này gồm khởi động Python, nạp mô hình, quét và một lần gọi backend. Cần đọc kèm các hạn chế sau:

- Các file mẫu là mã đơn giản (`x_1 = 1  # dòng mẫu`) nên ít candidate; file thật có nhiều chuỗi nghi vấn hơn sẽ tốn thời gian tính feature và dự đoán hơn, nên 2,43 s có thể lạc quan.
- Chỉ đo ba lần trên một máy; lần đầu chậm hơn các lần sau (3,11 s so với 2,19 s).
- Backend chạy cục bộ (nếu không, thời gian gọi mạng, tối đa 5 s theo timeout, sẽ cộng thêm).
- `main.py` end-to-end đo bằng `measure_time` cho 5,27 đến 7,82 s và chưa giải thích được chênh lệch với số trên. Nếu lấy số này làm chuẩn thì không đạt, nên báo cáo cần nêu cả hai.

Gitleaks và TruffleHog là chương trình biên dịch sẵn (Go), còn pipeline của đề tài chạy trên Python nên phải trả thêm chi phí khởi động trình thông dịch và nạp mô hình; cần nêu điều này khi so sánh.

Số của Gitleaks (61,71 s và 403,46 s) chậm bất thường so với TruffleHog trên cùng thư mục. Nguyên nhân chưa được xác định (có thể do dùng bản x32, quét lịch sử git hoặc phần mềm diệt virus). Ở lần B, các công cụ không quét cùng tập file với `main.py`: `main.py` loại `venv`, `secret-detector`, `node_modules`, `data` và chỉ quét 79 file, còn Gitleaks và TruffleHog quét thư mục theo cấu hình riêng của chúng, có thể gồm cả `venv`. Vì vậy các số end-to-end của lần B không so sánh trực tiếp được giữa ba công cụ, và không dùng hai số Gitleaks để kết luận Gitleaks chậm hơn pipeline; cần đo lại trên bản clone sạch.

Khi chạy mô hình có cảnh báo `InconsistentVersionWarning`: mô hình được lưu bằng scikit-learn 1.9.0 nhưng môi trường đo dùng 1.9.1. Nên ghim đúng phiên bản trong `requirements.txt` hoặc huấn luyện lại để tránh sai khác.

## 11. Tái lập

Xem mục "Tái lập thực nghiệm" trong [README](../README.md). Mỗi mô hình có `models/experiments/<tên>/model_card.json` (thời điểm huấn luyện, số mẫu, tỉ lệ lớp, chỉ số validation, các feature quan trọng, định nghĩa nhãn); thư viện được ghim trong `secret-detector/requirements.txt`.

## 12. Các yếu tố có thể ảnh hưởng đến tính hợp lệ

### Về cách đánh giá

- Validation đã dùng nhiều lần (hai vòng feature, chọn mô hình, chọn ngưỡng) nên có thể lạc quan. Tập test là bằng chứng độc lập và chỉ được chạm 2 lần, cùng ngày và cùng cấu hình (mô hình, ngưỡng 0,5 và 0,8 đã chốt trước), theo `reports/test_access_log.txt`. Kết quả test không thấp hơn validation, nên không thấy dấu hiệu validation lạc quan rõ rệt. Điều này chưa chứng minh mô hình ổn định trên dữ liệu khác với CredData.
- Validation và test khác nhau về phân phối: tỉ lệ secret là 15,9% và 22,3%; tỉ lệ dòng thuộc thư mục test và mẫu là 27,4% (3.220/11.775) và 57,7% (4.295/7.438). Precision và F1 phụ thuộc tỉ lệ secret nên không so trực tiếp giữa hai tập; recall và FPR so sánh được tốt hơn, nhưng cũng bị ảnh hưởng bởi tỉ lệ dòng thuộc thư mục test và mẫu.
- Độ không đồng đều giữa các repo làm khoảng tin cậy rộng (test: ROC-AUC 0,80 đến 0,91; PR-AUC 0,56 đến 0,85 với 51 repo). Ở mức chặn, chênh lệch F1 so với Regex và Gitleaks có khoảng tin cậy chứa 0 nên chưa kết luận được.

### Về tính công bằng của so sánh

- So sánh thiên về pipeline: mô hình huấn luyện trên chính phân phối CredData, còn Gitleaks và TruffleHog thì không.
- TruffleHog bị thiệt do thiết lập đo: tắt xác minh bằng API và chỉ thấy một dòng thay vì cả file.
- Chỉ một dòng ngữ cảnh: cả pipeline và các công cụ đối chứng chỉ thấy từng dòng. Điều này đặc biệt bất lợi với khóa nhiều dòng như PEM.

### Về dữ liệu

- CredData chỉ gồm các dòng nghi vấn đã được công cụ gắn cờ, giá trị đã làm mờ, nhãn có thể nhiễu (cùng loại mẫu như UUID mang cả hai nhãn). Quy tắc "credential trong thư mục test là secret" là lựa chọn của bộ dữ liệu và làm FPR ở thư mục test và mẫu cao hơn hẳn (7,38% so với 0,39% ở mức cảnh báo).
- Các dòng "không phải secret" đã bị công cụ khác gắn cờ nên khó hơn mã bình thường; ngược lại, tỉ lệ secret trong mã thật thấp hơn nhiều. Vì vậy precision ngoài đời có thể khác xa số đo (xem mục 8).

### Về mô hình và lỗi

- Hiệu chỉnh xác suất bị ảnh hưởng bởi lệch tỉ lệ lớp giữa các repo. Độ tin cậy của điểm (mục 6) chỉ được đo trên validation, chưa đo lại trên test.
- Bộ trích candidate làm mất 5,36% dòng secret trên test (11,4% trên validation) trước khi đến mô hình, nên đây là trần của recall.
- Loại lỗi `PEM Private Key` (bỏ sót 124/124 ở test) không nổi bật ở validation. Giả thuyết về khóa nhiều dòng chưa được kiểm chứng riêng, nên không nên xem là nguyên nhân đã xác nhận.
- `main.py` loại cứng các thư mục tên `data`, `build`, `dist`, `venv`, `secret-detector`...; mã thật nằm trong thư mục có tên như vậy sẽ không được quét và bị bỏ sót im lặng.

### Chưa đo

- Độ dao động giữa các lần huấn luyện với seed khác nhau.
- Hiệu năng khi quét lịch sử commit.
- Hiệu quả ở quy mô một tổ chức.
- Thời gian xử lý trên mã thật có nhiều candidate, và độ dao động ngoài ba lần đo.
