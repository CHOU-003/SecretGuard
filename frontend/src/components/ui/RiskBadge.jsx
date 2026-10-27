import { TONES } from '../../constants/status.js';
import { getRiskMeta } from '../../constants/risk.js';

export default function RiskBadge({ level }) {
  const { label, tone } = getRiskMeta(level);
  return (
    <span
      className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide ${TONES[tone].badge}`}
    >
      {label}
    </span>
  );
}
