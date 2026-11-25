import { useState } from 'react';
import { apiFetch } from '../api/client';
import { useProjects } from '../hooks/useProjects';
import DashboardLayout from '../components/layout/DashboardLayout.jsx';

const THRESHOLDS = [
  { value: 'medium', label: 'Medium (chặn từ MEDIUM trở lên)' },
  { value: 'high', label: 'High (chỉ chặn HIGH)' },
];

const selectCls =
  'field-select rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white ' +
  'focus:border-[#4a76ff] focus:outline-none';

function formatDate(value) {
  if (!value) return 'Chưa có scan';
  return new Date(value).toLocaleString('vi-VN');
}

export default function Projects() {
  const { projects, loading, error, reload } = useProjects();
  const [drafts, setDrafts] = useState({}); // { [projectId]: giá trị đang chọn }
  const [savingId, setSavingId] = useState(null);
  const [message, setMessage] = useState(null); // { type: 'ok' | 'error', text }

  async function save(project) {
    const next = drafts[project.id];
    setSavingId(project.id);
    setMessage(null);
    try {
      await apiFetch(`/api/projects/${project.id}/threshold`, {
        method: 'PUT',
        body: JSON.stringify({ risk_threshold: next }),
      });
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[project.id];
        return next;
      });
      await reload();
      setMessage({ type: 'ok', text: `Đã đổi ngưỡng của "${project.name}" sang ${next}.` });
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setSavingId(null);
    }
  }

  return (
    <DashboardLayout>
      <section className="space-y-5">
        <div>
          <h2 className="text-2xl font-bold text-white">Quản lý project</h2>
          <p className="text-sm text-white/60">
            Xem hoạt động quét của từng project và chỉnh ngưỡng chặn commit.
          </p>
        </div>

        {error && (
          <p className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</p>
        )}
        {message && (
          <p
            className={`rounded-lg border px-4 py-3 text-sm ${
              message.type === 'ok'
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                : 'border-red-500/40 bg-red-500/10 text-red-300'
            }`}
          >
            {message.text}
          </p>
        )}

        <div className="overflow-x-auto rounded-2xl border border-white/10">
          <table className="w-full min-w-205 text-left text-sm">
            <thead className="bg-[#0f1d52] text-white">
              <tr>
                <th className="px-5 py-4 font-semibold">Project</th>
                <th className="px-5 py-4 font-semibold">Tổng scan</th>
                <th className="px-5 py-4 font-semibold">Blocked</th>
                <th className="px-5 py-4 font-semibold">Lần quét gần nhất</th>
                <th className="px-5 py-4 font-semibold">Ngưỡng chặn</th>
                <th className="px-5 py-4" />
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-white/90">
              {loading && (
                <tr><td colSpan={6} className="px-5 py-10 text-center text-white/60">Đang tải…</td></tr>
              )}
              {!loading && projects.length === 0 && (
                <tr><td colSpan={6} className="px-5 py-10 text-center text-white/60">Chưa có project nào.</td></tr>
              )}
              {projects.map((p) => {
                const current = drafts[p.id] ?? p.risk_threshold ?? 'high';
                const dirty = current !== (p.risk_threshold ?? 'high') || p.risk_threshold == null;
                return (
                  <tr key={p.id}>
                    <td className="px-5 py-4 font-medium text-white">{p.name}</td>
                    <td className="px-5 py-4">{p.total_scans}</td>
                    <td className="px-5 py-4 text-red-300">{p.blocked_scans}</td>
                    <td className="px-5 py-4">{formatDate(p.last_scan_at)}</td>
                    <td className="px-5 py-4">
                      <select
                        className={selectCls}
                        value={current}
                        onChange={(e) => setDrafts((d) => ({ ...d, [p.id]: e.target.value }))}
                      >
                        {THRESHOLDS.map((t) => (
                          <option key={t.value} value={t.value}>{t.label}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-5 py-4 text-right">
                      <button
                        onClick={() => save(p)}
                        disabled={!dirty || savingId === p.id}
                        className="rounded-lg bg-nav px-4 py-2 text-sm font-medium text-white transition hover:bg-[#4a76ff] disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {savingId === p.id ? 'Đang lưu…' : 'Lưu'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </DashboardLayout>
  );
}