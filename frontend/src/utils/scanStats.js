import { TIME_RANGES } from '../constants/scanFilters.js';

const DAY = 86_400_000;

const sum = (arr) => arr.reduce((a, b) => a + b, 0);

function startOfDay(value) {
  const d = new Date(value);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

// Số scan mỗi ngày trong `days` ngày gần nhất (phần tử cuối = hôm nay).
export function dailyCounts(scans, predicate = () => true, days = 7) {
  const today = startOfDay(Date.now());
  const counts = Array(days).fill(0);
  for (const scan of scans) {
    if (!predicate(scan)) continue;
    const index = days - 1 - Math.round((today - startOfDay(scan.created_at)) / DAY);
    if (index >= 0 && index < days) counts[index] += 1;
  }
  return counts;
}



  // So sánh `days` ngày gần nhất với `days` ngày liền trước đó.
  export function trend(scans, predicate = () => true, days = 7) {
    const counts = dailyCounts(scans, predicate, days * 2);
    const previous = sum(counts.slice(0, days));
    const series = counts.slice(days);
    const current = sum(series);
    return { series, current, previous, delta: current - previous };
  }

export function filterScans(scans, { query = '', range = 'all' } = {}) {
  const q = query.trim().toLowerCase();
  const days = TIME_RANGES.find((r) => r.value === range)?.days ?? null;
  const from = days ? startOfDay(Date.now()) - (days - 1) * DAY : null;

  return scans.filter((scan) => {
    if (from !== null && new Date(scan.created_at).getTime() < from) return false;
    if (!q) return true;
    return [scan.commit_hash, scan.branch].some((v) => v && v.toLowerCase().includes(q));
  });
}
