import { useEffect, useState } from 'react';
import { apiFetch } from '../api/client';
import { useScanHistory } from '../hooks/useScanHistory';
import ScanTable from '../components/dashboard/ScanTable.jsx';
import DashboardLayout from '../components/layout/DashboardLayout.jsx';
import { apiDownload } from '../api/client';
import { Download } from 'lucide-react';

const EMPTY = { q: '', status: '', branch: '', trigger_type: '', from: '', to: '' };

const inputCls =
  'rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white ' +
  'placeholder:text-white/40 focus:border-[#4a76ff] focus:outline-none';

export default function History() {
  const [filters, setFilters] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const [branches, setBranches] = useState([]);
  const { scans, pagination, loading, error } = useScanHistory(filters, page);

  const selectCls = `${inputCls} field-select`;
  const dateCls = `${inputCls} field-date`;

  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');

  useEffect(() => {
    apiFetch('/api/scans/branches')
      .then((r) => setBranches(r.branches ?? []))
      .catch(() => {});
  }, []);

  function setFilter(name, value) {
    setFilters((f) => ({ ...f, [name]: value }));
    setPage(1); // đổi filter thì quay về trang 1
  }

  async function handleExport() {
    setExporting(true);
    setExportError('');
    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => v && params.set(k, v));
      const date = new Date().toISOString().slice(0, 10);
      await apiDownload(`/api/scans/export?${params}`, `scans_${date}.csv`);
    } catch (err) {
      setExportError(err.message);
    } finally {
      setExporting(false);
    }
  }

  const hasFilter = Object.values(filters).some(Boolean);

  return (
    <DashboardLayout>
      <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white">Lịch sử quét</h2>
          <p className="text-sm text-white/60">Toàn bộ các lần quét, có lọc và phân trang.</p>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting || !pagination || pagination.total === 0}
          className="inline-flex items-center gap-2 rounded-lg bg-nav px-4 py-2 text-sm font-medium text-white transition hover:bg-[#4a76ff] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {exporting ? 'Đang xuất…' : 'Xuất CSV'}
          <Download size={16} className="text-white" />
        </button>
      </div>
      {exportError && (
        <p className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">{exportError}</p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <input
          className={`${inputCls} min-w-64 flex-1`}
          placeholder="Tìm theo commit, branch…"
          value={filters.q}
          onChange={(e) => setFilter('q', e.target.value)}
        />
        <select className={selectCls} value={filters.status} onChange={(e) => setFilter('status', e.target.value)}>
          <option value="">Mọi trạng thái</option>
          <option value="passed">Passed</option>
          <option value="warned">Warned</option>
          <option value="blocked">Blocked</option>
        </select>
        <select className={selectCls} value={filters.branch} onChange={(e) => setFilter('branch', e.target.value)}>
          <option value="">Mọi branch</option>
          {branches.map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
        <input type="date" className={dateCls} value={filters.from} max={filters.to || undefined}
          onChange={(e) => setFilter('from', e.target.value)} />
        <span className="text-white/40">→</span>
        <input type="date" className={dateCls} value={filters.to} min={filters.from || undefined}
          onChange={(e) => setFilter('to', e.target.value)} />
        {hasFilter && (
          <button className="text-sm text-[#58b0ff] hover:underline"
            onClick={() => { setFilters(EMPTY); setPage(1); }}>
            Xoá bộ lọc
          </button>
        )}
      </div>

      {error && <p className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</p>}

      <div className={loading ? 'opacity-60 transition-opacity' : 'transition-opacity'}>
        {!loading && scans.length === 0 ? (
          <p className="py-16 text-center text-white/60">Không có lần quét nào khớp bộ lọc.</p>
        ) : (
          <ScanTable scans={scans} />
        )}
      </div>

      {pagination && pagination.total > 0 && (
        <div className="flex items-center justify-between text-sm text-white/70">
          <span>
            {(pagination.page - 1) * pagination.limit + 1}–
            {Math.min(pagination.page * pagination.limit, pagination.total)} / {pagination.total} lần quét
          </span>
          <div className="flex items-center gap-2">
            <button className={inputCls} disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>← Trước</button>
            <span>Trang {pagination.page}/{pagination.totalPages}</span>
            <button className={inputCls} disabled={page >= pagination.totalPages} onClick={() => setPage((p) => p + 1)}>Sau →</button>
          </div>
        </div>
      )}
     </section>
    </DashboardLayout>
  );
}

