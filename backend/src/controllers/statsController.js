const { sql, getPool } = require('../db');

// GET /api/stats/overview — số liệu tổng hợp cho dashboard (qua authenticateAdmin)
async function getOverview(req, res) {
  try {
    const pool = await getPool();

    const scanStatsResult = await pool.request().query(`
      SELECT
        COUNT(*) AS total_scans,
        SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) AS blocked,
        SUM(CASE WHEN status = 'warned' THEN 1 ELSE 0 END) AS warned,
        SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS passed
      FROM scans
    `);

    const findingsByRiskResult = await pool.request().query(`
      SELECT risk_level, COUNT(*) AS count
      FROM findings
      WHERE risk_level IS NOT NULL
      GROUP BY risk_level
    `);

    const row = scanStatsResult.recordset[0];
    const totalScans = row.total_scans || 0;
    const blocked = row.blocked || 0;
    const warned = row.warned || 0;
    const passed = row.passed || 0;

    const findingsByRisk = { high: 0, medium: 0, low: 0 };
    for (const r of findingsByRiskResult.recordset) {
      if (r.risk_level in findingsByRisk) {
        findingsByRisk[r.risk_level] = r.count;
      }
    }

    return res.json({
      total_scans: totalScans,
      blocked,
      warned,
      passed,
      blocked_rate: totalScans ? Math.round((blocked / totalScans) * 1000) / 10 : 0,
      warned_rate: totalScans ? Math.round((warned / totalScans) * 1000) / 10 : 0,
      passed_rate: totalScans ? Math.round((passed / totalScans) * 1000) / 10 : 0,
      findings_by_risk: findingsByRisk,
    });
  } catch (err) {
    console.error('Get overview stats error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

// GET /api/stats/timeline — dữ liệu theo thời gian, phục vụ biểu đồ trend (qua authenticateAdmin)
// Query: ?days=30 (mặc định 30 ngày gần nhất)
async function getTimeline(req, res) {
  const days = Math.min(Math.max(parseInt(req.query.days, 10) || 30, 1), 365);

  try {
    const pool = await getPool();

    const result = await pool.request()
      .input('days', sql.Int, days)
      .query(`
        SELECT
          CAST(created_at AS DATE) AS scan_date,
          status,
          COUNT(*) AS count
        FROM scans
        WHERE created_at >= DATEADD(DAY, -@days, CAST(GETDATE() AS DATE))
        GROUP BY CAST(created_at AS DATE), status
        ORDER BY scan_date ASC
      `);

    // Gom theo ngày: { date, blocked, warned, passed }
    const byDate = {};
    for (const r of result.recordset) {
      const dateKey = r.scan_date.toISOString().slice(0, 10);
      if (!byDate[dateKey]) {
        byDate[dateKey] = { date: dateKey, blocked: 0, warned: 0, passed: 0 };
      }
      if (r.status in byDate[dateKey]) {
        byDate[dateKey][r.status] = r.count;
      }
    }

    const timeline = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date));

    return res.json({ days, timeline });
  } catch (err) {
    console.error('Get timeline stats error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

module.exports = { getOverview, getTimeline };