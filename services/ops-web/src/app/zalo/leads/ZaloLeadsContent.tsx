'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  fetchAgencyClients,
  fetchZaloForms,
  fetchZaloLeads,
  pollZaloForm,
  staffMe,
  staffRefresh,
  type AgencyClient,
  type ZaloFormSyncRow,
  type ZaloLeadRow,
} from '@/lib/api';
import { jobTypeLabel } from '@/lib/job-labels';
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

type Tab = 'leads' | 'forms';

export function ZaloLeadsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [tab, setTab] = useState<Tab>('leads');
  const [leads, setLeads] = useState<ZaloLeadRow[]>([]);
  const [forms, setForms] = useState<ZaloFormSyncRow[]>([]);
  const [clients, setClients] = useState<AgencyClient[]>([]);
  const [clientId, setClientId] = useState(searchParams.get('client_id') ?? '');
  const [formFilter, setFormFilter] = useState('');
  const [q, setQ] = useState('');
  const [total, setTotal] = useState(0);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(true);
  const [busyFormId, setBusyFormId] = useState<string | null>(null);

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
      const ok = hasCap(me, 'crm_zalo_ads', 'view') || hasCap(me, 'crm_agency', 'view');
      if (!ok) {
        setError('Không có quyền xem Zalo leads');
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

  const loadData = useCallback(async () => {
    const access = await ensureAuth();
    if (!access) return;
    setLoading(true);
    setError('');
    try {
      const [leadRes, formRes, clientRes] = await Promise.all([
        fetchZaloLeads(access, {
          client_id: clientId || undefined,
          form_id: formFilter || undefined,
          q: q || undefined,
          limit: 100,
        }),
        fetchZaloForms(access, clientId || undefined),
        fetchAgencyClients(access),
      ]);
      setLeads(leadRes.leads ?? []);
      setTotal(leadRes.total ?? 0);
      setForms(formRes.forms ?? []);
      setClients(clientRes.clients ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải Zalo leads thất bại');
    } finally {
      setLoading(false);
    }
  }, [clientId, ensureAuth, formFilter, q]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  async function handlePoll(form: ZaloFormSyncRow, force = false) {
    const access = getAccessToken();
    if (!access) return;
    setBusyFormId(form.form_id);
    setMsg('');
    setError('');
    try {
      const out = await pollZaloForm(access, form.form_id, {
        client_id: form.client_id,
        force,
      });
      const job = out.jobs_enqueued?.[0];
      setMsg(
        job
          ? `Đã enqueue: ${jobTypeLabel(job.job_type)} (${job.id.slice(0, 8)}…)`
          : 'Đã gửi poll job',
      );
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Poll form thất bại');
    } finally {
      setBusyFormId(null);
    }
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
      <OpsNav user={user} onLogout={() => { clearSession(); router.push('/login'); }} />
      <h1 style={{ fontSize: '1.25rem' }}>Zalo Leads Monitor</h1>
      <p className="muted">Form poll + CRM leads · Wave Z2</p>
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
        <Link href="/zalo/zalo-ads" className="btn btn-sm btn-secondary">
          Zalo Ads hub
        </Link>
        <Link href="/meta/ads-combined" className="btn btn-sm btn-secondary">
          Ads CPL combined
        </Link>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {msg ? <p className="muted">{msg}</p> : null}

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button type="button" className={`btn btn-sm ${tab === 'leads' ? '' : 'btn-secondary'}`} onClick={() => setTab('leads')}>
          Leads ({total})
        </button>
        <button type="button" className={`btn btn-sm ${tab === 'forms' ? '' : 'btn-secondary'}`} onClick={() => setTab('forms')}>
          Form sync ({forms.length})
        </button>
      </div>

      <div className="card" style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.75rem' }}>
          <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
            Client
            <select value={clientId} onChange={(e) => setClientId(e.target.value)} style={{ padding: '0.4rem' }}>
              <option value="">Tất cả</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code || c.name}
                </option>
              ))}
            </select>
          </label>
          {tab === 'leads' ? (
            <>
              <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
                Form ID
                <input value={formFilter} onChange={(e) => setFormFilter(e.target.value)} style={{ padding: '0.4rem' }} />
              </label>
              <label className="muted" style={{ display: 'grid', gap: '0.25rem' }}>
                Tìm kiếm
                <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tên / SĐT / email" style={{ padding: '0.4rem' }} />
              </label>
            </>
          ) : null}
        </div>
        <button type="button" className="btn btn-sm" disabled={loading} style={{ marginTop: '0.75rem' }} onClick={() => void loadData()}>
          {loading ? 'Đang tải…' : 'Áp dụng / Làm mới'}
        </button>
      </div>

      {tab === 'leads' ? (
        <table className="perf-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Tên</th>
              <th>SĐT</th>
              <th>Form</th>
              <th>Status</th>
              <th>Dedup</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {leads.map((lead) => (
              <tr key={lead.id}>
                <td>{lead.id}</td>
                <td>{lead.full_name ?? '—'}</td>
                <td>{lead.phone ?? '—'}</td>
                <td>{lead.form_id ?? '—'}</td>
                <td>{lead.status ?? '—'}</td>
                <td>{lead.is_duplicate ? 'yes' : '—'}</td>
                <td>{lead.created_at ? new Date(lead.created_at).toLocaleString('vi-VN') : '—'}</td>
              </tr>
            ))}
            {leads.length === 0 ? (
              <tr>
                <td colSpan={7} className="muted">
                  {loading ? 'Đang tải…' : 'Chưa có lead Zalo — poll form hoặc webhook'}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      ) : (
        <table className="perf-table">
          <thead>
            <tr>
              <th>Client</th>
              <th>OA ID</th>
              <th>Form ID</th>
              <th>Cursor</th>
              <th>Last poll</th>
              <th>Status</th>
              <th>Token</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {forms.map((form) => (
              <tr key={`${form.client_id}:${form.oa_id}:${form.form_id}`}>
                <td>{form.client_code || form.client_name || form.client_id.slice(0, 8)}</td>
                <td>{form.oa_id}</td>
                <td>{form.form_id}</td>
                <td>{form.last_form_data_id ?? '—'}</td>
                <td>{form.last_polled_at ? new Date(form.last_polled_at).toLocaleString('vi-VN') : '—'}</td>
                <td>{form.last_status ?? '—'}{form.last_error ? ` · ${form.last_error}` : ''}</td>
                <td>{form.has_token ? 'ok' : '—'}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button
                    type="button"
                    className="btn btn-sm btn-secondary"
                    disabled={busyFormId === form.form_id}
                    onClick={() => void handlePoll(form, false)}
                  >
                    Poll now
                  </button>{' '}
                  <button
                    type="button"
                    className="btn btn-sm btn-secondary"
                    disabled={busyFormId === form.form_id}
                    onClick={() => void handlePoll(form, true)}
                  >
                    Force
                  </button>
                </td>
              </tr>
            ))}
            {forms.length === 0 ? (
              <tr>
                <td colSpan={8} className="muted">
                  Chưa có form — cấu hình Form IDs trên channel Zalo (Agency → Channels)
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      )}
    </main>
  );
}
