const { verifyAccessToken } = require('../utils/token');

// Áp dụng cho toàn bộ route admin: yêu cầu header Authorization: Bearer <accessToken>
function authenticateAdmin(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Thiếu access token' });
  }

  const token = authHeader.split(' ')[1];

  try {
    const payload = verifyAccessToken(token);
    req.user = {
      id: payload.sub,
      username: payload.username,
      role: payload.role,
    };
    next();
  } catch (err) {
    return res.status(401).json({ error: 'Access token không hợp lệ hoặc đã hết hạn' });
  }
}

module.exports = authenticateAdmin;