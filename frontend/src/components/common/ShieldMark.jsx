import { useId } from 'react';

export default function ShieldMark({ className = 'h-10 w-auto' }) {
  const gradientId = useId();

  return (
    <svg viewBox="0 0 32 38" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="2" y1="4" x2="30" y2="34" gradientUnits="userSpaceOnUse">
          <stop stopColor="#6A4BFF" />
          <stop offset="1" stopColor="#1AA9FF" />
        </linearGradient>
      </defs>
      <path
        d="M16 1 3 6.2v10.3c0 9.5 5.5 17.1 13 20.5 7.5-3.4 13-11 13-20.5V6.2L16 1Z"
        fill={`url(#${gradientId})`}
      />
      <rect x="10.5" y="16" width="11" height="9" rx="1.8" fill="#fff" />
      <path d="M12.5 16v-2.4a3.5 3.5 0 0 1 7 0V16" fill="none" stroke="#fff" strokeWidth="2" />
      <circle cx="16" cy="20.2" r="1.2" fill="#3B3FD8" />
    </svg>
  );
}