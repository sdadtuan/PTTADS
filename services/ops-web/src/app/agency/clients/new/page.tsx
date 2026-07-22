'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { AgencyReadOnlyBadge, canAgencyWrite } from '@/components/AgencyReadOnlyBadge';
import { createAgencyClient, staffMe, staffRefresh } from '@/lib/api';
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

export default function NewClientPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return;
    }
    staffMe(access)
      .then((me) => {
        setUser(me);
        if (!hasCap(me, 'crm_agency', 'view')) {
          router.replace('/agency');
          return;
        }
        if (!canAgencyWrite(me)) {
          setError('Không có quyền tạo client');
        }
      })
      .catch(async () => {
        const refresh = getRefreshToken();
        if (!refresh) {
          router.replace('/login');
          return;
        }
        const out = await staffRefresh(refresh);
        updateAccessToken(out.access_token);
        const me = await staffMe(out.access_token);
        setUser(me);
        updateStoredUser(me);
      });
  }, [router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const access = getAccessToken();
    if (!access || !user || !canAgencyWrite(user)) return;
    setSaving(true);
    setError('');
    try {
      const client = await createAgencyClient(access, {
        code: code.trim().toUpperCase(),
        name: name.trim(),
      });
      router.push(`/agency/clients/${client.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo client thất bại');
    } finally {
      setSaving(false);
    }
  }

  if (!user) {
    return (
      <main style={{ padding: '2rem' }}>
        <p className="muted">Đang tải…</p>
      </main>
    );
  }

  const canWrite = canAgencyWrite(user);

  return (
    <main style={{ maxWidth: 520, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/agency" className="nav-link">
          ← Agency
        </Link>
      </p>
      <div className="card">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', marginBottom: '0.5rem' }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Client mới</h2>
          <AgencyReadOnlyBadge user={user} />
        </div>
        {error ? <p className="error">{error}</p> : null}
        <form onSubmit={(e) => void onSubmit(e)} style={{ display: 'grid', gap: '0.85rem' }}>
          <label style={{ display: 'grid', gap: '0.35rem' }}>
            <span className="muted">Mã (CODE)</span>
            <input
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
              style={{ padding: '0.55rem', borderRadius: 8, border: '1px solid var(--border)' }}
            />
          </label>
          <label style={{ display: 'grid', gap: '0.35rem' }}>
            <span className="muted">Tên</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{ padding: '0.55rem', borderRadius: 8, border: '1px solid var(--border)' }}
            />
          </label>
          <button type="submit" className="btn btn-sm" disabled={saving || !canWrite || !!error}>
            {saving ? 'Đang tạo…' : 'Tạo client'}
          </button>
        </form>
      </div>
    </main>
  );
}
