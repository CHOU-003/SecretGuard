export function formatDateTime(value) {
  return value ? new Date(value).toLocaleString('vi-VN') : '—';
}

export function shortHash(hash, length = 10) {
  return hash ? hash.slice(0, length) : '—';
}

export function capitalize(text = '') {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : '';
}

// 0.999 -> "99.9%", 0.91 -> "91%"
export function formatConfidence(score) {
  const n = Number(score);
  return Number.isFinite(n) ? `${Number((n * 100).toFixed(1))}%` : '—';
}

// "C:\\Users\\Acer\\Doc\\app\\src\\config.js" -> "…/app/src/config.js"
export function shortPath(path, segments = 3) {
  if (!path) return '—';
  const parts = path.replace(/\\/g, '/').split('/').filter(Boolean);
  return parts.length > segments ? `…/${parts.slice(-segments).join('/')}` : parts.join('/');
}
