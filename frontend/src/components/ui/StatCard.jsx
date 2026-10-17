import Sparkline from './Sparkline.jsx';

const THEMES = {
  scan: {
    card: 'border-[#4a76ff] from-[#2150f0] to-[#0f2a9c] shadow-[0_0_36px_-10px_rgba(74,118,255,0.8)]',
    icon: 'bg-[#6d92ff]/45',
    spark: '#58b0ff',
  },
  blocked: {
    card: 'border-[#1fa596]/70 from-[#075a55] to-[#053a40] shadow-[0_0_36px_-12px_rgba(31,165,150,0.6)]',
    icon: 'bg-[#25c2a4]',
    spark: '#34d9a5',
  },
  warned: {
    card: 'border-[#a8661f]/70 from-[#68390f] to-[#3a210b] shadow-[0_0_36px_-12px_rgba(245,165,36,0.45)]',
    icon: 'bg-[#f59e0b]',
    spark: '#f5a524',
  },
  passed: {
    card: 'border-[#7a4df0]/70 from-[#43209f] to-[#26106e] shadow-[0_0_36px_-12px_rgba(139,92,246,0.6)]',
    icon: 'bg-[#8b5cf6]',
    spark: '#b36bff',
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
