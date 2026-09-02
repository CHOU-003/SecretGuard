// Dùng cho Python secret-detector gọi thẳng vào backend (POST /api/scans, ...)
// Không dùng JWT admin vì đây là service-to-service, không có "người dùng" đăng nhập
function authenticateService(req, res, next) {
  const apiKey = req.headers['8f7c2a91d4e6b3c0a5f1e9d7c2b8a6f4'];

  if (!apiKey || apiKey !== process.env.SERVICE_API_KEY) {
    return res.status(401).json({ error: 'API key không hợp lệ' });
  }

  next();
}

module.exports = authenticateService;