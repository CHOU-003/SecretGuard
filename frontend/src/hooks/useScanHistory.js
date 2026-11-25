import { useEffect, useState } from 'react';
import { apiFetch } from '../api/client';

export function useScanHistory(filters, page, limit = 20) {
  const [data, setData] = useState({ scans: [], pagination: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const key = JSON.stringify(filters);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ page, limit });
    Object.entries(filters).forEach(([k, v]) => v && params.set(k, v));

    // debounce để không gọi API mỗi lần gõ phím
    const timer = setTimeout(async () => {
      setLoading(true);
      setError('');
      try {
        const res = await apiFetch(`/api/scans?${params}`);
        if (!cancelled) setData({ scans: res.scans ?? [], pagination: res.pagination });
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 300);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, page, limit]);

  return { ...data, loading, error };
}