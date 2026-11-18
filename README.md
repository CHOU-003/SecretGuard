# SecretGuard 🔐

Hệ thống **tự động phát hiện và ngăn chặn rò rỉ secret** (API key, token, mật khẩu, khóa riêng tư, chuỗi kết nối...) trong mã nguồn **trước khi triển khai** theo hướng DevSecOps: chặn ngay ở Git hook, chặn lại ở CI, và chỉ cho phép deploy khi bước quét thành công.

## Mục lục

- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Kết quả chính](#kết-quả-chính)
- [Công nghệ sử dụng](#công-nghệ-sử-dụng)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Cài đặt](#cài-đặt)
- [Cấu hình môi trường](#cấu-hình-môi-trường)
- [Chạy dự án](#chạy-dự-án)
- [CI/CD](#cicd)
- [Tái lập thực nghiệm](#tái-lập-thực-nghiệm)
- [Dữ liệu](#dữ-liệu)
- [Tính năng và hạn chế](#tính-năng-và-hạn-chế)
- [Tài liệu](#tài-liệu)

## Kiến trúc hệ thống

```bash
 Lập trình viên                      GitHub
      │ git commit                      │ push / pull request
      ▼                                 ▼
 Hook pre-commit               GitHub Actions: secret-scan ──(needs)──► deploy ──► EC2 (Nginx + PM2)
      │                                 │
      └──────────────┬──────────────────┘
                     ▼
   Scanning Engine (Python)
   dòng mã → trích candidate → 36 feature → XGBoost đã hiệu chỉnh → điểm của dòng
                     │
                     ├── điểm ≥ 0,8 ──► ⛔ CHẶN (mã thoát 1: hủy commit / làm job CI thất bại)
                     ├── điểm ≥ 0,5 ──► ⚠️ CẢNH BÁO
                     ▼
   POST /api/scans (header x-api-key) ──► Backend (Node.js + Express) ──► SQL Server
                                                  │
                                                  ▼ (JWT)
                                      Frontend (React): dashboard
```

**Nguyên tắc thiết kế.** Quyết định chặn luôn do Scanning Engine đưa ra tại chỗ, không phụ thuộc backend hay mạng. Backend chỉ ghi nhận lịch sử và phục vụ dashboard. Hook cục bộ có thể bị bỏ qua bằng `git commit --no-verify`, nên điểm chặn bắt buộc là bước `secret-scan` trong CI kết hợp branch protection.

## Kết quả chính

Đánh giá ở mức **dòng mã** trên CredData (dữ liệu thật), chia theo repository. Số liệu **validation** (dùng để chọn mô hình và ngưỡng); số liệu **test** điền sau khi chạy đánh giá cuối.

|Phương pháp|Precision|Recall|F1|FPR|
|---|---|---|---|---|
|Regex|73,9%|8,9%|15,9%|0,60%|
|Gitleaks 8.30.1|89,6%|20,7%|33,6%|0,45%|
|TruffleHog 3.99.7 (không xác minh)|24,7%|1,1%|2,2%|0,65%|
|**SecretGuard, mức cảnh báo (≥ 0,5)**|64,8%|56,0%|60,1%|5,75%|
|**SecretGuard, mức chặn (≥ 0,8)**|78,5%|36,4%|49,7%|1,89%|

Số liệu test: 【TEST: điền từ `reports/production/evaluation_report.md` và `reports/tool_benchmark.md`】.

Đọc kết quả một cách thận trọng: Gitleaks chính xác hơn nhưng bắt ít hơn nhiều; mô hình được huấn luyện trên cùng phân phối dữ liệu còn hai công cụ kia thì không; TruffleHog bị tắt bước xác minh. Chi tiết và các hạn chế ở [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).

## Công nghệ sử dụng

|Thành phần|Công nghệ|
|---|---|
|Scanning Engine|Python; scikit-learn, XGBoost, pandas, joblib; regex và entropy Shannon|
|Backend API|Node.js + Express; gói `mssql`|
|Database|SQL Server|
|Frontend|React + Vite|
|Authentication|JWT (access token) + refresh token cho quản trị viên; API key riêng cho engine|
|CI/CD|GitHub Actions|
|Triển khai|AWS EC2 (Ubuntu) + Nginx + PM2|

## Cấu trúc thư mục

```bash
secret-guard/
├── .github/workflows/         devsecops-ci.yml: secret-scan, rồi deploy (needs: secret-scan)
├── backend/                   REST API (Node.js + Express), schema SQL
├── frontend/                  Dashboard quản trị (React)
├── deploy/                    secretguard-nginx.conf, setup.sh (dựng máy chủ EC2)
├── docs/                      DATASET.md, EXPERIMENTS.md, CI_CD_DEMO.md
├── .secretguardignore         (tùy chọn) file/thư mục được loại khỏi quét
└── secret-detector/           Scanning Engine
    ├── main.py                điểm vào của hook và CI
    ├── install_hook.py        cài Git hook pre-commit
    ├── requirements.txt       thư viện đã ghim phiên bản
    ├── models/                secret_ml_model.pkl, feature_columns.pkl, model_card.json
    │   └── experiments/       các thí nghiệm huấn luyện (không commit)
    ├── data/                  dữ liệu tổng hợp; external/ (CredData) và features/ không commit
    ├── reports/               kết quả đánh giá (không commit)
    └── src/
        ├── regex_scanner.py, entropy_scanner.py     thuật toán nền, dùng làm đối chứng
        ├── candidate.py                              trích candidate (4 nguồn)
        ├── feature_extractor.py                      36 feature
        ├── scoring.py                                chấm điểm cấp dòng, dùng chung
        ├── build_dataset.py, import_external.py      dữ liệu tổng hợp, nạp CredData
        ├── check_dataset.py                          kiểm tra overlap dữ liệu
        ├── build_features.py, train_ml.py            trích feature, huấn luyện
        └── evaluate.py, benchmark_tools.py, measure_time.py   đánh giá, so sánh, đo thời gian
```

## Cài đặt

### Yêu cầu hệ thống

- Python (dùng **cùng phiên bản** với phiên bản đã huấn luyện mô hình; xem `models/model_card.json` và `requirements.txt`, vì mô hình lưu bằng pickle gắn với phiên bản thư viện)
- Node.js 18+ (khuyến nghị 20)
- SQL Server 2019+ (bật **Mixed Mode Authentication** và **TCP/IP**)
- Git

### 1. Clone repository

```bash
git clone <repo-url>
cd secret-guard
```

### 2. Scanning Engine

```bash
cd secret-detector
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux, macOS
pip install -r requirements.txt
```

### 3. Backend

```bash
cd backend
npm install
```

### 4. Frontend

```bash
cd frontend
npm install
```

### 5. Cơ sở dữ liệu

Chạy file `schema.sql` (trong `backend/`) trên SQL Server để tạo các bảng: `projects`, `scans`, `findings`, `audit_log`, `users`, `refresh_tokens`.

## Cấu hình môi trường

Không commit các file `.env`. Dùng giá trị ngẫu nhiên riêng, **không dùng lại giá trị trong ví dụ**.

`backend/.env`:

```dotenv
DB_USER=secretguard_app
DB_PASSWORD=<mật khẩu SQL Server>
DB_SERVER=127.0.0.1
DB_NAME=SecretGuardDB
DB_PORT=1433

PORT=3000
JWT_ACCESS_SECRET=<chuỗi ngẫu nhiên>
JWT_REFRESH_SECRET=<chuỗi ngẫu nhiên khác>
JWT_ACCESS_EXPIRES=15m
JWT_REFRESH_EXPIRES_DAYS=7
SERVICE_API_KEY=<chuỗi ngẫu nhiên, dùng chung với engine>
FRONTEND_URL=http://localhost:5173
```

`secret-detector/.env` (để engine ghi kết quả về backend):

```dotenv
BACKEND_URL=http://localhost:3000
SERVICE_API_KEY=<cùng giá trị với backend>
```

Tạo chuỗi ngẫu nhiên: `python -c "import secrets; print(secrets.token_hex(32))"`.

## Chạy dự án

### Backend và frontend

```bash
cd backend && npm run dev
cd frontend && npm run dev
```

### Cài Git hook pre-commit (chặn secret tại máy lập trình viên)

```bash
python secret-detector/install_hook.py
```

Hook nằm trong `.git/hooks` nên không được Git theo dõi; **mỗi máy chạy lệnh này một lần**. Hook gọi Python của `secret-detector/venv`, hủy commit khi có phát hiện vượt ngưỡng chặn, và nói rõ lý do (mã 1: bị chặn; mã 2: engine lỗi). Gỡ hook: `python secret-detector/install_hook.py --uninstall`.

### Quét thủ công

```bash
# quét các file đã git add (như hook)
python secret-detector/main.py --path . --mode staged --no-report

# quét toàn bộ cây thư mục (như CI)
python secret-detector/main.py --path . --mode full --no-report
```

|Tham số|Ý nghĩa|
|---|---|
|`--warn-threshold`|Ngưỡng cảnh báo (mặc định 0,5)|
|`--threshold`|Ngưỡng chặn (mặc định 0,8)|
|`--no-report`|Không gửi kết quả về backend|
|`--model|`production` (mặc định) hoặc tên thí nghiệm trong `models/experiments/`|

Mã thoát: `0` cho qua, `1` bị chặn, `2` lỗi của engine. Giá trị secret luôn bị che khi in (ví dụ `AK***(20)`).

### Loại trừ có kiểm soát

- Thêm `# secretguard:ignore` vào cuối dòng cần bỏ qua.
- Hoặc liệt kê đường dẫn/mẫu glob trong `.secretguardignore` ở gốc repo (mỗi dòng một mục; `#` là chú thích; mục kết thúc bằng `/` loại cả thư mục).

Số dòng và số file bị loại luôn được in ra để việc lạm dụng không bị che giấu.

## CI/CD

Workflow `.github/workflows/devsecops-ci.yml`:

1. **`secret-scan`**: chạy ở mọi push và pull request vào `develop` và `main`; quét toàn repo (`--mode full`), thất bại khi có phát hiện vượt ngưỡng chặn.
2. **`deploy`**: `needs: secret-scan`, chỉ chạy khi push lên `main`; đồng bộ mã lên EC2, dựng frontend, khởi động lại backend bằng PM2.

Cần cấu hình trên GitHub: secrets `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`, `SERVICE_API_KEY`; variable `BACKEND_URL`; và **branch protection yêu cầu check `secret-scan` thành công** (không có bước này thì ai cũng merge được dù scan đỏ). Hướng dẫn từng bước và cách demo: [docs/CI_CD_DEMO.md](docs/CI_CD_DEMO.md).

## Tái lập thực nghiệm

Chạy trong `secret-detector`, theo thứ tự. Chi tiết và cách diễn giải: [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).

```bash
python -m src.build_dataset                                   # dữ liệu tổng hợp (chỉ để kiểm tra quy trình)
python -m src.import_external --creddata-dir <đường dẫn CredData>
python -m src.check_dataset                                   # kiểm tra overlap
python -m src.build_features
python -m src.train_ml --train-on creddata --tag creddata_v2
python -m src.evaluate --models creddata_v2 --split val --sources creddata    # chọn ngưỡng trên validation
python -m src.train_ml --promote creddata_v2
python -m src.measure_time                                    # thời gian xử lý
# đánh giá cuối trên test: mỗi lệnh chạy MỘT lần, sau khi đã chốt mô hình và ngưỡng
python -m src.evaluate --models production --sources creddata --threshold 0.8
python -m src.benchmark_tools --model production --sources creddata --gitleaks <gitleaks.exe> --trufflehog <trufflehog.exe> --warn-threshold 0.5 --threshold 0.8
```

Mỗi lần chạm tập test được ghi vào `reports/test_access_log.txt`. Seed cố định là 42; mỗi mô hình có `model_card.json`.

## Dữ liệu

- **CredData** (Samsung, dữ liệu thật): các dòng mã nguồn nghi vấn từ các dự án mã nguồn mở, do người duyệt gán nhãn; giá trị credential đã được làm mờ. Dùng để huấn luyện và đánh giá. Chia theo repository.
- **Dữ liệu tổng hợp** do tác giả sinh: chỉ dùng để kiểm tra quy trình; mô hình học từ nó không áp dụng được cho dữ liệu thật.

Nguồn gốc, schema, thống kê, cách chia và kiểm tra overlap: [docs/DATASET.md](docs/DATASET.md). **Không commit** `data/external/`, `data/features/` và `reports/` (chứa nội dung mã nguồn của các dự án khác), và không gọi API thật bằng bất kỳ khóa nào tìm thấy trong dữ liệu.

`.gitignore` khuyến nghị: `.env`, `secret-detector/venv/`, `secret-detector/data/external/`, `secret-detector/data/features/`, `secret-detector/reports/`, `secret-detector/models/experiments/`.

## Tính năng và hạn chế

### Đã hoàn thành

- [x] Scanning Engine: trích candidate, 36 feature, XGBoost đã hiệu chỉnh xác suất, điểm cấp dòng
- [x] Git hook pre-commit (đọc nội dung staged) và script cài đặt
- [x] Bước quét CI (`--mode full`), cổng chặn deploy (`needs`)
- [x] Backend ↔ SQL Server; API ghi nhận và truy vấn lịch sử quét; xác thực JWT (quản trị viên) và API key (engine)
- [x] Dashboard: tổng quan theo trạng thái và lịch sử quét
- [x] Cơ chế loại trừ có kiểm soát, che giá trị secret khi in
- [x] Bộ công cụ dữ liệu, huấn luyện, đánh giá, so sánh với Gitleaks và TruffleHog, đo thời gian

### Chưa làm

- [ ] Dashboard: biểu đồ, audit log, quản lý project và cấu hình ngưỡng, duyệt hoặc đánh dấu báo nhầm
- [ ] Quét lịch sử commit
- [ ] Vòng phản hồi để huấn luyện lại mô hình

### Hạn chế đã biết

- Recall còn hạn chế (xem docs/EXPERIMENTS.md); bộ trích candidate bỏ sót dạng `Authorization: Bearer ...`, giá trị bọc trong lời gọi hàm và một phần mật khẩu trong URL.
- Điểm tin cậy quá tự tin ở các dải điểm cao; không nên hiểu "điểm 0,95" là 95% xác suất.
- Precision phụ thuộc mạnh vào tỉ lệ secret thực tế; khi secret hiếm, phần lớn cảnh báo là báo nhầm.
- Ở chế độ pre-commit, `commit_hash` ghi vào cơ sở dữ liệu là commit cha.
- Chưa xác minh khóa còn hiệu lực (cố ý, vì lý do an toàn).

## Tài liệu

- [docs/DATASET.md](docs/DATASET.md): nguồn gốc dữ liệu, schema, thống kê, kiểm tra overlap
- [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md): giao thức, kết quả thực nghiệm, thời gian xử lý
- [docs/CI_CD_DEMO.md](docs/CI_CD_DEMO.md): cấu hình branch protection và demo Pull Request bị chặn

## Giấy phép

Đồ án tốt nghiệp, mục đích học thuật. Dữ liệu CredData và các công cụ bên thứ ba (Gitleaks, TruffleHog) tuân theo giấy phép riêng của chúng.
