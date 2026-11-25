const nodemailer = require('nodemailer');

let transporter = null;

function getTransporter() {
  if (transporter) return transporter;
  const { SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS } = process.env;
  if (!SMTP_HOST || !SMTP_USER || !SMTP_PASS) return null; // chưa cấu hình -> bỏ qua
  const port = Number(SMTP_PORT) || 587;
  transporter = nodemailer.createTransport({
    host: SMTP_HOST,
    port,
    secure: port === 465,
    auth: { user: SMTP_USER, pass: SMTP_PASS },
  });
  return transporter;
}

const escapeHtml = (v) =>
  String(v ?? '—').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));

const RISK_COLOR = { high: '#e03131', medium: '#e8890c', low: '#1c7ed6' };

function buildHtml({ scanId, projectName, branch, commitHash, triggerType, findings }) {
  const base = (process.env.FRONTEND_URL || '').replace(/\/$/, '');
  const link = base ? `${base}/scans/${scanId}` : null;
  const shown = findings.slice(0, 10);

  const rows = shown.map((f) => {
    const color = RISK_COLOR[String(f.risk_level).toLowerCase()] || '#555';
    const conf = typeof f.confidence_score === 'number'
      ? `${(f.confidence_score * 100).toFixed(1)}%` : '—';
    return `<tr>
      <td style="padding:8px;border-bottom:1px solid #eee;color:${color};font-weight:700">${escapeHtml(String(f.risk_level || '').toUpperCase())}</td>
      <td style="padding:8px;border-bottom:1px solid #eee">${escapeHtml(f.secret_type)}</td>
      <td style="padding:8px;border-bottom:1px solid #eee;font-family:monospace">${escapeHtml(f.file_path)}:${escapeHtml(f.line_number)}</td>
      <td style="padding:8px;border-bottom:1px solid #eee">${conf}</td>
    </tr>`;
  }).join('');

  const more = findings.length > shown.length
    ? `<p style="color:#666">…và ${findings.length - shown.length} finding khác.</p>` : '';

  return `
  <div style="font-family:Arial,sans-serif;max-width:640px;margin:auto">
    <div style="background:#7a1c1c;color:#fff;padding:16px 20px;border-radius:8px 8px 0 0">
      <h2 style="margin:0">🚫 Commit bị chặn: phát hiện ${findings.length} secret</h2>
    </div>
    <div style="border:1px solid #eee;border-top:0;padding:20px;border-radius:0 0 8px 8px">
      <table style="font-size:14px;margin-bottom:16px">
        <tr><td style="padding:2px 12px 2px 0;color:#666">Project</td><td><b>${escapeHtml(projectName)}</b></td></tr>
        <tr><td style="padding:2px 12px 2px 0;color:#666">Branch</td><td>${escapeHtml(branch)}</td></tr>
        <tr><td style="padding:2px 12px 2px 0;color:#666">Commit</td><td style="font-family:monospace">${escapeHtml((commitHash || '').slice(0, 12))}</td></tr>
        <tr><td style="padding:2px 12px 2px 0;color:#666">Nguồn</td><td>${escapeHtml(triggerType)}</td></tr>
      </table>
      <table style="width:100%;border-collapse:collapse;font-size:14px">
        <tr style="background:#f5f6fa;text-align:left">
          <th style="padding:8px">Mức độ</th><th style="padding:8px">Loại</th>
          <th style="padding:8px">Vị trí</th><th style="padding:8px">Độ tin cậy</th>
        </tr>${rows}
      </table>
      ${more}
      ${link ? `<p style="margin-top:20px"><a href="${link}" style="background:#2f5bff;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none">Xem chi tiết &amp; hướng dẫn khắc phục</a></p>` : ''}
      <p style="color:#999;font-size:12px;margin-top:24px">Giá trị secret không được lưu hay gửi qua email, chỉ ghi nhận vị trí phát hiện.</p>
    </div>
  </div>`;
}

async function notifyBlockedScan(scan) {
  const t = getTransporter();
  const to = (process.env.NOTIFY_EMAILS || '').split(',').map((s) => s.trim()).filter(Boolean);
  if (!t || to.length === 0) return; // chưa cấu hình thì im lặng

  await t.sendMail({
    from: process.env.MAIL_FROM || process.env.SMTP_USER,
    to,
    subject: `[SecretGuard] Commit bị chặn tại ${scan.projectName} (${scan.findings.length} secret)`,
    html: buildHtml(scan),
  });
}

module.exports = { notifyBlockedScan };