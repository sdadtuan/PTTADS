'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { EmailEmptyState, EmailStatusBadge } from '@/components/email';
import { emailSendEnabled } from '@/lib/email-flags';
import {
  createEmailCampaign,
  fetchEmailCampaigns,
  fetchEmailSegments,
  fetchEmailTemplates,
  staffMe,
  staffRefresh,
  type EmailCampaignRow,
  type EmailSegmentRow,
  type EmailTemplateRow,
} from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  hasCap,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';

export default function EmailCampaignsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [campaigns, setCampaigns] = useState<EmailCampaignRow[]>([]);
  const [segments, setSegments] = useState<EmailSegmentRow[]>([]);
  const [templates, setTemplates] = useState<EmailTemplateRow[]>([]);
  const [clientId, setClientId] = useState('');
  const [name, setName] = useState('');
  const [segmentId, setSegmentId] = useState('');
  const [templateId, setTemplateId] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

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
      if (!hasCap(me, 'crm_email_mkt', 'view') && !hasCap(me, 'crm_agency', 'view')) {
        setError('Không có quyền');
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
      setUser(await staffMe(access));
      return access;
    }
  }, [router]);

  const load = useCallback(
    async (access: string) => {
      setLoading(true);
      setError('');
      try {
        const cid = clientId.trim() || undefined;
        const [campData, segData, tmplData] = await Promise.all([
          fetchEmailCampaigns(access, { client_id: cid, status: statusFilter || undefined, limit: 100 }),
          fetchEmailSegments(access, { client_id: cid, limit: 100 }),
          fetchEmailTemplates(access, { client_id: cid, limit: 100 }),
        ]);
        setCampaigns(campData.items);
        setSegments(segData.items);
        setTemplates(tmplData.items);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải campaigns thất bại');
      } finally {
        setLoading(false);
      }
    },
    [clientId, statusFilter],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await load(access);
    })();
  }, [ensureAuth, load]);

  async function create() {
    const access = getAccessToken();
    if (!access || !clientId.trim() || !name.trim() || !templateId) return;
    setError('');
    try {
      const row = await createEmailCampaign(access, {
        client_id: clientId.trim(),
        name: name.trim(),
        template_id: templateId,
        segment_id: segmentId || undefined,
      });
      setName('');
      router.push(`/email/campaigns/${row.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo campaign thất bại');
    }
  }

  if (!user) return <main style={{ padding: '2rem' }}><p className="muted">Đang tải…</p></main>;

  const canWrite = hasCap(user, 'crm_email_mkt', 'write') || hasCap(user, 'crm_agency', 'create');

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>EM-2 E-09 — Campaign builder</p>
        <Link href="/email/hub" className="btn btn-secondary btn-sm">← Hub</Link>
        <div className="email-filter-bar" style={{ marginTop: '0.75rem' }}>
          <input value={clientId} onChange={(e) => setClientId(e.target.value)} placeholder="Client UUID" style={{ width: 280 }} />
          <div className="email-status-tabs">
            {['', 'draft', 'pending_approval', 'approved', 'sending', 'sent'].map((s) => (
              <button
                key={s || 'all'}
                type="button"
                className={statusFilter === s ? 'active' : undefined}
                onClick={() => setStatusFilter(s)}
              >
                {s || 'All'}
              </button>
            ))}
          </div>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => { const a = getAccessToken(); if (a) void load(a); }}>Làm mới</button>
        </div>
        {!emailSendEnabled() ? (
          <p className="muted" style={{ marginTop: '0.5rem' }}>
            Send platform tắt (PTT_EMAIL_SEND_ENABLED=0) — campaign chỉ draft/approval.
          </p>
        ) : null}
      </div>
      {error ? <p className="error">{error}</p> : null}
      {canWrite ? (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Tên campaign" style={{ marginRight: '0.5rem' }} />
          <select value={templateId} onChange={(e) => setTemplateId(e.target.value)} style={{ marginRight: '0.5rem' }}>
            <option value="">Template…</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
          <select value={segmentId} onChange={(e) => setSegmentId(e.target.value)} style={{ marginRight: '0.5rem' }}>
            <option value="">Segment (optional)…</option>
            {segments.map((s) => (
              <option key={s.id} value={s.id}>{s.name} ({s.member_count})</option>
            ))}
          </select>
          <button type="button" className="btn btn-sm" onClick={() => void create()}>+ Tạo campaign</button>
        </div>
      ) : null}
      <div className="card email-campaign-table-wrap">
        <table className="perf-table">
          <thead><tr><th scope="col">Name</th><th scope="col">Client</th><th scope="col">Segment</th><th scope="col">Template</th><th scope="col">Audience</th><th scope="col">Status</th><th scope="col" /></tr></thead>
          <tbody>
            {campaigns.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.client_name}</td>
                <td>{c.segment_name ?? '—'}</td>
                <td>{c.template_name}</td>
                <td>{c.audience_count ?? '—'}</td>
                <td><EmailStatusBadge status={c.status} /></td>
                <td>
                  <Link href={`/email/campaigns/${c.id}`} className="btn btn-sm">Mở</Link>
                  {c.status === 'draft' ? (
                    <Link href={`/email/campaigns/${c.id}/review`} className="btn btn-secondary btn-sm" style={{ marginLeft: '0.35rem' }}>
                      Review
                    </Link>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && campaigns.length === 0 ? (
          <EmailEmptyState message="Chưa có chiến dịch." ctaLabel="+ Chiến dịch mới" ctaHref="/email/campaigns" />
        ) : null}
      </div>
      <div className="email-campaign-cards">
        {campaigns.map((c) => (
          <div key={c.id} className="email-campaign-card">
            <strong>{c.name}</strong>
            <p className="muted" style={{ margin: '0.25rem 0' }}>{c.client_name}</p>
            <EmailStatusBadge status={c.status} />
            <div style={{ marginTop: '0.5rem' }}>
              <Link href={`/email/campaigns/${c.id}`} className="btn btn-sm">Mở</Link>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
