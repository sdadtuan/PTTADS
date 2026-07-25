'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { OpsNav } from '@/components/OpsNav';
import {
  approveSeoContent,
  fetchSeoAeoChecklist,
  fetchSeoContentDetail,
  fetchSeoContentVersions,
  patchSeoContent,
  saveSeoContentVersion,
  staffMe,
  staffRefresh,
  updateSeoContentStatus,
  type SeoAeoChecklistResponse,
  type SeoContentRow,
} from '@/lib/api';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  getStoredUser,
  updateAccessToken,
  updateStoredUser,
  type StoredStaffUser,
} from '@/lib/auth';
import { canApproveSeo, canViewSeoContent, canWriteSeo } from '@/lib/seo/caps';

const REVIEW_STAGES = ['seo_review', 'aeo_review', 'technical_review', 'client_review'] as const;

const STATUS_OPTIONS = [
  'idea',
  'researching',
  'brief_ready',
  'in_writing',
  'seo_review',
  'aeo_review',
  'technical_review',
  'client_review',
  'approved',
  'published',
  'monitoring',
  'refresh_required',
  'archived',
];

export default function SeoContentDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const contentId = Number.parseInt(params.id, 10);
  const [user, setUser] = useState<StoredStaffUser | null>(null);
  const [content, setContent] = useState<SeoContentRow | null>(null);
  const [checklist, setChecklist] = useState<SeoAeoChecklistResponse | null>(null);
  const [versions, setVersions] = useState<
    Array<{ id: number; version_number: number; changes_summary: string; created_by: string; created_at: string | null }>
  >([]);
  const [panel, setPanel] = useState<'brief' | 'body' | 'versions'>('brief');
  const [bodyDraft, setBodyDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
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
      if (!canViewSeoContent(me)) {
        setError('Không có quyền xem content');
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

  const reload = useCallback(
    async (access: string) => {
      if (Number.isNaN(contentId)) return;
      setLoading(true);
      setError('');
      try {
        const [detail, cl, vers] = await Promise.all([
          fetchSeoContentDetail(access, contentId),
          fetchSeoAeoChecklist(access, contentId),
          fetchSeoContentVersions(access, contentId),
        ]);
        setContent(detail.content);
        setBodyDraft(detail.content.body_html ?? '');
        setChecklist(cl.checklist);
        setVersions(vers.versions);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Không tải được content');
      } finally {
        setLoading(false);
      }
    },
    [contentId],
  );

  useEffect(() => {
    void (async () => {
      const access = await ensureAuth();
      if (!access) return;
      await reload(access);
    })();
  }, [ensureAuth, reload]);

  const logout = () => {
    clearSession();
    router.push('/login');
  };

  const canWrite = canWriteSeo(user);
  const canApprove = canApproveSeo(user);
  const currentStage = content?.workflow_status ?? '';

  const pendingApprovalStage = useMemo(() => {
    if (!content?.approvals) return null;
    if (REVIEW_STAGES.includes(currentStage as (typeof REVIEW_STAGES)[number])) return currentStage;
    const pending = content.approvals.find((a) => a.status === 'pending');
    return pending?.stage ?? null;
  }, [content, currentStage]);

  async function handleStatusChange(next: string) {
    if (!canWrite || !content) return;
    const access = await ensureAuth();
    if (!access) return;
    setBusy(true);
    try {
      await updateSeoContentStatus(access, content.id, { workflow_status: next });
      await reload(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Chuyển trạng thái thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove(approved: boolean) {
    if (!canApprove || !content || !pendingApprovalStage) return;
    const notes = window.prompt(approved ? 'Ghi chú duyệt (tuỳ chọn)' : 'Lý do từ chối') ?? '';
    const access = await ensureAuth();
    if (!access) return;
    setBusy(true);
    try {
      await approveSeoContent(access, content.id, {
        stage: pendingApprovalStage,
        approved,
        notes,
      });
      await reload(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approval thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveBody() {
    if (!canWrite || !content) return;
    const access = await ensureAuth();
    if (!access) return;
    setBusy(true);
    try {
      await saveSeoContentVersion(access, content.id, {
        body_html: bodyDraft,
        changes_summary: 'Manual edit from ops-web',
      });
      await reload(access);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu body thất bại');
    } finally {
      setBusy(false);
    }
  }

  async function handlePatchTitle() {
    if (!canWrite || !content) return;
    const title = window.prompt('Tiêu đề mới', content.title);
    if (!title?.trim()) return;
    const access = await ensureAuth();
    if (!access) return;
    await patchSeoContent(access, content.id, { title: title.trim() });
    await reload(access);
  }

  return (
    <div className="page">
      <OpsNav user={user} onLogout={logout} />
      <main className="main-content">
        <div className="page-header">
          <div>
            <Link href="/seo/content" className="nav-link">
              ← Pipeline
            </Link>
            <h1>{content?.title ?? 'Content detail'}</h1>
            {content && (
              <p className="muted">
                #{content.id} · Client {content.customer_id} · {content.workflow_status}
                {content.target_keyword?.phrase ? ` · KW: ${content.target_keyword.phrase}` : ''}
              </p>
            )}
          </div>
          <div className="page-actions">
            {canWrite && content && (
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => void handlePatchTitle()}>
                Sửa tiêu đề
              </button>
            )}
            {canWrite && content && (
              <select
                value={content.workflow_status}
                disabled={busy}
                onChange={(e) => void handleStatusChange(e.target.value)}
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        {error && <p className="error">{error}</p>}
        {loading ? (
          <p className="muted">Đang tải…</p>
        ) : !content ? (
          <p className="error">Không tìm thấy content</p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '1rem' }}>
            <div className="card">
              <div className="tabs" style={{ marginBottom: '1rem' }}>
                {(['brief', 'body', 'versions'] as const).map((p) => (
                  <button
                    key={p}
                    type="button"
                    className={panel === p ? 'tab active' : 'tab'}
                    onClick={() => setPanel(p)}
                  >
                    {p === 'brief' ? 'Brief' : p === 'body' ? 'Body' : 'Versions'}
                  </button>
                ))}
              </div>

              {panel === 'brief' && (
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem' }}>
                  {JSON.stringify(content.brief ?? {}, null, 2)}
                </pre>
              )}

              {panel === 'body' && (
                <>
                  <textarea
                    value={bodyDraft}
                    onChange={(e) => setBodyDraft(e.target.value)}
                    rows={18}
                    style={{ width: '100%', fontFamily: 'monospace' }}
                    disabled={!canWrite}
                  />
                  {canWrite && (
                    <button type="button" className="btn btn-sm" disabled={busy} onClick={() => void handleSaveBody()}>
                      Lưu version
                    </button>
                  )}
                </>
              )}

              {panel === 'versions' && (
                <ul>
                  {versions.map((v) => (
                    <li key={v.id}>
                      v{v.version_number} — {v.changes_summary || '—'} ({v.created_by}){' '}
                      {v.created_at ?? ''}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <div className="card" style={{ marginBottom: '1rem' }}>
                <h3>Approval timeline</h3>
                <ul style={{ listStyle: 'none', padding: 0 }}>
                  {(content.approvals ?? []).map((a) => (
                    <li key={a.stage} style={{ marginBottom: '0.5rem' }}>
                      <strong>{a.stage}</strong>: {a.status}
                      {a.actor_id ? ` · ${a.actor_id}` : ''}
                    </li>
                  ))}
                </ul>
                {canApprove && pendingApprovalStage && (
                  <div className="page-actions" style={{ marginTop: '0.75rem' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={busy}
                      onClick={() => void handleApprove(false)}
                    >
                      Reject
                    </button>
                    <button type="button" className="btn btn-sm" disabled={busy} onClick={() => void handleApprove(true)}>
                      Approve {pendingApprovalStage}
                    </button>
                  </div>
                )}
              </div>

              <div className="card">
                <h3>AEO checklist</h3>
                {checklist ? (
                  <>
                    <p>
                      {checklist.done_count}/{checklist.total} ({checklist.score_pct}%)
                    </p>
                    <ul>
                      {checklist.items.map((item) => (
                        <li key={item.label}>
                          {item.done ? '☑' : '☐'} {item.label}
                        </li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <p className="muted">Chưa có checklist</p>
                )}
                <p className="muted" style={{ marginTop: '0.5rem' }}>
                  SEO: {content.seo_score ?? '—'} · AEO: {content.aeo_score ?? '—'}
                </p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
