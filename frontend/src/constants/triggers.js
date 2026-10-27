// Giá trị cột scans.trigger_type -> nhãn hiển thị (không có thì hiện nguyên giá trị)
export const TRIGGER_LABELS = {
  local_precommit: 'Pre-commit (máy cục bộ)',
};

export function getTriggerLabel(type) {
  return TRIGGER_LABELS[type] ?? type ?? '—';
}
