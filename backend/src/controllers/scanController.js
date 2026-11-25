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
        .query('INSERT INTO projects (name, risk_threshold) OUTPUT INSERTED.id VALUES (@name, \'high\')');
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

const VALID_STATUS = ['blocked', 'warned', 'passed'];
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function buildScanFilters(query) {
  const { project_id, status, branch, trigger_type, q, from, to } = query;
  const where = [];
  const binds = []; // [name, type, value]

  if (project_id) {
    if (Number.isNaN(parseInt(project_id, 10))) return { error: 'project_id phải là số' };
    where.push('s.project_id = @project_id');
    binds.push(['project_id', sql.Int, parseInt(project_id, 10)]);
  }
  if (status) {
    if (!VALID_STATUS.includes(status)) {
      return { error: `status phải là một trong: ${VALID_STATUS.join(', ')}` };
    }
    where.push('s.status = @status');
    binds.push(['status', sql.NVarChar, status]);
  }
  if (branch) {
    where.push('s.branch = @branch');
    binds.push(['branch', sql.NVarChar, branch]);
  }
  if (trigger_type) {
    where.push('s.trigger_type = @trigger_type');
    binds.push(['trigger_type', sql.NVarChar, trigger_type]);
  }
  if (q && q.trim()) {
    // escape ký tự đặc biệt của LIKE
    const safe = q.trim().replace(/[%_[]/g, '[$&]');
    where.push('(s.commit_hash LIKE @q OR s.branch LIKE @q)');
    binds.push(['q', sql.NVarChar, `%${safe}%`]);
  }
  if (from) {
    if (!DATE_RE.test(from)) return { error: 'from phải có dạng YYYY-MM-DD' };
    where.push('s.created_at >= @from');
    binds.push(['from', sql.Date, new Date(from)]);
  }
  if (to) {
    if (!DATE_RE.test(to)) return { error: 'to phải có dạng YYYY-MM-DD' };
    // gồm cả ngày "to"
    where.push('s.created_at < DATEADD(DAY, 1, @to)');
    binds.push(['to', sql.Date, new Date(to)]);
  }

  return {
    whereSql: where.length ? `WHERE ${where.join(' AND ')}` : '',
    apply(request) {
      for (const [name, type, value] of binds) request.input(name, type, value);
      return request;
    },
  };
}

// GET /api/scans?page=&limit=&project_id=&status=&branch=&trigger_type=&q=&from=&to=
async function listScans(req, res) {
  const page = Math.max(parseInt(req.query.page, 10) || 1, 1);
  const limit = Math.min(Math.max(parseInt(req.query.limit, 10) || 20, 1), 200);
  const offset = (page - 1) * limit;

  const filters = buildScanFilters(req.query);
  if (filters.error) return res.status(400).json({ error: filters.error });

  try {
    const pool = await getPool();

    const countResult = await filters
      .apply(pool.request())
      .query(`SELECT COUNT(*) AS total FROM scans s ${filters.whereSql}`);
    const total = countResult.recordset[0].total;

    const dataResult = await filters
      .apply(pool.request())
      .input('offset', sql.Int, offset)
      .input('limit', sql.Int, limit)
      .query(`
        SELECT
          s.id, s.commit_hash, s.branch, s.trigger_type, s.status,
          s.total_findings, s.created_at,
          p.id AS project_id, p.name AS project_name
        FROM scans s
        JOIN projects p ON p.id = s.project_id
        ${filters.whereSql}
        ORDER BY s.created_at DESC, s.id DESC
        OFFSET @offset ROWS FETCH NEXT @limit ROWS ONLY
      `);

    return res.json({
      scans: dataResult.recordset,
      pagination: { page, limit, total, totalPages: Math.ceil(total / limit) || 1 },
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
        s.total_findings, s.created_at,
        p.id AS project_id, p.name AS project_name, p.risk_threshold
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

async function listBranches(req, res) {
  try {
    const pool = await getPool();
    const r = await pool.request().query(
      `SELECT DISTINCT branch FROM scans WHERE branch IS NOT NULL ORDER BY branch`
    );
    return res.json({ branches: r.recordset.map((x) => x.branch) });
  } catch (err) {
    console.error('List branches error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

// Chặn ô bắt đầu bằng = + - @ để Excel không chạy như công thức (CSV injection)
function csvCell(value) {
  if (value === null || value === undefined) return '';
  let s = value instanceof Date ? value.toISOString() : String(value);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

const EXPORT_MAX_ROWS = 10000;

// GET /api/scans/export?status=&branch=&q=&from=&to=...  (cùng filter với listScans)
async function exportScans(req, res) {
  const filters = buildScanFilters(req.query);
  if (filters.error) return res.status(400).json({ error: filters.error });

  try {
    const pool = await getPool();
    const result = await filters
      .apply(pool.request())
      .input('max', sql.Int, EXPORT_MAX_ROWS)
      .query(`
        SELECT TOP (@max)
          s.id, p.name AS project_name, s.commit_hash, s.branch,
          s.trigger_type, s.status, s.total_findings, s.created_at
        FROM scans s
        JOIN projects p ON p.id = s.project_id
        ${filters.whereSql}
        ORDER BY s.created_at DESC, s.id DESC
      `);

    const columns = [
      'id', 'project_name', 'commit_hash', 'branch',
      'trigger_type', 'status', 'total_findings', 'created_at',
    ];
    const lines = [columns.join(',')];
    for (const row of result.recordset) {
      lines.push(columns.map((c) => csvCell(row[c])).join(','));
    }

    const filename = `scans_${new Date().toISOString().slice(0, 10)}.csv`;
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    // BOM để Excel đọc đúng UTF-8
    return res.send('\uFEFF' + lines.join('\r\n'));
  } catch (err) {
    console.error('Export scans error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

module.exports = { createScan, listScans, getScanById, listBranches, exportScans };