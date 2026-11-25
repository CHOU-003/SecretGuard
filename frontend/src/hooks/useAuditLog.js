
import { useEffect, useMemo, useState } from 'react';
import { apiFetch } from '../api/client';

export function useAuditLog(filters, page, limit = 20) {
  const [data, setData] = useState({ logs: [], pagination: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const filtersKey = JSON.stringify(filters);

  const stableFilters = useMemo(
    () => JSON.parse(filtersKey),
    [filtersKey]
  );

  useEffect(() => {
    let cancelled = false;

    const params = new URLSearchParams({
      page: String(page),
      limit: String(limit),
    });

    Object.entries(stableFilters).forEach(([k, v]) => {
      if (v) params.set(k, v);
    });

    async function load() {
      setLoading(true);
      setError('');

      try {
        const res = await apiFetch(`/api/audit-log?${params}`);

        if (!cancelled) {
          setData({
            logs: res.logs ?? [],
            pagination: res.pagination,
          });
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [stableFilters, page, limit]);

  return { ...data, loading, error };
}
