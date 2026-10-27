import { Link, useParams } from 'react-router-dom';
import DashboardLayout from '../components/layout/DashboardLayout.jsx';
import Alert from '../components/common/Alert.jsx';
import { ArrowLeftIcon } from '../components/common/icons.jsx';
import ScanSummary from '../components/scan-detail/ScanSummary.jsx';
import ScanVerdict from '../components/scan-detail/ScanVerdict.jsx';
import FindingsTable from '../components/scan-detail/FindingsTable.jsx';
import RemediationGuide from '../components/scan-detail/RemediationGuide.jsx';
import RelatedScans from '../components/scan-detail/RelatedScans.jsx';
import { useScanDetail } from '../hooks/useScanDetail.js';

export default function ScanDetail() {
  const { id } = useParams();
  const { data, loading, error } = useScanDetail(id);

  return (
    <DashboardLayout>
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-sm text-fg-muted transition hover:text-fg"
      >
        <ArrowLeftIcon className="h-4 w-4" />
        Quay lại tổng quan
      </Link>

      <Alert>{error && `Không tải được chi tiết scan: ${error}`}</Alert>
      {loading && <p className="text-sm text-fg-muted">Đang tải...</p>}

      {data && (
        <>
          <ScanSummary scan={data.scan} />
          <ScanVerdict scan={data.scan} findings={data.findings ?? []} />

          <div className="grid items-start gap-6 xl:grid-cols-[1fr_360px]">
            <FindingsTable findings={data.findings ?? []} />
            <div className="space-y-6">
              <RemediationGuide findings={data.findings ?? []} />
              <RelatedScans scans={data.related_scans} />
            </div>
          </div>
        </>
      )}
    </DashboardLayout>
  );
}
