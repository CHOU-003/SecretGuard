const { sql, getPool } = require('../db');

// GET /api/audit-log — xem lịch sử ai đổi gì, khi nào (qua authenticateAdmin)
// Query: ?project_id=&page=1&limit=20
async function listAuditLog(req, res) {
  const page = Math.max(parseInt(req.query.page, 10) || 1, 1);
  const limit = Math.min(Math.max(parseInt(req.query.limit, 10) || 20, 1), 200);
  const offset = (page - 1) * limit;

  const { project_id } = req.query;

  if (project_id && Number.isNaN(parseInt(project_id, 10))) {
    return res.status(400).json({ error: 'project_id phải là số' });
  }

  try {
    const pool = await getPool();

    const whereSql = project_id ? 'WHERE a.project_id = @project_id' : '';

    const countRequest = pool.request();
    if (project_id) countRequest.input('project_id', sql.Int, parseInt(project_id, 10));
    const countResult = await countRequest.query(`SELECT COUNT(*) AS total FROM audit_log a ${whereSql}`);
    const total = countResult.recordset[0].total;

    const dataRequest = pool.request();
    if (project_id) dataRequest.input('project_id', sql.Int, parseInt(project_id, 10));
    dataRequest.input('offset', sql.Int, offset);
    dataRequest.input('limit', sql.Int, limit);

    const dataResult = await dataRequest.query(`
      SELECT
        a.id, a.project_id, p.name AS project_name,
        a.user_id, u.username,
        a.action, a.old_value, a.new_value, a.changed_at
      FROM audit_log a
      LEFT JOIN projects p ON p.id = a.project_id
      LEFT JOIN users u ON u.id = a.user_id
      ${whereSql}
      ORDER BY a.changed_at DESC
      OFFSET @offset ROWS FETCH NEXT @limit ROWS ONLY
    `);

    return res.json({
      logs: dataResult.recordset,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit) || 1,
      },
    });
  } catch (err) {
    console.error('List audit log error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

module.exports = { listAuditLog };