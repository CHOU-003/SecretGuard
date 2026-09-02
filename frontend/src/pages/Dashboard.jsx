import { useEffect, useState } from 'react';
import { apiFetch } from '../api/client';
import DashboardLayout from '../components/layout/DashboardLayout.jsx';
import { StatCard, StatusBadge } from '../components/ui/index.jsx';

export default function Dashboard() {
  const [scans, setScans] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const [scansData, statsData] = await Promise.all([
          apiFetch('/api/scans'),
          apiFetch('/api/stats'),
        ]);
        if (!cancelled) {
          setScans(scansData.scans || scansData || []);
          setStats(statsData);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <DashboardLayout title="Tổng quan">
      {error && (
        <div className="mb-6 border border-critical/40 bg-critical/10 px-4 py-3 text-sm text-critical">
          Không tải được dữ liệu: {error}. Kiểm tra route{' '}
          <code className="font-mono">/api/scans</code> và{' '}
          <code className="font-mono">/api/stats</code> ở backend đã được tạo chưa.
        </div>
      )}

      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Tổng số scan" value={stats?.total_scans ?? '—'} />
        <StatCard label="Blocked" value={stats?.blocked ?? '—'} accent="text-critical" />
        <StatCard label="Warned" value={stats?.warned ?? '—'} accent="text-warn" />
        <StatCard label="Passed" value={stats?.passed ?? '—'} accent="text-safe" />
      </div>

      <div className="border border-line bg-surface">
        <div className="border-b border-line px-5 py-3 text-sm text-muted">
          Lịch sử scan gần đây
        </div>

        {loading ? (
          <div className="px-5 py-8 text-center text-sm text-muted">Đang tải...</div>
        ) : scans.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-muted">
            Chưa có scan nào được ghi nhận.
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line text-muted">
                <th className="px-5 py-2.5 font-normal">Trạng thái</th>
                <th className="px-5 py-2.5 font-normal">Commit</th>
                <th className="px-5 py-2.5 font-normal">Branch</th>
                <th className="px-5 py-2.5 font-normal">Số finding</th>
                <th className="px-5 py-2.5 font-normal">Thời gian</th>
              </tr>
            </thead>
            <tbody>
              {scans.map((scan) => (
                <tr key={scan.id} className="border-b border-line last:border-0">
                  <td className="px-5 py-3">
                    <StatusBadge status={scan.status} />
                  </td>
                  <td className="px-5 py-3 font-mono text-muted">
                    {scan.commit_hash ? scan.commit_hash.slice(0, 10) : '—'}
                  </td>
                  <td className="px-5 py-3 font-mono text-text">{scan.branch || '—'}</td>
                  <td className="px-5 py-3 text-text">{scan.total_findings}</td>
                  <td className="px-5 py-3 text-muted">
                    {new Date(scan.created_at).toLocaleString('vi-VN')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </DashboardLayout>
  );
}