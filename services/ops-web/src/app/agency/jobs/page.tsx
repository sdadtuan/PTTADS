'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchAgencyJobs, staffMe, staffRefresh } from '@/lib/api';
import type { JobRow } from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  hasCap,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';

export default function AgencyJobsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [filter, setFilter] = useState('');
  const [error, setError] = useState('');

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return null;
    }
    try {
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      if (!hasCap(me, 'crm_agency', 'view')) return null;
      return access;
    } catch {
      const refresh = getRefreshToken();
      if (!refresh) {
        clearSession();
        router.replace('/login');
        return null;
      }
      const out = await staffRefresh(refresh);
      updateAccessToken(out.access_token);
      access = out.access_token;
      return access;
    }
  }, [router]);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      try {
        const data = await fetchAgencyJobs(access, filter || undefined);
        setJobs(data.jobs);
        setStats(data.stats);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải jobs thất bại');
      }
    })();
  }, [ensureAuth, filter]);

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/agency" className="nav-link">
          ← Agency
        </Link>
      </p>
      <div className="card">
        <p className="muted">
          pending {stats.pending ?? 0} · dead {stats.dead ?? 0} · failed {stats.failed ?? 0}
        </p>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{ marginBottom: '1rem', padding: '0.4rem' }}
        >
          <option value="">Tất cả</option>
          <option value="pending">pending</option>
          <option value="dead">dead (DLQ)</option>
          <option value="failed">failed</option>
        </select>
        {error ? <p className="error">{error}</p> : null}
        <table className="perf-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Status</th>
              <th>Client</th>
              <th>Lỗi</th>
              <th>Thời gian</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id}>
                <td>{j.job_type}</td>
                <td>{j.status}</td>
                <td>{j.client_code ?? '—'}</td>
                <td>{j.last_error?.slice(0, 80) ?? '—'}</td>
                <td>{j.created_at?.slice(0, 16) ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
