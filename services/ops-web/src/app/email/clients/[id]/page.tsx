'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { EmailClientWorkspaceTabs, EmailKpiCard } from '@/components/email';
import {
  fetchEmailWorkspaces,
  patchEmailWorkspace,
  staffMe,
  staffRefresh,
  type EmailWorkspaceRow,
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

export default function EmailClientWorkspacePage() {
  const router = useRouter();
  const params = useParams();
  const clientId = String(params.id ?? '');

  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [workspace, setWorkspace] = useState<EmailWorkspaceRow | null>(null);
  const [tab, setTab] = useState<'overview' | 'settings'>('overview');
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const sp = new URLSearchParams(window.location.search);
      const t = sp.get('tab');
      if (t === 'settings') setTab('settings');
    }
  }, []);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [settingsForm, setSettingsForm] = useState({
    default_from_name: '',
    default_from_email: '',
    default_reply_to: '',
    esp_provider: 'sendgrid',
    daily_send_cap: 10000,
    frequency_cap_7d: 5,
    timezone: 'Asia/Ho_Chi_Minh',
  });

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

  useEffect(() => {
    if (!clientId) return;
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      setError('');
      try {
        const data = await fetchEmailWorkspaces(access, { client_id: clientId, limit: 1 });
        const ws = data.items[0] ?? null;
        setWorkspace(ws);
        if (ws) {
          setSettingsForm({
            default_from_name: ws.default_from_name ?? '',
            default_from_email: ws.default_from_email ?? '',
            default_reply_to: ws.default_reply_to ?? '',
            esp_provider: ws.esp_provider,
            daily_send_cap: ws.daily_send_cap,
            frequency_cap_7d: ws.frequency_cap_7d,
            timezone: ws.timezone,
          });
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải workspace thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, clientId]);

  async function saveSettings() {
    if (!workspace) return;
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    try {
      const updated = await patchEmailWorkspace(access, workspace.id, settingsForm);
      setWorkspace(updated);
      setTab('overview');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu settings thất bại');
    } finally {
      setSaving(false);
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
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/email/clients" className="nav-link">
          ← Email clients
        </Link>
      </p>

      {loading ? <p className="muted">Đang tải…</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {workspace ? (
        <>
          <div className="card" style={{ marginBottom: '1rem' }}>
            <h2 style={{ marginTop: 0 }}>
              {workspace.client_name} · {workspace.name}
            </h2>
            <p className="muted" style={{ margin: 0 }}>
              {workspace.esp_provider} · TZ {workspace.timezone}
            </p>
            <EmailClientWorkspaceTabs clientId={clientId} active={tab === 'settings' ? 'settings' : 'overview'} />
            {tab === 'settings' ? null : (
              <div style={{ marginTop: '0.75rem' }}>
                <button type="button" className="btn btn-sm btn-secondary" onClick={() => setTab('settings')}>
                  Cài đặt workspace
                </button>
              </div>
            )}
          </div>

          {tab === 'overview' ? (
            <div className="card email-kpi-grid" style={{ marginBottom: '1rem' }}>
              <EmailKpiCard label="Contacts" value={workspace.contact_count} />
              <EmailKpiCard label="Subscribers" value={workspace.subscriber_count} />
              <EmailKpiCard label="Suppressed" value={workspace.suppressed_count} />
              <EmailKpiCard label="Daily cap" value={workspace.daily_send_cap.toLocaleString()} />
            </div>
          ) : (
            <div className="card">
              <h3 style={{ marginTop: 0 }}>Workspace settings</h3>
              <div style={{ display: 'grid', gap: '0.75rem', maxWidth: 480 }}>
                <label>
                  From name
                  <input
                    value={settingsForm.default_from_name}
                    onChange={(e) => setSettingsForm({ ...settingsForm, default_from_name: e.target.value })}
                    style={{ display: 'block', width: '100%', marginTop: '0.25rem' }}
                  />
                </label>
                <label>
                  From email
                  <input
                    value={settingsForm.default_from_email}
                    onChange={(e) => setSettingsForm({ ...settingsForm, default_from_email: e.target.value })}
                    style={{ display: 'block', width: '100%', marginTop: '0.25rem' }}
                  />
                </label>
                <label>
                  Reply-to
                  <input
                    value={settingsForm.default_reply_to}
                    onChange={(e) => setSettingsForm({ ...settingsForm, default_reply_to: e.target.value })}
                    style={{ display: 'block', width: '100%', marginTop: '0.25rem' }}
                  />
                </label>
                <label>
                  ESP
                  <select
                    value={settingsForm.esp_provider}
                    onChange={(e) => setSettingsForm({ ...settingsForm, esp_provider: e.target.value })}
                    style={{ display: 'block', marginTop: '0.25rem' }}
                  >
                    <option value="sendgrid">SendGrid</option>
                    <option value="mailgun">Mailgun</option>
                  </select>
                </label>
                <label>
                  Daily send cap
                  <input
                    type="number"
                    value={settingsForm.daily_send_cap}
                    onChange={(e) =>
                      setSettingsForm({ ...settingsForm, daily_send_cap: Number(e.target.value) })
                    }
                    style={{ display: 'block', width: '100%', marginTop: '0.25rem' }}
                  />
                </label>
                <button type="button" className="btn" disabled={saving} onClick={() => void saveSettings()}>
                  {saving ? 'Đang lưu…' : 'Lưu'}
                </button>
              </div>
            </div>
          )}
        </>
      ) : !loading ? (
        <p className="muted">Client chưa có workspace — tạo từ danh sách clients.</p>
      ) : null}
    </main>
  );
}
