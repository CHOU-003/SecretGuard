import StatusGlyph from '../ui/StatusGlyph.jsx';
import { TONES } from '../../constants/status.js';

function describe(scan, count) {
  const threshold = scan.risk_threshold ?? '—';
  if (count === 0) {
    return { tone: 'ok', icon: 'check', text: 'Không phát hiện secret nào trong lần quét này.' };
  }
  if (scan.status === 'blocked') {
    return {
      tone: 'danger',
      icon: 'alert',
      text: `Commit bị chặn: phát hiện ${count} secret, ngưỡng chặn của project là "${threshold}".`,
    };
  }
  if (scan.status === 'warned') {
    return {
      tone: 'caution',
      icon: 'alert',
      text: `Phát hiện ${count} secret nhưng dưới ngưỡng chặn ("${threshold}") nên chỉ cảnh báo.`,
    };
  }
  return { tone: 'neutral', icon: 'alert', text: `Có ${count} finding được ghi nhận.` };
}

export default function ScanVerdict({ scan, findings }) {
  const { tone, icon, text } = describe(scan, findings.length);

  return (
    <div className={`flex items-center gap-3 rounded-xl border px-5 py-4 ${TONES[tone].badge}`}>
      <StatusGlyph tone={tone} icon={icon} />
      <p className="text-[15px] font-medium">{text}</p>
    </div>
  );
}
