'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { EmailApprovalTimeline, EmailStatusBadge, PreflightChecklist } from '@/components/email';
import { emailSendEnabled } from '@/lib/email-flags';
import {
  approveEmailCampaign,
  fetchEmailCampaign,
  preflightEmailCampaign,
  submitEmailCampaign,
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

function toDatetimeLocalValue(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function EmailCampaignReviewPage() {
  const router = useRouter();
  const params = useParams();
  const campaignId = String(params.id ?? '');
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [campaign, setCampaign] = useState<EmailCampaignRow | null>(null);
  const [checks, setChecks] = useState<EmailPreflightCheck[]>([]);
  const [preflightPassed, setPreflightPassed] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [approving, setApproving] = useState(false);
  const [scheduleAt, setScheduleAt] = useState('');

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

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setError('');
      try {
        const row = await fetchEmailCampaign(access, campaignId);
        setCampaign(row);
        setScheduleAt(toDatetimeLocalValue(row.scheduled_at));
        const pf = await preflightEmailCampaign(access, campaignId);
        setChecks(pf.checks);
        setPreflightPassed(pf.passed);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải review thất bại');
      }
    })();
  }, [ensureAuth, campaignId]);

  async function submit() {
    const access = getAccessToken();
    if (!access || !preflightPassed) return;
    setSubmitting(true);
    setError('');
    try {
      const row = await submitEmailCampaign(access, campaignId);
      setCampaign(row);
      router.push(`/email/campaigns/${campaignId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submit thất bại');
    } finally {
      setSubmitting(false);
    }
  }

  async function approve() {
    const access = getAccessToken();
    if (!access || !preflightPassed) return;
    setApproving(true);
    setError('');
    try {
      const scheduled_at = scheduleAt.trim()
        ? new Date(scheduleAt).toISOString()
        : undefined;
      const row = await approveEmailCampaign(access, campaignId, { scheduled_at });
      setCampaign(row);
      router.push(`/email/campaigns/${campaignId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approve thất bại');
    } finally {
      setApproving(false);
    }
  }

  if (!user) return <main style={{ padding: '2rem' }}><p className="muted">Đang tải…</p></main>;

  const canSubmit =
    campaign?.status === 'draft' &&
    (hasCap(user, 'crm_email_mkt', 'write') || hasCap(user, 'crm_agency', 'create'));

  const canApprove =
    campaign?.status === 'pending_approval' &&
    (hasCap(user, 'crm_email_mkt', 'approve') || hasCap(user, 'crm_agency', 'create'));

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>EM-10 E-09c — Campaign review, preflight & approve</p>
        <Link href={`/email/campaigns/${campaignId}`} className="btn btn-secondary btn-sm">← Campaign</Link>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {campaign ? (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h2 style={{ marginTop: 0 }}>{campaign.name}</h2>
          <p className="muted">
            {campaign.client_name} · audience {campaign.audience_count ?? 0} ·{' '}
            <EmailStatusBadge status={campaign.status} />
          </p>
          {campaign.scheduled_at ? (
            <p className="muted">Scheduled: {campaign.scheduled_at.slice(0, 16).replace('T', ' ')}</p>
          ) : null}
          <EmailApprovalTimeline status={campaign.status} />
        </div>
      ) : null}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>
          Preflight checklist {preflightPassed ? '✓' : '✗'}
        </h2>
        <PreflightChecklist checks={checks} />
      </div>
      {canSubmit ? (
        <button
          type="button"
          className="btn"
          disabled={!preflightPassed || submitting || !emailSendEnabled()}
          onClick={() => void submit()}
          title={!emailSendEnabled() ? 'Send platform disabled' : undefined}
        >
          {submitting ? '…' : 'Submit for approval'}
        </button>
      ) : null}
      {canApprove ? (
        <div className="card" style={{ marginTop: '1rem' }}>
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Staff approve</h2>
          <label className="muted" style={{ display: 'block', marginBottom: '0.75rem' }}>
            Schedule send (optional){' '}
            <input
              type="datetime-local"
              value={scheduleAt}
              onChange={(e) => setScheduleAt(e.target.value)}
              style={{ marginLeft: '0.35rem' }}
            />
          </label>
          <p className="muted" style={{ marginTop: 0 }}>
            Để trống = gửi ngay sau approve. Chọn thời gian tương lai = status scheduled, cron enqueue prepare.
          </p>
          <button
            type="button"
            className="btn"
            disabled={!preflightPassed || approving || !emailSendEnabled()}
            onClick={() => void approve()}
          >
            {approving ? '…' : scheduleAt.trim() ? 'Approve & schedule' : 'Approve & send'}
          </button>
        </div>
      ) : null}
      {!canSubmit && !canApprove ? (
        <p className="muted">Campaign không ở trạng thái draft/pending hoặc thiếu quyền.</p>
      ) : null}
    </main>
  );
}
