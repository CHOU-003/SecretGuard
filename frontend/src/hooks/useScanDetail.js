import { useEffect, useState } from 'react';
import { apiFetch } from '../api/client';

function normalize(raw) {
  const scan = raw?.scan ?? raw;
  if (!scan || scan.id == null) {
    throw new Error('Phản hồi từ /api/scans/:id không đúng định dạng (thiếu thông tin scan).');
  }
  return {
    scan: {
      ...scan,
      project_name: scan.project_name ?? scan.project?.name,
      risk_threshold: scan.risk_threshold ?? scan.project?.risk_threshold,
    },
    findings: raw.findings ?? scan.findings ?? [],
    related_scans: raw.related_scans ?? raw.relatedScans ?? [],
  };
}

export function useScanDetail(id) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      setData(null);
      try {
        const raw = await apiFetch(`/api/scans/${id}`);
        if (!cancelled) setData(normalize(raw));
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
  }, [id]);

  return { data, loading, error };
}