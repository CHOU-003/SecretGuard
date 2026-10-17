import { useMemo, useState } from 'react';
import ScanTable from './ScanTable.jsx';
import ScanToolbar from './ScanToolbar.jsx';
import { ClockIcon } from '../common/icons.jsx';
import { filterScans } from '../../utils/scanStats.js';

function EmptyState({ children }) {
  return <div className="px-5 py-10 text-center text-sm text-fg-muted">{children}</div>;
}

export default function ScanHistory({ scans, loading }) {
  const [query, setQuery] = useState('');
  const [range, setRange] = useState('all');
  const visible = useMemo(() => filterScans(scans, { query, range }), [scans, query, range]);

  let body;
  if (loading) body = <EmptyState>Đang tải...</EmptyState>;
  else if (scans.length === 0) body = <EmptyState>Chưa có scan nào được ghi nhận.</EmptyState>;
  else if (visible.length === 0) body = <EmptyState>Không có scan nào khớp bộ lọc.</EmptyState>;
  else body = <ScanTable scans={visible} />;

  return (
    <section className="rounded-2xl border border-rim/70 bg-panel/60 p-5 backdrop-blur-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-4">
          <ClockIcon className="h-10 w-10 shrink-0 text-brand-sky" />
          <div>
            <h2 className="text-xl font-semibold text-fg">Lịch sử scan gần đây</h2>
            <p className="text-sm text-fg-muted">Danh sách các lần quét mã nguồn gần nhất của bạn</p>
          </div>
        </div>
        <ScanToolbar query={query} onQueryChange={setQuery} range={range} onRangeChange={setRange} />
      </div>

      <div className="mt-5">{body}</div>
    </section>
  );
}