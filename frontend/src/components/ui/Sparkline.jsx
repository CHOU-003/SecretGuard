import { useId } from 'react';

export default function Sparkline({ data, color, className = '' }) {
  const gradientId = useId();
  const w = 120;
  const h = 48;
  const pad = 4;
  const max = Math.max(...data, 1);
  const step = (w - pad * 2) / (data.length - 1);
  const points = data.map((v, i) => [pad + i * step, h - pad - (v / max) * (h - pad * 2)]);
  const line = points.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const area = `${line} L${points[points.length - 1][0]} ${h} L${points[0][0]} ${h} Z`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.35" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradientId})`} />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
