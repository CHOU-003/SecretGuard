export const RISK_LEVELS = {
  critical: { label: 'Critical', tone: 'danger', rank: 4 },
  high: { label: 'High', tone: 'danger', rank: 3 },
  medium: { label: 'Medium', tone: 'caution', rank: 2 },
  low: { label: 'Low', tone: 'neutral', rank: 1 },
};

export function getRiskMeta(level) {
  return (
    RISK_LEVELS[String(level ?? '').toLowerCase()] ?? {
      label: level ?? '—',
      tone: 'neutral',
      rank: 0,
    }
  );
}
