require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { getPool } = require('./src/db');

const authRoutes = require('./src/routes/auth');
const scanRoutes = require('./src/routes/scans');
const statsRoutes = require('./src/routes/stats');
const projectRoutes = require('./src/routes/projects');
const auditLogRoutes = require('./src/routes/auditLog');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors({
  origin: process.env.FRONTEND_URL || 'http://localhost:5173',
  credentials: true,
}));
app.use(express.json());

// Route auth: /api/auth/login, /api/auth/logout, /api/auth/refresh
app.use('/api/auth', authRoutes);
app.use('/api/scans', scanRoutes);
app.use('/api/stats', statsRoutes);
app.use('/api/projects', projectRoutes);
app.use('/api/audit-log', auditLogRoutes);

// Health check nhanh
app.get('/', (req, res) => {
  res.json({ message: 'SecretGuard backend đang chạy' });
});

async function start() {
  try {
    await getPool(); // kết nối SQL Server trước khi lắng nghe request
    app.listen(PORT, () => {
      console.log(`🚀 Server đang chạy tại http://localhost:${PORT}`);
    });
  } catch (err) {
    console.error('❌ Không thể khởi động server vì lỗi kết nối DB:', err.message);
    process.exit(1);
  }
}

start();