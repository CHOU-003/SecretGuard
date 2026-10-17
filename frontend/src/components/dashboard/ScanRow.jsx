import StatusBadge from '../ui/StatusBadge.jsx';
import StatusGlyph from '../ui/StatusGlyph.jsx';
import CopyButton from './CopyButton.jsx';
import { BranchIcon, CalendarIcon } from '../common/icons.jsx';
import { TONES, getFindingsTone } from '../../constants/status.js';
import { formatDateTime, shortHash } from '../../utils/format.js';

export default function ScanRow({ scan }) {
  const findingsTone = getFindingsTone(scan);

  return (
    <tr className="border-t border-rim/50 transition-colors hover:bg-white/3">
      <td className="px-5 py-3">
        <StatusBadge status={scan.status} />
      </td>

      <td className="px-5 py-3">
        <span className="inline-flex items-center gap-2 font-mono text-[15px] text-fg">
          {shortHash(scan.commit_hash)}
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
    </tr>
  );
}
