'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  createCustomerIssue,
  createCustomerRelation,
  fetchCustomerDetail,
  patchCustomer,
  staffMe,
  staffRefresh,
  type CustomerDetailBundle,
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

export default function CrmCustomerDetailPage() {
  const router = useRouter();
  const params = useParams();
  const customerId = Number(params.id);

  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [bundle, setBundle] = useState<CustomerDetailBundle | null>(null);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [profileNotes, setProfileNotes] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [relationName, setRelationName] = useState('');
  const [relationPhone, setRelationPhone] = useState('');
  const [issueTitle, setIssueTitle] = useState('');

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
      if (!hasCap(me, 'crm_board_customers', 'view')) {
        setError('Không có quyền xem khách hàng');
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
    if (!Number.isFinite(customerId) || customerId <= 0) {
      setError('Customer ID không hợp lệ');
      setLoading(false);
      return;
    }
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      setError('');
      try {
        const data = await fetchCustomerDetail(access, customerId);
        setBundle(data);
        setName(data.customer.name || '');
        setPhone(data.customer.phone || '');
        setEmail(data.customer.email || '');
        setCompany(data.customer.company || '');
        setProfileNotes(data.customer.profile_notes || '');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải khách hàng thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, customerId]);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    if (!user || !bundle) return;
    if (!hasCap(user, 'crm_board_customers', 'edit')) {
      setError('Không có quyền sửa');
      return;
    }
    const access = getAccessToken();
    if (!access) return;

    setSaving(true);
    setError('');
    setMessage('');
    try {
      const updated = await patchCustomer(access, customerId, {
        name: name.trim(),
        phone: phone.trim(),
        email: email.trim(),
        company: company.trim(),
        profile_notes: profileNotes.trim(),
      });
      setBundle({
        ...bundle,
        customer: { ...bundle.customer, ...updated },
      });
      setMessage('Đã lưu hồ sơ');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onAddRelation(e: React.FormEvent) {
    e.preventDefault();
    if (!user || !bundle || !relationName.trim()) return;
    if (!hasCap(user, 'crm_board_customers', 'edit')) {
      setError('Không có quyền sửa');
      return;
    }
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await createCustomerRelation(access, customerId, {
        full_name: relationName.trim(),
        phone: relationPhone.trim(),
      });
      const data = await fetchCustomerDetail(access, customerId);
      setBundle(data);
      setRelationName('');
      setRelationPhone('');
      setMessage('Đã thêm quan hệ');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thêm quan hệ thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onAddIssue(e: React.FormEvent) {
    e.preventDefault();
    if (!user || !bundle || !issueTitle.trim()) return;
    if (!hasCap(user, 'crm_board_customers', 'edit')) {
      setError('Không có quyền sửa');
      return;
    }
    const access = getAccessToken();
    if (!access) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await createCustomerIssue(access, customerId, { title: issueTitle.trim() });
      const data = await fetchCustomerDetail(access, customerId);
      setBundle(data);
      setIssueTitle('');
      setMessage('Đã tạo vấn đề');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tạo vấn đề thất bại');
    } finally {
      setSaving(false);
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
    <main style={{ maxWidth: 900, margin: '0 auto', padding: '1.5rem' }}>
      <OpsNav user={user} onLogout={logout} />
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/crm/customers" className="nav-link">
          ← Danh sách khách hàng
        </Link>
      </p>

      <div className="card" style={{ marginBottom: '1rem' }}>
        {loading ? <p className="muted">Đang tải #{customerId}…</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {message ? <p style={{ color: 'var(--accent)' }}>{message}</p> : null}

        {bundle && !loading ? (
          <>
            <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>
              #{bundle.customer.id} · {bundle.customer.name}
            </h2>
            <p className="muted">
              {bundle.stats.relations_total} quan hệ · {bundle.stats.purchases_total} mua hàng ·{' '}
              {bundle.stats.issues_open}/{bundle.stats.issues_total} vấn đề mở
            </p>

            <form onSubmit={(e) => void onSave(e)} style={{ display: 'grid', gap: '0.75rem' }}>
              {(
                [
                  ['Tên', name, setName],
                  ['SĐT', phone, setPhone],
                  ['Email', email, setEmail],
                  ['Công ty', company, setCompany],
                ] as const
              ).map(([label, val, setVal]) => (
                <label key={label} style={{ display: 'grid', gap: '0.35rem' }}>
                  <span className="muted">{label}</span>
                  <input
                    value={val}
                    onChange={(e) => setVal(e.target.value)}
                    disabled={!hasCap(user, 'crm_board_customers', 'edit') || saving}
                    style={{
                      background: 'var(--bg)',
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                      padding: '0.55rem 0.75rem',
                      color: 'var(--text)',
                    }}
                  />
                </label>
              ))}
              <label style={{ display: 'grid', gap: '0.35rem' }}>
                <span className="muted">Ghi chú</span>
                <textarea
                  value={profileNotes}
                  onChange={(e) => setProfileNotes(e.target.value)}
                  rows={3}
                  disabled={!hasCap(user, 'crm_board_customers', 'edit') || saving}
                  style={{
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.55rem 0.75rem',
                    color: 'var(--text)',
                    resize: 'vertical',
                  }}
                />
              </label>
              <button
                type="submit"
                className="btn btn-sm"
                disabled={saving || !hasCap(user, 'crm_board_customers', 'edit')}
              >
                {saving ? 'Đang lưu…' : 'Lưu hồ sơ'}
              </button>
            </form>
          </>
        ) : null}
      </div>

      {bundle && !loading ? (
        <>
          <div className="card" style={{ marginBottom: '1rem' }}>
            <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Quan hệ</h3>
            {bundle.relations.length === 0 ? (
              <p className="muted">Chưa có quan hệ.</p>
            ) : (
              <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
                {bundle.relations.map((r) => (
                  <li key={r.id}>
                    {r.relation_type_label}: {r.full_name} {r.phone ? `· ${r.phone}` : ''}
                  </li>
                ))}
              </ul>
            )}
            <form onSubmit={(e) => void onAddRelation(e)} style={{ display: 'grid', gap: '0.5rem' }}>
              <input
                placeholder="Họ tên người liên quan"
                value={relationName}
                onChange={(e) => setRelationName(e.target.value)}
                disabled={!hasCap(user, 'crm_board_customers', 'edit') || saving}
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.55rem 0.75rem',
                  color: 'var(--text)',
                }}
              />
              <input
                placeholder="SĐT (tuỳ chọn)"
                value={relationPhone}
                onChange={(e) => setRelationPhone(e.target.value)}
                disabled={!hasCap(user, 'crm_board_customers', 'edit') || saving}
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.55rem 0.75rem',
                  color: 'var(--text)',
                }}
              />
              <button
                type="submit"
                className="btn btn-secondary btn-sm"
                disabled={saving || !hasCap(user, 'crm_board_customers', 'edit') || !relationName.trim()}
              >
                + Thêm quan hệ
              </button>
            </form>
          </div>

          <div className="card">
            <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Vấn đề gần đây</h3>
            {bundle.issues.length === 0 ? (
              <p className="muted">Chưa có vấn đề.</p>
            ) : (
              <ul style={{ margin: '0 0 1rem', paddingLeft: '1.1rem' }}>
                {bundle.issues.slice(0, 10).map((i) => (
                  <li key={i.id}>
                    {i.title} — {i.status_label} ({i.priority_label})
                  </li>
                ))}
              </ul>
            )}
            <form onSubmit={(e) => void onAddIssue(e)} style={{ display: 'grid', gap: '0.5rem' }}>
              <input
                placeholder="Tiêu đề vấn đề mới"
                value={issueTitle}
                onChange={(e) => setIssueTitle(e.target.value)}
                disabled={!hasCap(user, 'crm_board_customers', 'edit') || saving}
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0.55rem 0.75rem',
                  color: 'var(--text)',
                }}
              />
              <button
                type="submit"
                className="btn btn-secondary btn-sm"
                disabled={saving || !hasCap(user, 'crm_board_customers', 'edit') || !issueTitle.trim()}
              >
                + Tạo vấn đề
              </button>
            </form>
          </div>
        </>
      ) : null}
    </main>
  );
}
