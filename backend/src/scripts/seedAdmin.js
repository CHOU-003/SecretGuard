// Cách dùng: node src/scripts/seedAdmin.js <username> <password>
require('dotenv').config();
const bcrypt = require('bcryptjs');
const { sql, getPool } = require('../db');

async function seedAdmin() {
  const username = process.argv[2];
  const password = process.argv[3];

  if (!username || !password) {
    console.log('Cách dùng: node src/scripts/seedAdmin.js <username> <password>');
    process.exit(1);
  }

  try {
    const pool = await getPool();

    const existing = await pool.request()
      .input('username', sql.NVarChar, username)
      .query('SELECT id FROM users WHERE username = @username');

    if (existing.recordset.length > 0) {
      console.log(`⚠️  User "${username}" đã tồn tại, dừng tạo.`);
      process.exit(0);
    }

    const passwordHash = await bcrypt.hash(password, 10);

    await pool.request()
      .input('username', sql.NVarChar, username)
      .input('password_hash', sql.NVarChar, passwordHash)
      .input('role', sql.NVarChar, 'admin')
      .query(`INSERT INTO users (username, password_hash, role, is_active)
              VALUES (@username, @password_hash, @role, 1)`);

    console.log(`✅ Đã tạo admin "${username}" thành công.`);
    process.exit(0);
  } catch (err) {
    console.error('❌ Lỗi khi tạo admin:', err.message);
    process.exit(1);
  }
}

seedAdmin();