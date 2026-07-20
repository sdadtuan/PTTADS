'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchEmailConsent,
  recordEmailConsent,
  staffMe,
  staffRefresh,
  type EmailConsentRow,
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

export default function EmailConsentPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [rows, setRows] = useState<EmailConsentRow[]>([]);
  const [clientId, setClientId] = useState('');
  const [form, setForm] = useState({ email: '', status: 'opted_in', source: 'manual' });
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
        const data = await fetchEmailConsent(access, {
          client_id: clientId.trim() || undefined,
          limit: 100,
        });
        setRows(data.items);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải consent thất bại');
      } finally {
        setLoading(false);
      }
    },
    [clientId],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await load(access);
    })();
  }, [ensureAuth, load]);

  async function submitConsent() {
    const access = getAccessToken();
    if (!access || !clientId.trim() || !form.email.trim()) {
      setError('Cần client_id và email');
      return;
    }
    setError('');
    try {
      await recordEmailConsent(access, {
        client_id: clientId.trim(),
        email: form.email.trim(),
        status: form.status,
        source: form.source,
        topic: 'marketing',
      });
      setForm({ email: '', status: 'opted_in', source: 'manual' });
      await load(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ghi consent thất bại');
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
          EM-1 E-05 — Consent registry (append-only)
        </p>
        <Link href="/email/hub" className="btn btn-secondary btn-sm">
          ← Email hub
        </Link>
        <div style={{ marginTop: '0.75rem' }}>
          <input
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            placeholder="Client UUID filter"
            style={{ width: 280 }}
          />
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            style={{ marginLeft: '0.5rem' }}
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
          <h3 style={{ marginTop: 0 }}>Ghi consent mới</h3>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <input
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="email@client.com"
              style={{ minWidth: 220 }}
            />
            <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
              <option value="opted_in">opted_in</option>
              <option value="opted_out">opted_out</option>
              <option value="pending_confirm">pending_confirm</option>
            </select>
            <button type="button" className="btn btn-sm" onClick={() => void submitConsent()}>
              Ghi
            </button>
          </div>
        </div>
      ) : null}

      <div className="card">
        <table className="perf-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Email</th>
              <th>Topic</th>
              <th>Status</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.recorded_at.slice(0, 19)}</td>
                <td>{r.contact_email}</td>
                <td>{r.topic}</td>
                <td>{r.status}</td>
                <td>{r.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && rows.length === 0 ? <p className="muted">Chưa có bản ghi consent.</p> : null}
      </div>
    </main>
  );
}
