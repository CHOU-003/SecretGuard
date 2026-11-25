import { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '../api/client';

export function useProjects() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    try {
      const res = await apiFetch('/api/projects');
      setProjects(res.projects ?? []);
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    const fetchProjects = async () => {
      try {
        const res = await apiFetch('/api/projects');

        if (!cancelled) {
          setProjects(res.projects ?? []);
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
    };

    fetchProjects();

    return () => {
      cancelled = true;
    };
  }, []);

  return { projects, loading, error, reload };
}