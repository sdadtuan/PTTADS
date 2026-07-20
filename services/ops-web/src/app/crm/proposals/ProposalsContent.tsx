'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  createProposal,
  deleteProposal,
  fetchCustomers,
  fetchProposals,
  generateProposal,
  staffMe,
  staffRefresh,
  type CustomerRow,
  type ProposalRow,
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

export function ProposalsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [customers, setCustomers] = useState<CustomerRow[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [proposals, setProposals] = useState<ProposalRow[]>([]);
  const [serviceSlugs, setServiceSlugs] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

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
      if (!hasCap(me, 'crm_board', 'view')) {
        setError('Không có quyền đề xuất');
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

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      setError('');
      try {
        const data = await fetchCustomers(access, { limit: 200 });
        setCustomers(data);
        const prefill = searchParams.get('customer_id') ?? '';
        if (prefill) setCustomerId(prefill);
        else if (data[0]) setCustomerId(String(data[0].id));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải khách hàng thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, searchParams]);

  useEffect(() => {
    void (async () => {
      const access = getAccessToken();
      if (!access || !customerId) return;
      setLoading(true);
      setError('');
      try {
        setProposals(await fetchProposals(access, Number(customerId)));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải đề xuất thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [customerId]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    const access = getAccessToken();
    if (!access || !customerId) return;
    const slugs = serviceSlugs
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if (!slugs.length) return;
    setSaving(true);
    setError('');
    try {
      await createProposal(access, {
        customer_id: Number(customerId),
        service_slugs: slugs,
        notes: notes.trim() || undefined,
      });
      setServiceSlugs('');
      setNotes('');
      setProposals(await fetchProposals(access, Number(customerId)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo đề xuất thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onGenerate(id: number) {
    const access = getAccessToken();
    if (!access) return;
    setError('');
    try {
      await generateProposal(access, id);
      setProposals(await fetchProposals(access, Number(customerId)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generate AI chưa sẵn sàng');
    }
  }

  async function onDelete(id: number) {
    const access = getAccessToken();
    if (!access || !customerId) return;
    if (!window.confirm('Xóa đề xuất này?')) return;
    setError('');
    try {
      await deleteProposal(access, id);
      setProposals(await fetchProposals(access, Number(customerId)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Xóa thất bại');
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
      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>Đề xuất dịch vụ</h2>
        <div style={{ marginBottom: '1rem' }}>
          <label className="muted" style={{ display: 'block', marginBottom: '0.35rem' }}>
            Khách hàng
          </label>
          <select
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            style={{
              width: '100%',
              maxWidth: 420,
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '0.55rem 0.75rem',
              color: 'var(--text)',
            }}
          >
            {customers.map((c) => (
              <option key={c.id} value={String(c.id)}>
                {c.name} {c.company ? `· ${c.company}` : ''}
              </option>
            ))}
          </select>
        </div>
        {loading ? <p className="muted">Đang tải…</p> : null}
        {error ? <p className="error">{error}</p> : null}
        <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
          {proposals.map((p) => (
            <li key={p.id} style={{ marginBottom: '0.5rem' }}>
              #{p.id} · {p.service_slugs.join(', ')} · {p.total_vnd.toLocaleString('vi-VN')} VND
              {hasCap(user, 'crm_board', 'edit') ? (
                <>
                  {' '}
                  <button type="button" className="btn btn-sm" onClick={() => void onGenerate(p.id)}>
                    AI
                  </button>{' '}
                  <button type="button" className="btn btn-sm btn-secondary" onClick={() => void onDelete(p.id)}>
                    Xóa
                  </button>
                </>
              ) : null}
            </li>
          ))}
        </ul>
        {proposals.length === 0 && !loading ? <p className="muted">Chưa có đề xuất.</p> : null}
        {hasCap(user, 'crm_board', 'edit') ? (
          <form onSubmit={(e) => void onCreate(e)} style={{ display: 'grid', gap: '0.5rem', maxWidth: 520 }}>
            <input
              value={serviceSlugs}
              onChange={(e) => setServiceSlugs(e.target.value)}
              placeholder="service slugs (vd: seo, ads)"
              disabled={saving}
              style={{
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '0.55rem 0.75rem',
                color: 'var(--text)',
              }}
            />
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ghi chú"
              rows={2}
              disabled={saving}
              style={{
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '0.55rem 0.75rem',
                color: 'var(--text)',
              }}
            />
            <button type="submit" className="btn btn-secondary btn-sm" disabled={saving || !serviceSlugs.trim()}>
              + Đề xuất
            </button>
          </form>
        ) : null}
      </div>
    </main>
  );
}
