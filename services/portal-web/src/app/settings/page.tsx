'use client';

import { FormEvent, useEffect, useState } from 'react';
import { PortalPageShell } from '@/components/PortalPageShell';
import { fetchPortalSettings, patchPortalSettings, type PortalSettingsResponse } from '@/lib/api';

export default function SettingsPage() {
  return (
    <PortalPageShell>
      {({ token, user }) => <SettingsForm token={token} canEdit={user.role === 'approver'} />}
    </PortalPageShell>
  );
}

function SettingsForm({ token, canEdit }: { token: string; canEdit: boolean }) {
  const [settings, setSettings] = useState<PortalSettingsResponse | null>(null);
  const [displayName, setDisplayName] = useState('');
  const [logoUrl, setLogoUrl] = useState('');
  const [amName, setAmName] = useState('');
  const [amEmail, setAmEmail] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void fetchPortalSettings(token)
      .then((data) => {
        setSettings(data);
        setDisplayName(data.display_name ?? '');
        setLogoUrl(data.logo_url ?? '');
        setAmName(data.am_contact_name ?? '');
        setAmEmail(data.am_contact_email ?? '');
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Không tải settings'));
  }, [token]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canEdit) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const out = await patchPortalSettings(token, {
        display_name: displayName.trim(),
        logo_url: logoUrl.trim(),
        am_contact_name: amName.trim(),
        am_contact_email: amEmail.trim(),
      });
      setSettings(out);
      setMessage('Đã lưu cài đặt portal.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu thất bại');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Branding & liên hệ AM</h2>
      {!settings?.table_ready ? (
        <p className="muted">
          Bảng `portal_client_settings` chưa apply — hiển thị tên client mặc định. Chạy DDL v3-portal-settings trên PG.
        </p>
      ) : null}
      {!canEdit ? (
        <p className="muted">Chỉ role approver được chỉnh branding.</p>
      ) : null}
      <form onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="display_name">Tên hiển thị</label>
          <input
            id="display_name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            disabled={!canEdit || busy}
          />
        </div>
        <div className="field">
          <label htmlFor="logo_url">Logo URL</label>
          <input
            id="logo_url"
            value={logoUrl}
            onChange={(e) => setLogoUrl(e.target.value)}
            disabled={!canEdit || busy}
            placeholder="https://..."
          />
        </div>
        <div className="field">
          <label htmlFor="am_name">Tên AM</label>
          <input
            id="am_name"
            value={amName}
            onChange={(e) => setAmName(e.target.value)}
            disabled={!canEdit || busy}
          />
        </div>
        <div className="field">
          <label htmlFor="am_email">Email AM</label>
          <input
            id="am_email"
            type="email"
            value={amEmail}
            onChange={(e) => setAmEmail(e.target.value)}
            disabled={!canEdit || busy}
          />
        </div>
        {error ? <p className="error">{error}</p> : null}
        {message ? <p className="muted">{message}</p> : null}
        {canEdit ? (
          <button type="submit" className="btn" disabled={busy}>
            {busy ? 'Đang lưu…' : 'Lưu cài đặt'}
          </button>
        ) : null}
      </form>
      <p className="muted" style={{ marginTop: '1rem', marginBottom: 0 }}>
        PDF export performance hiện ở dạng stub — báo cáo đầy đủ sẽ có ở Phase 4.
      </p>
    </section>
  );
}
