'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchFacebookHub, fetchGoogleHub, staffMe, staffRefresh } from '@/lib/api';
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

function AdsCombinedContent() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null);
  const [google, setGoogle] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');

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

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      try {
        const [m, g] = await Promise.all([
          fetchFacebookHub(access, { days: 7 }).catch(() => null),
          fetchGoogleHub(access, { days: 7 }).catch(() => null),
        ]);
        setMeta(m?.summary ?? null);
        setGoogle(g?.summary ?? null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải combined view thất bại');
      }
    })();
  }, [ensureAuth]);

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 1000, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <h1 style={{ fontSize: '1.25rem' }}>Ads CPL — Meta + Google</h1>
      <p className="muted">Tổng quan 7 ngày gần nhất · drill-down từng kênh</p>
      {error ? <p className="error">{error}</p> : null}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
        <div className="card">
          <h2 style={{ marginTop: 0, fontSize: '1.05rem' }}>Meta</h2>
          <p className="muted">Spend: {fmtVnd(Number(meta?.total_spend ?? 0))}</p>
          <p className="muted">Leads: {String(meta?.total_leads ?? 0)} · CPL TB: {fmtVnd(meta?.avg_cpl as number)}</p>
          <Link href="/meta/facebook-ads" className="nav-link">
            Mở Meta hub →
          </Link>
        </div>
        <div className="card">
          <h2 style={{ marginTop: 0, fontSize: '1.05rem' }}>Google</h2>
          <p className="muted">Spend: {fmtVnd(Number(google?.total_spend ?? 0))}</p>
          <p className="muted">Leads: {String(google?.total_leads ?? 0)} · CPL TB: {fmtVnd(google?.avg_cpl as number)}</p>
          <Link href="/google/google-ads" className="nav-link">
            Mở Google hub →
          </Link>
        </div>
      </div>
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
