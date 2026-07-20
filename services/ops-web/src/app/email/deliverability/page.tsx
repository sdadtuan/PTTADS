'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  EmailDnsStatus,
  EmailEmptyState,
  EmailStatusBadge,
  EmailWarmupMeter,
} from '@/components/email';
import {
  fetchEmailDeliverabilityDomains,
  pauseEmailDomain,
  registerEmailDomain,
  verifyEmailDomain,
  staffMe,
  staffRefresh,
  type EmailDeliverabilityDomainRow,
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


export default function EmailDeliverabilityPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [domains, setDomains] = useState<EmailDeliverabilityDomainRow[]>([]);
  const [clientId, setClientId] = useState('');
  const [domainInput, setDomainInput] = useState('');
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
      try {
        const data = await fetchEmailDeliverabilityDomains(access, {
          client_id: clientId.trim() || undefined,
          limit: 100,
        });
        setDomains(data.items);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải domains thất bại');
      } finally {
        setLoading(false);
      }
    },
    [clientId],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await load(access);
    })();
  }, [ensureAuth, load]);

  async function register() {
    const access = getAccessToken();
    if (!access || !clientId.trim() || !domainInput.trim()) return;
    setError('');
    try {
      await registerEmailDomain(access, { client_id: clientId.trim(), domain: domainInput.trim() });
      setDomainInput('');
      await load(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đăng ký domain thất bại');
    }
  }

  async function verify(id: string) {
    const access = getAccessToken();
    if (!access) return;
    try {
      await verifyEmailDomain(access, id);
      await load(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verify thất bại');
    }
  }

  async function pause(id: string) {
    const access = getAccessToken();
    if (!access) return;
    if (!window.confirm('Tạm dừng gửi từ domain này?')) return;
    try {
      await pauseEmailDomain(access, id);
      await load(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Pause thất bại');
    }
  }

  if (!user) return <main style={{ padding: '2rem' }}><p className="muted">Đang tải…</p></main>;

  const canDeliverability =
    hasCap(user, 'crm_email_mkt', 'deliverability') ||
    hasCap(user, 'crm_email_mkt', 'settings') ||
    hasCap(user, 'crm_agency', 'create');

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <div className="card" style={{ marginBottom: '1rem' }}>
        <p className="muted" style={{ marginTop: 0 }}>EM-3 E-11 — Deliverability console</p>
        <Link href="/email/hub" className="btn btn-secondary btn-sm">← Hub</Link>
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
          <input value={clientId} onChange={(e) => setClientId(e.target.value)} placeholder="Client UUID" style={{ width: 280 }} />
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => { const a = getAccessToken(); if (a) void load(a); }}>Làm mới</button>
        </div>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {canDeliverability ? (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <input value={domainInput} onChange={(e) => setDomainInput(e.target.value)} placeholder="mail.client.com" style={{ marginRight: '0.5rem', minWidth: 220 }} />
          <button type="button" className="btn btn-sm" onClick={() => void register()}>+ Thêm domain</button>
        </div>
      ) : null}
      <div className="card">
        <table className="perf-table">
          <thead>
            <tr>
              <th>Domain</th>
              <th>Client</th>
              <th>SPF</th>
              <th>DKIM</th>
              <th>DMARC</th>
              <th>Warm-up</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {domains.map((d) => (
              <tr key={d.id}>
                <td><strong>{d.domain}</strong></td>
                <td>{d.client_name}</td>
                <td><EmailDnsStatus status={d.spf_status} label="SPF" /></td>
                <td><EmailDnsStatus status={d.dkim_status} label="DKIM" /></td>
                <td><EmailDnsStatus status={d.dmarc_status} label="DMARC" /></td>
                <td><EmailWarmupMeter stage={d.warm_up_stage} /></td>
                <td><EmailStatusBadge status={d.status} /></td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  {canDeliverability ? (
                    <>
                      <button type="button" className="btn btn-sm" onClick={() => void verify(d.id)}>Verify</button>{' '}
                      {d.status !== 'paused' ? (
                        <button type="button" className="btn btn-secondary btn-sm" onClick={() => void pause(d.id)}>Pause</button>
                      ) : null}
                    </>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && domains.length === 0 ? (
          <EmailEmptyState message="Chưa cấu hình domain gửi." ctaLabel="← Hub" ctaHref="/email/hub" />
        ) : null}
      </div>
    </main>
  );
}
