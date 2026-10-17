// Màu theo "tone" -> dùng chung cho badge, icon findings...
export const TONES = {
  danger: { text: 'text-danger', solid: 'bg-danger', badge: 'border-danger/35 bg-danger/15 text-danger' },
  caution: { text: 'text-caution', solid: 'bg-caution', badge: 'border-caution/35 bg-caution/15 text-caution' },
  ok: { text: 'text-ok', solid: 'bg-ok', badge: 'border-ok/35 bg-ok/15 text-ok' },
  neutral: { text: 'text-fg-muted', solid: 'bg-fg-muted/60', badge: 'border-field bg-field/30 text-fg-muted' },
};

export const SCAN_STATUS = {
  blocked: { label: 'Blocked', tone: 'danger', icon: 'alert' },
  warned: { label: 'Warned', tone: 'caution', icon: 'alert' },
  passed: { label: 'Passed', tone: 'ok', icon: 'check' },
};

export function getStatusMeta(status) {
  return SCAN_STATUS[status] ?? { label: status ?? '—', tone: 'neutral', icon: 'alert' };
}

export function getFindingsTone(scan) {
  if (!scan.total_findings) return 'ok';
  return scan.status === 'warned' ? 'caution' : 'danger';
}
