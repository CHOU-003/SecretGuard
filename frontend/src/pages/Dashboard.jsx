import DashboardLayout from '../components/layout/DashboardLayout.jsx';
import StatsGrid from '../components/dashboard/StatsGrid.jsx';
import ScanHistory from '../components/dashboard/ScanHistory.jsx';
import Alert from '../components/common/Alert.jsx';
import { useDashboardData } from '../hooks/useDashboardData.js';

export default function Dashboard() {
  const { scans, stats, loading, error } = useDashboardData();

  return (
    <DashboardLayout>
      <Alert>
        {error &&
          `Không tải được dữ liệu: ${error}. Kiểm tra route /api/scans và /api/stats/overview ở backend đã được tạo chưa.`}
      </Alert>
      <StatsGrid stats={stats} scans={scans} loading={loading} />
      <ScanHistory scans={scans} loading={loading} />
    </DashboardLayout>
  );
}