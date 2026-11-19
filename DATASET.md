# Mô tả dữ liệu

Tài liệu này ghi rõ nguồn gốc, cấu trúc, cách gán nhãn, cách chia và các hạn chế của dữ liệu dùng trong đề tài. Các mục đánh dấu 【...】 là thông tin chỉ có được sau khi chạy lệnh tương ứng trên máy của tác giả.

## 1. Tổng quan

| Nguồn | Vai trò | Quy mô | Có dùng làm bằng chứng chất lượng? |
| --- | --- | --- | --- |
| **CredData** (Samsung) | Huấn luyện, chọn mô hình, chọn ngưỡng, đánh giá cuối | 64.326 dòng, 335 repo | Có |
| **Dữ liệu tổng hợp** (tự sinh) | Kiểm tra quy trình; đo khoảng cách giữa dữ liệu giả và dữ liệu thật | 4.152 mẫu, 80 repo giả lập | **Không** |

Lý do không dùng dữ liệu tổng hợp làm bằng chứng: mô hình huấn luyện trên nó đạt gần 100% trên chính nó nhưng chỉ đạt ROC-AUC 0,491 (ngang đoán bừa) trên dữ liệu thật.

## 2. Nguồn gốc và điều kiện sử dụng

### CredData

- **Nguồn:** <https://github.com/Samsung/CredData> (bộ dữ liệu credential trong mã nguồn mở, kèm nhãn do người duyệt gán).
- **Cách lấy:** chạy `download_data.py` của CredData (trên Linux/WSL) để tải các repo nguồn và dựng thư mục `data/` cùng `meta/`. Đề tài dùng thư mục `meta/*.csv` (nhãn và vị trí) và các file mã nguồn đã dựng lại.
- **Phiên bản đã dùng:** commit `c49ed10629d9139eb88b71b6b7ab4054fff806ea` ; ngày tải 25/10/2026.
- **Làm mờ:** theo tài liệu của CredData, giá trị credential trong dữ liệu đã được thay bằng giá trị ngẫu nhiên cùng bộ ký tự và độ dài (hoặc giá trị ví dụ với các định dạng cố định như khóa AWS). Vì vậy dữ liệu không chứa credential thật để dùng, nhưng một số đặc trưng trên giá trị có thể lệch so với khóa thật.
- **Giấy phép:** xem tệp `LICENSE` của CredData; mã nguồn trong dữ liệu thuộc giấy phép của từng dự án gốc, và tài liệu của CredData cho biết các repo đã được lọc theo giấy phép.

### Dữ liệu tổng hợp

Do tác giả sinh bằng `src/build_dataset.py` (seed cố định 42), không lấy từ nguồn bên ngoài.

### Nguyên tắc xử lý

- Không thử dùng hoặc xác minh bất kỳ chuỗi nào trong dữ liệu bằng cách gọi API thật. TruffleHog luôn chạy với `--no-verification`.
- Không commit `data/external/`, `data/features/` và `reports/` lên Git (chứa nội dung mã nguồn của các dự án khác).
- Báo cáo và file lỗi chỉ lưu chỉ số dòng, nhãn, loại và dự đoán; nội dung dòng được che.

## 3. Cấu trúc dữ liệu

### `data/external/creddata.csv` (do `import_external.py` sinh)

| Cột | Ý nghĩa |
| --- | --- |
| `text` | Dòng mã nguồn đầy đủ (đã `strip`, cắt tối đa 1.500 ký tự) |
| `label` | 1 nếu nhãn gốc là T, ngược lại 0 (F và X) |
| `type` | Category gốc của CredData (ví dụ `Password`, `Key`, `UUID`) |
| `repo` | Mã băm định danh repo (CredData đã làm mờ tên repo) |
| `file_path` | Đường dẫn trong repo, đã bỏ tiền tố `data/<repo>/` (ví dụ `test/ab12cd34.py`) |
| `gt` | Nhãn gốc T, F hoặc X |
| `value` | Giá trị credential theo `ValueStart:ValueEnd` (rỗng nếu không có hoặc nhiều dòng) |
| `multiline` | 1 nếu credential trải nhiều dòng (khi đó `text` chỉ là dòng đầu) |
| `split` | `train`, `val` hoặc `test`; chia theo repo |

### `data/train.csv`, `val.csv`, `test.csv` (dữ liệu tổng hợp)

Các cột `text`, `label`, `type`, `repo`, `file_path`.

### `data/features/<nguồn>_<tập>.csv` (do `build_features.py` sinh)

Mỗi hàng là **một candidate** (không phải một dòng): 36 cột feature và các cột meta `label`, `_original_type`, `_repo`, `_line_id`, `_source`. Các cột meta không đưa vào mô hình. Cột loại mẫu gốc **không** được dùng làm feature vì nó gần như là đáp án (xem mục 9).

## 4. Nhãn

| Nhãn gốc CredData | Ý nghĩa | Nhãn của đề tài |
| --- | --- | --- |
| T | Trông giống credential thật | 1 |
| F | Dương tính giả | 0 |
| X | Giá trị thử nghiệm, ví dụ hoặc placeholder | 0 |

**Quy tắc quan trọng của CredData:** mọi credential nằm trong thư mục test đều được gán nhãn T. Điều này khiến tỉ lệ secret ở thư mục `test` rất cao (37,1%) so với `src` (8,8%), và là lý do dữ liệu tổng hợp (nơi giá trị giả trong thư mục test bị coi là *không* phải secret) mâu thuẫn với CredData.

Khi nhiều công cụ cùng đánh dấu một dòng, các bản ghi trùng vị trí được gộp với thứ tự ưu tiên T trước, rồi X, rồi F.

## 5. Thống kê CredData

### Toàn bộ

| Mục | Giá trị |
| --- | --- |
| Số file `meta` đọc được | 335 |
| Dòng có nhãn sau khi gộp trùng vị trí | 64.438 (đã gộp 3.082 dòng trùng) |
| Dòng bị loại (giá trị nằm ngoài phần cắt của dòng quá dài: 109; độ lệch vượt độ dài dòng: 3) | 112 |
| **Dòng giữ lại** | **64.326** |
| Nhãn T / F / X | 15.138 (23,5%) / 45.143 / 4.045 |
| Dòng nhiều dòng | 1.348 |
| Dòng T có vị trí giá trị hợp lệ | 13.776 / 15.138 |

### Theo thư mục đầu của đường dẫn (10 thư mục lớn nhất)

| Thư mục | Không phải secret | Secret | Tỉ lệ secret |
| --- | --- | --- | --- |
| `test` | 17.576 | 10.375 | 37,1% |
| `src` | 10.231 | 986 | 8,8% |
| `_` | 6.467 | 984 | 13,2% |
| `lang` | 1.841 | 0 | 0,0% |
| `lib` | 1.492 | 71 | 4,5% |
| `docs` | 1.265 | 453 | 26,4% |
| `example` | 1.173 | 439 | 27,2% |
| `spec` | 1.170 | 386 | 24,8% |
| `vendor` | 1.131 | 89 | 7,3% |
| `conf` | 877 | 265 | 23,2% |

Thư mục `lang` có 1.841 dòng và không dòng nào là secret: đó là các chuỗi giao diện chứa chữ “password”.

### Mức candidate (đầu vào của mô hình)

| Tập | Dòng | Dòng T | T không sinh được candidate | T có candidate nhưng không phủ giá trị | T bị bỏ qua (không biết giá trị) | Candidate | Candidate là secret |
| --- | --- | --- | --- | --- | --- | --- | --- |
| train | 45.113 | 11.606 | 1.215 | 277 | 247 | 44.040 | 9.867 |
| val | 11.775 | 1.873 | 213 | 77 | 73 | 14.151 | 1.510 |
| test | 7.438 | 1.659 | 89 | 64 | 137 | 9.907 | 1.369 |

Trên tập train, bộ trích candidate phủ 93,7% giá trị thật (9.867/10.529 dòng T có vị trí giá trị) và 89,5% dòng secret có ít nhất một candidate.

## 6. Cách chia và kiểm tra overlap

**Chia theo repository, không theo dòng.** Các dòng cùng repo không độc lập; chia theo dòng làm rò rỉ thông tin sang tập test. Hai bước `GroupShuffleSplit` (70% train, rồi chia đôi phần còn lại thành validation và test), thử nhiều seed cho tới khi validation và test đều chiếm 10 đến 20% số dòng và chứa ít nhất 10% số dòng T. Seed được chọn: 45.

| Tập | Số dòng | Số repo | Tỉ lệ dòng secret |
| --- | --- | --- | --- |
| Train | 45.113 | 234 | 25,7% |
| Validation | 11.775 | 50 | 15,9% |
| Test | 7.438 | 51 | 22,3% |

Tỉ lệ secret giữa các tập khác nhau vì các repo rất không đồng đều; repo lớn nhất chiếm 15% tổng số dòng.

### Kiểm tra overlap

Chạy `python -m src.check_dataset`. Kết quả (nguồn CredData, đã lưu tại `reports/dataset_check.json`):

| Kiểm tra | Kết quả |
| --- | --- |
| Overlap repo giữa mọi cặp tập (phải bằng 0) | 0 (train-val = 0, train-test = 0, val-test = 0); đã xác nhận bằng `check_dataset`, kết quả lưu ở `reports/dataset_check.json` |
| Số dòng val có văn bản trùng một dòng của train | 322 dòng (2,7% số dòng val), thuộc 133 văn bản duy nhất |
| Số dòng test có văn bản trùng một dòng của train | 551 dòng (7,4% số dòng test), thuộc 200 văn bản duy nhất; **vượt ngưỡng cảnh báo 5%** |
| Số trường hợp cùng văn bản nhưng khác nhãn | 98 văn bản xuất hiện với cả hai nhãn trong toàn bộ dữ liệu (trong đó có 2 văn bản khác nhãn ở cặp train→test và 2 ở cặp val→test; không có ở train→val) |

Chia theo repo bảo đảm không trùng repo nhưng **không** bảo đảm không trùng dòng: nhiều dòng mẫu (cấu hình mặc định, chú thích) lặp lại giữa các dự án. Với CredData, 551/7.438 dòng test (7,4%) có văn bản trùng một dòng của train, vượt ngưỡng cảnh báo 5%, nên kết quả trên tập test đã loại các dòng trùng được báo cáo bổ sung và nêu trong phần hạn chế. Trùng nội bộ trong từng tập cũng cao (khoảng 35 đến 38% số dòng).

Với CredData, 7,4% dòng test trùng văn bản với train (551/7.438), vượt ngưỡng 5%, nên báo cáo bổ sung kết quả trên tập test đã loại các dòng trùng và nêu rõ trong phần hạn chế. Ngoài ra, trùng nội bộ trong từng tập cũng cao (khoảng 35 đến 38% số dòng), cho thấy nhiều dòng lặp lại giữa các dự án.

## 7. Dữ liệu tổng hợp

Gồm 4.152 mẫu: 2.948 train, 602 validation, 602 test; 80 repo giả lập chia theo repo; 56, 12 và 12 repo cho ba tập; tỉ lệ secret 37,1%, 42,4% và 41,5%.

| Nhãn | Nhóm mẫu | Số mẫu |
| --- | --- | --- |
| Secret | Khóa AWS (`AKIA...`, dùng bảng ký tự A–Z và 2–7 như khóa thật) | 300 |
| Secret | Secret chung (`const API_SECRET = '...'`) | 400 |
| Secret | Token Slack (định dạng hiện đại) | 300 |
| Secret | Token GitHub (`ghp_...`) | 200 |
| Secret | Secret không theo định dạng biết trước (`INTERNAL_TOKEN`, `DB_PASSWORD`, hex hoặc base64 ngẫu nhiên) | 400 |
| Không | Hash Git / SHA1 | 250 |
| Không | Checksum SHA256 | 150 |
| Không | UUID | 200 |
| Không | Base64 của văn bản thường | 200 |
| Không | Placeholder (`your_api_key_here`...) | 300 |
| Không | Khóa mẫu trong tài liệu (`AKIA...EXAMPLE`) | 152 |
| Không | Giá trị giả trong file test (`fake_`, `mock_`...) | 300 |
| Không | Code thường, URL, markdown, SQL | 1.000 |

**Các lỗi đã phát hiện và sửa trong bộ sinh dữ liệu** (để người đọc biết vì sao không tin dữ liệu này):

1. Phiên bản đầu lặp lại nhiều chuỗi y hệt rồi chia theo dòng, nên cùng một dòng nằm ở cả train và test. Đã chuyển sang mẫu có phần ngẫu nhiên, loại trùng, chia theo repo.
2. Khóa AWS tổng hợp dùng đủ mười chữ số trong khi ID khóa AWS thật chỉ dùng `A–Z` và `2–7`; chỉ 7/48 khóa khớp regex của Gitleaks. Token Slack dùng định dạng cũ. Cả hai đã được sửa theo định dạng thật.

## 8. Tái lập

```bash
python -m src.build_dataset                                          # dữ liệu tổng hợp
python -m src.import_external --creddata-dir <đường dẫn CredData>   # CredData
python -m src.check_dataset                                          # kiểm tra overlap
python -m src.build_features                                         # feature mức candidate
```

## 9. Hạn chế của dữ liệu

- **Chỉ gồm dòng nghi vấn.** CredData chứa các dòng đã bị công cụ gắn cờ rồi được người duyệt; không phải mọi dòng của repo. Tỉ lệ secret (~23%) và độ khó của các dòng không phải secret không đại diện cho toàn bộ mã nguồn.
- **Định nghĩa nhãn đặc thù.** Credential trong thư mục test luôn là T. Công cụ khác có thể coi chúng là không đáng báo.
- **Giá trị đã làm mờ**, nhãn có thể nhiễu, và một số loại mẫu (ví dụ `UUID`) xuất hiện ở cả hai nhãn.
- **Rò rỉ nhãn qua cột loại.** Cột `type` gốc gần như là đáp án nên bị loại khỏi feature; loại regex được tính lại bằng chính bộ quét lúc suy luận.
- **Không đồng đều giữa các repo.** Repo lớn nhất chiếm 15% số dòng; tỉ lệ secret giữa các tập khác nhau; khoảng tin cậy vì thế khá rộng.
- **Chỉ một dòng ngữ cảnh.** Credential trải nhiều dòng chỉ được biểu diễn bằng dòng đầu; 137 dòng T trong tập test không có vị trí giá trị nên không dùng để huấn luyện (vẫn được tính ở bước đánh giá cấp dòng).
