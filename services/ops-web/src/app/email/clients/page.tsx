'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  createEmailWorkspace,
  fetchEmailClients,
  staffMe,
  staffRefresh,
  type EmailClientListRow,
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

export default function EmailClientsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [clients, setClients] = useState<EmailClientListRow[]>([]);
  const [q, setQ] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState<string | null>(null);

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
        const data = await fetchEmailClients(access, { q: q.trim() || undefined, limit: 100 });
        setClients(data.items);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải clients thất bại');
      } finally {
        setLoading(false);
      }
    },
    [q],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await load(access);
    })();
  }, [ensureAuth, load]);

  async function createWorkspace(client: EmailClientListRow) {
    const access = getAccessToken();
    if (!access) return;
    setCreating(client.client_id);
    setError('');
    try {
      await createEmailWorkspace(access, {
        client_id: client.client_id,
        name: `${client.client_name} Email`,
      });
      await load(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo workspace thất bại');
    } finally {
      setCreating(null);
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

  const canSettings = hasCap(user, 'crm_email_mkt', 'settings') || hasCap(user, 'crm_agency', 'create');

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>
          EM-1 E-02 — Danh sách client Email · workspace per client
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <Link href="/email/hub" className="btn btn-secondary btn-sm">
            ← Email hub
          </Link>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Tìm code / tên"
            style={{ minWidth: 200 }}
          />
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

      <div className="card">
        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>Client</th>
                <th>Status</th>
                <th>Workspace</th>
                <th>Contacts</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr key={c.client_id}>
                  <td>
                    <strong>{c.client_name}</strong>
                    <br />
                    <span className="muted">{c.client_code}</span>
                  </td>
                  <td>{c.client_status}</td>
                  <td>
                    {c.has_workspace ? (
                      <>
                        {c.workspace_name} · {c.esp_provider}
                      </>
                    ) : (
                      <span className="muted">Chưa có</span>
                    )}
                  </td>
                  <td>{c.contact_count}</td>
                  <td>
                    {c.has_workspace ? (
                      <Link href={`/email/clients/${c.client_id}`} className="btn btn-sm">
                        Mở
                      </Link>
                    ) : canSettings ? (
                      <button
                        type="button"
                        className="btn btn-sm"
                        disabled={creating === c.client_id}
                        onClick={() => void createWorkspace(c)}
                      >
                        {creating === c.client_id ? '…' : 'Tạo workspace'}
                      </button>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && clients.length === 0 ? <p className="muted">Không có client.</p> : null}
        </div>
      </div>
    </main>
  );
}
