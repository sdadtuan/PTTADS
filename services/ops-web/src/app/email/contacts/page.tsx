'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { EmailConsentBadge, EmailEmptyState } from '@/components/email';
import {
  fetchEmailContacts,
  importEmailContacts,
  staffMe,
  staffRefresh,
  type EmailContactRow,
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

export default function EmailContactsPage() {
  const router = useRouter();

  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [contacts, setContacts] = useState<EmailContactRow[]>([]);
  const [clientId, setClientId] = useState('');
  const [q, setQ] = useState('');
  const [importText, setImportText] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
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
        const data = await fetchEmailContacts(access, {
          client_id: clientId.trim() || undefined,
          q: q.trim() || undefined,
          limit: 100,
        });
        setContacts(data.items);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải contacts thất bại');
      } finally {
        setLoading(false);
      }
    },
    [clientId, q],
  );

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const sp = new URLSearchParams(window.location.search);
      const cid = sp.get('client_id');
      if (cid) setClientId(cid);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await load(access);
    })();
  }, [ensureAuth, load]);

  async function runImport() {
    const access = getAccessToken();
    if (!access || !clientId.trim()) {
      setError('Cần client_id để import');
      return;
    }
    const rows = importText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [email, first_name] = line.split(',').map((s) => s.trim());
        return { email, first_name };
      });
    setError('');
    setMessage('');
    try {
      const out = await importEmailContacts(access, { client_id: clientId.trim(), rows });
      setMessage(`Import: +${out.created} mới, ~${out.updated} cập nhật, ${out.skipped} bỏ qua`);
      await load(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import thất bại');
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

  const canWrite = hasCap(user, 'crm_email_mkt', 'write') || hasCap(user, 'crm_agency', 'create');

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>
          EM-1 E-04 — Danh bạ contacts
        </p>
        <Link href="/email/hub" className="btn btn-secondary btn-sm">
          ← Email hub
        </Link>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '0.75rem' }}>
          <input
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            placeholder="Client UUID"
            style={{ width: 280 }}
          />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm email / tên" style={{ width: 200 }} />
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
      {message ? <p className="badge">{message}</p> : null}

      {canWrite ? (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h3 style={{ marginTop: 0 }}>Bulk import (email, first_name mỗi dòng)</h3>
          <textarea
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            rows={4}
            style={{ width: '100%', fontFamily: 'monospace' }}
            placeholder={'user@example.com,Nguyen\nother@example.com'}
          />
          <button type="button" className="btn btn-sm" style={{ marginTop: '0.5rem' }} onClick={() => void runImport()}>
            Import
          </button>
        </div>
      ) : null}

      <div className="card">
        <table className="perf-table">
          <thead>
            <tr>
              <th scope="col">Email</th>
              <th scope="col">Client</th>
              <th scope="col">Consent</th>
              <th scope="col">Suppressed</th>
            </tr>
          </thead>
          <tbody>
            {contacts.map((c) => (
              <tr key={c.id}>
                <td>
                  {c.email}
                  {c.first_name ? <span className="muted"> · {c.first_name}</span> : null}
                </td>
                <td>{c.client_name}</td>
                <td><EmailConsentBadge status={c.consent_status} /></td>
                <td>{c.suppressed ? <span className="email-suppressed">Suppressed</span> : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && contacts.length === 0 ? (
          <EmailEmptyState message="Chưa có contact. Import từ CRM hoặc form capture." ctaLabel="← Email hub" ctaHref="/email/hub" />
        ) : null}
      </div>
    </main>
  );
}
