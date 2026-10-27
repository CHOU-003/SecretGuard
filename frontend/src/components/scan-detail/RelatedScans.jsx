import { Link } from 'react-router-dom';
import StatusBadge from '../ui/StatusBadge.jsx';
import { formatDateTime } from '../../utils/format.js';

export default function RelatedScans({ scans }) {
  if (!scans?.length) return null;

  return (
    <section className="rounded-2xl border border-rim/70 bg-panel/60 p-5 backdrop-blur-sm">
      <h2 className="text-xl font-semibold text-fg">Các lần quét khác của commit này</h2>
      <ul className="mt-4 space-y-1">
        {scans.map((s) => (
          <li key={s.id}>
            <Link
              to={`/scans/${s.id}`}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl px-3 py-2.5 transition hover:bg-white/5"
            >
              <StatusBadge status={s.status} />
              <span className="text-sm text-fg-muted">{formatDateTime(s.created_at)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
