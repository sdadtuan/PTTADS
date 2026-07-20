'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { fetchHubCampaignMaps, staffMe, staffRefresh } from '@/lib/api';
import type { HubMapRow } from '@/lib/api';
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

export function CrmHubContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const campaignFilter = searchParams.get('campaign_id') ?? '';

  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [maps, setMaps] = useState<HubMapRow[]>([]);
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
      if (!hasCap(me, 'crm_agency', 'view')) {
        setError('Không có quyền Hub map');
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
      setLoading(true);
      try {
        const out = await fetchHubCampaignMaps(access, {
          campaign_id: campaignFilter || undefined,
        });
        setMaps(out.maps);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải hub map thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, campaignFilter]);

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

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card">
        <p className="muted" style={{ marginTop: 0 }}>
          Hub campaign map (PG) · Phase 2
          {campaignFilter ? ` · filter campaign_id=${campaignFilter}` : ''}
        </p>
        {error ? <p className="error">{error}</p> : null}

        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>Client</th>
                <th>Hub ID</th>
                <th>Meta campaign</th>
                <th>Target CPL</th>
                <th>Active</th>
              </tr>
            </thead>
            <tbody>
              {maps.map((m, i) => (
                <tr key={`${m.client_id}-${m.external_campaign_id}-${i}`}>
                  <td>
                    {m.client_id ? (
                      <Link href={`/agency/clients/${m.client_id}`} className="nav-link">
                        {m.client_code || m.client_name || m.client_id.slice(0, 8)}
                      </Link>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>{m.hub_campaign_id ?? '—'}</td>
                  <td>{m.external_campaign_name || m.external_campaign_id || '—'}</td>
                  <td>
                    {m.target_cpl_vnd != null
                      ? Math.round(m.target_cpl_vnd).toLocaleString('vi-VN') + ' ₫'
                      : '—'}
                  </td>
                  <td>{m.active ? '✓' : '—'}</td>
                </tr>
              ))}
              {!loading && maps.length === 0 ? (
                <tr>
                  <td colSpan={5} className="muted">
                    Chưa có map — chạy ./scripts/sync_hub_campaign_map.sh
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
