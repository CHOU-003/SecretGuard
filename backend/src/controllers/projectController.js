const { sql, getPool } = require('../db');

const VALID_THRESHOLDS = ['medium', 'high'];

// POST /api/projects — tạo project mới
async function createProject(req, res) {
  const { name, risk_threshold } = req.body;

  if (!name) {
    return res.status(400).json({ error: 'Thiếu name' });
  }

  if (risk_threshold && !VALID_THRESHOLDS.includes(risk_threshold)) {
    return res.status(400).json({ error: `risk_threshold phải là một trong: ${VALID_THRESHOLDS.join(', ')}` });
  }

  try {
    const pool = await getPool();

    const existing = await pool.request()
      .input('name', sql.NVarChar, name)
      .query('SELECT id FROM projects WHERE name = @name');

    if (existing.recordset.length > 0) {
      return res.status(409).json({ error: 'Project đã tồn tại' });
    }

    const inserted = await pool.request()
      .input('name', sql.NVarChar, name)
      .input('risk_threshold', sql.NVarChar, risk_threshold || 'high')
      .query(`INSERT INTO projects (name, risk_threshold)
              OUTPUT INSERTED.id, INSERTED.name, INSERTED.risk_threshold, INSERTED.created_at
              VALUES (@name, @risk_threshold)`);

    return res.status(201).json(inserted.recordset[0]);
  } catch (err) {
    console.error('Create project error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

// GET /api/projects — danh sách project
async function listProjects(req, res) {
  try {
    const pool = await getPool();

    const result = await pool.request().query(`
      SELECT
        p.id, p.name, p.risk_threshold, p.created_at,
        COUNT(s.id) AS total_scans,
        ISNULL(SUM(CASE WHEN s.status = 'blocked' THEN 1 ELSE 0 END), 0) AS blocked_scans,
        MAX(s.created_at) AS last_scan_at
      FROM projects p
      LEFT JOIN scans s ON s.project_id = p.id
      GROUP BY p.id, p.name, p.risk_threshold, p.created_at
      ORDER BY p.name ASC
    `);

    return res.json({ projects: result.recordset });
  } catch (err) {
    console.error('List projects error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

// GET /api/projects/:id — chi tiết 1 project
async function getProjectById(req, res) {
  const projectId = parseInt(req.params.id, 10);

  if (Number.isNaN(projectId)) {
    return res.status(400).json({ error: 'id không hợp lệ' });
  }

  try {
    const pool = await getPool();

    const result = await pool.request()
      .input('id', sql.Int, projectId)
      .query('SELECT id, name, risk_threshold, created_at FROM projects WHERE id = @id');

    const project = result.recordset[0];

    if (!project) {
      return res.status(404).json({ error: 'Không tìm thấy project' });
    }

    return res.json(project);
  } catch (err) {
    console.error('Get project by id error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

async function updateThreshold(req, res) {
  const projectId = parseInt(req.params.id, 10);
  const { risk_threshold } = req.body;

  if (Number.isNaN(projectId)) {
    return res.status(400).json({ error: 'id không hợp lệ' });
  }
  if (!risk_threshold || !VALID_THRESHOLDS.includes(risk_threshold)) {
    return res.status(400).json({ error: `risk_threshold phải là một trong: ${VALID_THRESHOLDS.join(', ')}` });
  }

  let tx;
  try {
    const pool = await getPool();
    tx = new sql.Transaction(pool);
    await tx.begin();

    // UPDLOCK: tránh 2 người đổi cùng lúc làm log sai old_value
    const existing = await tx.request()
      .input('id', sql.Int, projectId)
      .query('SELECT id, risk_threshold FROM projects WITH (UPDLOCK) WHERE id = @id');

    const project = existing.recordset[0];
    if (!project) {
      await tx.rollback();
      return res.status(404).json({ error: 'Không tìm thấy project' });
    }

    const oldValue = project.risk_threshold;
    if (oldValue === risk_threshold) {
      await tx.rollback();
      return res.json({ id: projectId, risk_threshold, message: 'Không có thay đổi' });
    }

    await tx.request()
      .input('id', sql.Int, projectId)
      .input('risk_threshold', sql.NVarChar, risk_threshold)
      .query('UPDATE projects SET risk_threshold = @risk_threshold WHERE id = @id');

    await tx.request()
      .input('project_id', sql.Int, projectId)
      .input('user_id', sql.Int, req.user.id)
      .input('action', sql.NVarChar, 'threshold_changed')
      .input('old_value', sql.NVarChar, oldValue)
      .input('new_value', sql.NVarChar, risk_threshold)
      .query(`INSERT INTO audit_log (project_id, user_id, action, old_value, new_value)
              VALUES (@project_id, @user_id, @action, @old_value, @new_value)`);

    await tx.commit();
    return res.json({ id: projectId, risk_threshold, previous: oldValue });
  } catch (err) {
    if (tx) { try { await tx.rollback(); } catch { /* đã rollback */ } }
    console.error('Update threshold error:', err);
    return res.status(500).json({ error: 'Lỗi server' });
  }
}

module.exports = { createProject, listProjects, getProjectById, updateThreshold };