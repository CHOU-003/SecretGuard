# SecretGuard 🔐

Hệ thống **tự động phát hiện và ngăn chặn rò rỉ secret** (API key, token, private key, connection string...) trong mã nguồn, tích hợp trực tiếp vào Git workflow và CI/CD pipeline — chặn commit/PR ngay khi phát hiện secret vượt ngưỡng rủi ro cho phép, không cần thao tác thủ công.

## Mục lục

- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Công nghệ sử dụng](#công-nghệ-sử-dụng)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Cài đặt](#cài-đặt)
- [Cấu hình môi trường](#cấu-hình-môi-trường)
- [Chạy dự án](#chạy-dự-án)
- [Tính năng](#tính-năng)
- [Roadmap](#roadmap)

## Kiến trúc hệ thống

Git commit / CI job
        │
        ▼
Scanning Engine (Python)  ──── Regex + Entropy + ML
        │
        ├── Risk score vượt ngưỡng ──► ⛔ CHẶN commit/pipeline (exit code ≠ 0)
        │
        ▼
POST /api/scans  ──► Backend (Node.js + Express)  ──► SQL Server
                              │
                              ▼
                  Frontend (React) — Dashboard giám sát

Nguyên tắc thiết kế: **quyết định chặn luôn do Scanning Engine (Python) thực hiện tại chỗ**, không phụ thuộc vào backend/mạng — đảm bảo tốc độ và hoạt động được cả khi offline. Backend chỉ đóng vai trò ghi nhận lịch sử và phục vụ dashboard quản trị.

## Công nghệ sử dụng

| Thành phần | Công nghệ |
| --- | --- |
| Scanning Engine | Python (regex, entropy analysis, scikit-learn) |
| Backend API | Node.js + Express |
| Database | SQL Server |
| Frontend | React + Vite |
| Authentication | JWT (access token) + Refresh token (revocable) |
| CI/CD | GitHub Actions |
| Containerization | Docker + Nginx |

## Cấu trúc thư mục

Jerney-main/
├── .github/workflows/       # GitHub Actions: chặn PR khi phát hiện secret
├── backend/                 # REST API (Node.js + Express)
│   └── src/
│       ├── routes/
│       ├── db.js
│       └── index.js
├── frontend/                 # Dashboard quản trị (React)
├── deploy/                   # Cấu hình Nginx, script triển khai
└── secret-detector/          # Scanning Engine (Python)
    ├── data/                 # train.csv / val.csv / test.csv
    ├── models/                # Model ML đã huấn luyện
    └── src/
        ├── regex_scanner.py
        ├── entropy_scanner.py
        ├── train_ml.py
        ├── build_dataset.py
        ├── benchmark.py
        └── main.py

## Cài đặt

### Yêu cầu hệ thống

- Node.js 18+
- Python 3.9+
- SQL Server 2019+ (đã bật **Mixed Mode Authentication** và **TCP/IP protocol**)
- Git

### 1. Clone repository

```bash
git clone <repo-url>
cd Jerney-main
```

### 2. Cài đặt Scanning Engine (Python)

```bash
cd secret-detector
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 3. Cài đặt Backend (Node.js)

```bash
cd backend
npm install
```

### 4. Cài đặt Frontend (React)

```bash
cd frontend
npm install
```

### 5. Khởi tạo Database

Chạy file `schema.sql` (trong `backend/`) trên SQL Server để tạo các bảng: `projects`, `scans`, `findings`, `audit_log`, `users`, `refresh_tokens`.

## Cấu hình môi trường

Tạo file `.env` trong thư mục `backend/` (không commit file này lên Git):

```dotenv
DB_USER=secretguard_app
DB_PASSWORD=<mật khẩu SQL Server>
DB_SERVER=127.0.0.1
DB_NAME=SecretGuardDB
DB_PORT=1433

PORT=3000
JWT_SECRET=<chuỗi bí mật ngẫu nhiên>
```

## Chạy dự án

### Backend

```bash
cd backend
npm run dev
```

### Frontend

```bash
cd frontend
npm run dev
```

### Kích hoạt pre-commit hook (chặn secret tại local)

```bash
cd secret-detector
# hướng dẫn cài hook sẽ được bổ sung
```

### Kiểm thử scanning engine độc lập

```bash
cd secret-detector/src
python main.py --path <đường-dẫn-cần-quét>
```

## Tính năng

### Đã hoàn thành

- [x] Scanning Engine: Regex + Entropy + ML
- [x] Pre-commit hook chặn commit chứa secret tại local
- [x] Kết nối Backend ↔ SQL Server

### Đang phát triển

- [ ] Authentication cho Admin (đăng nhập / đăng xuất / refresh token)
- [ ] API ghi nhận & truy vấn lịch sử quét (`/api/scans`)
- [ ] Quản lý project & cấu hình ngưỡng rủi ro
- [ ] Dashboard thống kê (biểu đồ, audit log)
- [ ] Tích hợp GitHub Actions chặn merge PR

## Roadmap

Xem chi tiết tiến độ và các mốc thời gian trong đề cương đồ án (`De_cuong_SecretGuard.docx`).

## Giấy phép

Đồ án tốt nghiệp — mục đích học thuật.
