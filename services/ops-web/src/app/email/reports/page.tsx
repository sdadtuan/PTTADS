'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { EmailEngagementChart } from '@/lib/email-charts';
import { EmailKpiCard } from '@/components/email';
import {
  createEmailReportSchedule,
  exportEmailClickhouse,
  fetchEmailDeliverabilityReport,
  fetchEmailEngagementSeries,
  fetchEmailReportSchedules,
  fetchEmailReportsSummary,
  runEmailReportSchedule,
  staffMe,
  staffRefresh,
  type EmailDeliverabilityReport,
  type EmailEngagementPoint,
  type EmailReportScheduleRow,
  type EmailReportsSummary,
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

export default function EmailReportsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [summary, setSummary] = useState<EmailReportsSummary | null>(null);
  const [deliverability, setDeliverability] = useState<EmailDeliverabilityReport | null>(null);
  const [series, setSeries] = useState<EmailEngagementPoint[]>([]);
  const [schedules, setSchedules] = useState<EmailReportScheduleRow[]>([]);
  const [exportMsg, setExportMsg] = useState('');
  const [scheduleMsg, setScheduleMsg] = useState('');
  const [scheduleEmail, setScheduleEmail] = useState('');
  const [clientId, setClientId] = useState('');
  const [days, setDays] = useState(28);
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
        const [sum, del, eng] = await Promise.all([
          fetchEmailReportsSummary(access, { client_id: cid, days }),
          fetchEmailDeliverabilityReport(access, { client_id: cid, days: 30 }),
          fetchEmailEngagementSeries(access, { client_id: cid, days }),
        ]);
        setSummary(sum);
        setDeliverability(del);
        setSeries(eng.points);
        if (cid) {
          const sched = await fetchEmailReportSchedules(access, cid);
          setSchedules(sched.items ?? []);
        } else {
          setSchedules([]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải báo cáo thất bại');
      } finally {
        setLoading(false);
      }
    },
    [clientId, days],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await load(access);
    })();
  }, [ensureAuth, load]);

  if (!user) return <main style={{ padding: '2rem' }}><p className="muted">Đang tải…</p></main>;

  const canExport =
    hasCap(user, 'crm_email_mkt', 'reports') ||
    hasCap(user, 'crm_email_mkt', 'write') ||
    hasCap(user, 'crm_agency', 'view');

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>EM-3 E-12 — Analytics center</p>
        <Link href="/email/hub" className="btn btn-secondary btn-sm">← Hub</Link>
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
          <input value={clientId} onChange={(e) => setClientId(e.target.value)} placeholder="Client UUID (all)" style={{ width: 280 }} />
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>7 ngày</option>
            <option value={28}>28 ngày</option>
            <option value={90}>90 ngày</option>
          </select>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => { const a = getAccessToken(); if (a) void load(a); }}>Làm mới</button>
          {canExport ? (
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => {
                const access = getAccessToken();
                if (!access) return;
                setExportMsg('');
                void exportEmailClickhouse(access, { client_id: clientId.trim() || undefined })
                  .then((out) => setExportMsg(out.job_id ? `Queued job ${out.job_id}` : `Mode: ${out.mode}`))
                  .catch((err) => setExportMsg(err instanceof Error ? err.message : 'Export failed'));
              }}
            >
              Export ClickHouse
            </button>
          ) : null}
        </div>
      </div>
      {exportMsg ? <p className="muted">{exportMsg}</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {summary ? (
        <div className="email-kpi-grid" style={{ marginBottom: '1rem' }}>
          <EmailKpiCard label="Sent" value={summary.sent.toLocaleString()} />
          <EmailKpiCard label="Delivered" value={summary.delivered.toLocaleString()} />
          <EmailKpiCard label="Open rate" value={`${summary.open_rate_pct}%`} />
          <EmailKpiCard label="Click rate" value={`${summary.click_rate_pct}%`} />
          <EmailKpiCard label="Unsubs" value={summary.unsubscribes} />
          <EmailKpiCard label="Revenue attrib." value={summary.revenue_attrib} />
        </div>
      ) : null}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
        <div className="card">
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Engagement ({days}d)</h2>
          <EmailEngagementChart points={series} days={days} />
        </div>
        <div className="card">
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Deliverability scorecard</h2>
          {deliverability ? (
            <>
              <p className="muted">Bounce rate: <strong>{deliverability.bounce_rate_pct}%</strong></p>
              <p className="muted">Complaint rate: <strong>{deliverability.complaint_rate_pct}%</strong></p>
              <p className="muted">Paused domains: <strong>{deliverability.paused_domains}</strong></p>
              <p className="muted">Domains tracked: <strong>{deliverability.domains.length}</strong></p>
            </>
          ) : (
            <p className="muted">—</p>
          )}
        </div>
      </div>
      {canExport && clientId.trim() ? (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Scheduled PDF reports</h2>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
            <input
              value={scheduleEmail}
              onChange={(e) => setScheduleEmail(e.target.value)}
              placeholder="recipient@example.com"
              style={{ width: 260 }}
            />
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                const access = getAccessToken();
                if (!access || !scheduleEmail.trim()) return;
                setScheduleMsg('');
                void createEmailReportSchedule(access, {
                  client_id: clientId.trim(),
                  report_type: 'executive',
                  cadence: 'weekly',
                  recipient_emails: [scheduleEmail.trim()],
                })
                  .then(() => fetchEmailReportSchedules(access, clientId.trim()))
                  .then((out) => {
                    setSchedules(out.items ?? []);
                    setScheduleMsg('Schedule created');
                  })
                  .catch((err) => setScheduleMsg(err instanceof Error ? err.message : 'Create failed'));
              }}
            >
              Add weekly schedule
            </button>
          </div>
          {scheduleMsg ? <p className="muted">{scheduleMsg}</p> : null}
          {schedules.length === 0 ? (
            <p className="muted">Chưa có lịch báo cáo cho client này.</p>
          ) : (
            <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
              {schedules.map((s) => (
                <li key={s.id} style={{ marginBottom: '0.35rem' }}>
                  {s.report_type} · {s.cadence} · next {s.next_run_at ?? '—'}
                  {' · '}
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      const access = getAccessToken();
                      if (!access) return;
                      void runEmailReportSchedule(access, s.id).then((out) =>
                        setScheduleMsg(out.job_id ? `Run queued ${out.job_id}` : 'Run queued'),
                      );
                    }}
                  >
                    Run now
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </main>
  );
}
