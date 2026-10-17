import { TONES } from '../../constants/status.js';
import { ExclamationIcon, CheckIcon } from '../common/icons.jsx';

const ICONS = { alert: ExclamationIcon, check: CheckIcon };

export default function StatusGlyph({ tone = 'neutral', icon = 'alert', className = 'h-6 w-6' }) {
  const Icon = ICONS[icon] ?? ExclamationIcon;
  return (
    <span
      className={`grid shrink-0 place-items-center rounded-full text-white ${TONES[tone].solid} ${className}`}
    >
      <Icon className="h-3.5 w-3.5" strokeWidth="2.6" />
    </span>
  );
}
