const { sql, getPool } = require('../db');

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

function localDateKey(d) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

async function getTimeline(req, res) {
  const days = Math.min(Math.max(parseInt(req.query.days, 10) || 30, 1), 365);

  try {
    const pool = await getPool();

    const result = await pool.request()
      .input('days', sql.Int, days)
      .query(`
        SELECT CAST(created_at AS DATE) AS scan_date, status, COUNT(*) AS count
        FROM scans
        WHERE created_at >= DATEADD(DAY, -(@days - 1), CAST(GETDATE() AS DATE))
        GROUP BY CAST(created_at AS DATE), status
      `);

    // Tạo sẵn đủ các ngày, mặc định bằng 0
    const byDate = {};
    const today = new Date();
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i);
      const key = localDateKey(d);
      byDate[key] = { date: key, blocked: 0, warned: 0, passed: 0 };
    }

    for (const r of result.recordset) {
      const key = r.scan_date.toISOString().slice(0, 10); // kiểu DATE của mssql là UTC 00:00
      if (byDate[key] && r.status in byDate[key]) byDate[key][r.status] = r.count;
    }

    return res.json({ days, timeline: Object.values(byDate) });
  } catch (err) {
    console.error('Get timeline stats error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

// GET /api/stats/breakdown?days=30
async function getBreakdown(req, res) {
  const days = Math.min(Math.max(parseInt(req.query.days, 10) || 30, 1), 365);

  const from = `s.created_at >= DATEADD(DAY, -(@days - 1), CAST(GETDATE() AS DATE))`;

  try {
    const pool = await getPool();
    const run = (query) => pool.request().input('days', sql.Int, days).query(query);

    const [risk, secrets, files] = await Promise.all([
      run(`
        SELECT LOWER(f.risk_level) AS risk_level, COUNT(*) AS count
        FROM findings f JOIN scans s ON s.id = f.scan_id
        WHERE f.risk_level IS NOT NULL AND ${from}
        GROUP BY LOWER(f.risk_level)
      `),
      run(`
        SELECT TOP 5 f.secret_type, COUNT(*) AS count
        FROM findings f JOIN scans s ON s.id = f.scan_id
        WHERE f.secret_type IS NOT NULL AND ${from}
        GROUP BY f.secret_type
        ORDER BY COUNT(*) DESC
      `),
      run(`
        SELECT TOP 5 f.file_path, COUNT(*) AS count, COUNT(DISTINCT f.scan_id) AS scans
        FROM findings f JOIN scans s ON s.id = f.scan_id
        WHERE ${from}
        GROUP BY f.file_path
        ORDER BY COUNT(*) DESC
      `),
    ]);

    const findingsByRisk = { high: 0, medium: 0, low: 0 };
    for (const r of risk.recordset) {
      if (r.risk_level in findingsByRisk) findingsByRisk[r.risk_level] = r.count;
    }

    return res.json({
      days,
      findings_by_risk: findingsByRisk,
      top_secret_types: secrets.recordset,
      top_files: files.recordset,
    });
  } catch (err) {
    console.error('Get breakdown stats error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

module.exports = { getOverview, getTimeline, getBreakdown };