import Sparkline from './Sparkline.jsx';

const THEMES = {
  scan: {
    card: 'border-[#4a76ff] from-[#2150f0] to-[#0f2a9c] shadow-[0_0_36px_-10px_rgba(74,118,255,0.8)]',
    icon: 'bg-[#6d92ff]/45',
    spark: '#58b0ff',
  },
  blocked: {
      card: 'border-[#e03131]/70 from-[#7a1c1c] to-[#450a0a] shadow-[0_0_36px_-12px_rgba(224,49,49,0.6)]',
      icon: 'bg-[#f03e3e]',
      spark: '#ff6b6b',
    },
  warned: {
    card: 'border-[#a8661f]/70 from-[#68390f] to-[#3a210b] shadow-[0_0_36px_-12px_rgba(245,165,36,0.45)]',
    icon: 'bg-[#f59e0b]',
    spark: '#f5a524',
  },
  passed: {
      card: 'border-emerald-500/70 from-emerald-900 to-emerald-950 shadow-[0_0_36px_-12px_rgba(16,185,129,0.6)]',
      icon: 'bg-emerald-500',
      spark: '#34d399',
    },
};

export default function StatCard({ label, value, icon: Icon, theme = 'scan', series, delta }) {
  const t = THEMES[theme];

  return (
    <div className={`relative overflow-hidden rounded-2xl border bg-linear-to-br p-5 ${t.card}`}>
      <div className="relative z-10 flex items-start gap-4">
        <span className={`grid h-16 w-16 shrink-0 place-items-center rounded-2xl text-white ${t.icon}`}>
          <Icon className="h-8 w-8" />
        </span>
        <div>
          <p className="text-lg text-fg/90">{label}</p>
          <p className="mt-1 text-4xl font-bold leading-none text-white">{value}</p>
          {delta != null && (
            <p className="mt-3 text-sm text-white/85">
              {delta > 0 ? `↑ +${delta} hôm nay` : '→ Không đổi'}
            </p>
          )}
        </div>
      </div>
      {series && (
        <Sparkline
          data={series}
          color={t.spark}
          className="pointer-events-none absolute bottom-3 right-4 h-14 w-[40%]"
        />
      )}
    </div>
  );
}
