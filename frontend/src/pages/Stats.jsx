import { useState } from 'react';
import { useStatsData } from '../hooks/useStatsData';
import DashboardLayout from '../components/layout/DashboardLayout.jsx';

const RANGES = [
  { value: 7, label: '7 ngày' },
  { value: 30, label: '30 ngày' },
  { value: 90, label: '90 ngày' },
];

const STATUS_COLORS = { blocked: '#ff6b6b', warned: '#f5a524', passed: '#34d399' };
const RISK_COLORS = { high: '#ff6b6b', medium: '#f5a524', low: '#58b0ff' };

const cardCls = 'rounded-2xl border border-white/10 bg-white/[0.03] p-5';

function Card({ title, subtitle, children, className = '' }) {
  return (
    <div className={`${cardCls} ${className}`}>
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      {subtitle && <p className="mb-4 text-sm text-white/60">{subtitle}</p>}
      {children}
    </div>
  );
}

function Empty({ text = 'Chưa có dữ liệu trong khoảng này.' }) {
  return <p className="py-10 text-center text-sm text-white/50">{text}</p>;
}

function Legend({ items }) {
  return (
    <div className="mb-3 flex flex-wrap gap-4 text-xs text-white/70">
      {items.map(([label, color]) => (
        <span key={label} className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
          {label}
        </span>
      ))}
    </div>
  );
}

function formatDay(key) {
  const [, m, d] = key.split('-');
  return `${d}/${m}`;
}

/* Cột chồng: số scan mỗi ngày theo trạng thái */
function TimelineChart({ timeline }) {
  const W = 800, H = 260, padL = 34, padB = 28, padT = 10;
  const totals = timeline.map((t) => t.blocked + t.warned + t.passed);
  const max = Math.max(...totals, 1);
  const niceMax = Math.max(Math.ceil(max / 4) * 4, 4);
  const innerW = W - padL - 8;
  const innerH = H - padB - padT;
  const slot = innerW / timeline.length;
  const barW = Math.max(Math.min(slot * 0.7, 28), 3);
  const labelEvery = Math.ceil(timeline.length / 8);

  if (totals.every((t) => t === 0)) return <Empty />;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Số scan theo ngày">
      {[0, 1, 2, 3, 4].map((i) => {
        const y = padT + innerH - (innerH * i) / 4;
        return (
          <g key={i}>
            <line x1={padL} x2={W - 8} y1={y} y2={y} stroke="white" strokeOpacity="0.08" />
            <text x={padL - 6} y={y + 4} textAnchor="end" fontSize="11" fill="white" fillOpacity="0.5">
              {Math.round((niceMax * i) / 4)}
            </text>
          </g>
        );
      })}

      {timeline.map((t, i) => {
        const x = padL + slot * i + (slot - barW) / 2;
        let y = padT + innerH;
        const segments = ['passed', 'warned', 'blocked'].map((status) => {
          const h = (t[status] / niceMax) * innerH;
          y -= h;
          return h > 0 ? (
            <rect key={status} x={x} y={y} width={barW} height={h} fill={STATUS_COLORS[status]} rx="1.5" />
          ) : null;
        });
        return (
          <g key={t.date}>
            <title>{`${formatDay(t.date)}: ${t.blocked} blocked, ${t.warned} warned, ${t.passed} passed`}</title>
            <rect x={padL + slot * i} y={padT} width={slot} height={innerH} fill="transparent" />
            {segments}
            {i % labelEvery === 0 && (
              <text x={x + barW / 2} y={H - 8} textAnchor="middle" fontSize="11" fill="white" fillOpacity="0.5">
                {formatDay(t.date)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

/* Donut: phân bố mức rủi ro */
function RiskDonut({ data }) {
  const entries = ['high', 'medium', 'low'].map((k) => [k, data?.[k] ?? 0]);
  const total = entries.reduce((s, [, v]) => s + v, 0);
  if (total === 0) return <Empty />;

  let offset = 25; // bắt đầu từ 12 giờ
  return (
    <div className="flex flex-wrap items-center gap-6">
      <svg viewBox="0 0 42 42" className="h-40 w-40 shrink-0 -rotate-0" role="img" aria-label="Phân bố mức rủi ro">
        <circle cx="21" cy="21" r="15.9155" fill="none" stroke="white" strokeOpacity="0.06" strokeWidth="6" />
        {entries.map(([key, value]) => {
          const pct = (value / total) * 100;
          const el = (
            <circle
              key={key}
              cx="21" cy="21" r="15.9155" fill="none"
              stroke={RISK_COLORS[key]} strokeWidth="6"
              strokeDasharray={`${pct} ${100 - pct}`}
              strokeDashoffset={offset}
            />
          );
          offset -= pct;
          return value > 0 ? el : null;
        })}
        <text x="21" y="21.5" textAnchor="middle" fontSize="7" fontWeight="700" fill="white">{total}</text>
        <text x="21" y="27" textAnchor="middle" fontSize="3" fill="white" fillOpacity="0.6">findings</text>
      </svg>

      <ul className="space-y-2 text-sm">
        {entries.map(([key, value]) => (
          <li key={key} className="flex items-center gap-2 text-white/90">
            <span className="h-3 w-3 rounded-full" style={{ background: RISK_COLORS[key] }} />
            <span className="w-16 font-semibold uppercase">{key}</span>
            <span>{value}</span>
            <span className="text-white/50">({Math.round((value / total) * 100)}%)</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* Thanh ngang xếp hạng */
function RankList({ items, labelKey, color, mono = false, extra }) {
  if (!items?.length) return <Empty />;
  const max = Math.max(...items.map((i) => i.count), 1);
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item[labelKey]}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className={`truncate text-white/90 ${mono ? 'font-mono text-[13px]' : ''}`} title={item[labelKey]}>
              {item[labelKey]}
            </span>
            <span className="shrink-0 font-semibold text-white">
              {item.count}
              {extra && <span className="ml-1.5 text-xs font-normal text-white/50">{extra(item)}</span>}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full" style={{ width: `${(item.count / max) * 100}%`, background: color }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

function Kpi({ label, value, tone = 'text-white' }) {
  return (
    <div className={cardCls}>
      <p className="text-sm text-white/60">{label}</p>
      <p className={`mt-1 text-3xl font-bold ${tone}`}>{value}</p>
    </div>
  );
}

export default function Stats() {
  const [days, setDays] = useState(30);
  const { data, loading, error } = useStatsData(days);

  const sum = (key) => (data?.timeline ?? []).reduce((s, t) => s + t[key], 0);
  const blocked = sum('blocked');
  const warned = sum('warned');
  const passed = sum('passed');
  const total = blocked + warned + passed;
  const totalFindings = Object.values(data?.findings_by_risk ?? {}).reduce((a, b) => a + b, 0);

  return (
    <DashboardLayout>
      <section className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-2xl font-bold text-white">Thống kê</h2>
            <p className="text-sm text-white/60">Xu hướng quét và các loại secret hay bị lộ nhất.</p>
          </div>
          <div className="inline-flex rounded-lg border border-white/10 bg-white/5 p-1">
            {RANGES.map((r) => (
              <button
                key={r.value}
                onClick={() => setDays(r.value)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  days === r.value ? 'bg-nav text-white' : 'text-white/70 hover:text-white'
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <p className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</p>
        )}

        <div className={`space-y-5 transition-opacity ${loading ? 'opacity-60' : ''}`}>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi label="Tổng số scan" value={total} />
            <Kpi label="Tỷ lệ bị chặn" value={total ? `${Math.round((blocked / total) * 100)}%` : '—'} tone="text-red-300" />
            <Kpi label="Tổng findings" value={totalFindings} tone="text-amber-300" />
            <Kpi label="Scan sạch (Passed)" value={passed} tone="text-emerald-300" />
          </div>

          <Card title="Số scan theo ngày" subtitle={`${days} ngày gần nhất`}>
            <Legend items={[['Passed', STATUS_COLORS.passed], ['Warned', STATUS_COLORS.warned], ['Blocked', STATUS_COLORS.blocked]]} />
            {data && <TimelineChart timeline={data.timeline} />}
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card title="Phân bố mức rủi ro" subtitle="Tỷ lệ findings theo HIGH / MEDIUM / LOW">
              {data && <RiskDonut data={data.findings_by_risk} />}
            </Card>
            <Card title="Loại secret hay bị lộ" subtitle="Top 5 theo số lần phát hiện">
              {data && <RankList items={data.top_secret_types} labelKey="secret_type" color="#58b0ff" />}
            </Card>
          </div>

          <Card title="File hay vi phạm nhất" subtitle="Top 5 file chứa nhiều secret nhất">
            {data && (
              <RankList
                items={data.top_files}
                labelKey="file_path"
                color="#ff6b6b"
                mono
                extra={(i) => `· ${i.scans} scan`}
              />
            )}
          </Card>
        </div>
      </section>
    </DashboardLayout>
  );
}