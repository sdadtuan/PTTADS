'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchFacebookHub,
  fetchGoogleHub,
  fetchZaloHub,
  staffMe,
  staffRefresh,
  type FacebookHubAlert,
  type FacebookHubResponse,
  type GoogleHubResponse,
  type ZaloHubResponse,
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

type ChannelTab = 'all' | 'meta' | 'google' | 'zalo';

function fmtVnd(n: number | null | undefined): string {
  if (n == null) return '—';
  return Math.round(n).toLocaleString('vi-VN') + ' ₫';
}

function AdsCombinedContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [tab, setTab] = useState<ChannelTab>((searchParams.get('channel') as ChannelTab) || 'all');
  const [days, setDays] = useState(Number(searchParams.get('days') ?? 7) || 7);
  const [metaHub, setMetaHub] = useState<FacebookHubResponse | null>(null);
  const [googleHub, setGoogleHub] = useState<GoogleHubResponse | null>(null);
  const [zaloHub, setZaloHub] = useState<ZaloHubResponse | null>(null);
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
      const ok =
        hasCap(me, 'crm_facebook_ads', 'view') ||
        hasCap(me, 'crm_google_ads', 'view') ||
        hasCap(me, 'crm_zalo_ads', 'view') ||
        hasCap(me, 'crm_agency', 'view');
      if (!ok) {
        setError('Không có quyền xem Ads CPL');
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
      return out.access_token;
    }
  }, [router]);

  const load = useCallback(async () => {
    const access = await ensureAuth();
    if (!access) return;
    setLoading(true);
    setError('');
    const params = { days };
    try {
      const [m, g, z] = await Promise.all([
        fetchFacebookHub(access, params).catch(() => null),
        fetchGoogleHub(access, params).catch(() => null),
        fetchZaloHub(access, params).catch(() => null),
      ]);
      setMetaHub(m);
      setGoogleHub(g);
      setZaloHub(z);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải combined view thất bại');
    } finally {
      setLoading(false);
    }
  }, [days, ensureAuth]);

  useEffect(() => {
    void load();
  }, [load]);

  const alerts = useMemo(() => {
    const out: FacebookHubAlert[] = [];
    if (tab === 'all' || tab === 'meta') out.push(...(metaHub?.alerts ?? []));
    if (tab === 'all' || tab === 'google') out.push(...(googleHub?.alerts ?? []));
    if (tab === 'all' || tab === 'zalo') out.push(...(zaloHub?.alerts ?? []));
    return out;
  }, [tab, metaHub, googleHub, zaloHub]);

  const combinedRows = useMemo(() => {
    const map = new Map<
      string,
      { id: string; code: string; name: string; meta?: number; google?: number; zalo?: number }
    >();
    for (const c of metaHub?.clients ?? []) {
      map.set(c.id, {
        id: c.id,
        code: c.code ?? c.id,
        name: c.name ?? '—',
        meta: c.spend,
      });
    }
    for (const c of googleHub?.clients ?? []) {
      const row = map.get(c.id) ?? { id: c.id, code: c.code ?? c.id, name: c.name ?? '—' };
      row.google = c.spend;
      map.set(c.id, row);
    }
    for (const c of zaloHub?.clients ?? []) {
      const row = map.get(c.id) ?? { id: c.id, code: c.code ?? c.id, name: c.name ?? '—' };
      row.zalo = c.spend;
      map.set(c.id, row);
    }
    return [...map.values()].sort(
      (a, b) =>
        (b.meta ?? 0) + (b.google ?? 0) + (b.zalo ?? 0) -
        ((a.meta ?? 0) + (a.google ?? 0) + (a.zalo ?? 0)),
    );
  }, [metaHub, googleHub, zaloHub]);

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  const metaSummary = metaHub?.summary ?? {};
  const googleSummary = googleHub?.summary ?? {};
  const zaloSummary = zaloHub?.summary ?? {};

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <h1 style={{ fontSize: '1.25rem' }}>Ads CPL — Combined</h1>
      <p className="muted">Meta + Google + Zalo · filter theo kênh · T-{days}</p>

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', margin: '1rem 0' }}>
        {(['all', 'meta', 'google', 'zalo'] as ChannelTab[]).map((ch) => (
          <button
            key={ch}
            type="button"
            className={tab === ch ? 'btn btn-sm' : 'btn btn-sm btn-muted'}
            onClick={() => setTab(ch)}
          >
            {ch === 'all' ? 'Tất cả' : ch.charAt(0).toUpperCase() + ch.slice(1)}
          </button>
        ))}
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          style={{ marginLeft: 'auto' }}
        >
          <option value={7}>T-7</option>
          <option value={30}>T-30</option>
        </select>
        <button type="button" className="btn btn-sm" onClick={() => void load()} disabled={loading}>
          Refresh
        </button>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '1rem',
          marginBottom: '1rem',
        }}
      >
        {(tab === 'all' || tab === 'meta') && (
          <div className="card">
            <h2 style={{ marginTop: 0, fontSize: '1.05rem' }}>Meta</h2>
            <p className="muted">Spend: {fmtVnd(Number(metaSummary.total_spend ?? 0))}</p>
            <p className="muted">
              Leads: {String(metaSummary.total_leads ?? 0)} · CPL: {fmtVnd(metaSummary.avg_cpl as number)}
            </p>
            <Link href="/meta/facebook-ads" className="nav-link">Meta hub →</Link>
          </div>
        )}
        {(tab === 'all' || tab === 'google') && (
          <div className="card">
            <h2 style={{ marginTop: 0, fontSize: '1.05rem' }}>Google</h2>
            <p className="muted">Spend: {fmtVnd(Number(googleSummary.total_spend ?? 0))}</p>
            <p className="muted">
              Leads: {String(googleSummary.total_leads ?? 0)} · CPL: {fmtVnd(googleSummary.avg_cpl as number)}
            </p>
            <Link href="/google/google-ads" className="nav-link">Google hub →</Link>
          </div>
        )}
        {(tab === 'all' || tab === 'zalo') && (
          <div className="card">
            <h2 style={{ marginTop: 0, fontSize: '1.05rem' }}>Zalo</h2>
            <p className="muted">Spend: {fmtVnd(Number(zaloSummary.total_spend ?? 0))}</p>
            <p className="muted">
              Leads: {String(zaloSummary.total_leads ?? 0)} · CPL: {fmtVnd(zaloSummary.avg_cpl as number)}
            </p>
            <p className="muted">
              Won: {String(zaloSummary.total_conversions ?? 0)} · CPA: {fmtVnd(zaloSummary.avg_cpa as number)}
            </p>
            <Link href="/zalo/zalo-ads" className="nav-link">Zalo hub →</Link>
          </div>
        )}
      </div>

      {alerts.length ? (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h2 style={{ marginTop: 0, fontSize: '1.05rem' }}>Alerts</h2>
          <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
            {alerts.map((a) => (
              <li key={a.message} style={{ marginBottom: '0.35rem' }}>
                {a.message}{' '}
                <Link href={a.link} className="nav-link">{a.link_label}</Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {tab === 'all' ? (
        <div className="card">
          <h2 style={{ marginTop: 0, fontSize: '1.05rem' }}>Clients — spend theo kênh</h2>
          <div style={{ overflowX: 'auto' }}>
            <table className="perf-table">
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Meta spend</th>
                  <th>Google spend</th>
                  <th>Zalo spend</th>
                </tr>
              </thead>
              <tbody>
                {combinedRows.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <Link href={`/agency/clients/${r.id}`} className="nav-link">
                        {r.code || r.name}
                      </Link>
                    </td>
                    <td>{fmtVnd(r.meta ?? null)}</td>
                    <td>{fmtVnd(r.google ?? null)}</td>
                    <td>{fmtVnd(r.zalo ?? null)}</td>
                  </tr>
                ))}
                {!loading && combinedRows.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="muted">Không có dữ liệu</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </main>
  );
}

export default function AdsCombinedPage() {
  return (
    <Suspense fallback={<main style={{ padding: '2rem' }}><p className="muted">Đang tải…</p></main>}>
      <AdsCombinedContent />
    </Suspense>
  );
}
