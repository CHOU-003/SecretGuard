const { sql, getPool } = require('../db');

// POST /api/scans — gọi bởi Python secret-detector (qua authenticateService)
// Body: { project_name, commit_hash, branch, trigger_type, status, findings: [...] }
async function createScan(req, res) {
  const {
    project_name,
    commit_hash,
    branch,
    trigger_type,
    status,
    findings,
  } = req.body;

  if (!project_name || !trigger_type || !status) {
    return res.status(400).json({ error: 'Thiếu project_name, trigger_type hoặc status' });
  }

  const validStatus = ['blocked', 'warned', 'passed'];
  if (!validStatus.includes(status)) {
    return res.status(400).json({ error: `status phải là một trong: ${validStatus.join(', ')}` });
  }

  try {
    const pool = await getPool();

    // Tìm project theo tên, tự tạo nếu chưa có
    let projectResult = await pool.request()
      .input('name', sql.NVarChar, project_name)
      .query('SELECT id FROM projects WHERE name = @name');

    let projectId;
    if (projectResult.recordset.length > 0) {
      projectId = projectResult.recordset[0].id;
    } else {
      const inserted = await pool.request()
        .input('name', sql.NVarChar, project_name)
        .query('INSERT INTO projects (name) OUTPUT INSERTED.id VALUES (@name)');
      projectId = inserted.recordset[0].id;
    }

    const totalFindings = Array.isArray(findings) ? findings.length : 0;

    const scanInsert = await pool.request()
      .input('project_id', sql.Int, projectId)
      .input('commit_hash', sql.NVarChar, commit_hash || null)
      .input('branch', sql.NVarChar, branch || null)
      .input('trigger_type', sql.NVarChar, trigger_type)
      .input('status', sql.NVarChar, status)
      .input('total_findings', sql.Int, totalFindings)
      .query(`INSERT INTO scans (project_id, commit_hash, branch, trigger_type, status, total_findings)
              OUTPUT INSERTED.id
              VALUES (@project_id, @commit_hash, @branch, @trigger_type, @status, @total_findings)`);

    const scanId = scanInsert.recordset[0].id;

    // Ghi từng finding nếu có
    if (totalFindings > 0) {
      for (const f of findings) {
        await pool.request()
          .input('scan_id', sql.Int, scanId)
          .input('file_path', sql.NVarChar, f.file_path)
          .input('line_number', sql.Int, f.line_number || null)
          .input('secret_type', sql.NVarChar, f.secret_type || null)
          .input('confidence_score', sql.Float, f.confidence_score || null)
          .input('risk_level', sql.NVarChar, f.risk_level || null)
          .query(`INSERT INTO findings (scan_id, file_path, line_number, secret_type, confidence_score, risk_level)
                  VALUES (@scan_id, @file_path, @line_number, @secret_type, @confidence_score, @risk_level)`);
      }
    }

    return res.status(201).json({ id: scanId, project_id: projectId, status, total_findings: totalFindings });
  } catch (err) {
    console.error('Create scan error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

// GET /api/scans — cho frontend hiển thị (qua authenticateAdmin)
// Query: ?project_id=&status=&page=1&limit=20
async function listScans(req, res) {
  const page = Math.max(parseInt(req.query.page, 10) || 1, 1);
  const limit = Math.min(Math.max(parseInt(req.query.limit, 10) || 20, 1), 200);
  const offset = (page - 1) * limit;

  const { project_id, status } = req.query;

  const validStatus = ['blocked', 'warned', 'passed'];
  if (status && !validStatus.includes(status)) {
    return res.status(400).json({ error: `status phải là một trong: ${validStatus.join(', ')}` });
  }
  if (project_id && Number.isNaN(parseInt(project_id, 10))) {
    return res.status(400).json({ error: 'project_id phải là số' });
  }

  try {
    const pool = await getPool();

    const whereClauses = [];
    const countRequest = pool.request();

    if (project_id) {
      whereClauses.push('s.project_id = @project_id');
      countRequest.input('project_id', sql.Int, parseInt(project_id, 10));
    }
    if (status) {
      whereClauses.push('s.status = @status');
      countRequest.input('status', sql.NVarChar, status);
    }

    const whereSql = whereClauses.length ? `WHERE ${whereClauses.join(' AND ')}` : '';

    const countResult = await countRequest
      .query(`SELECT COUNT(*) AS total FROM scans s ${whereSql}`);
    const total = countResult.recordset[0].total;

    // mssql không cho tái dùng input đã bind trên cùng 1 request -> tạo request mới cho query chính
    const dataRequest = pool.request();
    if (project_id) dataRequest.input('project_id', sql.Int, parseInt(project_id, 10));
    if (status) dataRequest.input('status', sql.NVarChar, status);
    dataRequest.input('offset', sql.Int, offset);
    dataRequest.input('limit', sql.Int, limit);

    const dataResult = await dataRequest.query(`
      SELECT
        s.id, s.commit_hash, s.branch, s.trigger_type, s.status,
        s.total_findings, s.created_at, p.id AS project_id, p.name AS project_name
      FROM scans s
      JOIN projects p ON p.id = s.project_id
      ${whereSql}
      ORDER BY s.created_at DESC
      OFFSET @offset ROWS FETCH NEXT @limit ROWS ONLY
    `);

    return res.json({
      scans: dataResult.recordset,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit) || 1,
      },
    });
  } catch (err) {
    console.error('List scans error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

// GET /api/scans/:id — chi tiết 1 scan kèm toàn bộ findings (qua authenticateAdmin)
async function getScanById(req, res) {
  const scanId = parseInt(req.params.id, 10);

  if (Number.isNaN(scanId)) {
    return res.status(400).json({ error: 'id không hợp lệ' });
  }

  try {
    const pool = await getPool();

    const scanResult = await pool.request()
      .input('id', sql.Int, scanId)
      .query(`
        SELECT
          s.id, s.commit_hash, s.branch, s.trigger_type, s.status,
          s.total_findings, s.created_at, p.id AS project_id, p.name AS project_name
        FROM scans s
        JOIN projects p ON p.id = s.project_id
        WHERE s.id = @id
      `);

    const scan = scanResult.recordset[0];

    if (!scan) {
      return res.status(404).json({ error: 'Không tìm thấy scan' });
    }

    const findingsResult = await pool.request()
      .input('scan_id', sql.Int, scanId)
      .query(`
        SELECT id, file_path, line_number, secret_type, confidence_score, risk_level
        FROM findings
        WHERE scan_id = @scan_id
        ORDER BY id ASC
      `);

    return res.json({ ...scan, findings: findingsResult.recordset });
  } catch (err) {
    console.error('Get scan by id error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

module.exports = { createScan, listScans, getScanById };