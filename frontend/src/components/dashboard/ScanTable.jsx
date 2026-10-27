import ScanRow from './ScanRow.jsx';

const COLUMNS = ['Trạng thái', 'Commit', 'Branch', 'Số findings', 'Thời gian'];

export default function ScanTable({ scans }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-rim/50">
      <table className="w-full min-w-[760px] text-left">
        <thead>
          <tr className="bg-thead text-sm text-fg">
            {COLUMNS.map((col) => (
              <th key={col} scope="col" className="px-5 py-4 font-semibold">
                {col}
              </th>
            ))}
            <th scope="col" className="w-14 px-3 py-4">
              <span className="sr-only">Chi tiết</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {scans.map((scan) => (
            <ScanRow key={scan.id} scan={scan} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
