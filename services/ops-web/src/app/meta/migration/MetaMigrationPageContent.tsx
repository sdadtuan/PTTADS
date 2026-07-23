'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { MetaMigrationPanel } from '@/components/MetaMigrationPanel';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchFacebookAdsMigrationStatus,
  patchFacebookAdsMigrationManualUat,
  staffMe,
  staffRefresh,
  type FacebookAdsMigrationStatus,
  type MetaMigrationManualUat,
  type MetaMigrationManualUatField,
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

export function MetaMigrationPageContent() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [status, setStatus] = useState<FacebookAdsMigrationStatus | null>(null);
  const [manualUat, setManualUat] = useState<MetaMigrationManualUat | null>(null);
  const [error, setError] = useState('');
  const [uatError, setUatError] = useState('');
  const [loading, setLoading] = useState(true);
  const [uatSavingField, setUatSavingField] = useState<MetaMigrationManualUatField | null>(null);

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
        setError('Không có quyền xem migration Meta');
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

  const loadStatus = useCallback(async (access: string) => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchFacebookAdsMigrationStatus(access);
      setStatus(data);
      setManualUat(
        data.manual_uat ?? {
          ops_web_hub_cpl_summary: false,
          webhook_test_lead_created: false,
          autosync_single_process: false,
          portal_meta_readonly: false,
          campaign_write_approve_smoke: false,
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải migration status thất bại');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await loadStatus(access);
    })();
  }, [ensureAuth, loadStatus]);

  async function handleToggleUat(field: MetaMigrationManualUatField, value: boolean) {
    const access = getAccessToken();
    if (!access || !manualUat) return;
    const prev = manualUat[field];
    setManualUat({ ...manualUat, [field]: value });
    setUatSavingField(field);
    setUatError('');
    try {
      const out = await patchFacebookAdsMigrationManualUat(access, { [field]: value });
      setManualUat(out.manual_uat);
      setStatus((current) =>
        current
          ? {
              ...current,
              manual_uat: out.manual_uat,
              manual_uat_updated_at: out.updated_at,
            }
          : current,
      );
    } catch (err) {
      setManualUat({ ...manualUat, [field]: prev });
      setUatError(err instanceof Error ? err.message : 'Lưu UAT thất bại');
    } finally {
      setUatSavingField(null);
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
    <main style={{ maxWidth: 960, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />

      <div className="card" style={{ marginBottom: '1rem' }}>
        <h1 style={{ marginTop: 0, fontSize: '1.25rem' }}>Meta Ads — Migration dashboard</h1>
        <p className="muted" style={{ marginTop: 0 }}>
          Theo dõi Gate M1 (G04–G12), UAT §E và signoff Horizon 1. DevOps chạy wave scripts trên VPS;
          QA tick UAT trực tiếp tại đây.
        </p>
      </div>

      {error ? <p className="error">{error}</p> : null}
      {loading && !status ? <p className="muted">Đang tải migration status…</p> : null}
      {status && manualUat ? (
        <MetaMigrationPanel
          status={status}
          variant="full"
          manualUat={manualUat}
          uatSavingField={uatSavingField}
          uatError={uatError}
          onToggleUat={(field, value) => void handleToggleUat(field, value)}
        />
      ) : null}
    </main>
  );
}
