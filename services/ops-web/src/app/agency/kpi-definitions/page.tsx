'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { AgencyReadOnlyBadge } from '@/components/AgencyReadOnlyBadge';
import { fetchKpiDefinitions, staffMe, staffRefresh } from '@/lib/api';
import type { KpiDefinition } from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  hasCap,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';

export default function AgencyKpiDefinitionsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [rows, setRows] = useState<KpiDefinition[]>([]);
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
      return out.access_token;
    }
  }, [router]);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      try {
        const data = await fetchKpiDefinitions(access);
        setRows(data.definitions);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải KPI definitions thất bại');
      }
    })();
  }, [ensureAuth]);

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/agency" className="nav-link">
          ← Agency
        </Link>
      </p>

      <div className="card">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', marginBottom: '0.5rem' }}>
          <h2 style={{ margin: 0, flex: '1 1 auto' }}>Định nghĩa KPI</h2>
          <AgencyReadOnlyBadge user={user} />
        </div>
        <p className="muted">Dictionary seed từ PostgreSQL · chỉ xem (CRUD → Wave B2)</p>
        {error ? <p className="error">{error}</p> : null}

        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Tên</th>
                <th>Công thức</th>
                <th>Granularity</th>
                <th>Mô tả</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.code}>
                  <td><code>{r.code}</code></td>
                  <td>{r.name}</td>
                  <td><code>{r.formula}</code></td>
                  <td>{r.granularity ?? '—'}</td>
                  <td>{r.description ?? '—'}</td>
                </tr>
              ))}
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="muted">
                    Chưa seed kpi_definitions — chạy ./scripts/seed_kpi_definitions.sh
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
