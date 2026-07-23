'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import { LeadFunnelPanel } from '@/components/LeadFunnelPanel';
import { LeadContractPanel } from '@/components/LeadContractPanel';
import {
  assignLead,
  createLeadActivity,
  fetchCatalogBundle,
  fetchLead,
  fetchLeadActivities,
  fetchLeadAudit,
  patchLeadLegacy,
  staffMe,
  staffRefresh,
  type CatalogStaffOption,
  type LeadActivityRow,
  type LeadAssignmentLogRow,
  type LeadAuditBundle,
  type LeadRow,
  type LeadStatusLogRow,
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

const STATUS_OPTIONS = [
  'moi',
  'da_lien_he',
  'dang_tu_van',
  'hen_gap',
  'bao_gia',
  'dam_phan',
  'chot',
  'post_sale',
  'lost',
  'pending_cleanup',
];

const ACTIVITY_TYPES = [
  { value: 'note', label: 'Ghi chú' },
  { value: 'call', label: 'Gọi điện' },
  { value: 'email', label: 'Email' },
  { value: 'message', label: 'Tin nhắn' },
  { value: 'meeting', label: 'Họp' },
  { value: 'proposal', label: 'Báo giá' },
  { value: 'task', label: 'Công việc' },
  { value: 'reminder', label: 'Nhắc việc' },
];

export default function CrmLeadDetailPage() {
  const router = useRouter();
  const params = useParams();
  const leadId = Number(params.id);

  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [lead, setLead] = useState<LeadRow | null>(null);
  const [staffOptions, setStaffOptions] = useState<CatalogStaffOption[]>([]);
  const [activities, setActivities] = useState<LeadActivityRow[]>([]);
  const [audit, setAudit] = useState<LeadAuditBundle | null>(null);
  const [status, setStatus] = useState('');
  const [auditNote, setAuditNote] = useState('');
  const [assignToId, setAssignToId] = useState('');
  const [assignReason, setAssignReason] = useState('');
  const [activityType, setActivityType] = useState('note');
  const [activityContent, setActivityContent] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [addingActivity, setAddingActivity] = useState(false);

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
      if (!hasCap(me, 'crm_leads', 'view')) {
        setError('Không có quyền xem CRM leads');
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

  const reloadTimeline = useCallback(async (access: string) => {
    const [acts, aud] = await Promise.all([
      fetchLeadActivities(access, leadId),
      fetchLeadAudit(access, leadId),
    ]);
    setActivities(acts);
    setAudit(aud);
  }, [leadId]);

  useEffect(() => {
    if (!Number.isFinite(leadId) || leadId <= 0) {
      setError('Lead ID không hợp lệ');
      setLoading(false);
      return;
    }
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      setLoading(true);
      setError('');
      try {
        const [row, catalog] = await Promise.all([
          fetchLead(access, leadId),
          fetchCatalogBundle(access).catch(() => null),
        ]);
        setLead(row);
        setStatus(row.status || 'moi');
        if (catalog?.staff?.length) {
          setStaffOptions(catalog.staff);
        }
        await reloadTimeline(access);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Tải lead thất bại');
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAuth, leadId, reloadTimeline]);

  async function onSaveStatus(e: React.FormEvent) {
    e.preventDefault();
    if (!user || !lead) return;
    if (!hasCap(user, 'crm_leads', 'edit')) {
      setError('Không có quyền sửa trạng thái');
      return;
    }
    const access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return;
    }
    if (status.trim() === lead.status) {
      setMessage('Trạng thái không đổi');
      return;
    }

    setSaving(true);
    setError('');
    setMessage('');
    try {
      const updated = await patchLeadLegacy(access, leadId, {
        status: status.trim(),
        audit_note: auditNote.trim(),
      });
      setLead(updated);
      setStatus(updated.status || status);
      setAuditNote('');
      setMessage('Đã lưu trạng thái + audit SQLite');
      await reloadTimeline(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu thất bại');
    } finally {
      setSaving(false);
    }
  }

  async function onAssign(e: React.FormEvent) {
    e.preventDefault();
    if (!user || !lead) return;
    if (!hasCap(user, 'crm_leads', 'assign')) {
      setError('Không có quyền phân lead');
      return;
    }
    const toId = Number(assignToId);
    const reason = assignReason.trim();
    if (!Number.isFinite(toId) || toId <= 0) {
      setError('Chọn nhân viên nhận lead');
      return;
    }
    if (reason.length < 3) {
      setError('Cần ghi lý do phân lại (≥ 3 ký tự)');
      return;
    }
    const access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return;
    }

    setAssigning(true);
    setError('');
    setMessage('');
    try {
      const updated = await assignLead(access, leadId, { to_user_id: toId, reason });
      setLead(updated);
      setAssignToId('');
      setAssignReason('');
      setMessage('Đã phân lead');
      await reloadTimeline(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Phân lead thất bại');
    } finally {
      setAssigning(false);
    }
  }

  async function onAddActivity(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;
    if (!hasCap(user, 'crm_leads', 'edit')) {
      setError('Không có quyền thêm hoạt động');
      return;
    }
    const content = activityContent.trim();
    if (!content) {
      setError('Nội dung hoạt động không được trống');
      return;
    }
    const access = getAccessToken();
    if (!access) {
      router.replace('/login');
      return;
    }

    setAddingActivity(true);
    setError('');
    setMessage('');
    try {
      await createLeadActivity(access, leadId, {
        activity_type: activityType,
        content,
      });
      setActivityContent('');
      setMessage('Đã thêm hoạt động');
      await reloadTimeline(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thêm hoạt động thất bại');
    } finally {
      setAddingActivity(false);
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
        <Link href="/crm/leads" className="nav-link">
          ← Danh sách leads
        </Link>
      </p>

      <div className="card" style={{ marginBottom: '1rem' }}>
        {loading ? <p className="muted">Đang tải lead #{leadId}…</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {message ? <p style={{ color: 'var(--accent)' }}>{message}</p> : null}

        {lead && !loading ? (
          <>
            <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>
              #{lead.id} · {lead.full_name || '—'}
            </h2>
            <p style={{ margin: '0 0 1rem' }}>
              <Link href={`/crm/intake?lead_id=${lead.id}`} className="nav-link">
                Mở Lead Intake →
              </Link>
            </p>
            <dl
              style={{
                display: 'grid',
                gridTemplateColumns: '120px 1fr',
                gap: '0.35rem 1rem',
                marginBottom: '1.25rem',
              }}
            >
              <dt className="muted">SĐT</dt>
              <dd style={{ margin: 0 }}>{lead.phone || '—'}</dd>
              <dt className="muted">Email</dt>
              <dd style={{ margin: 0 }}>{lead.email || '—'}</dd>
              <dt className="muted">Nguồn</dt>
              <dd style={{ margin: 0 }}>{lead.source || '—'}</dd>
              <dt className="muted">Owner</dt>
              <dd style={{ margin: 0 }}>{lead.owner_id ?? '—'}</dd>
              <dt className="muted">Ngày</dt>
              <dd style={{ margin: 0 }}>{lead.created_at?.slice(0, 10) ?? '—'}</dd>
            </dl>

            {getAccessToken() ? (
              <LeadFunnelPanel
                token={getAccessToken()!}
                leadId={leadId}
                user={user}
                onMessage={setMessage}
                onError={setError}
              />
            ) : null}

            {getAccessToken() ? (
              <LeadContractPanel
                token={getAccessToken()!}
                leadId={leadId}
                user={user}
                onMessage={setMessage}
                onError={setError}
              />
            ) : null}

            <form onSubmit={(e) => void onSaveStatus(e)} style={{ display: 'grid', gap: '0.85rem', marginTop: '1rem' }}>
              <label style={{ display: 'grid', gap: '0.35rem' }}>
                <span className="muted">Trạng thái</span>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  disabled={!hasCap(user, 'crm_leads', 'edit') || saving}
                  style={{
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.55rem 0.75rem',
                    color: 'var(--text)',
                  }}
                >
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'grid', gap: '0.35rem' }}>
                <span className="muted">Ghi chú audit (tùy chọn)</span>
                <input
                  value={auditNote}
                  onChange={(e) => setAuditNote(e.target.value)}
                  placeholder="Lý do đổi trạng thái"
                  disabled={!hasCap(user, 'crm_leads', 'edit') || saving}
                  style={{
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.55rem 0.75rem',
                    color: 'var(--text)',
                  }}
                />
              </label>
              <button
                type="submit"
                className="btn btn-sm"
                disabled={saving || !hasCap(user, 'crm_leads', 'edit')}
              >
                {saving ? 'Đang lưu…' : 'Lưu trạng thái'}
              </button>
            </form>
          </>
        ) : null}
      </div>

      {lead && !loading ? (
        <>
          <div className="card" style={{ marginBottom: '1rem' }}>
            <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Phân lead</h3>
            <form onSubmit={(e) => void onAssign(e)} style={{ display: 'grid', gap: '0.75rem' }}>
              <label style={{ display: 'grid', gap: '0.35rem' }}>
                <span className="muted">Nhân viên</span>
                <select
                  value={assignToId}
                  onChange={(e) => setAssignToId(e.target.value)}
                  disabled={!hasCap(user, 'crm_leads', 'assign') || assigning}
                  style={{
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.55rem 0.75rem',
                    color: 'var(--text)',
                  }}
                >
                  <option value="">— Chọn —</option>
                  {staffOptions.map((s) => (
                    <option key={s.id} value={String(s.id)}>
                      {s.name} (#{s.id})
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'grid', gap: '0.35rem' }}>
                <span className="muted">Lý do</span>
                <input
                  value={assignReason}
                  onChange={(e) => setAssignReason(e.target.value)}
                  placeholder="Bắt buộc"
                  disabled={!hasCap(user, 'crm_leads', 'assign') || assigning}
                  style={{
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.55rem 0.75rem',
                    color: 'var(--text)',
                  }}
                />
              </label>
              <button
                type="submit"
                className="btn btn-sm"
                disabled={assigning || !hasCap(user, 'crm_leads', 'assign')}
              >
                {assigning ? 'Đang phân…' : 'Phân lead'}
              </button>
            </form>
          </div>

          <div className="card" style={{ marginBottom: '1rem' }}>
            <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Thêm hoạt động</h3>
            <form onSubmit={(e) => void onAddActivity(e)} style={{ display: 'grid', gap: '0.75rem' }}>
              <label style={{ display: 'grid', gap: '0.35rem' }}>
                <span className="muted">Loại</span>
                <select
                  value={activityType}
                  onChange={(e) => setActivityType(e.target.value)}
                  disabled={!hasCap(user, 'crm_leads', 'edit') || addingActivity}
                  style={{
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.55rem 0.75rem',
                    color: 'var(--text)',
                  }}
                >
                  {ACTIVITY_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'grid', gap: '0.35rem' }}>
                <span className="muted">Nội dung</span>
                <textarea
                  value={activityContent}
                  onChange={(e) => setActivityContent(e.target.value)}
                  rows={3}
                  disabled={!hasCap(user, 'crm_leads', 'edit') || addingActivity}
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
                disabled={addingActivity || !hasCap(user, 'crm_leads', 'edit')}
              >
                {addingActivity ? 'Đang thêm…' : 'Thêm hoạt động'}
              </button>
            </form>
          </div>

          <div className="card" style={{ marginBottom: '1rem' }}>
            <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Timeline hoạt động</h3>
            {activities.length === 0 ? (
              <p className="muted">Chưa có hoạt động.</p>
            ) : (
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '0.75rem' }}>
                {activities.map((a) => (
                  <li
                    key={a.id}
                    style={{
                      borderLeft: '3px solid var(--border)',
                      paddingLeft: '0.75rem',
                    }}
                  >
                    <div style={{ fontSize: '0.85rem' }} className="muted">
                      {a.created_at?.slice(0, 16)} · {a.activity_type_label || a.activity_type}
                      {a.user_name ? ` · ${a.user_name}` : ''}
                    </div>
                    <div>{a.content || '—'}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card">
            <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Audit</h3>
            <AuditSection audit={audit} />
          </div>
        </>
      ) : null}
    </main>
  );
}

function AuditSection({ audit }: { audit: LeadAuditBundle | null }) {
  if (!audit) return <p className="muted">Đang tải audit…</p>;

  return (
    <div style={{ display: 'grid', gap: '1.25rem' }}>
      <div>
        <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>Trạng thái</h4>
        {audit.status_logs.length === 0 ? (
          <p className="muted">Chưa có log.</p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
            {audit.status_logs.map((l: LeadStatusLogRow) => (
              <li key={l.id} style={{ marginBottom: '0.35rem' }}>
                {l.created_at?.slice(0, 16)} · {l.old_status} → {l.new_status}
                {l.note ? ` — ${l.note}` : ''}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>Phân công</h4>
        {audit.assignment_logs.length === 0 ? (
          <p className="muted">Chưa có log.</p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
            {audit.assignment_logs.map((l: LeadAssignmentLogRow) => (
              <li key={l.id} style={{ marginBottom: '0.35rem' }}>
                {l.created_at?.slice(0, 16)} · {l.from_name} → {l.to_name}
                {l.reason ? ` — ${l.reason}` : ''}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
