'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  addEmailSuppression,
  fetchEmailSuppression,
  staffMe,
  staffRefresh,
  type EmailSuppressionRow,
} from '@/lib/api';
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

export default function EmailSuppressionPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [rows, setRows] = useState<EmailSuppressionRow[]>([]);
  const [clientId, setClientId] = useState('');
  const [q, setQ] = useState('');
  const [form, setForm] = useState({ email: '', reason: 'manual', scope: 'client' });
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
        const data = await fetchEmailSuppression(access, {
          client_id: clientId.trim() || undefined,
          q: q.trim() || undefined,
          limit: 100,
        });
        setRows(data.items);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải suppression thất bại');
      } finally {
        setLoading(false);
      }
    },
    [clientId, q],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await load(access);
    })();
  }, [ensureAuth, load]);

  async function submitSuppression() {
    const access = getAccessToken();
    if (!access || !form.email.trim()) {
      setError('Cần email');
      return;
    }
    setError('');
    try {
      await addEmailSuppression(access, {
        client_id: clientId.trim() || undefined,
        email: form.email.trim(),
        reason: form.reason,
        scope: form.scope,
      });
      setForm({ email: '', reason: 'manual', scope: 'client' });
      await load(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thêm suppression thất bại');
    }
  }

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

  const canCompliance =
    hasCap(user, 'crm_email_mkt', 'compliance') ||
    hasCap(user, 'crm_email_mkt', 'write') ||
    hasCap(user, 'crm_agency', 'create');

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>
          EM-1 E-06 — Suppression master
        </p>
        <Link href="/email/hub" className="btn btn-secondary btn-sm">
          ← Email hub
        </Link>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.75rem' }}>
          <input
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            placeholder="Client UUID"
            style={{ width: 280 }}
          />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Email" style={{ width: 200 }} />
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

      {canCompliance ? (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h3 style={{ marginTop: 0 }}>Thêm suppression</h3>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <input
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="email@example.com"
              style={{ minWidth: 220 }}
            />
            <select value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })}>
              <option value="manual">manual</option>
              <option value="unsubscribe">unsubscribe</option>
              <option value="complaint">complaint</option>
              <option value="hard_bounce">hard_bounce</option>
            </select>
            <button type="button" className="btn btn-sm" onClick={() => void submitSuppression()}>
              Thêm
            </button>
          </div>
        </div>
      ) : null}

      <div className="card">
        <table className="perf-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Client</th>
              <th>Reason</th>
              <th>Scope</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.email_normalized}</td>
                <td>{r.client_name ?? 'global'}</td>
                <td>{r.reason}</td>
                <td>{r.scope}</td>
                <td>{r.created_at.slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && rows.length === 0 ? <p className="muted">Không có suppression entry.</p> : null}
      </div>
    </main>
  );
}
