'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchLaunchQaRuns, fetchLaunchQaStats, staffMe, staffRefresh } from '@/lib/api';
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

type StatusTab = 'all' | 'in_progress' | 'passed' | 'failed' | 'blocked' | 'timeout';

type RunRow = {
  id: string;
  client_id: string;
  external_campaign_id: string;
  campaign_name: string | null;
  status: string;
  launch_ready: boolean;
  progress: { total: number; completed: number; percent: number };
  temporal_workflow_id: string | null;
  started_at: string;
  completed_at: string | null;
  lifecycle_id: number | null;
};

const TABS: Array<{ id: StatusTab; label: string }> = [
  { id: 'all', label: 'Tất cả' },
  { id: 'in_progress', label: 'Đang QA' },
  { id: 'passed', label: 'Passed' },
  { id: 'failed', label: 'Failed' },
  { id: 'blocked', label: 'Blocked' },
  { id: 'timeout', label: 'Timeout' },
];

const STATUS_LABEL: Record<string, string> = {
  in_progress: 'Đang QA',
  passed: 'Passed',
  failed: 'Failed',
  blocked: 'Blocked',
  timeout: 'Timeout',
};

export default function CrmLaunchQaPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [tab, setTab] = useState<StatusTab>('all');
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const ensureAuth = useCallback(async (): Promise<string | null> => {
    let access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return null;
    }
    const cached = getStoredUser();
    if (cached) setUser(cached);
    try {
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      if (!hasCap(me, 'crm_board', 'view')) {
        setError('Không có quyền Launch QA');
        return null;
      }
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
      const me = await staffMe(access);
      setUser(me);
      updateStoredUser(me);
      return access;
    }
  }, [router]);

  const reload = useCallback(async (access: string, status: StatusTab) => {
    const [statsOut, runsOut] = await Promise.all([
      fetchLaunchQaStats(access),
      fetchLaunchQaRuns(access, status),
    ]);
    setStats(statsOut.stats ?? {});
    setRuns(runsOut.runs ?? []);
  }, []);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      setError('');
      try {
        await reload(access, tab);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải Launch QA thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, reload, tab]);

  function logout() {
    clearSession();
    router.push('/login');
  }

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <h1 style={{ margin: '0 0 0.35rem', fontSize: '1.25rem' }}>Launch QA Board</h1>
      <p className="muted" style={{ margin: '0 0 1rem' }}>
        Checklist triển khai campaign — PG-first, link lifecycle khi có HĐ + campaign code.
      </p>

      {loading ? <p className="muted">Đang tải…</p> : null}
      {error ? <p className="error">{error}</p> : null}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
          gap: '0.5rem',
          marginBottom: '1rem',
        }}
      >
        {(['in_progress', 'passed', 'failed', 'blocked'] as const).map((key) => (
          <div key={key} className="card" style={{ padding: '0.65rem 0.75rem' }}>
            <div className="muted" style={{ fontSize: '0.75rem' }}>
              {STATUS_LABEL[key] ?? key}
            </div>
            <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{stats[key] ?? 0}</div>
          </div>
        ))}
        <div className="card" style={{ padding: '0.65rem 0.75rem' }}>
          <div className="muted" style={{ fontSize: '0.75rem' }}>
            Tổng
          </div>
          <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{stats.all ?? 0}</div>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginBottom: '0.75rem' }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={tab === t.id ? 'btn btn-sm' : 'btn btn-sm btn-ghost'}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {t.id === 'all' ? ` (${stats.all ?? 0})` : ` (${stats[t.id] ?? 0})`}
          </button>
        ))}
      </div>

      <div className="card" style={{ padding: '0.75rem', overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr className="muted">
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Campaign</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Client</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Tiến độ</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Status</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Temporal</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Bắt đầu</th>
              <th style={{ textAlign: 'left', padding: '0.35rem' }}>Link</th>
            </tr>
          </thead>
          <tbody>
            {runs.length === 0 ? (
              <tr>
                <td colSpan={7} className="muted" style={{ padding: '0.75rem' }}>
                  Không có run — lifecycle vào Deliver sẽ auto-start (nếu env bật).
                </td>
              </tr>
            ) : null}
            {runs.map((run) => (
              <tr key={run.id} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: '0.35rem' }}>
                  <strong>{run.external_campaign_id}</strong>
                  {run.campaign_name ? (
                    <div className="muted" style={{ fontSize: '0.8rem' }}>
                      {run.campaign_name}
                    </div>
                  ) : null}
                </td>
                <td style={{ padding: '0.35rem', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                  {run.client_id.slice(0, 8)}…
                </td>
                <td style={{ padding: '0.35rem' }}>
                  {run.progress.completed}/{run.progress.total} · {run.progress.percent}%
                  {run.launch_ready ? (
                    <span style={{ color: 'var(--accent)', marginLeft: '0.35rem' }}>✓ ready</span>
                  ) : null}
                </td>
                <td style={{ padding: '0.35rem' }}>{STATUS_LABEL[run.status] ?? run.status}</td>
                <td style={{ padding: '0.35rem' }}>
                  {run.temporal_workflow_id ? (
                    <span className="muted" title={run.temporal_workflow_id}>
                      linked
                    </span>
                  ) : (
                    'PG-only'
                  )}
                </td>
                <td style={{ padding: '0.35rem' }}>{run.started_at?.slice(0, 10) ?? '—'}</td>
                <td style={{ padding: '0.35rem' }}>
                  {run.lifecycle_id ? (
                    <Link
                      href={`/crm/service-delivery/${run.lifecycle_id}?tab=launch_qa`}
                      className="nav-link"
                    >
                      Lifecycle #{run.lifecycle_id}
                    </Link>
                  ) : (
                    <Link
                      href={`/agency/clients/${encodeURIComponent(run.client_id)}`}
                      className="nav-link"
                    >
                      Client
                    </Link>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
