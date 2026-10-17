import StatCard from '../ui/StatCard.jsx';
import { TargetIcon, ShieldPlusIcon, WarningIcon, CheckIcon } from '../common/icons.jsx';
import { dailyCounts } from '../../utils/scanStats.js';

const CARDS = [
  { key: 'total', label: 'Tổng số scan', statKey: 'total_scans', icon: TargetIcon, theme: 'scan', match: () => true },
  { key: 'blocked', label: 'Blocked', statKey: 'blocked', icon: ShieldPlusIcon, theme: 'blocked', match: (s) => s.status === 'blocked' },
  { key: 'warned', label: 'Warned', statKey: 'warned', icon: WarningIcon, theme: 'warned', match: (s) => s.status === 'warned' },
  { key: 'passed', label: 'Passed', statKey: 'passed', icon: CheckIcon, theme: 'passed', match: (s) => s.status === 'passed' },
];

export default function StatsGrid({ stats, scans, loading }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {CARDS.map(({ key, label, statKey, icon, theme, match }) => {
        // Biểu đồ + "hôm nay" tính từ danh sách scan đã tải (7 ngày gần nhất)
        const series = dailyCounts(scans, match);
        return (
          <StatCard
            key={key}
            label={label}
            value={stats?.[statKey] ?? '—'}
            icon={icon}
            theme={theme}
            series={series}
            delta={loading ? null : series[series.length - 1]}
          />
        );
      })}
    </div>
  );
}