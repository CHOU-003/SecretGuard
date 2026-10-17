export function formatDateTime(value) {
  return value ? new Date(value).toLocaleString('vi-VN') : '—';
}

export function shortHash(hash, length = 10) {
  return hash ? hash.slice(0, length) : '—';
}

export function capitalize(text = '') {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : '';
}
