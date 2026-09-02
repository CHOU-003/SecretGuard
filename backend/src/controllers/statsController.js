const { getPool } = require('../db');

// GET /api/stats — cho frontend hiển thị StatCard (qua authenticateAdmin)
async function getStats(req, res) {
  try {
    const pool = await getPool();

    const result = await pool.request().query(`
      SELECT
        COUNT(*) AS total_scans,
        SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) AS blocked,
        SUM(CASE WHEN status = 'warned' THEN 1 ELSE 0 END) AS warned,
        SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS passed
      FROM scans
    `);

    const row = result.recordset[0];

    return res.json({
      total_scans: row.total_scans || 0,
      blocked: row.blocked || 0,
      warned: row.warned || 0,
      passed: row.passed || 0,
    });
  } catch (err) {
    console.error('Get stats error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

module.exports = { getStats };