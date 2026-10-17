import { useId } from 'react';
import ShieldMark from '../common/ShieldMark.jsx';

export default function SidebarPromo() {
  const gradientId = useId();

  return (
    <div className="relative overflow-hidden rounded-2xl border border-rim bg-linear-to-b from-[#0d1f6b] to-[#07123d] px-5 pb-16 pt-6 text-center">
      <ShieldMark className="mx-auto h-16 w-auto drop-shadow-[0_0_16px_rgba(90,110,255,0.7)]" />
      <p className="mt-4 text-sm font-semibold leading-snug text-fg">
        Bảo vệ mã nguồn
        <br />
        trước khi triển khai
      </p>
      <p className="mt-2 text-xs text-fg-muted">Phát hiện secret, ngăn chặn rủi ro.</p>
      <svg viewBox="0 0 240 70" className="absolute inset-x-0 bottom-0 w-full" aria-hidden="true">
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#6a5cff" />
            <stop offset="1" stopColor="#1a2a9a" />
          </linearGradient>
        </defs>
        <path d="M0 70 L50 32 L82 52 L125 12 L180 56 L212 36 L240 60 V70Z" fill={`url(#${gradientId})`} opacity="0.65" />
        <path d="M0 70 L40 48 L90 66 L150 40 L240 70Z" fill={`url(#${gradientId})`} opacity="0.5" />
      </svg>
    </div>
  );
}