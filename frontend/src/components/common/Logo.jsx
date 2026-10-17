import ShieldMark from './ShieldMark.jsx';

export default function Logo({ tagline, className = '' }) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <ShieldMark className="h-10 w-auto" />
      <div className="leading-tight">
        <span className="block text-2xl font-semibold tracking-tight text-fg">
          Secret<span className="text-brand-ink">Guard</span>
        </span>
        {tagline && <span className="mt-0.5 block text-xs text-fg/80">{tagline}</span>}
      </div>
    </div>
  );
}