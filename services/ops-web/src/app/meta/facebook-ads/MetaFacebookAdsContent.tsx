'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  downloadFacebookHubExport,
  fetchAgencyClients,
  fetchFacebookAdsMigrationStatus,
  fetchFacebookHub,
  staffMe,
  staffRefresh,
  type AgencyClient,
  type FacebookAdsMigrationStatus,
  type FacebookHubResponse,
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

function fmtVnd(n: number | null | undefined): string {
  if (n == null) return '—';
  return Math.round(n).toLocaleString('vi-VN') + ' ₫';
}

function yesterdayIso(): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}

function opsWebLink(path: string): string {
  if (path.startsWith('/crm/hub')) return '/crm/hub';
  if (path.startsWith('/crm/agency')) return path.replace('/crm/agency', '/agency');
  return path;
}

export function MetaFacebookAdsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [hub, setHub] = useState<FacebookHubResponse | null>(null);
  const [migration, setMigration] = useState<FacebookAdsMigrationStatus | null>(null);
  const [clientOptions, setClientOptions] = useState<AgencyClient[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [exportBusy, setExportBusy] = useState(false);

  const [days, setDays] = useState(Number(searchParams.get('days') ?? 7) || 7);
  const [dateTo, setDateTo] = useState(searchParams.get('date_to') ?? yesterdayIso());
  const [dateFrom, setDateFrom] = useState(searchParams.get('date_from') ?? '');
  const [clientId, setClientId] = useState(searchParams.get('client_id') ?? '');
  const [status, setStatus] = useState(searchParams.get('status') ?? '');
  const [q, setQ] = useState(searchParams.get('q') ?? '');
  const [exportScope, setExportScope] = useState<'clients' | 'campaigns'>('clients');

  const hubQuery = useMemo(
    () => ({
      days: dateFrom ? undefined : days,
      date_to: dateTo || undefined,
      date_from: dateFrom || undefined,
      status: status || undefined,
      client_id: clientId || undefined,
      q: q || undefined,
    }),
    [clientId, dateFrom, dateTo, days, q, status],
  );

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
      const ok =
        hasCap(me, 'crm_facebook_ads', 'view') || hasCap(me, 'crm_agency', 'view');
      if (!ok) {
        setError('Không có quyền Meta hub');
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
      return access;
    }
  }, [router]);

  const syncUrl = useCallback(() => {
    const qs = new URLSearchParams();
    if (days !== 7) qs.set('days', String(days));
    if (dateTo) qs.set('date_to', dateTo);
    if (dateFrom) qs.set('date_from', dateFrom);
    if (clientId) qs.set('client_id', clientId);
    if (status) qs.set('status', status);
    if (q) qs.set('q', q);
    const suffix = qs.toString();
    router.replace(suffix ? `/meta/facebook-ads?${suffix}` : '/meta/facebook-ads', {
      scroll: false,
    });
  }, [clientId, dateFrom, dateTo, days, q, router, status]);

  const loadHub = useCallback(
    async (access: string) => {
      setLoading(true);
      setError('');
      try {
        const data = await fetchFacebookHub(access, hubQuery);
        setHub(data);
        syncUrl();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải Meta hub thất bại');
      } finally {
        setLoading(false);
      }
    },
    [hubQuery, syncUrl],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      try {
        const list = await fetchAgencyClients(access, { status: 'active' });
        setClientOptions(list.clients ?? []);
      } catch {
        /* optional filter list */
      }
      try {
        const mig = await fetchFacebookAdsMigrationStatus(access);
        setMigration(mig);
      } catch {
        /* optional */
      }
      await loadHub(access);
    })();
  }, [ensureAuth, loadHub]);

  async function handleRefresh() {
    const access = getAccessToken();
    if (!access) return;
    await loadHub(access);
  }

  async function handleExport() {
    const access = getAccessToken();
    if (!access) return;
    setExportBusy(true);
    setError('');
    try {
      const { blob, filename } = await downloadFacebookHubExport(access, {
        ...hubQuery,
        scope: exportScope,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export CSV thất bại');
    } finally {
      setExportBusy(false);
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

  const summary = hub?.summary ?? {};
  const rows = hub?.clients ?? [];

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />

      {migration?.flask_meta_ads_admin_retired ? (
        <div
          className="card"
          style={{
            marginBottom: '1rem',
            borderLeft: '4px solid var(--accent, #2563eb)',
            padding: '0.75rem 1rem',
          }}
        >
          <p style={{ margin: 0 }}>
            Hub Meta canonical trên ops-web · Flask <code>/crm/facebook-ads</code> đã retire (M1-G09).
            Bookmark cũ trên rs.pttads.vn sẽ redirect về đây.
          </p>
        </div>
      ) : null}

      <div className="card" style={{ marginBottom: '1rem' }}>
        <h1 style={{ marginTop: 0, fontSize: '1.25rem' }}>Meta Ads Hub</h1>
        <p className="muted" style={{ marginTop: 0 }}>
          Closed-loop spend + CPL · kỳ {hub?.date_from ?? '—'} → {hub?.date_to ?? '—'}
          {hub?.window_days ? ` (${hub.window_days} ngày)` : ''}
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <Link href="/crm/hub" className="btn btn-sm btn-secondary">
            Hub campaign map
          </Link>
          <Link href="/agency/clients" className="btn btn-sm btn-secondary">
            Agency clients
          </Link>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
            gap: '0.75rem',
            marginBottom: '1rem',
          }}
        >
          <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
            Khoảng ngày
            <select
              value={days}
              disabled={Boolean(dateFrom)}
              onChange={(e) => setDays(Number(e.target.value))}
              style={{ padding: '0.4rem' }}
            >
              <option value={7}>7 ngày</option>
              <option value={14}>14 ngày</option>
              <option value={28}>28 ngày</option>
              <option value={90}>90 ngày</option>
            </select>
          </label>
          <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
            Đến ngày
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              style={{ padding: '0.4rem' }}
            />
          </label>
          <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
            Từ ngày (tuỳ chọn)
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              style={{ padding: '0.4rem' }}
            />
          </label>
          <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
            Client
            <select
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              style={{ padding: '0.4rem' }}
            >
              <option value="">Tất cả</option>
              {clientOptions.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code || c.name} ({c.status})
                </option>
              ))}
            </select>
          </label>
          <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
            Status
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              style={{ padding: '0.4rem' }}
            >
              <option value="">Tất cả</option>
              <option value="active">active</option>
              <option value="onboarding">onboarding</option>
              <option value="prospect">prospect</option>
            </select>
          </label>
          <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
            Tìm mã/tên
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="TCLT…"
              style={{ padding: '0.4rem' }}
            />
          </label>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <button type="button" className="btn btn-sm" disabled={loading} onClick={() => void handleRefresh()}>
            {loading ? 'Đang tải…' : 'Áp dụng / Làm mới'}
          </button>
          <select
            value={exportScope}
            onChange={(e) => setExportScope(e.target.value as 'clients' | 'campaigns')}
            style={{ padding: '0.35rem' }}
            aria-label="Export scope"
          >
            <option value="clients">Export CSV — theo client</option>
            <option value="campaigns">Export CSV — theo campaign</option>
          </select>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={exportBusy || loading}
            onClick={() => void handleExport()}
          >
            {exportBusy ? 'Đang export…' : 'Tải CSV'}
          </button>
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <div
        className="card"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
          gap: '1rem',
          marginBottom: '1rem',
        }}
      >
        <div>
          <p className="muted" style={{ margin: 0 }}>
            Spend
          </p>
          <strong>{fmtVnd(Number(summary.total_spend ?? 0))}</strong>
        </div>
        <div>
          <p className="muted" style={{ margin: 0 }}>
            Leads CRM
          </p>
          <strong>{String(summary.total_leads ?? 0)}</strong>
        </div>
        <div>
          <p className="muted" style={{ margin: 0 }}>
            CPL TB
          </p>
          <strong>{fmtVnd(summary.avg_cpl as number | null)}</strong>
        </div>
        <div>
          <p className="muted" style={{ margin: 0 }}>
            Clients
          </p>
          <strong>{String(summary.meta_clients ?? rows.length)}</strong>
        </div>
        <div>
          <p className="muted" style={{ margin: 0 }}>
            Chưa map
          </p>
          <strong>{String(summary.unmapped_campaigns ?? 0)}</strong>
        </div>
        <div>
          <p className="muted" style={{ margin: 0 }}>
            Vượt target
          </p>
          <strong>{String(summary.over_target_rows ?? 0)}</strong>
        </div>
      </div>

      {hub?.alerts?.length ? (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Alerts</h2>
          <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
            {hub.alerts.map((alert) => (
              <li key={alert.message} style={{ marginBottom: '0.5rem' }}>
                <span className={alert.severity === 'danger' ? 'error' : 'muted'}>{alert.message}</span>{' '}
                <Link href={opsWebLink(alert.link)} className="nav-link">
                  {alert.link_label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="card" id="clients-table">
        <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Clients overview</h2>
        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>Client</th>
                <th>Status</th>
                <th>Spend</th>
                <th>Leads</th>
                <th>CPL</th>
                <th>Campaigns</th>
                <th>Chưa map</th>
                <th>Vượt target</th>
                <th>Token</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link href={`/agency/clients/${c.id}`} className="nav-link">
                      {c.code || c.name}
                    </Link>
                  </td>
                  <td>{c.status ?? '—'}</td>
                  <td>{fmtVnd(c.spend)}</td>
                  <td>{c.leads_crm}</td>
                  <td>{fmtVnd(c.cpl)}</td>
                  <td>{c.campaigns}</td>
                  <td>{c.unmapped_campaigns ?? 0}</td>
                  <td>{c.over_target_rows}</td>
                  <td>{c.token_status ?? (c.meta_has_token ? 'ok' : '—')}</td>
                </tr>
              ))}
              {!loading && rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="muted">
                    Không có dữ liệu Meta cho bộ lọc đã chọn
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
