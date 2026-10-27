import RiskBadge from '../ui/RiskBadge.jsx';
import { getRiskMeta } from '../../constants/risk.js';
import { formatConfidence, shortPath } from '../../utils/format.js';

function ConfidenceBar({ score }) {
  const pct = Math.max(0, Math.min(100, Number(score) * 100 || 0));
  return (
    <span className="inline-flex items-center gap-3">
      <span className="h-1.5 w-20 overflow-hidden rounded-full bg-field">
        <span
          className="block h-full rounded-full bg-linear-to-r from-brand-violet to-brand-sky"
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="text-sm text-fg">{formatConfidence(score)}</span>
    </span>
  );
}

const COLUMNS = ['Mức độ', 'Loại secret', 'File', 'Dòng', 'Độ tin cậy'];

export default function FindingsTable({ findings }) {
  const sorted = [...findings].sort(
    (a, b) =>
      getRiskMeta(b.risk_level).rank - getRiskMeta(a.risk_level).rank ||
      a.file_path?.localeCompare(b.file_path ?? '') ||
      a.line_number - b.line_number,
  );

  return (
    <section className="rounded-2xl border border-rim/70 bg-panel/60 p-5 backdrop-blur-sm">
      <h2 className="text-xl font-semibold text-fg">
        Findings <span className="text-fg-muted">({findings.length})</span>
      </h2>
      <p className="mt-1 text-sm text-fg-muted">
        Giá trị secret không được lưu và không hiển thị, chỉ ghi nhận vị trí phát hiện.
      </p>

      {findings.length === 0 ? (
        <div className="px-5 py-10 text-center text-sm text-fg-muted">
          Lần quét này không có finding nào.
        </div>
      ) : (
        <div className="mt-5 overflow-x-auto rounded-xl border border-rim/50">
          <table className="w-full min-w-[680px] text-left">
            <thead>
              <tr className="bg-thead text-sm text-fg">
                {COLUMNS.map((col) => (
                  <th key={col} scope="col" className="px-5 py-4 font-semibold">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((f) => (
                <tr key={f.id} className="border-t border-rim/50 hover:bg-white/[0.03]">
                  <td className="px-5 py-3">
                    <RiskBadge level={f.risk_level} />
                  </td>
                  <td className="px-5 py-3 text-[15px] text-fg">{f.secret_type}</td>
                  <td className="px-5 py-3">
                    <span title={f.file_path} className="font-mono text-sm text-fg">
                      {shortPath(f.file_path)}
                    </span>
                  </td>
                  <td className="px-5 py-3 font-mono text-[15px] text-fg">{f.line_number}</td>
                  <td className="px-5 py-3">
                    <ConfidenceBar score={f.confidence_score} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
