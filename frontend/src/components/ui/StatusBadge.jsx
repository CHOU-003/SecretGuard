import { TONES, getStatusMeta } from '../../constants/status.js';
import StatusGlyph from './StatusGlyph.jsx';

export default function StatusBadge({ status }) {
  const { label, tone, icon } = getStatusMeta(status);

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border py-1 pl-1.5 pr-4 text-sm font-semibold ${TONES[tone].badge}`}
    >
      <StatusGlyph tone={tone} icon={icon} />
      {label}
    </span>
  );
}
