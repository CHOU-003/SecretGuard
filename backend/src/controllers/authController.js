const bcrypt = require('bcryptjs');
const { sql, getPool } = require('../db');
const {
  generateAccessToken,
  generateRefreshToken,
  verifyRefreshToken,
  hashToken,
  getRefreshExpiryDate,
} = require('../utils/token');

// POST /api/auth/login
async function login(req, res) {
  const { username, password } = req.body;

  if (!username || !password) {
    return res.status(400).json({ error: 'Thiếu username hoặc password' });
  }

  try {
    const pool = await getPool();

    const result = await pool.request()
      .input('username', sql.NVarChar, username)
      .query('SELECT * FROM users WHERE username = @username');

    const user = result.recordset[0];

    if (!user || !user.is_active) {
      return res.status(401).json({ error: 'Sai tài khoản hoặc mật khẩu' });
    }

    const passwordMatch = await bcrypt.compare(password, user.password_hash);

    if (!passwordMatch) {
      return res.status(401).json({ error: 'Sai tài khoản hoặc mật khẩu' });
    }

    const accessToken = generateAccessToken(user);
    const refreshToken = generateRefreshToken(user);

    await pool.request()
      .input('user_id', sql.Int, user.id)
      .input('token_hash', sql.NVarChar, hashToken(refreshToken))
      .input('expires_at', sql.DateTime2, getRefreshExpiryDate())
      .query(`INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
              VALUES (@user_id, @token_hash, @expires_at)`);

    await pool.request()
      .input('id', sql.Int, user.id)
      .query('UPDATE users SET last_login = GETDATE() WHERE id = @id');

    return res.json({
      accessToken,
      refreshToken,
      user: { id: user.id, username: user.username, role: user.role },
    });
  } catch (err) {
    console.error('Login error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

// POST /api/auth/logout
async function logout(req, res) {
  const { refreshToken } = req.body;

  if (!refreshToken) {
    return res.status(400).json({ error: 'Thiếu refreshToken' });
  }

  try {
    const pool = await getPool();
    const tokenHash = hashToken(refreshToken);

    await pool.request()
      .input('token_hash', sql.NVarChar, tokenHash)
      .query('UPDATE refresh_tokens SET is_revoked = 1 WHERE token_hash = @token_hash');

    return res.json({ message: 'Đăng xuất thành công' });
  } catch (err) {
    console.error('Logout error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

// POST /api/auth/refresh
async function refresh(req, res) {
  const { refreshToken } = req.body;

  if (!refreshToken) {
    return res.status(400).json({ error: 'Thiếu refreshToken' });
  }

  let payload;
  try {
    payload = verifyRefreshToken(refreshToken);
  } catch (err) {
    return res.status(401).json({ error: 'Refresh token không hợp lệ hoặc đã hết hạn' });
  }

  try {
    const pool = await getPool();
    const tokenHash = hashToken(refreshToken);

    const tokenResult = await pool.request()
      .input('token_hash', sql.NVarChar, tokenHash)
      .query(`SELECT * FROM refresh_tokens
              WHERE token_hash = @token_hash AND is_revoked = 0 AND expires_at > GETDATE()`);

    const tokenRecord = tokenResult.recordset[0];

    if (!tokenRecord) {
      return res.status(401).json({ error: 'Refresh token đã bị thu hồi hoặc hết hạn' });
    }

    const userResult = await pool.request()
      .input('id', sql.Int, payload.sub)
      .query('SELECT * FROM users WHERE id = @id AND is_active = 1');

    const user = userResult.recordset[0];

    if (!user) {
      return res.status(401).json({ error: 'Tài khoản không tồn tại hoặc đã bị khóa' });
    }

    // Xoay vòng refresh token: revoke token cũ, phát hành token mới (chống replay)
    await pool.request()
      .input('id', sql.Int, tokenRecord.id)
      .query('UPDATE refresh_tokens SET is_revoked = 1 WHERE id = @id');

    const newAccessToken = generateAccessToken(user);
    const newRefreshToken = generateRefreshToken(user);

    await pool.request()
      .input('user_id', sql.Int, user.id)
      .input('token_hash', sql.NVarChar, hashToken(newRefreshToken))
      .input('expires_at', sql.DateTime2, getRefreshExpiryDate())
      .query(`INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
              VALUES (@user_id, @token_hash, @expires_at)`);

    return res.json({ accessToken: newAccessToken, refreshToken: newRefreshToken });
  } catch (err) {
    console.error('Refresh error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

module.exports = { login, logout, refresh };