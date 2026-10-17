import { useEffect, useState } from 'react';
import { apiFetch } from '../api/client';

export function useDashboardData() {
  const [scans, setScans] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const [scansData, statsData] = await Promise.all([
          apiFetch('/api/scans'),
          apiFetch('/api/stats/overview'),
        ]);
        if (!cancelled) {
          setScans(scansData.scans || scansData || []);
          setStats(statsData);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { scans, stats, loading, error };
}
