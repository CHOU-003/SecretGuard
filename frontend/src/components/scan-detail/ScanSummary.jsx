import StatusBadge from '../ui/StatusBadge.jsx';
import CopyButton from '../dashboard/CopyButton.jsx';
import { BranchIcon } from '../common/icons.jsx';
import { getTriggerLabel } from '../../constants/triggers.js';
import { formatDateTime } from '../../utils/format.js';

function Meta({ label, children }) {
  return (
    <div>
      <dt className="text-sm text-fg-muted">{label}</dt>
      <dd className="mt-1.5 text-[15px] font-medium text-fg">{children}</dd>
    </div>
  );
}

export default function ScanSummary({ scan }) {
  return (
    <section className="rounded-2xl border border-rim/70 bg-panel/60 p-6 backdrop-blur-sm">
      <div className="flex flex-wrap items-center gap-4">
        <StatusBadge status={scan.status} />
        <span className="inline-flex items-center gap-2 break-all font-mono text-lg text-fg">
          {scan.commit_hash ?? 'Không gắn với commit nào'}
          {scan.commit_hash && <CopyButton value={scan.commit_hash} label="Sao chép commit" />}
        </span>
      </div>

      <dl className="mt-6 grid gap-x-8 gap-y-5 sm:grid-cols-2 xl:grid-cols-4">
        <Meta label="Project">{scan.project_name ?? '—'}</Meta>
        <Meta label="Branch">
          {scan.branch ? (
            <span className="inline-flex items-center gap-2 rounded-full bg-[#14246a]/80 px-3 py-1 text-sm">
              <BranchIcon className="h-4 w-4 text-brand-sky" />
              {scan.branch}
            </span>
          ) : (
            '—'
          )}
        </Meta>
        <Meta label="Nguồn kích hoạt">{getTriggerLabel(scan.trigger_type)}</Meta>
        <Meta label="Thời gian">{formatDateTime(scan.created_at)}</Meta>
      </dl>
    </section>
  );
}
