import { Link } from 'react-router-dom';
import StatusBadge from '../ui/StatusBadge.jsx';
import StatusGlyph from '../ui/StatusGlyph.jsx';
import CopyButton from './CopyButton.jsx';
import { BranchIcon, CalendarIcon, ChevronRightIcon } from '../common/icons.jsx';
import { TONES, getFindingsTone } from '../../constants/status.js';
import { formatDateTime, shortHash } from '../../utils/format.js';

export default function ScanRow({ scan }) {
  const findingsTone = getFindingsTone(scan);
  const detailPath = `/scans/${scan.id}`;

  return (
    <tr className="border-t border-rim/50 transition-colors hover:bg-white/[0.03]">
      <td className="px-5 py-3">
        <StatusBadge status={scan.status} />
      </td>

      <td className="px-5 py-3">
        <span className="inline-flex items-center gap-2 font-mono text-[15px] text-fg">
          {scan.commit_hash ? (
            <Link
              to={detailPath}
              className="underline-offset-4 transition hover:text-brand-sky hover:underline"
            >
              {shortHash(scan.commit_hash)}
            </Link>
          ) : (
            '—'
          )}
          {scan.commit_hash && <CopyButton value={scan.commit_hash} label="Sao chép commit" />}
        </span>
      </td>

      <td className="px-5 py-3">
        {scan.branch ? (
          <span className="inline-flex items-center gap-2 rounded-full bg-[#14246a]/80 px-3 py-1 text-sm text-fg">
            <BranchIcon className="h-4 w-4 text-brand-sky" />
            {scan.branch}
          </span>
        ) : (
          <span className="text-fg-muted">—</span>
        )}
      </td>

      <td className="px-5 py-3">
        <span className={`inline-flex items-center gap-2 font-semibold ${TONES[findingsTone].text}`}>
          <StatusGlyph
            tone={findingsTone}
            icon={findingsTone === 'ok' ? 'check' : 'alert'}
            className="h-6 w-6"
          />
          {scan.total_findings ?? 0}
        </span>
      </td>

      <td className="px-5 py-3">
        <span className="inline-flex items-center gap-2.5 text-[15px] text-fg">
          <CalendarIcon className="h-5 w-5 text-brand-sky/80" />
          {formatDateTime(scan.created_at)}
        </span>
      </td>

      <td className="px-3 py-3 text-right">
        <Link
          to={detailPath}
          aria-label="Xem chi tiết scan"
          title="Xem chi tiết"
          className="inline-grid h-9 w-9 place-items-center rounded-lg text-fg-muted transition hover:bg-white/5 hover:text-fg"
        >
          <ChevronRightIcon className="h-5 w-5" />
        </Link>
      </td>
    </tr>
  );
}
