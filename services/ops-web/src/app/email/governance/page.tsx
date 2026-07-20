'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchEmailGovernance, staffMe, staffRefresh, type EmailGovernanceResponse } from '@/lib/api';
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

export default function EmailGovernancePage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [data, setData] = useState<EmailGovernanceResponse | null>(null);
  const [scope, setScope] = useState('');
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
      if (!hasCap(me, 'crm_email_mkt', 'view') && !hasCap(me, 'crm_agency', 'view')) {
        setError('Không có quyền Email Marketing');
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

  const load = useCallback(
    async (access: string) => {
      setLoading(true);
      setError('');
      try {
        const out = await fetchEmailGovernance(access, {
          scope: scope.trim() || undefined,
        });
        setData(out);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải governance thất bại');
      } finally {
        setLoading(false);
      }
    },
    [scope],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await load(access);
    })();
  }, [ensureAuth, load]);

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
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>
          EM-0 — E-13 Governance hub (read-only) · global rules + audit tail
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <Link href="/email/hub" className="btn btn-sm">
            ← Email hub
          </Link>
          {data?.read_only ? <span className="badge">Read-only</span> : null}
          <label className="muted">
            Scope{' '}
            <select value={scope} onChange={(e) => setScope(e.target.value)} style={{ marginLeft: '0.35rem' }}>
              <option value="">All</option>
              <option value="global">Global</option>
              <option value="brand">Brand</option>
              <option value="market">Market</option>
              <option value="client">Client</option>
            </select>
          </label>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={loading}
            onClick={() => {
              const access = getAccessToken();
              if (access) void load(access);
            }}
          >
            Làm mới
          </button>
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <div className="card" style={{ marginBottom: '1rem' }}>
        <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Global rules</h2>
        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>Scope</th>
                <th>Type</th>
                <th>Config</th>
                <th>Priority</th>
                <th>Enabled</th>
              </tr>
            </thead>
            <tbody>
              {(data?.rules ?? []).map((rule) => (
                <tr key={rule.id}>
                  <td>{rule.scope}</td>
                  <td>{rule.rule_type}</td>
                  <td>
                    <code style={{ fontSize: '0.85rem' }}>{JSON.stringify(rule.config_json)}</code>
                  </td>
                  <td>{rule.priority}</td>
                  <td>{rule.enabled ? '✓' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && (data?.rules?.length ?? 0) === 0 ? (
            <p className="muted">
              Chưa có rules — apply DDL để seed global defaults hoặc cấu hình EM-1.
            </p>
          ) : null}
        </div>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Audit log (50 gần nhất)</h2>
        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Entity</th>
              </tr>
            </thead>
            <tbody>
              {(data?.audit_log ?? []).map((row) => (
                <tr key={row.id}>
                  <td>{row.created_at ? row.created_at.slice(0, 19) : '—'}</td>
                  <td>{row.actor}</td>
                  <td>{row.action}</td>
                  <td>
                    {row.entity_type}
                    {row.entity_id ? ` · ${row.entity_id.slice(0, 8)}…` : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && (data?.audit_log?.length ?? 0) === 0 ? (
            <p className="muted">Chưa có audit entries.</p>
          ) : null}
        </div>
      </div>
    </main>
  );
}
