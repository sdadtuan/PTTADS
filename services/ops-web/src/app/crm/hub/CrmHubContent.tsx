'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { AgencyReadOnlyBadge, canAgencyWrite } from '@/components/AgencyReadOnlyBadge';
import { fetchHubCampaignMaps, patchHubCampaignMap, staffMe, staffRefresh } from '@/lib/api';
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

function normalizeMetaId(raw: string): string {
  return raw.replace(/\D/g, '').trim();
}

export function CrmHubContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const campaignFilter = searchParams.get('campaign_id') ?? '';

  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [maps, setMaps] = useState<HubMapRow[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState('');

  const canWrite = canAgencyWrite(user);

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

  const reload = useCallback(
    async (access: string) => {
      const out = await fetchHubCampaignMaps(access, {
        campaign_id: campaignFilter || undefined,
      });
      setMaps(out.maps);
      const nextDrafts: Record<string, string> = {};
      for (const m of out.maps) {
        const key = `${m.client_id}-${m.hub_campaign_id}`;
        nextDrafts[key] = m.external_campaign_id ?? '';
      }
      setDrafts(nextDrafts);
    },
    [campaignFilter],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      try {
        await reload(access);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải hub map thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, reload]);

  async function saveMap(row: HubMapRow) {
    const access = getAccessToken();
    if (!access || !canWrite || !row.client_id || row.hub_campaign_id == null) return;
    const key = `${row.client_id}-${row.hub_campaign_id}`;
    const externalId = normalizeMetaId(drafts[key] ?? '');
    if (!/^[0-9]{5,20}$/.test(externalId)) {
      setError('Meta Campaign ID phải là số 5–20 chữ số');
      return;
    }
    setSavingKey(key);
    setError('');
    setMsg('');
    try {
      await patchHubCampaignMap(access, {
        client_id: row.client_id,
        hub_campaign_id: row.hub_campaign_id,
        external_campaign_id: externalId,
      });
      setMsg('Đã lưu Meta Campaign ID');
      await reload(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu map thất bại');
    } finally {
      setSavingKey('');
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

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <div className="card">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', marginBottom: '0.5rem' }}>
          <p className="muted" style={{ margin: 0, flex: '1 1 auto' }}>
            Hub campaign map (PG) · chỉnh Meta Campaign ID inline
            {campaignFilter ? ` · filter campaign_id=${campaignFilter}` : ''}
          </p>
          <AgencyReadOnlyBadge user={user} />
        </div>
        {error ? <p className="error">{error}</p> : null}
        {msg ? <p className="muted">{msg}</p> : null}

        <div style={{ overflowX: 'auto' }}>
          <table className="perf-table">
            <thead>
              <tr>
                <th>Client</th>
                <th>Hub ID</th>
                <th>Campaign name</th>
                <th>Meta Campaign ID</th>
                <th>Target CPL</th>
                <th>Mapped</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {maps.map((m, i) => {
                const key = `${m.client_id}-${m.hub_campaign_id}`;
                const mapped = Boolean(m.external_campaign_id);
                return (
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
                    <td>{m.external_campaign_name || '—'}</td>
                    <td>
                      {canWrite && m.client_id && m.hub_campaign_id != null ? (
                        <input
                          className="hub-meta-campaign-id"
                          value={drafts[key] ?? ''}
                          onChange={(e) =>
                            setDrafts((d) => ({ ...d, [key]: e.target.value }))
                          }
                          placeholder="120210334455667"
                          style={{ width: '100%', minWidth: 160, padding: '0.35rem 0.5rem' }}
                        />
                      ) : (
                        m.external_campaign_id || '—'
                      )}
                    </td>
                    <td>
                      {m.target_cpl_vnd != null
                        ? Math.round(m.target_cpl_vnd).toLocaleString('vi-VN') + ' ₫'
                        : '—'}
                    </td>
                    <td>{mapped ? '✓' : '—'}</td>
                    <td>
                      {canWrite && m.client_id && m.hub_campaign_id != null ? (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          disabled={savingKey === key}
                          onClick={() => void saveMap(m)}
                        >
                          Lưu
                        </button>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
              {!loading && maps.length === 0 ? (
                <tr>
                  <td colSpan={7} className="muted">
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
