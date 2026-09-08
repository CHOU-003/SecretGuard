#!/bin/bash
# ============================================
# SecretGuard - EC2 Setup Script
# Run this script on a fresh Ubuntu 22.04 EC2 instance
# ============================================

set -e

echo "🔐 Setting up SecretGuard Platform..."
echo "==========================================="

PROJECT_NAME="secret-guard"
PROJECT_DIR="/var/www/$PROJECT_NAME"

DB_NAME="SecretGuardDB"
DB_USER="secretguard_app"

# ⚠️  ĐỔI 2 MẬT KHẨU NÀY TRƯỚC KHI CHẠY SCRIPT
# DB_PASSWORD phải khớp với DB_PASSWORD trong backend/.env
DB_PASSWORD="CHANGE_ME_STRONG_DB_PASSWORD"
# SA_PASSWORD chỉ dùng nội bộ lúc setup SQL Server, không dùng ở đâu khác
SA_PASSWORD="CHANGE_ME_STRONG_SA_PASSWORD"

# --- Update system ---
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# --- Install Node.js 20.x ---
echo "📦 Installing Node.js 20.x..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
echo "Node.js version: $(node -v)"
echo "npm version: $(npm -v)"

# --- Install Nginx ---
echo "📦 Installing Nginx..."
sudo apt install -y nginx

# --- Install PM2 (process manager) ---
echo "📦 Installing PM2..."
sudo npm install -g pm2

# --- Install Microsoft SQL Server ---
echo "📦 Installing Microsoft SQL Server (mssql-server)..."
curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
curl -fsSL https://packages.microsoft.com/config/ubuntu/22.04/mssql-server-2022.list | sudo tee /etc/apt/sources.list.d/mssql-server-2022.list
sudo apt update
sudo apt install -y mssql-server

echo "⚙️  Configuring SQL Server (non-interactive, edition: Developer - miễn phí)..."
sudo MSSQL_PID=Developer MSSQL_SA_PASSWORD="$SA_PASSWORD" ACCEPT_EULA=Y /opt/mssql/bin/mssql-conf -n setup
sudo systemctl enable --now mssql-server

echo "📦 Installing sqlcmd tools..."
curl -fsSL https://packages.microsoft.com/config/ubuntu/22.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt update
sudo ACCEPT_EULA=Y apt install -y mssql-tools18 unixodbc-dev
echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.bashrc
export PATH="$PATH:/opt/mssql-tools18/bin"

# --- Create database + app login (khớp với backend/.env) ---
echo "🗄️  Creating database and app user..."
sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -C -Q "CREATE DATABASE [$DB_NAME];"
sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -C -Q "CREATE LOGIN [$DB_USER] WITH PASSWORD = '$DB_PASSWORD', CHECK_POLICY = OFF;"
sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -C -d "$DB_NAME" -Q "CREATE USER [$DB_USER] FOR LOGIN [$DB_USER]; ALTER ROLE db_owner ADD MEMBER [$DB_USER];"

echo "✅ SQL Server configured (DB: $DB_NAME, user: $DB_USER)"
echo "⚠️  Nếu có file schema tạo bảng (projects/scans/findings), chạy thêm:"
echo "    sqlcmd -S localhost -U $DB_USER -P '****' -C -d $DB_NAME -i \$PROJECT_DIR/backend/db/schema.sql"

# --- Set up project directory ---
echo "📁 Setting up project..."
sudo mkdir -p "$PROJECT_DIR"
sudo chown -R $USER:$USER "$PROJECT_DIR"

# Copy project files (assumes you've transferred them to ~/secret-guard)
cp -r ~/secret-guard/* "$PROJECT_DIR/"

# --- Install backend dependencies ---
echo "📦 Installing backend dependencies..."
cd "$PROJECT_DIR/backend"
npm install --production

# ⚠️  Tạo file backend/.env thủ công trên server (KHÔNG commit .env lên git).
#     Dùng scp để copy riêng, hoặc tạo trực tiếp bằng nano/vim tại đây:
#     nano $PROJECT_DIR/backend/.env

# --- Build frontend ---
echo "🔨 Building frontend..."
cd "$PROJECT_DIR/frontend"
npm install
npm run build

# --- Configure Nginx ---
echo "🌐 Configuring Nginx..."
sudo cp "$PROJECT_DIR/deploy/secretguard-nginx.conf" /etc/nginx/sites-available/secret-guard
sudo ln -sf /etc/nginx/sites-available/secret-guard /etc/nginx/sites-enabled/secret-guard
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

# --- Configure firewall ---
echo "🔥 Configuring firewall..."
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable

# --- Start backend with PM2 ---
echo "🚀 Starting backend with PM2..."
cd "$PROJECT_DIR/backend"
pm2 start server.js --name secretguard-backend
pm2 save
pm2 startup systemd -u $USER --hp /home/$USER | tail -1 | sudo bash

echo ""
echo "==========================================="
echo "🎉 SecretGuard is now live!"
echo "==========================================="
echo ""
echo "Access your app at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo '<your-ec2-public-ip>')"
echo ""
echo "Useful commands:"
echo "  pm2 status                     - Check backend status"
echo "  pm2 logs                       - View backend logs"
echo "  pm2 restart all                - Restart backend"
echo "  sudo systemctl restart nginx   - Restart Nginx"
echo "  sqlcmd -S localhost -U $DB_USER -C -d $DB_NAME  - Connect to DB"
echo ""