const STATUS_MAP = {
  blocked: { label: 'Blocked', color: 'text-critical', dot: 'bg-critical' },
  warned: { label: 'Warned', color: 'text-warn', dot: 'bg-warn' },
  passed: { label: 'Passed', color: 'text-safe', dot: 'bg-safe' },
};

export function StatusBadge({ status }) {
  const meta = STATUS_MAP[status] || { label: status, color: 'text-muted', dot: 'bg-muted' };

  return (
    <span className={`inline-flex items-center gap-1.5 text-sm ${meta.color}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
      {meta.label}
    </span>
  );
}

export function StatCard({ label, value, accent }) {
  return (
    <div className="border border-line bg-surface px-5 py-4">
      <div className="text-sm text-muted">{label}</div>
      <div className={`mt-2 font-mono text-3xl ${accent || 'text-text'}`}>{value}</div>
    </div>
  );
}