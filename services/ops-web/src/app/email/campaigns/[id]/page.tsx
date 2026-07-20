'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { EmailStatusBadge, PreflightChecklist, CampaignExperimentPanel } from '@/components/email';
import { emailSendEnabled } from '@/lib/email-flags';
import {
  fetchEmailCampaign,
  preflightEmailCampaign,
  scheduleEmailCampaign,
  staffMe,
  staffRefresh,
  type EmailCampaignRow,
  type EmailPreflightCheck,
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

export default function EmailCampaignDetailPage() {
  const router = useRouter();
  const params = useParams();
  const campaignId = String(params.id ?? '');
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [campaign, setCampaign] = useState<EmailCampaignRow | null>(null);
  const [checks, setChecks] = useState<EmailPreflightCheck[]>([]);
  const [preflightPassed, setPreflightPassed] = useState<boolean | null>(null);
  const [scheduleAt, setScheduleAt] = useState('');
  const [scheduling, setScheduling] = useState(false);
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
      setError('');
      try {
        const row = await fetchEmailCampaign(access, campaignId);
        setCampaign(row);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải campaign thất bại');
      }
    },
    [campaignId],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await load(access);
    })();
  }, [ensureAuth, load]);

  async function runPreflight() {
    const access = getAccessToken();
    if (!access) return;
    setError('');
    try {
      const out = await preflightEmailCampaign(access, campaignId);
      setChecks(out.checks);
      setPreflightPassed(out.passed);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Preflight thất bại');
    }
  }

  async function scheduleSend() {
    const access = getAccessToken();
    if (!access || !scheduleAt.trim()) return;
    setScheduling(true);
    setError('');
    try {
      const row = await scheduleEmailCampaign(access, campaignId, new Date(scheduleAt).toISOString());
      setCampaign(row);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Schedule thất bại');
    } finally {
      setScheduling(false);
    }
  }

  if (!user) return <main style={{ padding: '2rem' }}><p className="muted">Đang tải…</p></main>;

  const canSubmit =
    campaign?.status === 'draft' &&
    (hasCap(user, 'crm_email_mkt', 'write') || hasCap(user, 'crm_agency', 'create'));

  const canSchedule =
    campaign?.status === 'approved' &&
    (hasCap(user, 'crm_email_mkt', 'approve') || hasCap(user, 'crm_agency', 'create'));

  const canWriteExperiment =
    hasCap(user, 'crm_email_mkt', 'write') || hasCap(user, 'crm_agency', 'create');
  const accessToken = getAccessToken();

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>EM-10 E-09 — Campaign detail</p>
        <Link href="/email/campaigns" className="btn btn-secondary btn-sm">← Campaigns</Link>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {campaign ? (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h2 style={{ marginTop: 0 }}>{campaign.name}</h2>
          <p className="muted">Client: {campaign.client_name}</p>
          <p className="muted">
            Status: <EmailStatusBadge status={campaign.status} />
          </p>
          {campaign.scheduled_at ? (
            <p className="muted">
              Scheduled: {campaign.scheduled_at.slice(0, 16).replace('T', ' ')}
            </p>
          ) : null}
          <p className="muted">Segment: {campaign.segment_name ?? '—'}</p>
          <p className="muted">Template: {campaign.template_name}</p>
          <p className="muted">Audience: {campaign.audience_count ?? '—'}</p>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '1rem' }}>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => void runPreflight()}>
              Preflight
            </button>
            {canSubmit ? (
              <Link href={`/email/campaigns/${campaignId}/review`} className="btn btn-sm">
                Review & submit
              </Link>
            ) : null}
            {campaign.status === 'pending_approval' ? (
              <Link href={`/email/campaigns/${campaignId}/review`} className="btn btn-sm">
                Review & approve
              </Link>
            ) : null}
            {campaign.template_id ? (
              <Link href={`/email/templates/${campaign.template_id}`} className="btn btn-secondary btn-sm">
                Mở template
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}
      {campaign && accessToken ? (
        <CampaignExperimentPanel
          token={accessToken}
          campaignId={campaignId}
          clientId={campaign.client_id}
          canWrite={canWriteExperiment}
        />
      ) : null}
      {canSchedule && emailSendEnabled() ? (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Schedule send</h2>
          <label className="muted">
            Thời gian gửi{' '}
            <input
              type="datetime-local"
              value={scheduleAt}
              onChange={(e) => setScheduleAt(e.target.value)}
              style={{ marginLeft: '0.35rem' }}
            />
          </label>
          <div style={{ marginTop: '0.75rem' }}>
            <button
              type="button"
              className="btn btn-sm"
              disabled={!scheduleAt.trim() || scheduling}
              onClick={() => void scheduleSend()}
            >
              {scheduling ? '…' : 'Lưu lịch gửi'}
            </button>
          </div>
        </div>
      ) : null}
      {checks.length > 0 ? (
        <div className="card">
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>
            Preflight {preflightPassed ? '✓ passed' : '✗ failed'}
          </h2>
          <PreflightChecklist checks={checks} />
        </div>
      ) : null}
    </main>
  );
}
