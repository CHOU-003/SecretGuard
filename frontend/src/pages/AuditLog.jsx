import { useEffect, useState } from 'react';
import { apiFetch } from '../api/client';
import { useAuditLog } from '../hooks/useAuditLog';
import DashboardLayout from '../components/layout/DashboardLayout.jsx';

const ACTIONS = {
  threshold_changed: 'Đổi ngưỡng chặn',
};

const selectCls =
  'field-select rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white ' +
  'focus:border-[#4a76ff] focus:outline-none';
const btnCls =
  'rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white ' +
  'transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40';

const VALUE_TONE = {
  high: 'bg-red-500/15 text-red-300 border-red-500/40',
  medium: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
};

function ValueBadge({ value }) {
  if (value == null || value === '') return <span className="text-white/40">—</span>;
  const tone = VALUE_TONE[String(value).toLowerCase()] ?? 'bg-white/5 text-white/80 border-white/15';
  return (
    <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase ${tone}`}>
      {value}
    </span>
  );
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString('vi-VN') : '—';
}

export default function AuditLog() {
  const [filters, setFilters] = useState({ project_id: '', action: '' });
  const [page, setPage] = useState(1);
  const [projects, setProjects] = useState([]);
  const { logs, pagination, loading, error } = useAuditLog(filters, page);

  useEffect(() => {
    apiFetch('/api/projects')
      .then((r) => setProjects(r.projects ?? []))
      .catch(() => {});
  }, []);

  function setFilter(name, value) {
    setFilters((f) => ({ ...f, [name]: value }));
    setPage(1);
  }

  const hasFilter = Object.values(filters).some(Boolean);

  return (
    <DashboardLayout>
      <section className="space-y-5">
        <div>
          <h2 className="text-2xl font-bold text-white">Nhật ký thay đổi</h2>
          <p className="text-sm text-white/60">Ai đã đổi cấu hình nào, vào lúc nào, từ giá trị nào sang giá trị nào.</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select className={selectCls} value={filters.project_id} onChange={(e) => setFilter('project_id', e.target.value)}>
            <option value="">Mọi project</option>
            {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <select className={selectCls} value={filters.action} onChange={(e) => setFilter('action', e.target.value)}>
            <option value="">Mọi hành động</option>
            {Object.entries(ACTIONS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          {hasFilter && (
            <button
              className="text-sm text-[#58b0ff] hover:underline"
              onClick={() => { setFilters({ project_id: '', action: '' }); setPage(1); }}
            >
              Xoá bộ lọc
            </button>
          )}
        </div>

        {error && (
          <p className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</p>
        )}

        <div className={`overflow-x-auto rounded-2xl border border-white/10 transition-opacity ${loading ? 'opacity-60' : ''}`}>
          <table className="w-full min-w-195 text-left text-sm">
            <thead className="bg-[#0f1d52] text-white">
              <tr>
                <th className="px-5 py-4 font-semibold">Thời gian</th>
                <th className="px-5 py-4 font-semibold">Người thực hiện</th>
                <th className="px-5 py-4 font-semibold">Project</th>
                <th className="px-5 py-4 font-semibold">Hành động</th>
                <th className="px-5 py-4 font-semibold">Thay đổi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-white/90">
              {!loading && logs.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-14 text-center text-white/60">
                    {hasFilter ? 'Không có bản ghi nào khớp bộ lọc.' : 'Chưa có thay đổi nào được ghi lại.'}
                  </td>
                </tr>
              )}
              {logs.map((log) => (
                <tr key={log.id}>
                  <td className="whitespace-nowrap px-5 py-4">{formatDate(log.changed_at)}</td>
                  <td className="px-5 py-4 font-medium text-white">{log.username ?? <span className="text-white/40">Không rõ</span>}</td>
                  <td className="px-5 py-4">{log.project_name ?? <span className="text-white/40">—</span>}</td>
                  <td className="px-5 py-4">{ACTIONS[log.action] ?? log.action}</td>
                  <td className="px-5 py-4">
                    <span className="inline-flex items-center gap-2">
                      <ValueBadge value={log.old_value} />
                      <span className="text-white/50">→</span>
                      <ValueBadge value={log.new_value} />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {pagination && pagination.total > 0 && (
          <div className="flex items-center justify-between text-sm text-white/70">
            <span>
              {(pagination.page - 1) * pagination.limit + 1}–
              {Math.min(pagination.page * pagination.limit, pagination.total)} / {pagination.total} bản ghi
            </span>
            <div className="flex items-center gap-2">
              <button className={btnCls} disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>← Trước</button>
              <span>Trang {pagination.page}/{pagination.totalPages}</span>
              <button className={btnCls} disabled={page >= pagination.totalPages} onClick={() => setPage((p) => p + 1)}>Sau →</button>
            </div>
          </div>
        )}
      </section>
    </DashboardLayout>
  );
}