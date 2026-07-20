'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  EmailAlertBanner,
  EmailEmptyState,
  EmailHealthDot,
  EmailKpiCard,
} from '@/components/email';
import { fetchEmailHub, staffMe, staffRefresh, type EmailHubResponse } from '@/lib/api';
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

export default function EmailHubPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [hub, setHub] = useState<EmailHubResponse | null>(null);
  const [days, setDays] = useState(28);
  const [clientId, setClientId] = useState('');
  const [domain, setDomain] = useState('');
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

  const loadHub = useCallback(
    async (access: string) => {
      setLoading(true);
      setError('');
      try {
        const data = await fetchEmailHub(access, {
          days,
          domain: domain.trim() || undefined,
          client_id: clientId.trim() || undefined,
        });
        setHub(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải Email hub thất bại');
      } finally {
        setLoading(false);
      }
    },
    [clientId, days, domain],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await loadHub(access);
    })();
  }, [ensureAuth, loadHub]);

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

  const summary = hub?.summary;

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav
        user={user}
        onLogout={logout}
        emailPendingApprovals={summary?.pending_approvals}
      />
      {!hub?.schema_ready ? (
        <EmailAlertBanner
          severity="warn"
          message="Schema email_mkt chưa apply — chạy ./scripts/apply_pg_ddl_email_mkt.sh"
          link="/email/governance"
          linkLabel="Governance"
        />
      ) : null}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>
          EM-0 — Email Ops hub skeleton · Nest PG native · E-01
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <Link href="/email/clients" className="btn btn-sm">
            Clients (E-02)
          </Link>
          <Link href="/email/contacts" className="btn btn-sm">
            Contacts
          </Link>
          <Link href="/email/consent" className="btn btn-sm">
            Consent
          </Link>
          <Link href="/email/suppression" className="btn btn-sm">
            Suppression
          </Link>
          <Link href="/email/segments" className="btn btn-sm">
            Segments (E-07)
          </Link>
          <Link href="/email/templates" className="btn btn-sm">
            Templates (E-08)
          </Link>
          <Link href="/email/campaigns" className="btn btn-sm">
            Campaigns (E-09)
          </Link>
          <Link href="/email/journeys" className="btn btn-sm">
            Journeys (E-10)
          </Link>
          <Link href="/email/deliverability" className="btn btn-sm">
            Deliverability (E-11)
          </Link>
          <Link href="/email/reports" className="btn btn-sm">
            Reports (E-12)
          </Link>
          <Link href="/email/governance" className="btn btn-sm">
            Governance (E-13)
          </Link>
          {hub?.schema_ready === false ? (
            <span className="error" style={{ alignSelf: 'center' }}>
              Schema chưa apply — chạy apply_pg_ddl_email_mkt.sh
            </span>
          ) : null}
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <label className="muted">
            Days{' '}
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              style={{ marginLeft: '0.35rem' }}
            >
              <option value={7}>7</option>
              <option value={28}>28</option>
              <option value={90}>90</option>
            </select>
          </label>
          <label className="muted">
            Client UUID{' '}
            <input
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="all"
              style={{ width: 220, marginLeft: '0.35rem' }}
            />
          </label>
          <label className="muted">
            Domain{' '}
            <input
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="all"
              style={{ width: 140, marginLeft: '0.35rem' }}
            />
          </label>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={loading}
            onClick={() => {
              const access = getAccessToken();
              if (access) void loadHub(access);
            }}
          >
            Làm mới
          </button>
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}

      {loading && !summary ? (
        <div className="email-kpi-grid" style={{ marginBottom: '1rem' }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="email-skeleton" style={{ height: 72 }} />
          ))}
        </div>
      ) : null}

      {summary ? (
        <div className="email-kpi-grid" style={{ marginBottom: '1rem' }}>
          <EmailKpiCard label="Emails sent" value={summary.emails_sent.toLocaleString()} />
          <EmailKpiCard label="Open rate" value={`${summary.open_rate_pct}%`} />
          <EmailKpiCard label="Complaint" value={`${summary.complaint_rate_pct}%`} />
          <EmailKpiCard label="Revenue attrib." value={summary.revenue_attrib} />
          <EmailKpiCard label="Pending approval" value={summary.pending_approvals} />
          <EmailKpiCard label="Queue lag (min)" value={summary.send_queue_lag_minutes} />
        </div>
      ) : null}

      {hub?.alerts?.length ? (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Alerts</h2>
          <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
            {hub.alerts.map((alert) => (
              <li key={alert.message} style={{ marginBottom: '0.5rem' }}>
                <span className={alert.severity === 'danger' ? 'error' : 'muted'}>{alert.message}</span>{' '}
                <Link href={alert.link} className="nav-link">
                  {alert.link_label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
        <div className="card">
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Send calendar (7d)</h2>
          {(hub?.send_calendar ?? []).length === 0 ? (
            <p className="muted">Chưa có lịch gửi trong 7 ngày tới.</p>
          ) : (
            <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
              {hub?.send_calendar.map((item) => (
                <li key={item.campaign_id} style={{ marginBottom: '0.35rem' }}>
                  {item.scheduled_at.slice(0, 10)} — {item.client_name}: {item.campaign_name}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="card">
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Pending approvals</h2>
          {(hub?.pending_approvals ?? []).length === 0 ? (
            <p className="muted">Không có chiến dịch chờ duyệt.</p>
          ) : (
            <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
              {hub?.pending_approvals.map((item) => (
                <li key={item.campaign_id} style={{ marginBottom: '0.35rem' }}>
                  {item.client_name} — {item.campaign_name}
                  {item.audience_count != null ? ` (${item.audience_count})` : ''}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Client email health</h2>
        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>Client</th>
                <th>Domain</th>
                <th>Complaint</th>
                <th>Last send</th>
                <th>Health</th>
              </tr>
            </thead>
            <tbody>
              {(hub?.clients ?? []).map((c) => (
                <tr key={c.client_id}>
                  <td>{c.client_name}</td>
                  <td>{c.primary_domain ?? '—'}</td>
                  <td>{c.complaint_rate_pct}%</td>
                  <td>{c.last_send_at ? c.last_send_at.slice(0, 10) : '—'}</td>
                  <td>
                    <EmailHealthDot health={c.domain_health} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && (hub?.clients?.length ?? 0) === 0 ? (
            <EmailEmptyState message="Chưa có workspace email — EM-1 sẽ tạo workspace per client." ctaLabel="Thêm workspace" ctaHref="/email/clients" />
          ) : null}
        </div>
      </div>
    </main>
  );
}
