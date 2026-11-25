
import { useEffect, useState } from 'react';
import { apiFetch } from '../api/client';

export function useStatsData(days) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [timeline, breakdown] = await Promise.all([
          apiFetch(`/api/stats/timeline?days=${days}`),
          apiFetch(`/api/stats/breakdown?days=${days}`),
        ]);

        if (!cancelled) {
          setData({
            timeline: timeline.timeline ?? [],
            ...breakdown,
          });
          setError('');
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
  }, [days]);

  return { data, loading, error };
}
